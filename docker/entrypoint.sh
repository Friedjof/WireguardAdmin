#!/bin/bash

# VPN Management Container Entrypoint
set -e

echo "Starting VPN Management Container..."

# Set default environment variables if not provided
export SERVER_PRIVATE_KEY=${SERVER_PRIVATE_KEY:-}
export SERVER_PUBLIC_KEY=${SERVER_PUBLIC_KEY:-}
export VPN_SERVER_IP=${VPN_SERVER_IP:-10.0.0.1}
export SERVER_PUBLIC_IP=${SERVER_PUBLIC_IP:-127.0.0.1}
export LISTEN_PORT=${LISTEN_PORT:-51820}
export VPN_SUBNET=${VPN_SUBNET:-10.0.0.0/24}

# Generate WireGuard keys if not provided
if [ -z "$SERVER_PRIVATE_KEY" ] || [ -z "$SERVER_PUBLIC_KEY" ]; then
    echo "Generating WireGuard server keys..."
    
    # Generate private key
    PRIVATE_KEY=$(wg genkey)
    PUBLIC_KEY=$(echo "$PRIVATE_KEY" | wg pubkey)
    
    export SERVER_PRIVATE_KEY="$PRIVATE_KEY"
    export SERVER_PUBLIC_KEY="$PUBLIC_KEY"
    
    echo "Generated new server keys:"
    echo "Private Key: $SERVER_PRIVATE_KEY"
    echo "Public Key: $SERVER_PUBLIC_KEY"
    echo ""
    echo "IMPORTANT: Save these keys! Add them to your environment variables:"
    echo "SERVER_PRIVATE_KEY=$SERVER_PRIVATE_KEY"
    echo "SERVER_PUBLIC_KEY=$SERVER_PUBLIC_KEY"
    echo ""
fi

# Create .env file for the application
cat > /app/.env << EOF
SERVER_PRIVATE_KEY=$SERVER_PRIVATE_KEY
SERVER_PUBLIC_KEY=$SERVER_PUBLIC_KEY
VPN_SERVER_IP=$VPN_SERVER_IP
SERVER_PUBLIC_IP=$SERVER_PUBLIC_IP
LISTEN_PORT=$LISTEN_PORT
VPN_SUBNET=$VPN_SUBNET
FLASK_ENV=production
FLASK_DEBUG=false
EOF

echo "Environment configuration:"
echo "VPN Server IP (internal): $VPN_SERVER_IP"
echo "Server Public IP (endpoint): $SERVER_PUBLIC_IP"
echo "Listen Port: $LISTEN_PORT"
echo "VPN Subnet: $VPN_SUBNET"
echo "Public Key: $SERVER_PUBLIC_KEY"

# Initialize database if it doesn't exist
cd /app
if [ ! -f "/app/instance/wireguard.db" ]; then
    echo "Initializing database..."
    . venv/bin/activate
    python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
"
    
    # Create dummy data for testing
    echo "Creating dummy data for testing..."
    . venv/bin/activate
    python3 create_dummy_data.py
fi

# Create initial empty wg0.conf (will be populated when app starts)
echo "Creating initial WireGuard configuration..."
cat > /app/wg0.conf << EOF
[Interface]
Address = $VPN_SERVER_IP
PrivateKey = $SERVER_PRIVATE_KEY
ListenPort = $LISTEN_PORT

# Peers will be added automatically by the application
EOF
echo "Initial wg0.conf template created"

# Copy wg0.conf to WireGuard directory
if [ -f "/app/wg0.conf" ]; then
    echo "Copying wg0.conf to /etc/wireguard/"
    cp /app/wg0.conf /etc/wireguard/wg0.conf
    chmod 600 /etc/wireguard/wg0.conf
    echo "WireGuard configuration ready at /etc/wireguard/wg0.conf"
else
    echo "Warning: wg0.conf not found"
fi

# Enable IP forwarding
echo "Enabling IP forwarding..."
echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/99-wireguard.conf
echo 1 > /proc/sys/net/ipv4/ip_forward

# Set up iptables rules for NAT
echo "Setting up basic iptables rules..."
iptables -t nat -A POSTROUTING -s $VPN_SUBNET ! -d $VPN_SUBNET -j MASQUERADE
iptables -A INPUT -p udp --dport $LISTEN_PORT -j ACCEPT
iptables -A FORWARD -i wg0 -j ACCEPT
iptables -A FORWARD -o wg0 -j ACCEPT

# Start WireGuard interface
echo "Starting WireGuard interface..."
if ! wg-quick up wg0 2>/dev/null; then
    echo "WireGuard interface startup failed or already running"
fi

echo "Container initialization complete!"
echo ""
echo "==================================="
echo "VPN Management System Ready"
echo "==================================="
echo "Web Interface: http://localhost:5000"
echo "WireGuard Port: $LISTEN_PORT/udp"
echo "Server Public Key: $SERVER_PUBLIC_KEY"
echo "==================================="

# Execute the main command
exec "$@"