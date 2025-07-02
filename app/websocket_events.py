#!/usr/bin/env python3
"""
WebSocket Event Handlers for VPN Management
Separated to avoid circular imports
"""

from flask import request
from flask_socketio import emit


def register_websocket_events(socketio, ws_manager):
    """Register WebSocket events with the SocketIO instance"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f"🔌 New WebSocket connection from {request.remote_addr}")
        ws_manager.add_client(request.sid)
        emit('connection_status', {'status': 'connected', 'message': 'WebSocket connected'})
        print(f"✅ WebSocket client connected: {request.sid}")
        
        # Send initial status update to new client
        print(f"📤 Sending initial status to new client {request.sid}")
        ws_manager._emit_status_update()

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        ws_manager.remove_client(request.sid)
        print(f"❌ WebSocket client disconnected: {request.sid}")

    @socketio.on('peer_action')
    def handle_peer_action(data):
        """Handle peer activation/deactivation requests"""
        print(f"🔄 Received peer action: {data}")
        result = ws_manager.handle_peer_action(data)
        emit('peer_action_response', result)

    @socketio.on('request_status_update')
    def handle_status_request():
        """Handle manual status update requests"""
        print("📊 Manual status update requested")
        ws_manager._emit_status_update()