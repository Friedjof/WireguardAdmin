# VPN Management System - Docker Setup

This Docker container provides a complete WireGuard VPN management system with web interface.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Host system with appropriate privileges for networking

### 1. Start the System
```bash
# Clone and enter directory
cd vpn

# Start with Docker Compose
make up
# OR
docker-compose up -d
```

### 2. Access the System
- **Web Interface**: http://localhost:5000
- **WireGuard Port**: 51820/udp

## 🔧 Configuration

### Environment Variables
Edit `docker-compose.yml` to customize:

```yaml
environment:
  - SERVER_IP=10.0.0.1          # VPN server IP
  - LISTEN_PORT=51820           # WireGuard listening port
  - VPN_SUBNET=10.0.0.0/24      # VPN network subnet
  - SERVER_PRIVATE_KEY=...      # Optional: your private key
  - SERVER_PUBLIC_KEY=...       # Optional: your public key
```

### Generated Keys
If you don't provide keys, they will be auto-generated on first start:
```bash
# View generated keys
make keys
```

## 📋 Available Commands

```bash
make help          # Show all available commands
make build         # Build the container
make up            # Start the system
make down          # Stop the system
make logs          # View logs
make shell         # Open container shell
make status        # Show system status
make restart       # Restart everything
make backup        # Create configuration backup
make clean         # Remove everything (destructive!)
```

## 🔒 WireGuard Integration

### Automatic Configuration
- wg0.conf is automatically generated when peers are added/modified
- WireGuard interface is automatically reloaded on configuration changes
- iptables rules are applied for proper routing

### Manual WireGuard Commands
```bash
# Enter container
make shell

# Check WireGuard status
wg show

# View configuration
cat /etc/wireguard/wg0.conf

# Manual restart
wg-quick down wg0 && wg-quick up wg0
```

## 📁 Data Persistence

### Volumes
- `./instance/` - Database files
- `./logs/` - Application logs  
- `./backups/` - Configuration backups
- Docker volume for `/etc/wireguard`

### Backup & Restore
```bash
# Create backup
make backup

# Manual backup
docker-compose exec vpn-manager cp /app/instance/wireguard.db /app/backups/
```

## 🛠 Troubleshooting

### Container Won't Start
```bash
# Check logs
make logs

# Check container status
docker-compose ps

# Rebuild if needed
make clean && make build && make up
```

### WireGuard Issues
```bash
# Check interface status
make shell
ip addr show wg0

# Check WireGuard status
wg show

# Check system logs
journalctl -u wg-quick@wg0
```

### Network Issues
```bash
# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward  # Should be 1

# Check iptables rules
iptables -t nat -L
iptables -L FORWARD
```

### Permission Issues
The container needs privileged mode for:
- WireGuard interface management
- iptables rule modification
- Network namespace manipulation

## 🔧 Development Mode

For development with live reload:
```bash
# Start in development mode
make dev

# Or manually
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 📊 Monitoring

### Health Check
```bash
# Container health
docker-compose ps

# Application health
curl http://localhost:5000/
```

### Logs
```bash
# All logs
make logs

# Specific service logs
docker-compose logs vpn-app
docker-compose logs wireguard-watcher
```

## 🚨 Security Considerations

### Host Requirements
- Container runs in privileged mode
- Requires NET_ADMIN capability
- Modifies host iptables rules
- Creates network interfaces

### Firewall Rules
- Port 51820/udp must be accessible from clients
- Port 5000/tcp for web interface (consider limiting access)
- VPN subnet should not conflict with existing networks

### Key Management
- Private keys are stored in container environment
- Back up your keys securely
- Consider using Docker secrets for production

## 🔄 Updates

```bash
# Update to latest version
git pull
make down
make build
make up
```

## 📝 Production Deployment

For production use:
1. Change default ports and subnets
2. Use proper SSL certificates
3. Implement proper authentication
4. Set up monitoring and backups
5. Use Docker secrets for sensitive data
6. Consider using a reverse proxy