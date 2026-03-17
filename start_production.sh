#!/bin/bash
# Edumi2 Production Startup Script for Linux/Mac
# Usage: ./start_production.sh [start|stop|restart|status]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="edumi2"
PIDFILE="gunicorn.pid"
LOG_DIR="logs"

# Ensure log directory exists
mkdir -p $LOG_DIR

# Function to check if server is running
is_running() {
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start the server
start_server() {
    if is_running; then
        echo -e "${YELLOW}⚠️  $APP_NAME is already running (PID: $(cat $PIDFILE))${NC}"
        exit 1
    fi

    echo -e "${GREEN}🚀 Starting $APP_NAME in production mode...${NC}"
    
    # Set production environment variables
    export DEBUG=False
    export PYTHONUNBUFFERED=1
    
    # Optional: Set these for your environment
    # export SECRET_KEY="your-production-secret-key"
    # export REDIS_URL="redis://localhost:6379/0"
    # export GUNICORN_WORKERS=4
    
    # Collect static files
    echo "📦 Collecting static files..."
    python manage.py collectstatic --noinput --clear 2>/dev/null || true
    
    # Run database migrations
    echo "🗄️  Running database migrations..."
    python manage.py migrate --noinput
    
    # Start Gunicorn with configuration
    echo "🌐 Starting Gunicorn server..."
    gunicorn school_project.asgi:application \
        --config gunicorn.conf.py \
        --daemon
    
    sleep 2
    
    if is_running; then
        echo -e "${GREEN}✅ $APP_NAME started successfully (PID: $(cat $PIDFILE))${NC}"
        echo -e "${GREEN}🌐 Server running at: http://localhost:8000${NC}"
    else
        echo -e "${RED}❌ Failed to start $APP_NAME${NC}"
        exit 1
    fi
}

# Function to stop the server
stop_server() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  $APP_NAME is not running${NC}"
        exit 1
    fi

    echo -e "${YELLOW}🛑 Stopping $APP_NAME...${NC}"
    
    pid=$(cat "$PIDFILE")
    kill -TERM "$pid" 2>/dev/null || true
    
    # Wait for graceful shutdown
    for i in {1..30}; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $APP_NAME stopped gracefully${NC}"
            rm -f "$PIDFILE"
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    echo -e "${YELLOW}⚠️  Force killing $APP_NAME...${NC}"
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo -e "${GREEN}✅ $APP_NAME stopped${NC}"
}

# Function to restart the server
restart_server() {
    echo -e "${YELLOW}🔄 Restarting $APP_NAME...${NC}"
    stop_server
    sleep 2
    start_server
}

# Function to check status
show_status() {
    if is_running; then
        pid=$(cat "$PIDFILE")
        echo -e "${GREEN}✅ $APP_NAME is running (PID: $pid)${NC}"
        
        # Show worker processes
        echo -e "${GREEN}📊 Worker processes:${NC}"
        ps -f --ppid "$pid" 2>/dev/null || true
    else
        echo -e "${RED}❌ $APP_NAME is not running${NC}"
    fi
}

# Function to reload configuration
reload_config() {
    if ! is_running; then
        echo -e "${RED}❌ $APP_NAME is not running${NC}"
        exit 1
    fi

    echo -e "${YELLOW}🔄 Reloading $APPNAME configuration...${NC}"
    pid=$(cat "$PIDFILE")
    kill -HUP "$pid"
    echo -e "${GREEN}✅ Configuration reloaded${NC}"
}

# Main script logic
case "${1:-start}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    reload)
        reload_config
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|reload}"
        exit 1
        ;;
esac
