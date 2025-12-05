#!/bin/bash
# Bus Stop Display Startup Script
# This script starts the bus stop display with proper environment

# Set the working directory to where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Log file location
LOG_FILE="$SCRIPT_DIR/bus_display.log"

# Create log file if it doesn't exist and set permissions
touch "$LOG_FILE" 2>/dev/null || true
chmod 666 "$LOG_FILE" 2>/dev/null || true

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting Bus Stop Display..."

# Wait for network to be available (important for API calls)
log_message "Waiting for network..."
for i in {1..30}; do
    if ping -c 1 8.8.8.8 &> /dev/null; then
        log_message "Network is available"
        break
    fi
    sleep 2
done

# Check if running in virtual environment
if [ -d "$SCRIPT_DIR/.venv" ]; then
    log_message "Activating virtual environment..."
    source "$SCRIPT_DIR/.venv/bin/activate"
else
    log_message "No virtual environment found, using system Python"
fi

# Run the bus stop display
log_message "Starting bus_stop.py..."
python3 "$SCRIPT_DIR/bus_stop.py" >> "$LOG_FILE" 2>&1

# If the script exits, log it
log_message "Bus Stop Display stopped"
