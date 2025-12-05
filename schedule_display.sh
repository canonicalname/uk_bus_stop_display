#!/bin/bash
# Schedule script to start or stop the bus display service, to be used with crontab

ACTION=$1

case "$ACTION" in
    start)
        echo "[$(date)] Starting bus display service"
        sudo systemctl start bus-display.service
        ;;
    stop)
        echo "[$(date)] Stopping bus display service"
        sudo systemctl stop bus-display.service
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac
