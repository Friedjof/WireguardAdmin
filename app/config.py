import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///wireguard.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVER_PUBLIC_KEY = os.getenv("SERVER_PUBLIC_KEY")
    SERVER_IP = os.getenv("SERVER_IP")
    LISTEN_PORT = os.getenv("LISTEN_PORT")
    VPN_SUBNET = os.getenv("VPN_SUBNET", "10.0.0.0/24")
