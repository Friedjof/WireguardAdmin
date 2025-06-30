from app import db
from datetime import datetime


class Peer(db.Model):
    __tablename__ = 'peers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    public_key = db.Column(db.String, nullable=False, unique=True)
    preshared_key = db.Column(db.String, nullable=False)
    assigned_ip = db.Column(db.String, nullable=False, unique=True)
    endpoint = db.Column(db.String, nullable=True)
    persistent_keepalive = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def combined_allowed_ips(self):
        """Combine assigned IP with allowed IP ranges"""
        ips = [f"{self.assigned_ip}/32"]
        # Get IPs from new table structure
        for allowed_ip in self.allowed_ip_ranges:
            ips.append(allowed_ip.ip_network)
        return ','.join(ips)
    
    @property
    def allowed_networks_list(self):
        """Get list of allowed IP networks for this peer"""
        return [allowed_ip.ip_network for allowed_ip in self.allowed_ip_ranges]


class AllowedIP(db.Model):
    __tablename__ = 'allowed_ips'
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('peers.id'), nullable=False)
    ip_network = db.Column(db.String, nullable=False)  # CIDR notation
    description = db.Column(db.String, nullable=True)  # Optional description
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to Peer
    peer = db.relationship('Peer', backref=db.backref('allowed_ip_ranges', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<AllowedIP {self.ip_network} for Peer {self.peer_id}>'
    def __repr__(self):
        return f'<AllowedIP {self.ip_network} for Peer {self.peer_id}>'
