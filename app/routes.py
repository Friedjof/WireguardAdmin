from flask import request, jsonify, render_template, Response, redirect, url_for, flash
from app import app, db
from app.models import Peer, AllowedIP, FirewallRule
from app.utils import generate_wg0_conf, validate_peer_data, get_next_available_ip, validate_multiple_allowed_ips, apply_iptables_rules, get_current_iptables_rules, validate_iptables_access, backup_iptables_rules, restore_iptables_rules, generate_iptables_rules, generate_peer_qr_code
from app.wireguard_status import get_wireguard_status, get_peer_connection_status, format_bytes, format_time_ago
import subprocess
import os
import re

# Web Interface Routes
@app.route('/', methods=['GET'])
def list_peers():
    peers = Peer.query.all()
    return render_template('peers/index.html', peers=peers)

@app.route('/peers/new', methods=['GET'])
def new_peer():
    try:
        next_ip = get_next_available_ip()
        return render_template('peers/form.html', peer=None, next_available_ip=next_ip)
    except Exception as e:
        flash(f'Error getting next available IP: {str(e)}', 'error')
        return render_template('peers/form.html', peer=None, next_available_ip=None)

@app.route('/api/v1/next-ip', methods=['GET'])
def get_next_ip():
    """Get the next available IP address"""
    try:
        next_ip = get_next_available_ip()
        return jsonify({
            'status': 'success',
            'ip': next_ip
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/peers', methods=['POST'])
def create_peer():
    try:
        # Get form data
        data = dict(request.form)
        print(f"Received data for new peer: {data}")

        # Get allowed IP networks and descriptions as lists
        allowed_ip_networks = request.form.getlist('allowed_ip_networks[]')
        allowed_ip_descriptions = request.form.getlist('allowed_ip_descriptions[]')
        
        # Filter out empty entries and pair networks with descriptions
        ip_data = []
        for i, network in enumerate(allowed_ip_networks):
            network = network.strip()
            if network:  # Only add non-empty networks
                description = allowed_ip_descriptions[i].strip() if i < len(allowed_ip_descriptions) else ""
                ip_data.append((network, description))
        
        print(f"Processed allowed IPs: {ip_data}")

        # Set default value for persistent_keepalive if not provided
        if not data.get('persistent_keepalive'):
            data['persistent_keepalive'] = '25'

        # Validate required fields
        required_fields = ['name', 'public_key']
        for field in required_fields:
            if not data.get(field) or not data.get(field).strip():
                flash(f'{field.replace("_", " ").title()} is required', 'error')
                return render_template('peers/form.html', peer=None), 400

        # Check for existing peer with same name
        if Peer.query.filter_by(name=data['name']).first():
            flash('Peer with this name already exists', 'error')
            return render_template('peers/form.html', peer=None), 400

        # Check for existing peer with same public key
        if Peer.query.filter_by(public_key=data['public_key']).first():
            flash('Peer with this public key already exists', 'error')
            return render_template('peers/form.html', peer=None), 400

        # Auto-assign IP address
        try:
            assigned_ip = get_next_available_ip()
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('peers/form.html', peer=None), 400

        # Validate allowed IP networks if provided
        if ip_data:
            networks_only = [network for network, desc in ip_data]
            is_valid, errors = validate_multiple_allowed_ips(networks_only)
            if not is_valid:
                for error in errors:
                    flash(error, 'error')
                return render_template('peers/form.html', peer=None), 400

        # Generate preshared key
        preshared_key = subprocess.check_output("wg genpsk", shell=True).decode().strip()
        
        # Create new peer
        new_peer = Peer(
            name=data['name'],
            public_key=data['public_key'],
            preshared_key=preshared_key,
            assigned_ip=assigned_ip,
            endpoint=data.get('endpoint') if data.get('endpoint') else None,
            persistent_keepalive=int(data['persistent_keepalive']) if data.get('persistent_keepalive') else None,
            is_active=True
        )
        
        # Add peer to session first to get an ID
        db.session.add(new_peer)
        db.session.flush()  # This assigns an ID without committing
        
        # Create AllowedIP objects
        for network, description in ip_data:
            allowed_ip = AllowedIP(
                peer_id=new_peer.id,
                ip_network=network,
                description=description if description else None
            )
            db.session.add(allowed_ip)
        
        # Process Firewall Rules
        firewall_rule_names = request.form.getlist('firewall_rule_names[]')
        firewall_rule_actions = request.form.getlist('firewall_rule_actions[]')
        firewall_rule_types = request.form.getlist('firewall_rule_types[]')
        firewall_rule_destinations = request.form.getlist('firewall_rule_destinations[]')
        firewall_rule_protocols = request.form.getlist('firewall_rule_protocols[]')
        firewall_rule_ports = request.form.getlist('firewall_rule_ports[]')
        
        # Create firewall rules
        firewall_rules_created = 0
        for i, rule_name in enumerate(firewall_rule_names):
            rule_name = rule_name.strip()
            if rule_name:  # Only create rules with names
                firewall_rule = FirewallRule(
                    peer_id=new_peer.id,
                    name=rule_name,
                    rule_type=firewall_rule_types[i] if i < len(firewall_rule_types) else 'custom',
                    action=firewall_rule_actions[i] if i < len(firewall_rule_actions) else 'ALLOW',
                    destination=firewall_rule_destinations[i].strip() if i < len(firewall_rule_destinations) and firewall_rule_destinations[i].strip() else None,
                    protocol=firewall_rule_protocols[i] if i < len(firewall_rule_protocols) else 'any',
                    port_range=firewall_rule_ports[i].strip() if i < len(firewall_rule_ports) and firewall_rule_ports[i].strip() else None,
                    priority=(i + 1) * 10,  # Set priority based on order
                    is_active=True
                )
                db.session.add(firewall_rule)
                firewall_rules_created += 1
        
        # Commit everything
        db.session.commit()
        generate_wg0_conf()
        
        success_msg = f'Peer created successfully with IP {assigned_ip}'
        if ip_data:
            success_msg += f' and {len(ip_data)} additional allowed IP(s)'
        if firewall_rules_created > 0:
            success_msg += f' and {firewall_rules_created} firewall rule(s)'
        flash(success_msg, 'success')
        return redirect(url_for('list_peers'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating peer: {str(e)}', 'error')
        return render_template('peers/form.html', peer=None), 500

@app.route('/peers/<int:peer_id>', methods=['GET'])
def show_peer(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    return render_template('peers/show.html', peer=peer, config=app.config)

@app.route('/peers/<int:peer_id>/edit', methods=['GET'])
def edit_peer(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    return render_template('peers/form.html', peer=peer)

@app.route('/peers/<int:peer_id>', methods=['POST'])
def update_peer(peer_id):
    try:
        peer = Peer.query.get_or_404(peer_id)
        data = dict(request.form)
        
        # Get allowed IP networks and descriptions as lists
        allowed_ip_networks = request.form.getlist('allowed_ip_networks[]')
        allowed_ip_descriptions = request.form.getlist('allowed_ip_descriptions[]')
        
        # Filter out empty entries and pair networks with descriptions
        ip_data = []
        for i, network in enumerate(allowed_ip_networks):
            network = network.strip()
            if network:  # Only add non-empty networks
                description = allowed_ip_descriptions[i].strip() if i < len(allowed_ip_descriptions) else ""
                ip_data.append((network, description))

        # Validate required fields
        required_fields = ['name', 'public_key']
        for field in required_fields:
            if not data.get(field) or not data.get(field).strip():
                flash(f'{field.replace("_", " ").title()} is required', 'error')
                return render_template('peers/form.html', peer=peer), 400

        # Check for existing peer with same name (excluding current peer)
        existing_peer = Peer.query.filter_by(name=data['name']).first()
        if existing_peer and existing_peer.id != peer_id:
            flash('Peer with this name already exists', 'error')
            return render_template('peers/form.html', peer=peer), 400

        # Check for existing peer with same public key (excluding current peer)
        existing_peer = Peer.query.filter_by(public_key=data['public_key']).first()
        if existing_peer and existing_peer.id != peer_id:
            flash('Peer with this public key already exists', 'error')
            return render_template('peers/form.html', peer=peer), 400

        # Validate allowed IP networks if provided
        if ip_data:
            networks_only = [network for network, desc in ip_data]
            is_valid, errors = validate_multiple_allowed_ips(networks_only, peer_id)
            if not is_valid:
                for error in errors:
                    flash(error, 'error')
                return render_template('peers/form.html', peer=peer), 400

        # Update peer basic data
        peer.name = data['name']
        peer.public_key = data['public_key']
        peer.endpoint = data.get('endpoint') if data.get('endpoint') else None
        peer.persistent_keepalive = int(data['persistent_keepalive']) if data.get('persistent_keepalive') else None
        
        # Remove existing allowed IPs for this peer
        AllowedIP.query.filter_by(peer_id=peer_id).delete()
        
        # Create new AllowedIP objects
        for network, description in ip_data:
            allowed_ip = AllowedIP(
                peer_id=peer.id,
                ip_network=network,
                description=description if description else None
            )
            db.session.add(allowed_ip)
        
        # Process Firewall Rules
        firewall_rule_names = request.form.getlist('firewall_rule_names[]')
        firewall_rule_actions = request.form.getlist('firewall_rule_actions[]')
        firewall_rule_types = request.form.getlist('firewall_rule_types[]')
        firewall_rule_destinations = request.form.getlist('firewall_rule_destinations[]')
        firewall_rule_protocols = request.form.getlist('firewall_rule_protocols[]')
        firewall_rule_ports = request.form.getlist('firewall_rule_ports[]')
        
        # Remove existing firewall rules for this peer
        FirewallRule.query.filter_by(peer_id=peer_id).delete()
        
        # Create new firewall rules
        firewall_rules_created = 0
        for i, rule_name in enumerate(firewall_rule_names):
            rule_name = rule_name.strip()
            if rule_name:  # Only create rules with names
                firewall_rule = FirewallRule(
                    peer_id=peer.id,
                    name=rule_name,
                    rule_type=firewall_rule_types[i] if i < len(firewall_rule_types) else 'custom',
                    action=firewall_rule_actions[i] if i < len(firewall_rule_actions) else 'ALLOW',
                    destination=firewall_rule_destinations[i].strip() if i < len(firewall_rule_destinations) and firewall_rule_destinations[i].strip() else None,
                    protocol=firewall_rule_protocols[i] if i < len(firewall_rule_protocols) else 'any',
                    port_range=firewall_rule_ports[i].strip() if i < len(firewall_rule_ports) and firewall_rule_ports[i].strip() else None,
                    priority=(i + 1) * 10,  # Set priority based on order
                    is_active=True
                )
                db.session.add(firewall_rule)
                firewall_rules_created += 1
        
        db.session.commit()
        generate_wg0_conf()
        
        success_msg = 'Peer updated successfully'
        if ip_data:
            success_msg += f' with {len(ip_data)} allowed IP(s)'
        if firewall_rules_created > 0:
            success_msg += f' and {firewall_rules_created} firewall rule(s)'
        flash(success_msg, 'success')
        return redirect(url_for('show_peer', peer_id=peer_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating peer: {str(e)}', 'error')
        return render_template('peers/form.html', peer=peer), 500

@app.route('/peers/<int:peer_id>/delete', methods=['GET'])
def delete_peer_confirm(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    return render_template('peers/delete_confirm.html', peer=peer)

@app.route('/peers/<int:peer_id>/delete', methods=['POST'])
def delete_peer(peer_id):
    try:
        peer = Peer.query.get_or_404(peer_id)
        peer_name = peer.name
        
        db.session.delete(peer)
        db.session.commit()
        generate_wg0_conf()
        
        flash(f'Peer "{peer_name}" deleted successfully', 'success')
        return redirect(url_for('list_peers'))
        
    except Exception as e:
        flash(f'Error deleting peer: {str(e)}', 'error')
        return redirect(url_for('list_peers'))

@app.route('/peers/<int:peer_id>/config', methods=['GET'])
def download_peer_config(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    
    server_public_key = os.getenv("SERVER_PUBLIC_KEY")
    server_public_ip = os.getenv("SERVER_PUBLIC_IP", "127.0.0.1")  # Public IP for client endpoint
    listen_port = os.getenv("LISTEN_PORT")

    # Use assigned_ip for client address if available, otherwise use combined_allowed_ips or fallback to allowed_ips
    if hasattr(peer, 'assigned_ip') and peer.assigned_ip:
        client_address = f"{peer.assigned_ip}/32"
    elif hasattr(peer, 'combined_allowed_ips'):
        client_address = peer.combined_allowed_ips
    else:
        client_address = peer.allowed_ips

    config = f"""[Interface]
PrivateKey = <PLACEHOLDER_FOR_CLIENT_PRIVATE_KEY>
Address = {client_address}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {server_ip}:{listen_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = {peer.persistent_keepalive or 25}
"""

    response = Response(config, mimetype='text/plain')
    response.headers["Content-Disposition"] = f"attachment; filename={peer.name}_wg0.conf"
    return response

@app.route('/peers/<int:peer_id>/qrcode', methods=['GET'])
def get_peer_qrcode(peer_id):
    """Generate QR code for peer configuration"""
    try:
        peer = Peer.query.get_or_404(peer_id)
        qr_code_data = generate_peer_qr_code(peer_id)
        
        return jsonify({
            'status': 'success',
            'peer_name': peer.name,
            'qr_code': qr_code_data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error generating QR code: {str(e)}'
        }), 500

@app.route('/peers/<int:peer_id>/toggle', methods=['POST'])
def toggle_peer_status(peer_id):
    """Toggle peer active status without confirmation dialog"""
    try:
        peer = Peer.query.get_or_404(peer_id)
        
        # Toggle the is_active status
        peer.is_active = not peer.is_active
        db.session.commit()
        
        # Regenerate WireGuard configuration
        generate_wg0_conf()
        
        status = "activated" if peer.is_active else "deactivated"
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'status': 'success',
                'message': f'Peer "{peer.name}" {status} successfully',
                'is_active': peer.is_active
            })
        
        # Flash message for regular form submissions
        flash(f'Peer "{peer.name}" {status} successfully', 'success')
        return redirect(url_for('list_peers'))
        
    except Exception as e:
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'status': 'error',
                'message': f'Error toggling peer status: {str(e)}'
            }), 500
        
        flash(f'Error toggling peer status: {str(e)}', 'error')
        return redirect(url_for('list_peers'))

# API Routes for peer activation/deactivation
@app.route('/api/v1/peers/<int:peer_id>/activate', methods=['POST'])
def api_activate_peer(peer_id):
    """Activate a peer and regenerate WireGuard configuration"""
    try:
        peer = Peer.query.get_or_404(peer_id)
        
        # Set peer as active
        peer.is_active = True
        db.session.commit()
        
        # Regenerate WireGuard configuration
        generate_wg0_conf()
        
        return jsonify({
            'status': 'success',
            'message': f'Peer "{peer.name}" activated successfully',
            'is_active': True
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error activating peer: {str(e)}'
        }), 500

@app.route('/api/v1/peers/<int:peer_id>/deactivate', methods=['POST'])
def api_deactivate_peer(peer_id):
    """Deactivate a peer and regenerate WireGuard configuration"""
    try:
        peer = Peer.query.get_or_404(peer_id)
        
        # Set peer as inactive
        peer.is_active = False
        db.session.commit()
        
        # Regenerate WireGuard configuration
        generate_wg0_conf()
        
        return jsonify({
            'status': 'success',
            'message': f'Peer "{peer.name}" deactivated successfully',
            'is_active': False
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deactivating peer: {str(e)}'
        }), 500

# API Routes
@app.route('/api/v1/peers', methods=['GET'])
def api_list_peers():
    peers = Peer.query.all()
    return jsonify({
        'status': 'success',
        'data': [{
            'id': peer.id,
            'name': peer.name,
            'public_key': peer.public_key,
            'preshared_key': peer.preshared_key,
            'allowed_ips': peer.allowed_ips,
            'endpoint': peer.endpoint,
            'persistent_keepalive': peer.persistent_keepalive,
            'created_at': peer.created_at.isoformat(),
            'updated_at': peer.updated_at.isoformat()
        } for peer in peers]
    })

@app.route('/api/v1/peers', methods=['POST'])
def api_create_peer():
    try:
        data = request.get_json()
        
        # Validate input data
        validation_errors = validate_peer_data(data)
        if validation_errors:
            return jsonify({
                'status': 'error',
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400

        # Check for existing peer
        if Peer.query.filter_by(name=data['name']).first():
            return jsonify({
                'status': 'error',
                'message': 'Peer with this name already exists'
            }), 400

        if Peer.query.filter_by(public_key=data['public_key']).first():
            return jsonify({
                'status': 'error',
                'message': 'Peer with this public key already exists'
            }), 400

        if Peer.query.filter_by(allowed_ips=data['allowed_ips']).first():
            return jsonify({
                'status': 'error',
                'message': 'Peer with this IP range already exists'
            }), 400

        # Generate preshared key and create peer
        preshared_key = subprocess.check_output("wg genpsk", shell=True).decode().strip()
        
        new_peer = Peer(
            name=data['name'],
            public_key=data['public_key'],
            preshared_key=preshared_key,
            allowed_ips=data['allowed_ips'],
            endpoint=data.get('endpoint'),
            persistent_keepalive=data.get('persistent_keepalive')
        )
        
        db.session.add(new_peer)
        db.session.commit()
        generate_wg0_conf()
        
        return jsonify({
            'status': 'success',
            'message': 'Peer created successfully',
            'data': {
                'id': new_peer.id,
                'name': new_peer.name,
                'public_key': new_peer.public_key,
                'preshared_key': new_peer.preshared_key,
                'allowed_ips': new_peer.allowed_ips,
                'endpoint': new_peer.endpoint,
                'persistent_keepalive': new_peer.persistent_keepalive,
                'created_at': new_peer.created_at.isoformat(),
                'updated_at': new_peer.updated_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error creating peer: {str(e)}'
        }), 500

@app.route('/api/v1/peers/<int:peer_id>', methods=['GET'])
def api_get_peer(peer_id):
    peer = Peer.query.get(peer_id)
    if not peer:
        return jsonify({
            'status': 'error',
            'message': 'Peer not found'
        }), 404
        
    return jsonify({
        'status': 'success',
        'data': {
            'id': peer.id,
            'name': peer.name,
            'public_key': peer.public_key,
            'preshared_key': peer.preshared_key,
            'allowed_ips': peer.allowed_ips,
            'endpoint': peer.endpoint,
            'persistent_keepalive': peer.persistent_keepalive,
            'created_at': peer.created_at.isoformat(),
            'updated_at': peer.updated_at.isoformat()
        }
    })

@app.route('/api/v1/peers/<int:peer_id>', methods=['PUT'])
def api_update_peer(peer_id):
    try:
        peer = Peer.query.get(peer_id)
        if not peer:
            return jsonify({
                'status': 'error',
                'message': 'Peer not found'
            }), 404
            
        data = request.get_json()
        
        # Validate input data
        validation_errors = validate_peer_data(data, peer_id)
        if validation_errors:
            return jsonify({
                'status': 'error',
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400

        # Check for existing peers (excluding current)
        existing_peer = Peer.query.filter_by(name=data['name']).first()
        if existing_peer and existing_peer.id != peer_id:
            return jsonify({
                'status': 'error',
                'message': 'Peer with this name already exists'
            }), 400

        existing_peer = Peer.query.filter_by(public_key=data['public_key']).first()
        if existing_peer and existing_peer.id != peer_id:
            return jsonify({
                'status': 'error',
                'message': 'Peer with this public key already exists'
            }), 400

        existing_peer = Peer.query.filter_by(allowed_ips=data['allowed_ips']).first()
        if existing_peer and existing_peer.id != peer_id:
            return jsonify({
                'status': 'error',
                'message': 'Peer with this IP range already exists'
            }), 400

        # Update peer
        peer.name = data['name']
        peer.public_key = data['public_key']
        peer.allowed_ips = data['allowed_ips']
        peer.endpoint = data.get('endpoint')
        peer.persistent_keepalive = data.get('persistent_keepalive')
        
        db.session.commit()
        generate_wg0_conf()
        
        return jsonify({
            'status': 'success',
            'message': 'Peer updated successfully',
            'data': {
                'id': peer.id,
                'name': peer.name,
                'public_key': peer.public_key,
                'preshared_key': peer.preshared_key,
                'allowed_ips': peer.allowed_ips,
                'endpoint': peer.endpoint,
                'persistent_keepalive': peer.persistent_keepalive,
                'created_at': peer.created_at.isoformat(),
                'updated_at': peer.updated_at.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error updating peer: {str(e)}'
        }), 500

@app.route('/api/v1/peers/<int:peer_id>', methods=['DELETE'])
def api_delete_peer(peer_id):
    try:
        peer = Peer.query.get(peer_id)
        if not peer:
            return jsonify({
                'status': 'error',
                'message': 'Peer not found'
            }), 404
            
        peer_name = peer.name
        db.session.delete(peer)
        db.session.commit()
        generate_wg0_conf()
        
        return jsonify({
            'status': 'success',
            'message': f'Peer "{peer_name}" deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error deleting peer: {str(e)}'
        }), 500

@app.route('/api/v1/peers/<int:peer_id>/config', methods=['GET'])
def api_get_peer_config(peer_id):
    peer = Peer.query.get(peer_id)
    if not peer:
        return jsonify({
            'status': 'error',
            'message': 'Peer not found'
        }), 404
    
    server_public_key = os.getenv("SERVER_PUBLIC_KEY")
    server_public_ip = os.getenv("SERVER_PUBLIC_IP", "127.0.0.1")  # Public IP for client endpoint
    listen_port = os.getenv("LISTEN_PORT")

    config = f"""[Interface]
PrivateKey = <PLACEHOLDER_FOR_CLIENT_PRIVATE_KEY>
Address = {peer.allowed_ips}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {server_public_ip}:{listen_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = {peer.persistent_keepalive or 25}
"""

    return jsonify({
        'status': 'success',
        'data': {
            'peer_name': peer.name,
            'config': config
        }
    })

# Legacy routes for backward compatibility
@app.route('/new', methods=['GET'])
def add_peer_form():
    return redirect(url_for('new_peer'))

@app.route('/peers/json', methods=['GET'])
def list_peers_json():
    return redirect(url_for('api_list_peers'))

@app.route('/download/<peer_name>', methods=['GET'])
def download_config(peer_name):
    peer = Peer.query.filter_by(name=peer_name).first_or_404()
    return redirect(url_for('download_peer_config', peer_id=peer.id))

# Firewall/iptables Management Routes
@app.route('/api/v1/firewall/status', methods=['GET'])
def api_firewall_status():
    """Check iptables access and get current status"""
    access_check = validate_iptables_access()
    current_rules = get_current_iptables_rules()
    
    return jsonify({
        'status': 'success',
        'iptables_access': access_check,
        'current_rules': current_rules
    })

@app.route('/api/v1/firewall/rules/generate', methods=['GET'])
def api_generate_firewall_rules():
    """Generate iptables rules without applying them (dry run)"""
    peer_id = request.args.get('peer_id', type=int)
    
    try:
        rules = generate_iptables_rules(peer_id)
        return jsonify({
            'status': 'success',
            'rules': rules,
            'message': f'Generated {len(rules)} rules'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error generating rules: {str(e)}'
        }), 500

@app.route('/api/v1/firewall/rules/apply', methods=['POST'])
def api_apply_firewall_rules():
    """Apply iptables rules to the system"""
    data = request.get_json() or {}
    peer_id = data.get('peer_id')
    dry_run = data.get('dry_run', False)
    
    try:
        result = apply_iptables_rules(peer_id, dry_run)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error applying rules: {str(e)}'
        }), 500

@app.route('/api/v1/firewall/backup', methods=['POST'])
def api_backup_firewall_rules():
    """Create a backup of current iptables rules"""
    try:
        result = backup_iptables_rules()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error creating backup: {str(e)}'
        }), 500

@app.route('/api/v1/firewall/restore', methods=['POST'])
def api_restore_firewall_rules():
    """Restore iptables rules from backup"""
    data = request.get_json()
    if not data or 'backup_file' not in data:
        return jsonify({
            'status': 'error',
            'message': 'backup_file is required'
        }), 400
    
    try:
        result = restore_iptables_rules(data['backup_file'])
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error restoring backup: {str(e)}'
        }), 500

# Firewall Rules CRUD API
@app.route('/api/v1/peers/<int:peer_id>/firewall-rules', methods=['GET'])
def api_get_peer_firewall_rules(peer_id):
    """Get all firewall rules for a specific peer"""
    peer = Peer.query.get(peer_id)
    if not peer:
        return jsonify({
            'status': 'error',
            'message': 'Peer not found'
        }), 404
    
    rules = FirewallRule.query.filter_by(peer_id=peer_id).order_by(FirewallRule.priority).all()
    
    return jsonify({
        'status': 'success',
        'data': [{
            'id': rule.id,
            'name': rule.name,
            'description': rule.description,
            'rule_type': rule.rule_type,
            'action': rule.action,
            'source': rule.source,
            'destination': rule.destination,
            'protocol': rule.protocol,
            'port_range': rule.port_range,
            'priority': rule.priority,
            'is_active': rule.is_active,
            'created_at': rule.created_at.isoformat(),
            'updated_at': rule.updated_at.isoformat()
        } for rule in rules]
    })

@app.route('/api/v1/peers/<int:peer_id>/firewall-rules', methods=['POST'])
def api_create_firewall_rule(peer_id):
    """Create a new firewall rule for a peer"""
    peer = Peer.query.get(peer_id)
    if not peer:
        return jsonify({
            'status': 'error',
            'message': 'Peer not found'
        }), 404
    
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'Invalid JSON data'
        }), 400
    
    # Validate required fields
    required_fields = ['name', 'rule_type', 'action']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'status': 'error',
                'message': f'{field} is required'
            }), 400
    
    try:
        new_rule = FirewallRule(
            peer_id=peer_id,
            name=data['name'],
            description=data.get('description'),
            rule_type=data['rule_type'],
            action=data['action'],
            source=data.get('source'),
            destination=data.get('destination'),
            protocol=data.get('protocol', 'any'),
            port_range=data.get('port_range', 'any'),
            priority=data.get('priority', 100),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(new_rule)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Firewall rule created successfully',
            'data': {
                'id': new_rule.id,
                'name': new_rule.name,
                'rule_type': new_rule.rule_type,
                'action': new_rule.action
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error creating rule: {str(e)}'
        }), 500

@app.route('/api/v1/firewall-rules/<int:rule_id>', methods=['PUT'])
def api_update_firewall_rule(rule_id):
    """Update a firewall rule"""
    rule = FirewallRule.query.get(rule_id)
    if not rule:
        return jsonify({
            'status': 'error',
            'message': 'Firewall rule not found'
        }), 404
    
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'Invalid JSON data'
        }), 400
    
    try:
        # Update fields
        if 'name' in data:
            rule.name = data['name']
        if 'description' in data:
            rule.description = data['description']
        if 'rule_type' in data:
            rule.rule_type = data['rule_type']
        if 'action' in data:
            rule.action = data['action']
        if 'source' in data:
            rule.source = data['source']
        if 'destination' in data:
            rule.destination = data['destination']
        if 'protocol' in data:
            rule.protocol = data['protocol']
        if 'port_range' in data:
            rule.port_range = data['port_range']
        if 'priority' in data:
            rule.priority = data['priority']
        if 'is_active' in data:
            rule.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Firewall rule updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error updating rule: {str(e)}'
        }), 500

@app.route('/api/v1/firewall-rules/<int:rule_id>', methods=['DELETE'])
def api_delete_firewall_rule(rule_id):
    """Delete a firewall rule"""
    rule = FirewallRule.query.get(rule_id)
    if not rule:
        return jsonify({
            'status': 'error',
            'message': 'Firewall rule not found'
        }), 404
    
    try:
        rule_name = rule.name
        db.session.delete(rule)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Firewall rule "{rule_name}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deleting rule: {str(e)}'
        }), 500

# WireGuard Live Status API
@app.route('/api/v1/wireguard/status', methods=['GET'])
def api_wireguard_status():
    """Get live WireGuard connection status for all peers"""
    try:
        # Get WireGuard status
        wg_status = get_wireguard_status()
        
        # Get all peers from database
        peers = Peer.query.all()
        
        # Combine database info with live status
        peer_status = {}
        for peer in peers:
            live_data = wg_status.get(peer.public_key, {})
            peer_status[str(peer.id)] = {
                'peer_id': peer.id,
                'name': peer.name,
                'public_key': peer.public_key,
                'assigned_ip': peer.assigned_ip,
                'is_active': peer.is_active,
                'is_connected': live_data.get('is_connected', False),
                'endpoint': live_data.get('endpoint'),
                'latest_handshake': format_time_ago(live_data.get('latest_handshake')),
                'transfer_rx': live_data.get('transfer_rx', 0),
                'transfer_tx': live_data.get('transfer_tx', 0),
                'transfer_rx_formatted': format_bytes(live_data.get('transfer_rx', 0)),
                'transfer_tx_formatted': format_bytes(live_data.get('transfer_tx', 0)),
                'persistent_keepalive': live_data.get('persistent_keepalive')
            }
        
        return jsonify({
            'status': 'success',
            'data': peer_status,
            'total_peers': len(peers),
            'connected_peers': len([p for p in peer_status.values() if p['is_connected']])
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error getting WireGuard status: {str(e)}'
        }), 500

@app.route('/api/v1/peers/<int:peer_id>/status', methods=['GET'])
def api_peer_live_status(peer_id):
    """Get live status for a specific peer"""
    try:
        peer = Peer.query.get_or_404(peer_id)
        status = get_peer_connection_status(peer.public_key)
        
        return jsonify({
            'status': 'success',
            'data': {
                'peer_id': peer.id,
                'name': peer.name,
                'is_active': peer.is_active,
                'is_connected': status['is_connected'],
                'endpoint': status['endpoint'],
                'latest_handshake': format_time_ago(status['latest_handshake']),
                'transfer_rx': status['transfer_rx'],
                'transfer_tx': status['transfer_tx'],
                'transfer_rx_formatted': format_bytes(status['transfer_rx']),
                'transfer_tx_formatted': format_bytes(status['transfer_tx']),
                'persistent_keepalive': status['persistent_keepalive']
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error getting peer status: {str(e)}'
        }), 500
