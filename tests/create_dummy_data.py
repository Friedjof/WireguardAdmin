#!/usr/bin/env python3
"""
Create dummy data for VPN management system
This script populates all tables with test data for development and testing
"""

import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
import random

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from app.models import (
    Peer, AllowedIP, FirewallRule, FirewallTemplate, FirewallTemplateRule,
    AuditLog, PeerStatistics, Migration,
    RuleAction, RuleType, Protocol, AuditAction
)

def generate_wg_key():
    """Generate a WireGuard key pair"""
    try:
        private_key = subprocess.check_output("wg genkey", shell=True).decode().strip()
        public_key = subprocess.check_output(f"echo {private_key} | wg pubkey", shell=True).decode().strip()
        preshared_key = subprocess.check_output("wg genpsk", shell=True).decode().strip()
        return private_key, public_key, preshared_key
    except:
        # Fallback if wg command is not available
        import base64
        import secrets
        key = base64.b64encode(secrets.token_bytes(32)).decode()
        return key, key, key

def create_dummy_data():
    """Create comprehensive dummy data for all tables"""
    print("Creating dummy data for VPN management system...")
    
    with app.app_context():
        # Clear existing data
        print("Clearing existing data...")
        db.drop_all()
        db.create_all()
        
        # 1. Create Migrations
        print("Creating migration records...")
        migrations = [
            Migration(version="001_initial_schema", description="Initial database schema", checksum="abc123"),
            Migration(version="002_add_firewall_rules", description="Add firewall rules support", checksum="def456"),
            Migration(version="003_add_peer_statistics", description="Add peer statistics tracking", checksum="ghi789"),
        ]
        for migration in migrations:
            db.session.add(migration)
        
        # 2. Create Firewall Templates
        print("Creating firewall templates...")
        
        # System template - Unrestricted
        unrestricted_template = FirewallTemplate(
            name="Unrestricted Access",
            description="Full access to all networks and services",
            category="basic",
            is_system=True,
            usage_count=5
        )
        db.session.add(unrestricted_template)
        db.session.flush()
        
        # System template - Internet Only
        internet_only_template = FirewallTemplate(
            name="Internet Only",
            description="Access to internet but no peer-to-peer communication",
            category="basic",
            is_system=True,
            usage_count=8
        )
        db.session.add(internet_only_template)
        db.session.flush()
        
        # Add rules for Internet Only template
        internet_rules = [
            FirewallTemplateRule(
                template_id=internet_only_template.id,
                name="Allow Internet HTTP",
                description="Allow HTTP traffic to internet",
                rule_type=RuleType.INTERNET,
                action=RuleAction.ALLOW,
                destination="0.0.0.0/0",
                protocol=Protocol.TCP,
                port_range="80",
                order=1
            ),
            FirewallTemplateRule(
                template_id=internet_only_template.id,
                name="Allow Internet HTTPS",
                description="Allow HTTPS traffic to internet",
                rule_type=RuleType.INTERNET,
                action=RuleAction.ALLOW,
                destination="0.0.0.0/0",
                protocol=Protocol.TCP,
                port_range="443",
                order=2
            ),
            FirewallTemplateRule(
                template_id=internet_only_template.id,
                name="Block Peer Communication",
                description="Block all peer-to-peer communication",
                rule_type=RuleType.PEER_COMM,
                action=RuleAction.DENY,
                destination="10.0.0.0/24",
                protocol=Protocol.ANY,
                port_range="any",
                order=3
            )
        ]
        for rule in internet_rules:
            db.session.add(rule)
        
        # Custom template - Developer Access
        dev_template = FirewallTemplate(
            name="Developer Access",
            description="Access for developers with SSH and web development ports",
            category="advanced",
            is_system=False,
            usage_count=3
        )
        db.session.add(dev_template)
        db.session.flush()
        
        dev_rules = [
            FirewallTemplateRule(
                template_id=dev_template.id,
                name="Allow SSH",
                description="Allow SSH access",
                rule_type=RuleType.PORT,
                action=RuleAction.ALLOW,
                protocol=Protocol.TCP,
                port_range="22",
                order=1
            ),
            FirewallTemplateRule(
                template_id=dev_template.id,
                name="Allow Web Dev Ports",
                description="Allow common web development ports",
                rule_type=RuleType.PORT,
                action=RuleAction.ALLOW,
                protocol=Protocol.TCP,
                port_range="3000,8000,8080,9000",
                order=2
            ),
            FirewallTemplateRule(
                template_id=dev_template.id,
                name="Allow Database Ports",
                description="Allow database access",
                rule_type=RuleType.PORT,
                action=RuleAction.ALLOW,
                protocol=Protocol.TCP,
                port_range="3306,5432,27017",
                order=3
            )
        ]
        for rule in dev_rules:
            db.session.add(rule)
        
        # 3. Create Peers with different configurations
        print("Creating peers...")
        
        peers_data = [
            {
                "name": "alice-laptop",
                "assigned_ip": "10.0.0.2",
                "endpoint": "alice.example.com:51820",
                "persistent_keepalive": 25,
                "is_active": True,
                "allowed_ips": [
                    ("192.168.1.0/24", "Home network access"),
                    ("172.16.0.0/12", "Corporate network")
                ],
                "firewall_rules": [
                    {"name": "Allow Web", "type": RuleType.INTERNET, "action": RuleAction.ALLOW, "destination": "0.0.0.0/0", "protocol": Protocol.TCP, "port": "80,443", "priority": 10},
                    {"name": "Allow SSH to servers", "type": RuleType.SUBNET, "action": RuleAction.ALLOW, "destination": "192.168.1.0/24", "protocol": Protocol.TCP, "port": "22", "priority": 20}
                ]
            },
            {
                "name": "bob-phone",
                "assigned_ip": "10.0.0.3",
                "endpoint": None,
                "persistent_keepalive": 25,
                "is_active": True,
                "allowed_ips": [
                    ("192.168.100.0/24", "Guest network"),
                ],
                "firewall_rules": [
                    {"name": "Allow Basic Web", "type": RuleType.INTERNET, "action": RuleAction.ALLOW, "destination": "0.0.0.0/0", "protocol": Protocol.TCP, "port": "80,443", "priority": 10},
                    {"name": "Block P2P", "type": RuleType.PEER_COMM, "action": RuleAction.DENY, "destination": "10.0.0.0/24", "protocol": Protocol.ANY, "port": "any", "priority": 5}
                ]
            },
            {
                "name": "charlie-desktop",
                "assigned_ip": "10.0.0.4",
                "endpoint": "charlie.dyndns.org:12345",
                "persistent_keepalive": 30,
                "is_active": False,
                "allowed_ips": [
                    ("10.1.0.0/16", "Lab network"),
                    ("172.20.0.0/16", "Test environment")
                ],
                "firewall_rules": [
                    {"name": "Full Internet", "type": RuleType.INTERNET, "action": RuleAction.ALLOW, "destination": "0.0.0.0/0", "protocol": Protocol.ANY, "port": "any", "priority": 10},
                    {"name": "Allow RDP", "type": RuleType.PORT, "action": RuleAction.ALLOW, "destination": "172.20.0.0/16", "protocol": Protocol.TCP, "port": "3389", "priority": 20}
                ]
            },
            {
                "name": "diana-tablet",
                "assigned_ip": "10.0.0.5",
                "endpoint": None,
                "persistent_keepalive": 25,
                "is_active": True,
                "allowed_ips": [],
                "firewall_rules": [
                    {"name": "Limited Web", "type": RuleType.INTERNET, "action": RuleAction.ALLOW, "destination": "0.0.0.0/0", "protocol": Protocol.TCP, "port": "80,443", "priority": 10},
                    {"name": "Allow DNS", "type": RuleType.INTERNET, "action": RuleAction.ALLOW, "destination": "8.8.8.8", "protocol": Protocol.UDP, "port": "53", "priority": 5}
                ]
            },
            {
                "name": "eve-server",
                "assigned_ip": "10.0.0.6",
                "endpoint": "eve-server.company.com:51820",
                "persistent_keepalive": None,
                "is_active": True,
                "allowed_ips": [
                    ("10.2.0.0/16", "Server subnet"),
                    ("10.3.0.0/16", "Backup subnet")
                ],
                "firewall_rules": [
                    {"name": "Allow all outbound", "type": RuleType.CUSTOM, "action": RuleAction.ALLOW, "destination": "0.0.0.0/0", "protocol": Protocol.ANY, "port": "any", "priority": 100}
                ]
            }
        ]
        
        created_peers = []
        for peer_data in peers_data:
            # Generate keys
            private_key, public_key, preshared_key = generate_wg_key()
            
            # Create peer
            peer = Peer(
                name=peer_data["name"],
                public_key=public_key,
                preshared_key=preshared_key,
                assigned_ip=peer_data["assigned_ip"],
                endpoint=peer_data["endpoint"],
                persistent_keepalive=peer_data["persistent_keepalive"],
                is_active=peer_data["is_active"]
            )
            db.session.add(peer)
            db.session.flush()  # Get peer ID
            created_peers.append(peer)
            
            # Create allowed IPs
            for ip_network, description in peer_data["allowed_ips"]:
                allowed_ip = AllowedIP(
                    peer_id=peer.id,
                    ip_network=ip_network,
                    description=description
                )
                db.session.add(allowed_ip)
            
            # Create firewall rules
            for rule_data in peer_data["firewall_rules"]:
                firewall_rule = FirewallRule(
                    peer_id=peer.id,
                    name=rule_data["name"],
                    rule_type=rule_data["type"],
                    action=rule_data["action"],
                    destination=rule_data.get("destination"),
                    protocol=rule_data["protocol"],
                    port_range=rule_data["port"],
                    priority=rule_data["priority"],
                    is_active=True
                )
                db.session.add(firewall_rule)
        
        # 4. Create Peer Statistics
        print("Creating peer statistics...")
        for peer in created_peers:
            # Create multiple statistics entries for each peer (simulating historical data)
            for days_ago in [7, 3, 1, 0]:
                recorded_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
                stats = PeerStatistics(
                    peer_id=peer.id,
                    last_handshake=recorded_time - timedelta(minutes=random.randint(1, 60)),
                    bytes_sent=random.randint(1024*1024, 1024*1024*100),  # 1MB to 100MB
                    bytes_received=random.randint(1024*1024, 1024*1024*50),  # 1MB to 50MB
                    connection_count=random.randint(1, 10),
                    last_endpoint=f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}:{random.randint(1024, 65535)}",
                    avg_latency_ms=random.uniform(10.0, 150.0),
                    packet_loss_percent=random.uniform(0.0, 5.0),
                    recorded_at=recorded_time,
                    window_start=recorded_time - timedelta(hours=1),
                    window_end=recorded_time
                )
                db.session.add(stats)
        
        # 5. Create Audit Log entries
        print("Creating audit log entries...")
        audit_entries = [
            {
                "table_name": "peers",
                "record_id": created_peers[0].id,
                "action": AuditAction.CREATE,
                "new_values": {"name": "alice-laptop", "is_active": True},
                "user_id": "admin",
                "ip_address": "192.168.1.100"
            },
            {
                "table_name": "peers",
                "record_id": created_peers[1].id,
                "action": AuditAction.UPDATE,
                "old_values": {"is_active": False},
                "new_values": {"is_active": True},
                "user_id": "admin",
                "ip_address": "192.168.1.100"
            },
            {
                "table_name": "firewall_rules",
                "record_id": 1,
                "action": AuditAction.CREATE,
                "new_values": {"name": "Allow Web", "action": "ALLOW"},
                "user_id": "admin",
                "ip_address": "192.168.1.100"
            },
            {
                "table_name": "peers",
                "record_id": created_peers[2].id,
                "action": AuditAction.SOFT_DELETE,
                "old_values": {"is_active": True},
                "new_values": {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()},
                "user_id": "admin",
                "ip_address": "10.0.0.1"
            }
        ]
        
        for entry in audit_entries:
            audit_log = AuditLog(
                table_name=entry["table_name"],
                record_id=entry["record_id"],
                action=entry["action"],
                old_values=str(entry.get("old_values")) if entry.get("old_values") else None,
                new_values=str(entry.get("new_values")) if entry.get("new_values") else None,
                user_id=entry.get("user_id"),
                ip_address=entry.get("ip_address"),
                user_agent="Mozilla/5.0 (VPN Management Script)"
            )
            db.session.add(audit_log)
        
        # Commit all changes
        print("Committing changes to database...")
        db.session.commit()
        
        # Print summary
        print("\n" + "="*50)
        print("DUMMY DATA CREATION COMPLETE")
        print("="*50)
        print(f"Created {len(migrations)} migration records")
        print(f"Created {FirewallTemplate.query.count()} firewall templates")
        print(f"Created {FirewallTemplateRule.query.count()} template rules")
        print(f"Created {len(created_peers)} peers")
        print(f"Created {AllowedIP.query.count()} allowed IP entries")
        print(f"Created {FirewallRule.query.count()} firewall rules")
        print(f"Created {PeerStatistics.query.count()} statistics entries")
        print(f"Created {AuditLog.query.count()} audit log entries")
        print("\nPeers created:")
        for peer in created_peers:
            status = "ACTIVE" if peer.is_active else "INACTIVE"
            print(f"  - {peer.name} ({peer.assigned_ip}) - {status}")
        print("\nFirewall templates created:")
        for template in FirewallTemplate.query.all():
            type_label = "SYSTEM" if template.is_system else "CUSTOM"
            print(f"  - {template.name} ({type_label}) - Used {template.usage_count} times")
        print("\nYou can now test the application with this data!")
        print("="*50)

if __name__ == "__main__":
    create_dummy_data()