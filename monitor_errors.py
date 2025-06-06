#!/usr/bin/env python3

import os
import sys
import time
import json
import logging
import requests
import redis
import docker
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_errors.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
        self.error_thresholds = {
            'cpu_percent': 80,
            'memory_percent': 80,
            'disk_percent': 85,
            'error_rate': 0.1,  # 10% error rate threshold
            'response_time': 5.0  # 5 seconds
        }
        self.alert_cooldown = 300  # 5 minutes between alerts
        self.last_alert_time = {}

    def check_container_health(self) -> List[Dict]:
        """Check health status of all containers."""
        issues = []
        try:
            containers = self.docker_client.containers.list()
            for container in containers:
                container_info = container.attrs
                health_status = container_info.get('State', {}).get('Health', {}).get('Status')
                
                if health_status != 'healthy':
                    issues.append({
                        'type': 'container_health',
                        'container': container.name,
                        'status': health_status,
                        'message': f'Container {container.name} is not healthy: {health_status}'
                    })
                
                # Check resource usage
                stats = container.stats(stream=False)
                cpu_percent = self._calculate_cpu_percent(stats)
                memory_percent = self._calculate_memory_percent(stats)
                
                if cpu_percent > self.error_thresholds['cpu_percent']:
                    issues.append({
                        'type': 'high_cpu',
                        'container': container.name,
                        'value': cpu_percent,
                        'threshold': self.error_thresholds['cpu_percent'],
                        'message': f'High CPU usage in {container.name}: {cpu_percent}%'
                    })
                
                if memory_percent > self.error_thresholds['memory_percent']:
                    issues.append({
                        'type': 'high_memory',
                        'container': container.name,
                        'value': memory_percent,
                        'threshold': self.error_thresholds['memory_percent'],
                        'message': f'High memory usage in {container.name}: {memory_percent}%'
                    })
                
        except Exception as e:
            logger.error(f"Error checking container health: {str(e)}")
            issues.append({
                'type': 'monitor_error',
                'message': f'Failed to check container health: {str(e)}'
            })
        return issues

    def check_redis_health(self) -> List[Dict]:
        """Check Redis health and performance."""
        issues = []
        try:
            # Check Redis connection
            self.redis_client.ping()
            
            # Check memory usage
            info = self.redis_client.info()
            used_memory = info['used_memory']
            max_memory = info.get('maxmemory', 0)
            
            if max_memory > 0:
                memory_percent = (used_memory / max_memory) * 100
                if memory_percent > self.error_thresholds['memory_percent']:
                    issues.append({
                        'type': 'redis_memory',
                        'value': memory_percent,
                        'threshold': self.error_thresholds['memory_percent'],
                        'message': f'High Redis memory usage: {memory_percent:.1f}%'
                    })
            
            # Check connected clients
            connected_clients = info['connected_clients']
            if connected_clients > 100:  # Arbitrary threshold
                issues.append({
                    'type': 'redis_clients',
                    'value': connected_clients,
                    'message': f'High number of Redis clients: {connected_clients}'
                })
                
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {str(e)}")
            issues.append({
                'type': 'redis_connection',
                'message': f'Redis connection failed: {str(e)}'
            })
        except Exception as e:
            logger.error(f"Error checking Redis health: {str(e)}")
            issues.append({
                'type': 'monitor_error',
                'message': f'Failed to check Redis health: {str(e)}'
            })
        return issues

    def check_bitcoin_node(self) -> List[Dict]:
        """Check Bitcoin node health and sync status."""
        issues = []
        try:
            # Check Bitcoin node RPC
            response = requests.post(
                'http://bitcoind:8332',
                json={
                    'jsonrpc': '1.0',
                    'id': 'monitor',
                    'method': 'getblockchaininfo',
                    'params': []
                },
                auth=(os.getenv('BTC_RPC_USER', 'user'), os.getenv('BTC_RPC_PASS', 'pass')),
                timeout=5
            )
            
            if response.status_code != 200:
                issues.append({
                    'type': 'bitcoin_rpc',
                    'status_code': response.status_code,
                    'message': f'Bitcoin RPC returned status code {response.status_code}'
                })
                return issues
            
            data = response.json()
            if 'error' in data:
                issues.append({
                    'type': 'bitcoin_rpc_error',
                    'error': data['error'],
                    'message': f'Bitcoin RPC error: {data["error"]}'
                })
                return issues
            
            result = data['result']
            
            # Check sync status
            if not result['initialblockdownload'] and result['blocks'] < result['headers']:
                issues.append({
                    'type': 'bitcoin_sync',
                    'blocks': result['blocks'],
                    'headers': result['headers'],
                    'message': f'Bitcoin node is not fully synced: {result["blocks"]}/{result["headers"]} blocks'
                })
            
            # Check verification progress
            if result['verificationprogress'] < 0.9999:
                issues.append({
                    'type': 'bitcoin_verification',
                    'progress': result['verificationprogress'],
                    'message': f'Bitcoin verification progress: {result["verificationprogress"]*100:.2f}%'
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Bitcoin node request error: {str(e)}")
            issues.append({
                'type': 'bitcoin_connection',
                'message': f'Failed to connect to Bitcoin node: {str(e)}'
            })
        except Exception as e:
            logger.error(f"Error checking Bitcoin node: {str(e)}")
            issues.append({
                'type': 'monitor_error',
                'message': f'Failed to check Bitcoin node: {str(e)}'
            })
        return issues

    def check_transaction_monitor(self) -> List[Dict]:
        """Check transaction monitor service health."""
        issues = []
        try:
            # Check recent transaction processing
            recent_txs = self.redis_client.get('recent_transactions')
            if recent_txs:
                tx_data = json.loads(recent_txs)
                current_time = time.time()
                
                # Check for processing delays
                for tx in tx_data:
                    if current_time - tx['timestamp'] > 300:  # 5 minutes
                        issues.append({
                            'type': 'tx_processing_delay',
                            'txid': tx['txid'],
                            'delay': current_time - tx['timestamp'],
                            'message': f'Transaction {tx["txid"]} processing delayed by {current_time - tx["timestamp"]:.0f} seconds'
                        })
            
            # Check error rate
            error_count = int(self.redis_client.get('error_count') or 0)
            total_processed = int(self.redis_client.get('total_processed') or 1)
            error_rate = error_count / total_processed
            
            if error_rate > self.error_thresholds['error_rate']:
                issues.append({
                    'type': 'high_error_rate',
                    'rate': error_rate,
                    'threshold': self.error_thresholds['error_rate'],
                    'message': f'High transaction processing error rate: {error_rate*100:.1f}%'
                })
                
        except Exception as e:
            logger.error(f"Error checking transaction monitor: {str(e)}")
            issues.append({
                'type': 'monitor_error',
                'message': f'Failed to check transaction monitor: {str(e)}'
            })
        return issues

    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """Calculate CPU usage percentage from container stats."""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            cpu_percent = (cpu_delta / system_delta) * 100.0
            return min(cpu_percent, 100.0)
        except (KeyError, ZeroDivisionError):
            return 0.0

    def _calculate_memory_percent(self, stats: Dict) -> float:
        """Calculate memory usage percentage from container stats."""
        try:
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            return (memory_usage / memory_limit) * 100.0
        except (KeyError, ZeroDivisionError):
            return 0.0

    def should_alert(self, issue_type: str) -> bool:
        """Check if we should send an alert based on cooldown period."""
        current_time = time.time()
        if issue_type not in self.last_alert_time:
            self.last_alert_time[issue_type] = 0
        
        if current_time - self.last_alert_time[issue_type] > self.alert_cooldown:
            self.last_alert_time[issue_type] = current_time
            return True
        return False

    def monitor_all(self):
        """Run all monitoring checks and handle alerts."""
        all_issues = []
        
        # Run all checks
        all_issues.extend(self.check_container_health())
        all_issues.extend(self.check_redis_health())
        all_issues.extend(self.check_bitcoin_node())
        all_issues.extend(self.check_transaction_monitor())
        
        # Process and log issues
        for issue in all_issues:
            issue_type = issue['type']
            if self.should_alert(issue_type):
                logger.warning(f"ALERT: {issue['message']}")
                # Store issue in Redis for tracking
                self.redis_client.lpush('monitor_alerts', json.dumps({
                    'timestamp': time.time(),
                    'type': issue_type,
                    'details': issue
                }))
                # Keep only last 1000 alerts
                self.redis_client.ltrim('monitor_alerts', 0, 999)
            else:
                logger.info(f"Non-alerting issue: {issue['message']}")

def main():
    monitor = SystemMonitor()
    while True:
        try:
            monitor.monitor_all()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in monitoring loop: {str(e)}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main() 