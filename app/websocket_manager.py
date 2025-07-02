#!/usr/bin/env python3
"""
WebSocket Manager for Real-time WireGuard Status Updates
"""

import threading
import time
import json
from datetime import datetime, timezone
from flask import request
from flask_socketio import emit
import eventlet
from app import socketio, db
from app import app
from app.models import Peer
from app.wireguard_status import get_wireguard_status, format_bytes, format_time_ago, format_duration


class WebSocketManager:
    def __init__(self):
        self.is_running = False
        self.update_thread = None
        self.connected_clients = set()
        self.peer_traffic_history = {}  # Store last 20 data points per peer
        
    def start(self):
        """Start the WebSocket manager and background status updates"""
        if self.is_running:
            return
            
        print("🚀 Starting WebSocket manager...")
        self.is_running = True
        
        # Start background thread for status updates using eventlet
        self.update_thread = eventlet.spawn(self._status_update_loop)
        
    def stop(self):
        """Stop the WebSocket manager"""
        if not self.is_running:
            return
            
        print("🛑 Stopping WebSocket manager...")
        self.is_running = False
        
        if self.update_thread:
            self.update_thread.kill()
            
    def _status_update_loop(self):
        """Background loop that sends status updates to all connected clients"""
        while self.is_running:
            try:
                if self.connected_clients:
                    self._emit_status_update()
                eventlet.sleep(2)  # Update every 2 seconds using eventlet
            except Exception as e:
                print(f"❌ Error in status update loop: {e}")
                eventlet.sleep(5)  # Wait longer on error
                
    def _emit_status_update(self):
        """Emit status update to all connected clients"""
        try:
            # Get WireGuard status
            wg_status = get_wireguard_status()

            # Get all peers from database
            with app.app_context():
                peers = Peer.query.all()

                # Combine database info with live status
                peer_status = {}
                current_time = datetime.now(timezone.utc)
                
                for peer in peers:
                    live_data = wg_status.get(peer.public_key, {})
                    
                    # Calculate traffic rates (bytes per second)
                    peer_id = str(peer.id)
                    current_rx = live_data.get('transfer_rx', 0)
                    current_tx = live_data.get('transfer_tx', 0)
                    
                    # Initialize history if not exists
                    if peer_id not in self.peer_traffic_history:
                        self.peer_traffic_history[peer_id] = {
                            'timestamps': [],
                            'rx_values': [],
                            'tx_values': [],
                            'rx_rates': [],
                            'tx_rates': []
                        }
                    
                    history = self.peer_traffic_history[peer_id]
                    
                    # Calculate rates if we have previous data
                    rx_rate = 0
                    tx_rate = 0
                    if history['timestamps'] and history['rx_values']:
                        time_diff = (current_time - history['timestamps'][-1]).total_seconds()
                        if time_diff > 0:
                            rx_diff = current_rx - history['rx_values'][-1]
                            tx_diff = current_tx - history['tx_values'][-1]
                            rx_rate = max(0, rx_diff / time_diff)  # bytes per second
                            tx_rate = max(0, tx_diff / time_diff)
                    
                    # Add current data to history
                    history['timestamps'].append(current_time)
                    history['rx_values'].append(current_rx)
                    history['tx_values'].append(current_tx)
                    history['rx_rates'].append(rx_rate)
                    history['tx_rates'].append(tx_rate)
                    
                    # Keep only last 20 data points (40 seconds of history)
                    if len(history['timestamps']) > 20:
                        for key in ['timestamps', 'rx_values', 'tx_values', 'rx_rates', 'tx_rates']:
                            history[key] = history[key][-20:]
                    
                    peer_status[peer_id] = {
                        'peer_id': peer.id,
                        'name': peer.name,
                        'public_key': peer.public_key,
                        'assigned_ip': peer.assigned_ip,
                        'is_active': peer.is_active,
                        'is_connected': live_data.get('is_connected', False),
                        'endpoint': live_data.get('endpoint'),
                        'client_ip': live_data.get('client_ip'),
                        'latest_handshake': format_time_ago(live_data.get('latest_handshake')),
                        'connection_duration': format_duration(live_data.get('connection_duration_seconds')),
                        'transfer_rx': live_data.get('transfer_rx', 0),
                        'transfer_tx': live_data.get('transfer_tx', 0),
                        'transfer_rx_formatted': format_bytes(live_data.get('transfer_rx', 0)),
                        'transfer_tx_formatted': format_bytes(live_data.get('transfer_tx', 0)),
                        'persistent_keepalive': live_data.get('persistent_keepalive'),
                        # Real-time rates
                        'rx_rate': rx_rate,
                        'tx_rate': tx_rate,
                        'rx_rate_formatted': format_bytes(rx_rate) + '/s',
                        'tx_rate_formatted': format_bytes(tx_rate) + '/s',
                        # Graph data (last 20 points)
                        'graph_data': {
                            'timestamps': [ts.isoformat() for ts in history['timestamps']],
                            'rx_rates': history['rx_rates'],
                            'tx_rates': history['tx_rates']
                        }
                    }
                
                # Emit to all connected clients
                try:
                    print(f"🔧 About to emit peer_status_update...", flush=True)
                    socketio.emit('peer_status_update', {
                    'status': 'success',
                    'data': peer_status,
                    'total_peers': len(peers),
                    'connected_peers': len([p for p in peer_status.values() if p['is_connected']]),
                    'timestamp': current_time.isoformat()
                    })
                    print(f"✅ Status update emitted successfully", flush=True)
                except Exception as emit_error:
                    print(f"❌ Emit error: {emit_error}", flush=True)
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}", flush=True)
                
        except Exception as e:
            print(f"❌ Error emitting status update: {e}")
            
    def add_client(self, session_id):
        """Add a connected client"""
        self.connected_clients.add(session_id)
        print(f"🔌 Client connected: {session_id} (Total: {len(self.connected_clients)})")
        
    def remove_client(self, session_id):
        """Remove a disconnected client"""
        self.connected_clients.discard(session_id)
        print(f"🔌 Client disconnected: {session_id} (Total: {len(self.connected_clients)})")
        
    def handle_peer_action(self, data):
        """Handle peer activation/deactivation via WebSocket"""
        try:
            peer_id = data.get('peer_id')
            action = data.get('action')  # 'activate' or 'deactivate'
            
            if not peer_id or not action:
                return {'status': 'error', 'message': 'Missing peer_id or action'}
                
            from app import db, socketio
            with db.app.app_context():
                peer = Peer.query.get(peer_id)
                if not peer:
                    return {'status': 'error', 'message': 'Peer not found'}
                    
                # Update peer status
                peer.is_active = (action == 'activate')
                db.session.commit()
                
                # Regenerate WireGuard configuration
                from app.utils import generate_wg0_conf
                generate_wg0_conf()
                
                # Emit update to all clients
                socketio.emit('peer_action_result', {
                    'status': 'success',
                    'peer_id': peer_id,
                    'action': action,
                    'is_active': peer.is_active,
                    'message': f'Peer "{peer.name}" {action}d successfully'
                })
                
                return {'status': 'success', 'message': f'Peer {action}d successfully'}
                
        except Exception as e:
            error_msg = f'Error {action}ing peer: {str(e)}'
            from app import socketio
            socketio.emit('peer_action_result', {
                'status': 'error',
                'peer_id': peer_id,
                'message': error_msg
            })
            return {'status': 'error', 'message': error_msg}


# Global WebSocket manager instance
ws_manager = WebSocketManager()


# Initialize WebSocket manager when module is imported
def init_websocket_manager():
    """Initialize and start the WebSocket manager"""
    from app import socketio
    from app.websocket_events import register_websocket_events
    
    register_websocket_events(socketio, ws_manager)
    ws_manager.start()
    print("✅ WebSocket manager initialized")


# Cleanup function
def cleanup_websocket_manager():
    """Cleanup WebSocket manager on shutdown"""
    ws_manager.stop()
    print("🧹 WebSocket manager cleaned up")