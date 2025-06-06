#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
for cmd in docker docker-compose; do
    if ! command_exists $cmd; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Function to display status
show_status() {
    echo "Container Status:"
    docker-compose ps
    echo ""
    echo "Resource Usage:"
    docker stats --no-stream
}

# Function to clean up old containers and images
cleanup() {
    echo "Cleaning up old containers and images..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    echo "Cleanup complete."
}

# Function to rebuild containers
rebuild() {
    echo "Rebuilding containers..."
    docker-compose build --no-cache --parallel
    echo "Build complete."
}

# Function to start containers
start() {
    echo "Starting containers..."
    docker-compose up -d --remove-orphans
    
    echo "Waiting for services to be healthy..."
    for i in {1..30}; do
        if docker-compose ps | grep -q "unhealthy"; then
            echo "Waiting for unhealthy services to recover... ($i/30)"
            sleep 10
        else
            echo "All services are healthy!"
            break
        fi
    done
    
    show_status
}

# Function to verify services
verify() {
    echo "Verifying services..."
    
    # Check Bitcoin node
    echo "Checking Bitcoin node..."
    if ! docker-compose exec bitcoind bitcoin-cli getblockchaininfo > /dev/null; then
        echo "Warning: Bitcoin node may not be fully operational"
    else
        echo "Bitcoin node is operational"
    fi
    
    # Check Redis
    echo "Checking Redis..."
    if ! docker-compose exec redis redis-cli ping > /dev/null; then
        echo "Warning: Redis may not be fully operational"
    else
        echo "Redis is operational"
    fi
    
    # Check transaction monitor
    echo "Checking transaction monitor..."
    if ! docker-compose exec tx_monitor python3 -c "import redis; redis.Redis(host='redis').ping()" > /dev/null; then
        echo "Warning: Transaction monitor may not be fully operational"
    else
        echo "Transaction monitor is operational"
    fi
    
    # Check error monitor
    echo "Checking error monitor..."
    if ! docker-compose exec monitor python3 -c "import redis; redis.Redis(host='redis').ping()" > /dev/null; then
        echo "Warning: Error monitor may not be fully operational"
    else
        echo "Error monitor is operational"
    fi
}

# Main execution
echo "Starting rebuild process..."

# Stop and clean up
cleanup

# Rebuild containers
rebuild

# Start containers
start

# Verify services
verify

echo "Rebuild process complete!"
echo "You can monitor the containers using: ./manage.sh status"
echo "View logs using: ./manage.sh logs" 