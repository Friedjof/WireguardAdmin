#!/bin/bash

# WireGuard Configuration Watcher
# This script monitors wg0.conf for changes and automatically applies them

echo "Starting WireGuard configuration watcher..."

WIREGUARD_CONFIG="/app/wg0.conf"
SYSTEM_CONFIG="/etc/wireguard/wg0.conf"

# Function to reload WireGuard configuration
reload_wireguard() {
    echo "$(date): Detected configuration change, reloading WireGuard..."
    
    # Copy new configuration
    if [ -f "$WIREGUARD_CONFIG" ]; then
        cp "$WIREGUARD_CONFIG" "$SYSTEM_CONFIG"
        chmod 600 "$SYSTEM_CONFIG"
        
        # Restart WireGuard interface
        echo "$(date): Restarting WireGuard interface..."
        wg-quick down wg0 2>/dev/null || true
        sleep 1
        
        if wg-quick up wg0; then
            echo "$(date): WireGuard reloaded successfully"
            
            # Show current status
            echo "$(date): Current WireGuard status:"
            wg show wg0 2>/dev/null || echo "No active connections"
        else
            echo "$(date): ERROR: Failed to reload WireGuard configuration"
        fi
    else
        echo "$(date): ERROR: Configuration file not found: $WIREGUARD_CONFIG"
    fi
}

# Initial load
if [ -f "$WIREGUARD_CONFIG" ]; then
    reload_wireguard
fi

# Monitor for changes using inotifywait (if available) or polling
if command -v inotifywait >/dev/null 2>&1; then
    echo "$(date): Using inotifywait for file monitoring"
    while true; do
        # Wait for file modifications
        inotifywait -e modify,create,move "$WIREGUARD_CONFIG" 2>/dev/null
        sleep 2  # Debounce multiple rapid changes
        reload_wireguard
    done
else
    echo "$(date): Using polling for file monitoring (install inotify-tools for better performance)"
    LAST_MODIFIED=""
    
    while true; do
        if [ -f "$WIREGUARD_CONFIG" ]; then
            CURRENT_MODIFIED=$(stat -c %Y "$WIREGUARD_CONFIG" 2>/dev/null)
            
            if [ "$CURRENT_MODIFIED" != "$LAST_MODIFIED" ]; then
                LAST_MODIFIED="$CURRENT_MODIFIED"
                reload_wireguard
            fi
        fi
        
        sleep 5  # Check every 5 seconds
    done
fi