import sys
import logging
from app import app, socketio

# Configure logging to output to stdout for Docker logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Ensure print statements flush immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

if __name__ == '__main__':
    print("🚀 Starting VPN Management Application...")
    print("🐳 Running in Docker container")
    print("📊 Debug logs enabled")
    
    # Use SocketIO's run method instead of app.run for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
