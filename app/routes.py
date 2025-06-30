from flask import request, jsonify, render_template, Response, redirect, url_for, flash
from app import app, db
from app.models import Peer
from app.utils import generate_wg0_conf, validate_peer_data, get_next_available_ip, validate_additional_ips
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
        return render_template('peers/create.html', next_available_ip=next_ip)
    except Exception as e:
        flash(f'Error getting next available IP: {str(e)}', 'error')
        return render_template('peers/create.html', next_available_ip=None)

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
        # Convert ImmutableMultiDict to mutable dict for further processing
        data = dict(request.form)

        print(f"Received data for new peer: {data}")

        # Set default value for persistent_keepalive if not provided
        if not data.get('persistent_keepalive'):
            data['persistent_keepalive'] = '25'

        # Validate required fields
        required_fields = ['name', 'public_key']
        for field in required_fields:
            if not data.get(field) or not data.get(field).strip():
                flash(f'{field.replace("_", " ").title()} is required', 'error')
                return render_template('peers/create.html'), 400

        # Check for existing peer with same name
        if Peer.query.filter_by(name=data['name']).first():
            flash('Peer with this name already exists', 'error')
            return render_template('peers/create.html'), 400

        # Check for existing peer with same public key
        if Peer.query.filter_by(public_key=data['public_key']).first():
            flash('Peer with this public key already exists', 'error')
            return render_template('peers/create.html'), 400

        # Auto-assign IP address
        try:
            assigned_ip = get_next_available_ip()
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('peers/create.html'), 400

        # Validate additional allowed IPs if provided
        additional_allowed_ips = None
        if data.get('additional_allowed_ips') and data['additional_allowed_ips'].strip():
            try:
                print(f"Validating additional allowed IPs: {data['additional_allowed_ips']}")
                validate_additional_ips(data['additional_allowed_ips'])
                additional_allowed_ips = data['additional_allowed_ips'].strip()
            except ValueError as e:
                flash(str(e), 'error')
                return render_template('peers/create.html'), 400

        # Generate preshared key
        preshared_key = subprocess.check_output("wg genpsk", shell=True).decode().strip()
        
        # Create new peer with new schema
        new_peer = Peer(
            name=data['name'],
            public_key=data['public_key'],
            preshared_key=preshared_key,
            assigned_ip=assigned_ip,
            endpoint=data.get('endpoint') if data.get('endpoint') else None,
            persistent_keepalive=int(data['persistent_keepalive']) if data.get('persistent_keepalive') else None,
            is_active=True
        )
        
        db.session.add(new_peer)
        db.session.commit()
        generate_wg0_conf()
        
        flash(f'Peer created successfully with IP {assigned_ip}', 'success')
        return redirect(url_for('list_peers'))
        
    except Exception as e:
        flash(f'Error creating peer: {str(e)}', 'error')
        return render_template('peers/create.html'), 500

@app.route('/peers/<int:peer_id>', methods=['GET'])
def show_peer(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    return render_template('peers/show.html', peer=peer, config=app.config)

@app.route('/peers/<int:peer_id>/edit', methods=['GET'])
def edit_peer(peer_id):
    peer = Peer.query.get_or_404(peer_id)
    return render_template('peers/edit.html', peer=peer)

@app.route('/peers/<int:peer_id>', methods=['POST'])
def update_peer(peer_id):
    try:
        peer = Peer.query.get_or_404(peer_id)
        data = request.form
        
        # Validate input data
        validation_errors = validate_peer_data(data, peer_id)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'error')
            return render_template('peers/edit.html', peer=peer), 400

        # Check for existing peer with same name (excluding current peer)
        existing_peer = Peer.query.filter_by(name=data['name']).first()
        if existing_peer and existing_peer.id != peer_id:
            flash('Peer with this name already exists', 'error')
            return render_template('peers/edit.html', peer=peer), 400

        # Check for existing peer with same public key (excluding current peer)
        existing_peer = Peer.query.filter_by(public_key=data['public_key']).first()
        if existing_peer and existing_peer.id != peer_id:
            flash('Peer with this public key already exists', 'error')
            return render_template('peers/edit.html', peer=peer), 400

        # Check for existing peer with same allowed IPs (excluding current peer)
        existing_peer = Peer.query.filter_by(allowed_ips=data['allowed_ips']).first()
        if existing_peer and existing_peer.id != peer_id:
            flash('Peer with this IP range already exists', 'error')
            return render_template('peers/edit.html', peer=peer), 400

        # Update peer data
        peer.name = data['name']
        peer.public_key = data['public_key']
        peer.allowed_ips = data['allowed_ips']
        peer.endpoint = data.get('endpoint') if data.get('endpoint') else None
        peer.persistent_keepalive = int(data['persistent_keepalive']) if data.get('persistent_keepalive') else None
        
        db.session.commit()
        generate_wg0_conf()
        
        flash('Peer updated successfully', 'success')
        return redirect(url_for('show_peer', peer_id=peer_id))
        
    except Exception as e:
        flash(f'Error updating peer: {str(e)}', 'error')
        return render_template('peers/edit.html', peer=peer), 500

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
    server_ip = os.getenv("SERVER_IP")
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
    server_ip = os.getenv("SERVER_IP")
    listen_port = os.getenv("LISTEN_PORT")

    config = f"""[Interface]
PrivateKey = <PLACEHOLDER_FOR_CLIENT_PRIVATE_KEY>
Address = {peer.allowed_ips}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {server_ip}:{listen_port}
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
