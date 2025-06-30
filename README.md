# WireGuard Peer Management Web App

This project is a Flask-based web application for managing WireGuard VPN peers. It provides a user-friendly web interface and a RESTful API to create, view, update, and delete peers, as well as to generate and download WireGuard configuration files.

## Features

- **Web Interface for Peer Management**
  - List all peers
  - Create new peers (auto-assigns next available IP, generates preshared key)
  - Edit peer details
  - Delete peers with confirmation
  - Toggle peer active status (activate/deactivate)
  - Download WireGuard configuration for each peer

- **API Endpoints**
  - List all peers (`GET /api/v1/peers`)
  - Create a new peer (`POST /api/v1/peers`)
  - Get details of a peer (`GET /api/v1/peers/<peer_id>`)
  - Update a peer (`PUT /api/v1/peers/<peer_id>`)
  - Delete a peer (`DELETE /api/v1/peers/<peer_id>`)
  - Download peer configuration (`GET /api/v1/peers/<peer_id>/config`)
  - Get next available IP (`GET /api/v1/next-ip`)

- **WireGuard Configuration Generation**
  - Automatically generates and updates `wg0.conf` after peer changes
  - Generates client configuration for download

- **Validation and Error Handling**
  - Validates input data for peers (name, public key, allowed IPs, etc.)
  - Prevents duplicate names, public keys, and IPs
  - Handles errors with user-friendly messages

- **Legacy Compatibility**
  - Redirects for legacy routes (`/new`, `/peers/json`, `/download/<peer_name>`)

## Setup

1. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   - `SERVER_PUBLIC_KEY`
   - `SERVER_IP`
   - `LISTEN_PORT`
   - (see `.env` for examples)

3. **Initialize the database:**
   ```
   python migrate_database.py
   ```

4. **Run the application:**
   ```
   python app.py
   ```

5. **Access the web interface:**
   - Open [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

- Use the web interface to manage peers and download configuration files.
- Use the REST API for programmatic access.

## File Structure

- `app/` - Application code (routes, models, utils)
- `templates/` - HTML templates
- `static/` - CSS files
- `wg0.conf` - Generated WireGuard server configuration
- `instance/wireguard.db` - SQLite database

## API Documentation

See the **Features** section above for available endpoints and their usage.

## License

MIT License
