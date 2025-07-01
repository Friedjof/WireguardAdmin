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


class FirewallRule(db.Model):
    __tablename__ = 'firewall_rules'
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('peers.id'), nullable=False)
    
    # Rule identification
    name = db.Column(db.String, nullable=False)  # User-friendly name
    description = db.Column(db.String, nullable=True)
    
    # Rule type and action
    rule_type = db.Column(db.String, nullable=False)  # 'peer_comm', 'internet', 'subnet', 'port', 'protocol', 'custom'
    action = db.Column(db.String, nullable=False)     # 'ALLOW', 'DENY'
    
    # Network targets
    source = db.Column(db.String, nullable=True)      # Source IP/CIDR (empty = this peer)
    destination = db.Column(db.String, nullable=True) # Destination IP/CIDR
    
    # Protocol and port filtering
    protocol = db.Column(db.String, default='any')    # 'tcp', 'udp', 'icmp', 'any'
    port_range = db.Column(db.String, default='any')  # '80', '80-443', 'any'
    
    # Rule management
    priority = db.Column(db.Integer, default=100)     # Lower = higher priority
    is_active = db.Column(db.Boolean, default=True)
    is_template = db.Column(db.Boolean, default=False) # For predefined templates
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to Peer
    peer = db.relationship('Peer', backref=db.backref('firewall_rules', lazy=True, cascade='all, delete-orphan', order_by='FirewallRule.priority'))
    
    def __repr__(self):
        return f'<FirewallRule {self.name} for Peer {self.peer_id}: {self.action}>'
    
    @property
    def is_peer_to_peer_rule(self):
        """Check if this rule affects peer-to-peer communication"""
        return self.rule_type == 'peer_comm'
    
    @property
    def is_internet_rule(self):
        """Check if this rule affects internet access"""
        return self.rule_type == 'internet'
    
    @property
    def is_port_rule(self):
        """Check if this rule is port-specific"""
        return self.port_range != 'any'
    
    @property
    def formatted_target(self):
        """Get human-readable target description"""
        if self.rule_type == 'internet':
            return 'Internet (0.0.0.0/0)'
        elif self.rule_type == 'peer_comm':
            return 'Other VPN Peers'
        elif self.destination:
            return self.destination
        else:
            return 'Any'
    
    def to_iptables_rule(self, peer_ip, vpn_interface='wg0'):
        """Convert this rule to iptables command"""
        # This will be implemented to generate actual iptables commands
        # For now, return a placeholder
        return f"# Rule '{self.name}': {self.action} {self.rule_type}"


class FirewallTemplate(db.Model):
    __tablename__ = 'firewall_templates'
    id = db.Column(db.Integer, primary_key=True)
    
    # Template identification
    name = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.String, nullable=True)
    category = db.Column(db.String, default='custom')  # 'basic', 'advanced', 'custom'
    
    # Template rules (JSON format)
    rules_json = db.Column(db.Text, nullable=False)  # Stores rule definitions as JSON
    
    # Template management
    is_system = db.Column(db.Boolean, default=False)  # System templates can't be deleted
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)    # How many peers use this template
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<FirewallTemplate {self.name}>'
    
    @classmethod
    def get_system_templates(cls):
        """Get all system-defined templates"""
        return cls.query.filter_by(is_system=True, is_active=True).all()
    
    @classmethod
    def get_user_templates(cls):
        """Get all user-defined templates"""
        return cls.query.filter_by(is_system=False, is_active=True).all()
