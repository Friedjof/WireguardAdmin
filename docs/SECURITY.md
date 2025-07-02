# 🔒 Security Guide

This document outlines security considerations, best practices, and guidelines for deploying and maintaining the WireGuard Management System.

## 🛡️ **Security Architecture**

### **Defense in Depth**

The system implements multiple layers of security:

```
┌─────────────────────────────────────────┐
│            Internet                      │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         Reverse Proxy                   │ ← SSL/TLS, Rate Limiting
│         (nginx/Traefik)                 │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        Application Layer                │ ← Input Validation, CSRF
│      (Flask + WebSocket)                │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        System Layer                     │ ← iptables, Containers
│    (Docker + WireGuard)                 │
└─────────────────────────────────────────┘
```

## 🔐 **Authentication & Authorization**

### **Current Implementation**

- **No built-in authentication** - designed for private networks
- **Network-level security** through VPN access
- **iptables integration** for traffic control

### **Recommended Additions**

For production deployments, consider implementing:

```python
# Example: Add basic authentication
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    if username == 'admin':
        return check_password_hash(os.environ.get('ADMIN_PASSWORD_HASH'), password)
    return False

@app.route('/admin')
@auth.login_required
def admin_panel():
    return render_template('admin.html')
```

## 🚫 **Input Validation & Sanitization**

### **Implemented Protections**

#### **1. SQLAlchemy ORM Protection**
```python
# All database queries use parameterized statements
peer = Peer.query.filter_by(name=peer_name).first()
# Automatically prevents SQL injection
```

#### **2. Form Validation**
```python
# Input validation for peer creation
def validate_peer_data(data):
    errors = []
    
    # Name validation
    if not data.get('name') or len(data['name']) > 50:
        errors.append('Invalid peer name')
    
    # Public key validation
    if not is_valid_wireguard_key(data.get('public_key')):
        errors.append('Invalid WireGuard public key')
    
    return errors
```

#### **3. IP Address Validation**
```python
import ipaddress

def validate_ip_network(network):
    try:
        ipaddress.ip_network(network, strict=False)
        return True
    except ipaddress.AddressValueError:
        return False
```

### **Security Headers**

Add these headers for enhanced security:

```python
# Add to Flask app
from flask_talisman import Talisman

Talisman(app, 
    force_https=True,
    strict_transport_security=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' cdn.socket.io cdn.jsdelivr.net",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data:",
    }
)
```

## 🔑 **Key Management**

### **WireGuard Keys**

#### **Generation**
```bash
# Server keys (do this once)
wg genkey | tee server_private_key | wg pubkey > server_public_key

# Client keys (for each peer)
wg genkey | tee client_private_key | wg pubkey > client_public_key
```

#### **Storage Best Practices**

```bash
# Secure key storage
chmod 600 server_private_key
chown root:root server_private_key

# Environment variables (never commit)
export SERVER_PRIVATE_KEY=$(cat server_private_key)
export SERVER_PUBLIC_KEY=$(cat server_public_key)
```

#### **Key Rotation**

```python
# Planned: Automated key rotation
def rotate_server_keys():
    # Generate new keypair
    new_private, new_public = generate_wireguard_keypair()
    
    # Update server configuration
    update_server_config(new_private, new_public)
    
    # Notify all peers of new public key
    notify_peers_key_change(new_public)
    
    # Archive old keys with timestamp
    archive_old_keys(current_private, current_public)
```

### **Database Security**

#### **Encryption at Rest**
```python
# Planned: Database encryption
from cryptography.fernet import Fernet

class EncryptedField(db.TypeDecorator):
    impl = db.Text
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return fernet.encrypt(value.encode()).decode()
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return fernet.decrypt(value.encode()).decode()
        return value
```

## 🌐 **Network Security**

### **Firewall Configuration**

#### **Host Firewall (UFW)**
```bash
# Basic host protection
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 51820/udp
sudo ufw enable
```

#### **iptables Rules**
```bash
# Automated by the application
iptables -A FORWARD -i wg0 -j wireguard_rules
iptables -A wireguard_rules -s 10.0.0.0/24 -d 192.168.1.0/24 -j ACCEPT
iptables -A wireguard_rules -j DROP
```

### **VPN Network Isolation**

```bash
# Separate VPN clients from host network
iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o wg0 -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -i wg0 -o wg0 -j DROP  # Prevent peer-to-peer communication
```

### **Rate Limiting**

```python
# Planned: API rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

@app.route('/api/v1/peers', methods=['POST'])
@limiter.limit("5 per minute")
def create_peer():
    # Limited to prevent abuse
    pass
```

## 🐳 **Container Security**

### **Docker Configuration**

#### **Secure Dockerfile**
```dockerfile
# Use specific version tags
FROM ubuntu:22.04

# Create non-root user (when possible)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set proper permissions
COPY --chown=appuser:appuser . /app
USER appuser

# Health checks
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1
```

#### **Runtime Security**
```yaml
# docker-compose.yml security options
services:
  vpn-manager:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN  # Only what's needed
      - SYS_MODULE
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100M
```

### **Secrets Management**

```yaml
# Use Docker secrets for production
secrets:
  server_private_key:
    file: ./secrets/server_private_key
  
services:
  vpn-manager:
    secrets:
      - server_private_key
    environment:
      - SERVER_PRIVATE_KEY_FILE=/run/secrets/server_private_key
```

## 📊 **Monitoring & Alerting**

### **Security Monitoring**

#### **Log Analysis**
```python
# Security event logging
import logging

security_logger = logging.getLogger('security')
security_logger.addHandler(logging.FileHandler('/app/logs/security.log'))

def log_security_event(event_type, details):
    security_logger.warning(f"Security Event: {event_type} - {details}")

# Usage
log_security_event("UNAUTHORIZED_ACCESS", f"IP: {request.remote_addr}")
log_security_event("PEER_CREATED", f"Name: {peer.name}, IP: {peer.assigned_ip}")
```

#### **Intrusion Detection**
```bash
# Monitor for suspicious patterns
tail -f /app/logs/security.log | grep -E "(UNAUTHORIZED|FAILED|SUSPICIOUS)"

# Alert on multiple failed attempts
awk '/FAILED_LOGIN/{count[$1]++} END{for(ip in count) if(count[ip]>5) print ip, count[ip]}' /app/logs/access.log
```

### **Health Monitoring**

```python
# Application health checks
@app.route('/health')
def health_check():
    checks = {
        'database': check_database_connection(),
        'wireguard': check_wireguard_interface(),
        'disk_space': check_disk_space(),
        'memory': check_memory_usage()
    }
    
    if all(checks.values()):
        return jsonify(checks), 200
    else:
        return jsonify(checks), 503
```

## 🚨 **Incident Response**

### **Security Incident Playbook**

#### **1. Compromise Detection**
```bash
# Check for suspicious activity
grep -E "(UNAUTHORIZED|FAILED|SUSPICIOUS)" /app/logs/security.log
netstat -tulpn | grep LISTEN
ps aux | grep -v grep | grep -E "(nc|netcat|wget|curl)"
```

#### **2. Immediate Response**
```bash
# Isolate the system
iptables -A INPUT -j DROP
iptables -A OUTPUT -j DROP

# Stop services
docker compose down

# Backup evidence
tar -czf incident-$(date +%Y%m%d-%H%M).tar.gz /app/logs /app/instance
```

#### **3. Recovery Steps**
```bash
# Rotate all keys
wg genkey | tee new_server_private | wg pubkey > new_server_public

# Update configuration
# Rebuild containers
docker compose build --no-cache
docker compose up -d

# Verify security
docker compose exec vpn-manager wg show
curl -f http://localhost:5000/health
```

## 🔧 **Security Testing**

### **Automated Security Scans**

```bash
# Docker image scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image vpn-vpn-manager

# Dependency scanning
pip install safety
safety check

# Code security analysis
pip install bandit
bandit -r app/
```

### **Penetration Testing**

```bash
# Network scanning
nmap -sS -O -p 1-65535 your-server-ip

# Web application scanning
nikto -h http://your-server:5000
sqlmap -u "http://your-server:5000/api/v1/peers" --batch

# SSL/TLS testing
sslscan your-server.com:443
testssl.sh your-server.com
```

## 📋 **Security Checklist**

### **Pre-Deployment**

- [ ] Generate strong WireGuard keys
- [ ] Configure environment variables
- [ ] Set up reverse proxy with SSL/TLS
- [ ] Configure host firewall
- [ ] Review Docker security settings
- [ ] Test backup and restore procedures

### **Post-Deployment**

- [ ] Verify SSL/TLS configuration
- [ ] Test WireGuard connectivity
- [ ] Validate firewall rules
- [ ] Check application logs
- [ ] Perform security scans
- [ ] Document configuration

### **Ongoing Maintenance**

- [ ] Regular security updates
- [ ] Log monitoring and analysis
- [ ] Key rotation procedures
- [ ] Backup verification
- [ ] Performance monitoring
- [ ] Incident response testing

## 🚨 **Vulnerability Disclosure**

If you discover a security vulnerability, please:

1. **Do not** create a public issue
2. Email security@your-domain.com
3. Include detailed reproduction steps
4. Allow reasonable time for fixes
5. Coordinate disclosure timeline

We'll acknowledge receipt within 48 hours and work to resolve critical vulnerabilities within 7 days.

## 📚 **Security Resources**

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [WireGuard Security Documentation](https://www.wireguard.com/papers/wireguard.pdf)
- [Flask Security Guidelines](https://flask.palletsprojects.com/en/2.0.x/security/)

Remember: Security is a continuous process, not a one-time setup!