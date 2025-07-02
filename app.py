from app import app, socketio

if __name__ == '__main__':
    # Use SocketIO's run method instead of app.run for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
