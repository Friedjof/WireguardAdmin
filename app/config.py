import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{os.path.abspath('instance/wireguard.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVER_PUBLIC_KEY = os.getenv("SERVER_PUBLIC_KEY")
    VPN_SERVER_IP = os.getenv("VPN_SERVER_IP", "10.0.0.1")
    SERVER_PUBLIC_IP = os.getenv("SERVER_PUBLIC_IP", "127.0.0.1")
    LISTEN_PORT = os.getenv("LISTEN_PORT")
    VPN_SUBNET = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    # WebSocket Status Refresh Configuration
    WS_REFRESH_INTERVAL_MS = int(os.getenv("WS_REFRESH_INTERVAL_MS", "5000"))  # Default: 5 seconds
