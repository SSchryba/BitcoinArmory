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

# Function to display help
show_help() {
    echo "Transaction Monitor Container Management"
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start all containers"
    echo "  stop        Stop all containers"
    echo "  restart     Restart all containers"
    echo "  status      Show container status"
    echo "  logs        Show container logs"
    echo "  optimize    Optimize container resources"
    echo "  clean       Remove unused containers and volumes"
    echo "  help        Show this help message"
}

# Function to start containers
start_containers() {
    echo "Starting containers..."
    docker-compose up -d
    echo "Containers started. Checking health..."
    sleep 5
    docker-compose ps
}

# Function to stop containers
stop_containers() {
    echo "Stopping containers..."
    docker-compose down
    echo "Containers stopped."
}

# Function to restart containers
restart_containers() {
    echo "Restarting containers..."
    docker-compose restart
    echo "Containers restarted. Checking health..."
    sleep 5
    docker-compose ps
}

# Function to show container status
show_status() {
    echo "Container Status:"
    docker-compose ps
    echo ""
    echo "Resource Usage:"
    docker stats --no-stream
}

# Function to show container logs
show_logs() {
    echo "Container Logs:"
    docker-compose logs --tail=100 -f
}

# Function to optimize container resources
optimize_containers() {
    echo "Optimizing container resources..."
    
    # Stop containers
    docker-compose down
    
    # Clean up unused resources
    docker system prune -f
    
    # Restart with optimized settings
    docker-compose up -d
    
    # Verify container health
    echo "Checking container health..."
    sleep 5
    docker-compose ps
    
    echo "Optimization complete."
}

# Function to clean up
clean_containers() {
    echo "Cleaning up unused containers and volumes..."
    docker-compose down -v
    docker system prune -af --volumes
    echo "Cleanup complete."
}

# Main command handling
case "$1" in
    start)
        start_containers
        ;;
    stop)
        stop_containers
        ;;
    restart)
        restart_containers
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    optimize)
        optimize_containers
        ;;
    clean)
        clean_containers
        ;;
    help|*)
        show_help
        ;;
esac 