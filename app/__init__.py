from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os

# Initialize Flask app and load configurations
load_dotenv()
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config.from_object('app.config.Config')

# Initialize database
db = SQLAlchemy(app)

# Initialize SocketIO with eventlet for better WebSocket support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Create database tables if they don't exist (only when running as main module)
def init_db():
    with app.app_context():
        db.create_all()

# Only initialize database if being run directly
if __name__ == "__main__":
    init_db()

# Import routes to register them with the app
try:
    from app import routes
    print("✓ Routes imported successfully")
except Exception as e:
    print(f"⚠️  Warning: Could not import routes: {e}")

# Import and initialize WebSocket manager
from app.websocket_manager import init_websocket_manager
init_websocket_manager()

# Generate initial wg0.conf file on startup
with app.app_context():
    try:
        from app.utils import generate_wg0_conf
        generate_wg0_conf()
        print("✓ Initial wg0.conf generated successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not generate initial wg0.conf: {e}")
