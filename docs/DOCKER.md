# 🐳 Docker Deployment Guide

This guide covers deploying the WireGuard Management System using Docker for production environments.

## 🚀 **Quick Start**

### **1. Basic Docker Compose Setup**

```bash
# Clone repository
git clone https://github.com/your-username/wireguard-management.git
cd wireguard-management

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Generate WireGuard keys
wg genkey | tee server_private_key | wg pubkey > server_public_key

# Update .env with generated keys
echo "SERVER_PRIVATE_KEY=$(cat server_private_key)" >> .env
echo "SERVER_PUBLIC_KEY=$(cat server_public_key)" >> .env

# Start services
docker compose up -d

# Check status
docker compose ps
```

### **2. Access the Application**

- **Web Interface**: http://your-server:5000
- **WireGuard Port**: 51820/UDP
- **Logs**: `docker compose logs -f`

## 🏗️ **Architecture**

### **Container Structure**

```
┌─────────────────────────────────────────┐
│            Host System                   │
│  ┌─────────────────────────────────────┐ │
│  │        Docker Container             │ │
│  │  ┌─────────────────────────────────┐│ │
│  │  │        Supervisor               ││ │
│  │  │  ┌─────────────┬──────────────┐ ││ │
│  │  │  │ Flask App   │ WireGuard    │ ││ │
│  │  │  │ (Port 5000) │ Watcher      │ ││ │
│  │  │  └─────────────┴──────────────┘ ││ │
│  │  └─────────────────────────────────┘│ │
│  └─────────────────────────────────────┘ │
│           Volumes Mounted                │
│  ┌─────────┬─────────┬─────────────────┐ │
│  │instance/│  logs/  │    backups/     │ │
│  │  (DB)   │ (Logs)  │  (Configs)      │ │
│  └─────────┴─────────┴─────────────────┘ │
└─────────────────────────────────────────┘
```

## ⚙️ **Configuration**

### **Environment Variables**

Create `.env` file with required configuration:

```bash
# Server Configuration
SERVER_PUBLIC_IP=your-server.example.com
SERVER_PRIVATE_KEY=your_wg_private_key_here
SERVER_PUBLIC_KEY=your_wg_public_key_here
LISTEN_PORT=51820

# Network Configuration
VPN_SERVER_IP=10.0.0.1
VPN_SUBNET=10.0.0.0/24

# Application Configuration
FLASK_ENV=production
FLASK_DEBUG=false

# Docker Configuration
TZ=UTC
```

### **docker-compose.yml Explained**

```yaml
services:
  vpn-manager:
    build: .                    # Build from local Dockerfile
    container_name: vpn-manager # Fixed container name
    privileged: true           # Required for WireGuard/iptables
    
    # Network capabilities
    cap_add:
      - NET_ADMIN              # Network administration
      - SYS_MODULE             # Kernel module loading
    
    # Kernel parameters
    sysctls:
      - net.ipv4.ip_forward=1  # Enable IP forwarding
      - net.ipv4.conf.all.src_valid_mark=1
    
    # Port mappings
    ports:
      - "5000:5000"            # Web interface
      - "51820:51820/udp"      # WireGuard VPN
    
    # Volume mounts for persistence
    volumes:
      - ./instance:/app/instance
      - ./logs:/app/logs
      - ./backups:/app/backups
      - vpn_wireguard_config:/etc/wireguard
    
    # Environment variables from .env
    env_file: .env
    
    # Restart policy
    restart: unless-stopped
    
    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 🔧 **Production Deployment**

### **1. Reverse Proxy Setup (nginx)**

```nginx
# /etc/nginx/sites-available/wireguard-manager
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### **2. Firewall Configuration**

```bash
# UFW Configuration
sudo ufw allow 22/tcp          # SSH
sudo ufw allow 80/tcp          # HTTP
sudo ufw allow 443/tcp         # HTTPS
sudo ufw allow 51820/udp       # WireGuard
sudo ufw enable

# Or iptables
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

### **3. Docker Compose for Production**

```yaml
# docker-compose.prod.yml
services:
  vpn-manager:
    build: .
    container_name: vpn-manager
    privileged: true
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
    ports:
      - "127.0.0.1:5000:5000"  # Only localhost access
      - "51820:51820/udp"
    volumes:
      - ./instance:/app/instance
      - ./logs:/app/logs
      - ./backups:/app/backups
      - vpn_wireguard_config:/etc/wireguard
    environment:
      - FLASK_ENV=production
      - FLASK_DEBUG=false
      - SERVER_PUBLIC_IP=${SERVER_PUBLIC_IP}
      - SERVER_PRIVATE_KEY=${SERVER_PRIVATE_KEY}
      - SERVER_PUBLIC_KEY=${SERVER_PUBLIC_KEY}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      default:
        ipv4_address: 172.24.0.2

volumes:
  vpn_wireguard_config:

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.24.0.0/28
```

## 🛠️ **Management Commands**

### **Container Management**

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Restart services
docker compose restart

# View logs
docker compose logs -f
docker compose logs vpn-manager

# Execute commands in container
docker compose exec vpn-manager bash
docker compose exec vpn-manager wg show

# Update application
docker compose down
docker compose pull
docker compose up -d --build
```

### **Backup & Restore**

```bash
# Backup database and configurations
docker compose exec vpn-manager tar -czf /app/backups/backup-$(date +%Y%m%d).tar.gz /app/instance /etc/wireguard

# Restore from backup
docker compose exec vpn-manager tar -xzf /app/backups/backup-20241201.tar.gz -C /

# Copy files from container
docker cp vpn-manager:/app/instance ./backup-instance
docker cp vpn-manager:/etc/wireguard ./backup-wireguard
```

### **Monitoring**

```bash
# Container stats
docker stats vpn-manager

# Health check
docker compose ps
curl -f http://localhost:5000/api/v1/peers

# WireGuard status
docker compose exec vpn-manager wg show

# Check processes inside container
docker compose exec vpn-manager ps aux
```

## 🔍 **Troubleshooting**

### **Common Issues**

#### **1. Container Won't Start**

```bash
# Check logs
docker compose logs vpn-manager

# Check permissions
ls -la instance/ logs/ backups/

# Verify environment
docker compose config
```

#### **2. WireGuard Interface Issues**

```bash
# Check if WireGuard is loaded
docker compose exec vpn-manager lsmod | grep wireguard

# Check interface status
docker compose exec vpn-manager ip addr show wg0

# Restart WireGuard
docker compose exec vpn-manager wg-quick down wg0
docker compose exec vpn-manager wg-quick up wg0
```

#### **3. Permission Errors**

```bash
# Fix volume permissions
sudo chown -R 1000:1000 instance/ logs/ backups/

# Check privileged mode
docker compose exec vpn-manager id
docker compose exec vpn-manager capsh --print
```

#### **4. Network Connectivity**

```bash
# Test container networking
docker compose exec vpn-manager ping 8.8.8.8

# Check port bindings
docker port vpn-manager
netstat -tlnp | grep :5000

# Test WireGuard connectivity
docker compose exec vpn-manager wg show
```

### **Debugging Steps**

1. **Check container status**: `docker compose ps`
2. **View logs**: `docker compose logs -f vpn-manager`
3. **Verify configuration**: `docker compose config`
4. **Test connectivity**: `curl http://localhost:5000`
5. **Check WireGuard**: `docker compose exec vpn-manager wg show`

## 📊 **Performance Tuning**

### **Resource Limits**

```yaml
services:
  vpn-manager:
    # Resource constraints
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    
    # Restart policy
    restart: unless-stopped
    
    # Healthcheck optimization
    healthcheck:
      interval: 60s    # Reduce frequency
      timeout: 5s
      retries: 3
```

### **Log Management**

```yaml
services:
  vpn-manager:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 🔒 **Security Hardening**

### **Container Security**

```yaml
services:
  vpn-manager:
    # Security options
    security_opt:
      - no-new-privileges:true
    
    # Read-only root filesystem
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100M
    
    # User namespace
    user: "1000:1000"  # Only if not using privileged mode
```

### **Network Security**

```bash
# Isolate container network
docker network create --driver bridge wireguard-network

# Use custom bridge in compose
networks:
  wireguard-network:
    external: true
```

## 📋 **Maintenance**

### **Regular Tasks**

```bash
# Weekly cleanup
docker system prune -f

# Update base images
docker compose pull
docker compose up -d --build

# Backup rotation
find ./backups -name "*.tar.gz" -mtime +30 -delete

# Log rotation
find ./logs -name "*.log" -mtime +7 -delete
```

### **Updates**

```bash
# Update to latest version
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify update
docker compose logs -f vpn-manager
curl http://localhost:5000/api/v1/peers
```

This Docker deployment provides a robust, production-ready setup for the WireGuard Management System with proper security, monitoring, and maintenance procedures.