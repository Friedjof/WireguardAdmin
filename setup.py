import os
import subprocess
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

from app import app, db
from app.models import Peer

# Load environment variables
load_dotenv()


def setup_database(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{os.path.abspath('instance/wireguard.db')}")

    with app.app_context():
        db.create_all()

# WireGuard key generation
def generate_keys():
    private_key = subprocess.check_output("wg genkey", shell=True).decode().strip()
    public_key = subprocess.check_output(f"echo {private_key} | wg pubkey", shell=True).decode().strip()
    return private_key, public_key

# Initial setup
def setup_wireguard():
    print("Setting up WireGuard...")
    private_key, public_key = generate_keys()
    server_ip = input("Enter the server IP address: ").strip()
    listen_port = input("Enter the WireGuard listen port: ").strip()
    with open('.env', 'w') as env_file:
        env_file.write(f"SERVER_PRIVATE_KEY={private_key}\n")
        env_file.write(f"SERVER_PUBLIC_KEY={public_key}\n")
        env_file.write(f"SERVER_IP={server_ip}\n")
        env_file.write(f"LISTEN_PORT={listen_port}\n")

    # Generate wg0.conf
    wg_config = f"""
[Interface]
Address = {server_ip}
PrivateKey = {private_key}
ListenPort = {listen_port}
"""
    with open("wg0.conf", "w") as f:
        f.write(wg_config)
    print("WireGuard configuration generated: wg0.conf")

from flask import Flask

if __name__ == "__main__":
    print("Starting setup...")
    setup_database(app)

    setup_wireguard()
    print("Setup complete. You can now start the Flask application.")
