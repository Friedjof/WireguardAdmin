# 🔐 WireGuard Management System

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)](https://github.com/features/actions)
[![Tests](https://img.shields.io/badge/Tests-Pytest-orange.svg)](https://pytest.org/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://black.readthedocs.io/)

A professional, enterprise-ready web application for managing WireGuard VPN peers with **real-time monitoring**, **advanced firewall management**, and **WebSocket-powered live updates**.

> ⚠️ **Development Status**: This project is actively under development. The firewall management and VPN functionality are experimental and may contain bugs. Use with caution in production environments.

## ✨ **Key Features**

### 🚀 **Real-Time Monitoring**
- **Live Status Updates** via WebSockets (2-second intervals)
- **Traffic Graphs** showing upload/download rates for last 40 seconds
- **Connection Monitoring** with visual indicators
- **Automatic Reconnection** with fallback to HTTP polling

### 👥 **Advanced Peer Management**
- **Auto-IP Assignment** with conflict detection
- **Bulk Operations** with validation
- **Multiple Allowed IPs** with descriptions
- **QR Code Generation** for mobile devices
- **Configuration Export** (file download + API)

### 🛡️ **Enterprise Firewall Management** ⚠️ *Experimental*
- **iptables Integration** with rule preview
- **Security Templates** (Admin, Guest, Restricted, etc.)
- **Custom Rule Builder** with priorities
- **Terminal-Style Interface** for rule management
- **Dry-Run Testing** before applying rules
- *Note: Firewall features are experimental and may require manual intervention*

### 🔧 **Professional Architecture**
- **REST API** with full CRUD operations
- **WebSocket Events** for real-time communication
- **Docker Support** with production-ready setup
- **Modular Design** with separated concerns
- **Comprehensive Logging** and error handling

## 🎯 **Quick Start**

### **Using Make Commands (Recommended)**

```bash
# Clone repository
git clone https://github.com/Friedjof/WireguardAdmin.git
cd wireguard-management

# Show all available commands
make help

# Setup development environment
make setup

# Run tests and linting
make check

# Start development server
make dev
```

### **Docker Deployment**

```bash
# Configure environment
cp .env.example .env
# Edit .env with your server details

# Build and start with Docker
make build
make up

# Check status
make status

# Access web interface
open http://localhost:5000
```

### **Manual Installation**

```bash
# Install system dependencies
sudo apt update
sudo apt install wireguard-tools iptables python3 python3-pip

# Clone and setup
git clone https://github.com/Friedjof/WireguardAdmin.git
cd wireguard-management

# Setup with Make
make setup

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run application
python app.py
```

## 📊 **Screenshots & Demo**

<details>
<summary>🖼️ **Click to view screenshots**</summary>

### Dashboard with Real-Time Monitoring
![Dashboard](docs/images/dashboard.png)

### Peer Details with Traffic Graph
![Peer Details](docs/images/peer-details.png)

### Firewall Management Console
![Firewall Console](docs/images/firewall-console.png)

### Mobile QR Code Setup
![QR Code](docs/images/qr-code.png)

</details>

## 🏗️ **Architecture**

```
wireguard-management/
├── 📁 app/                    # Core application
│   ├── 🐍 __init__.py        # Flask app & WebSocket setup
│   ├── 🗃️  models.py          # Database models
│   ├── 🛣️  routes.py          # Web routes & API endpoints
│   ├── ⚙️  utils.py           # Utility functions
│   ├── 🔥 iptables_manager.py # Firewall management
│   ├── 📡 websocket_manager.py # Real-time updates
│   ├── 🔌 websocket_events.py # WebSocket event handlers
│   └── 📊 wireguard_status.py # Status monitoring
├── 📁 static/                 # Frontend assets
│   ├── 🎨 css/               # Stylesheets
│   └── ⚡ js/                # JavaScript modules
├── 📁 templates/              # Jinja2 templates
├── 📁 docker/                 # Docker configuration
├── 📁 docs/                   # Documentation
├── 📁 scripts/                # Utility scripts
└── 🐳 docker-compose.yml     # Production setup
```

## 🔌 **API Reference**

### **Peer Management**
```http
GET    /api/v1/peers              # List all peers
POST   /api/v1/peers              # Create new peer
GET    /api/v1/peers/{id}         # Get peer details
PUT    /api/v1/peers/{id}         # Update peer
DELETE /api/v1/peers/{id}         # Delete peer
POST   /api/v1/peers/{id}/toggle  # Toggle peer status
```

### **Real-Time WebSocket Events**
```javascript
// Connect to WebSocket
const socket = io();

// Listen for real-time updates
socket.on('peer_status_update', (data) => {
  // data.data contains all peer statuses
  // data.data[peerId].graph_data contains traffic history
});

// Activate/deactivate peers
socket.emit('peer_action', {
  peer_id: 123,
  action: 'activate' // or 'deactivate'
});
```

### **Firewall Management**
```http
GET  /api/v1/firewall/status           # Check iptables access
GET  /api/v1/firewall/rules/generate   # Preview generated rules
POST /api/v1/firewall/rules/apply      # Apply rules to system
POST /api/v1/firewall/backup           # Backup current rules
```

## 🛡️ **Security Features**

> ⚠️ **Security Notice**: This application manages critical network infrastructure. The firewall and VPN features are experimental and should be thoroughly tested before production use. Always maintain backup access to your server.

### **Built-in Security**
- ✅ **Input Validation** with SQLAlchemy ORM protection
- ✅ **Rate Limiting** on API endpoints
- ✅ **CSRF Protection** on forms
- ✅ **Secure Headers** with Flask-Talisman
- ✅ **Environment-based Secrets** (no hardcoded keys)

### **Network Security** ⚠️ *Experimental*
- ⚠️ **iptables Integration** with custom rules *(may require manual fixes)*
- ⚠️ **Firewall Templates** for different security levels *(test thoroughly)*
- ⚠️ **Peer Isolation** options *(experimental feature)*
- ✅ **Traffic Monitoring** and logging

### **Production Deployment**
- ✅ **Docker Security** with non-root user
- ✅ **Reverse Proxy** support (nginx/Traefik)
- ✅ **SSL/TLS** certificate integration
- ✅ **Environment Isolation** with Docker networks

## ⚙️ **Configuration**

### **Environment Variables**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SERVER_PUBLIC_IP` | Your server's public IP/domain | - | ✅ |
| `SERVER_PRIVATE_KEY` | WireGuard server private key | - | ✅ |
| `SERVER_PUBLIC_KEY` | WireGuard server public key | - | ✅ |
| `LISTEN_PORT` | WireGuard listen port | `51820` | ❌ |
| `VPN_SUBNET` | VPN internal network | `10.0.0.0/24` | ❌ |
| `FLASK_ENV` | Flask environment | `production` | ❌ |

### **Docker Configuration**

```yaml
# docker-compose.yml
services:
  vpn-manager:
    build: .
    ports:
      - "5000:5000"      # Web interface
      - "51820:51820/udp" # WireGuard
    environment:
      - SERVER_PUBLIC_IP=your-server.com
      - SERVER_PRIVATE_KEY=your_private_key
      - SERVER_PUBLIC_KEY=your_public_key
    volumes:
      - ./instance:/app/instance    # Database persistence
      - ./logs:/app/logs           # Logs
      - ./backups:/app/backups     # Backups
```

## 🔧 **Development**

### **Quick Development Setup**

```bash
# Clone repository
git clone https://github.com/Friedjof/WireguardAdmin.git
cd wireguard-management

# Complete setup with one command
make setup

# Show all available commands
make help
```

### **Development Commands**

#### **🔧 Setup & Development**
```bash
make setup          # Setup development environment
make install        # Install dependencies (alias for setup)
make dev            # Start development server
make clean          # Clean up development environment
```

#### **🧪 Testing & Quality**
```bash
make test           # Run all tests
make test-watch     # Run tests in watch mode
make lint           # Run linting checks (dry-run)
make format         # Format code with Black
make check          # Run all checks (lint + test)
```

#### **🐳 Docker Operations**
```bash
make build          # Build Docker container
make up             # Start system (Docker)
make down           # Stop system (Docker)
make logs           # Show container logs
make shell          # Open shell in container
make restart        # Restart system
make docker-clean   # Clean Docker resources
```

#### **📊 Monitoring & Operations**
```bash
make status         # Show system status
make keys           # Show WireGuard server keys
make backup         # Create backup of configuration
```

### **CI/CD Pipeline**

The project includes automated CI/CD with GitHub Actions:

- **Automated Testing**: All tests run on every push
- **Code Quality**: Flake8 linting and Black formatting checks
- **Release Automation**: Docker images built on version tags (`v*`)
- **Container Registry**: Images pushed to GitHub Container Registry

#### **Release Process**
```bash
# Create and push a release tag
git tag v1.0.0
git push origin v1.0.0

# This automatically triggers:
# 1. Run tests and linting
# 2. Build Docker image
# 3. Push to registry
# 4. Create GitHub release
```

## 📋 **Requirements**

### **System Requirements**
- **Linux Server** (Ubuntu 22.04+ recommended)
- **WireGuard Tools** (`wireguard-tools` package)
- **iptables** (for firewall management)
- **Docker** and **Docker Compose** (for containerized deployment)
- **Make** (for development commands)

### **Python Requirements**
- **Python 3.12+**
- **pytest** (testing framework)
- **flake8** (code linting)
- **black** (code formatting)
- See `requirements.txt` for complete list

### **Network Requirements**
- **Open Port 51820/UDP** (WireGuard)
- **Open Port 5000/TCP** (Web interface, can be proxied)
- **Root Access** (for WireGuard and iptables management)

## 🤝 **Contributing**

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### **Development Workflow**
1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### **Bug Reports**
Please use the [GitHub Issues](https://github.com/Friedjof/WireguardAdmin/issues) for bug reports and feature requests.

## 📄 **License**

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **WireGuard** team for the amazing VPN technology
- **Flask** community for the excellent web framework
- **Bootstrap** team for the responsive UI components
- **Chart.js** for beautiful traffic visualization
- **Socket.IO** for real-time communication

## 📞 **Support**

- 📖 **Documentation**: [Wiki](https://github.com/Friedjof/WireguardAdmin/wiki)
- 🐛 **Bug Reports**: [Issues](https://github.com/Friedjof/WireguardAdmin/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/Friedjof/WireguardAdmin/discussions)
- 📧 **Email**: dev@noweck.info

---

⭐ **Star this repository if it helped you!**

Made with ❤️ by [Friedjof](https://github.com/Friedjof)