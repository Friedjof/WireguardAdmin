# WireGuard Peer Management Web App

A professional Flask-based web application for managing WireGuard VPN peers with advanced security features, QR code generation, and comprehensive firewall rule management.

## 🌟 Key Features

### 🖥️ Modern Web Interface
- **Responsive Design**: Bootstrap-powered UI with professional styling
- **Real-time Validation**: Form validation with instant feedback
- **Intuitive Navigation**: Clean, organized interface for all operations
- **Mobile-Friendly**: Optimized for desktop and mobile devices

### 👥 Peer Management
- **Auto-Assignment**: Automatically assigns next available IP address
- **Secure Key Generation**: Auto-generates preshared keys for enhanced security
- **Advanced IP Management**: Support for additional allowed IP ranges with descriptions
- **Peer Status Control**: Enable/disable peers without deletion
- **Comprehensive Validation**: Prevents duplicate names, keys, and IP conflicts

### 📱 QR Code Integration
- **Mobile Configuration**: Generate QR codes for easy mobile device setup
- **Download Support**: Save QR codes as PNG files
- **Instant Preview**: Modal-based QR code display
- **WireGuard App Compatible**: Direct import into WireGuard mobile apps

### 🛡️ Advanced Firewall Management
- **Rule Templates**: Predefined security templates (Unrestricted, Internet Only, Restricted, Admin, Guest)
- **Custom Rules**: Create granular firewall rules with multiple criteria
- **iptables Integration**: Generate and preview iptables rules
- **Console Interface**: Professional terminal-style iptables preview with copy/download
- **Rule Priorities**: Organize rules with priority levels

### 🔧 Professional Architecture
- **Modular Design**: Separated CSS, JavaScript, and template files
- **DRY Principles**: Eliminated code duplication across templates
- **Template Inheritance**: Unified form templates for create/edit operations
- **Static Asset Organization**: Professional file structure with organized assets

### 🚀 RESTful API
- **Complete CRUD Operations**: Full peer management via REST API
- **Firewall Rule API**: Programmatic firewall rule management
- **Configuration Export**: Download configurations via API
- **Status Management**: API endpoints for peer activation/deactivation

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- WireGuard tools installed (`wg`, `wg-quick`)
- iptables (for firewall management)

### Installation

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd vpn
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your server details:
   # SERVER_PUBLIC_KEY=your_server_public_key
   # SERVER_IP=your_server_ip
   # LISTEN_PORT=51820
   ```

3. **Initialize database:**
   ```bash
   python migrate_database.py
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Access the interface:**
   - Web UI: [http://localhost:5000](http://localhost:5000)
   - API: [http://localhost:5000/api/v1/](http://localhost:5000/api/v1/)

## 📖 Usage Guide

### Creating Peers
1. Navigate to "Add New Peer"
2. Enter peer name and public key (or generate one)
3. Configure additional allowed IPs if needed
4. Set up firewall rules using templates or custom rules
5. Save and download the configuration or scan the QR code

### Firewall Templates
- **🔓 Unrestricted**: Full access to all networks
- **🌐 Internet Only**: Internet access without peer communication
- **🔒 Restricted**: Custom rules for specific access
- **👑 Administrator**: Full administrative access
- **👥 Guest**: Limited access with basic internet

### QR Code Usage
1. Click "Show QR Code" on any peer
2. Scan with WireGuard mobile app
3. Replace placeholder with client's private key
4. Connect instantly

## 🏗️ Architecture

### Professional File Structure
```
vpn/
├── app/
│   ├── models.py          # Database models
│   ├── routes.py          # Web routes and API endpoints
│   └── utils.py           # Utility functions
├── static/
│   ├── css/
│   │   └── console.css    # Terminal-style interface
│   └── js/
│       ├── utils.js       # General utilities
│       ├── console.js     # iptables console
│       ├── firewall.js    # Firewall management
│       ├── peer-form.js   # Form validation
│       └── qr-code.js     # QR code functionality
├── templates/
│   ├── base.html          # Base template
│   └── peers/
│       ├── index.html     # Peer list
│       ├── show.html      # Peer details
│       └── form.html      # Unified create/edit form
├── wg0.conf              # Generated WireGuard config
└── instance/wireguard.db # SQLite database
```

### Key Components
- **Flask Application**: Modern web framework with Jinja2 templating
- **SQLAlchemy ORM**: Database abstraction with relationship management
- **Bootstrap UI**: Responsive, professional interface
- **Modular JavaScript**: Separated concerns with reusable components

## 🔌 API Reference

### Peer Management
- `GET /api/v1/peers` - List all peers
- `POST /api/v1/peers` - Create new peer
- `GET /api/v1/peers/<id>` - Get peer details
- `PUT /api/v1/peers/<id>` - Update peer
- `DELETE /api/v1/peers/<id>` - Delete peer
- `GET /api/v1/peers/<id>/config` - Download configuration
- `GET /api/v1/peers/<id>/qrcode` - Get QR code

### Firewall Management
- `GET /api/v1/firewall/status` - Check iptables access
- `GET /api/v1/firewall/rules/generate` - Generate rules preview
- `POST /api/v1/firewall/rules/apply` - Apply rules to system
- `GET /api/v1/peers/<id>/firewall-rules` - List peer rules
- `POST /api/v1/peers/<id>/firewall-rules` - Create rule
- `PUT /api/v1/firewall-rules/<id>` - Update rule
- `DELETE /api/v1/firewall-rules/<id>` - Delete rule

### Utilities
- `GET /api/v1/next-ip` - Get next available IP address

## License

MIT License
