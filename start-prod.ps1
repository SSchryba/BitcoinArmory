# Generate secure random credentials
$btcRpcUser = "armory_" + (-join ((48..57) + (97..122) | Get-Random -Count 8 | ForEach-Object {[char]$_}))
$btcRpcPass = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$redisPass = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})

# Create .env file with generated credentials and default values
@"
# Auto-generated credentials - DO NOT MODIFY MANUALLY
BTC_RPC_USER=$btcRpcUser
BTC_RPC_PASS=$btcRpcPass
REDIS_PASSWORD=$redisPass

# System Configuration
TARGET_AMOUNT=0.1
MEV_MIN_PROFIT=0.01
MEV_MAX_GAS=100
LOG_LEVEL=INFO
NODE_HEALTH_CHECK_INTERVAL=60
TRANSACTION_BATCH_SIZE=100
NODE_SWARM_ENABLED=true
MEV_ENABLED=true

# Store credentials securely
"@ | Out-File -FilePath .env -Encoding UTF8

Write-Host "Generated secure credentials and created .env file"

# Check if services are already running
$running = docker-compose ps --services --filter "status=running"
if ($running) {
    Write-Host "Services are already running. Current status:"
    docker-compose ps
    Write-Host "`nTo view logs, use: docker-compose logs -f"
    exit 0
}

# Start services if not running
Write-Host "Starting services in production mode..."
docker-compose up -d

# Wait for services to initialize
Write-Host "Waiting for services to initialize..."
Start-Sleep -Seconds 10

# Check service status
Write-Host "`nService Status:"
docker-compose ps

# Display important information
Write-Host "`nImportant Information:"
Write-Host "BTC RPC User: $btcRpcUser"
Write-Host "Redis Password: $redisPass"
Write-Host "`nCredentials have been saved to .env file"
Write-Host "Please keep these credentials secure and do not share them"

# Monitor logs
Write-Host "`nMonitoring logs (Ctrl+C to exit)..."
docker-compose logs -f 