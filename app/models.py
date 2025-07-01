from app import db
from datetime import datetime, timezone
from sqlalchemy import event, Index
from enum import Enum
import ipaddress
import re
import json


# Enums for better type safety and validation
class RuleAction(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"

class RuleType(Enum):
    PEER_COMM = "peer_comm"
    INTERNET = "internet"
    SUBNET = "subnet"
    PORT = "port"
    CUSTOM = "custom"

class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ANY = "any"

class AuditAction(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SOFT_DELETE = "SOFT_DELETE"
    RESTORE = "RESTORE"


class Peer(db.Model):
    __tablename__ = 'peers'
    
    # Primary key and identifiers
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    public_key = db.Column(db.String(44), nullable=False, unique=True)  # WG keys are exactly 44 chars
    preshared_key = db.Column(db.String(44), nullable=True)  # Optional for enhanced security
    assigned_ip = db.Column(db.String(18), nullable=False, unique=True)  # IPv4 CIDR max length
    endpoint = db.Column(db.String(255), nullable=True)
    persistent_keepalive = db.Column(db.Integer, nullable=True)
    
    # Status and management
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_peer_name', 'name'),
        Index('idx_peer_public_key', 'public_key'),
        Index('idx_peer_assigned_ip', 'assigned_ip'),
        Index('idx_peer_active', 'is_active'),
        Index('idx_peer_deleted', 'deleted_at'),
    )
    
    # Soft delete property
    @property
    def is_deleted(self):
        """Check if peer is soft deleted"""
        return self.deleted_at is not None
    
    # Query methods for active peers
    @classmethod
    def get_active(cls):
        """Get all active (non-deleted) peers"""
        return cls.query.filter_by(deleted_at=None)
    
    @classmethod
    def get_with_relations(cls, peer_id):
        """Get peer with eager-loaded relationships for performance"""
        return cls.query.options(
            db.joinedload(cls.allowed_ip_ranges),
            db.joinedload(cls.firewall_rules)
        ).filter_by(id=peer_id, deleted_at=None).first()
    
    # Soft delete method
    def soft_delete(self):
        """Soft delete the peer"""
        self.deleted_at = datetime.now(timezone.utc)
        self.is_active = False
        db.session.commit()
    
    def restore(self):
        """Restore soft deleted peer"""
        self.deleted_at = None
        db.session.commit()
    
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
    
    def __repr__(self):
        return f'<Peer {self.name} ({self.assigned_ip})>'


class AllowedIP(db.Model):
    __tablename__ = 'allowed_ips'
    
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('peers.id', ondelete='CASCADE'), nullable=False)
    ip_network = db.Column(db.String(43), nullable=False)  # IPv6 CIDR can be up to 43 chars
    description = db.Column(db.String(255), nullable=True)  # Optional description
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship to Peer with better performance settings
    peer = db.relationship('Peer', 
                          backref=db.backref('allowed_ip_ranges', 
                                            lazy='dynamic',  # For better performance
                                            cascade='all, delete-orphan',
                                            order_by='AllowedIP.created_at'))
    
    # Indexes
    __table_args__ = (
        Index('idx_allowed_ip_peer', 'peer_id'),
        Index('idx_allowed_ip_network', 'ip_network'),
    )
    
    def __repr__(self):
        return f'<AllowedIP {self.ip_network} for Peer {self.peer_id}>'


class FirewallRule(db.Model):
    __tablename__ = 'firewall_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('peers.id', ondelete='CASCADE'), nullable=False)
    
    # Rule identification
    name = db.Column(db.String(100), nullable=False)  # User-friendly name
    description = db.Column(db.String(500), nullable=True)
    
    # Rule type and action with enums
    rule_type = db.Column(db.Enum(RuleType), nullable=False)
    action = db.Column(db.Enum(RuleAction), nullable=False)
    
    # Network targets
    source = db.Column(db.String(43), nullable=True)      # Source IP/CIDR (empty = this peer)
    destination = db.Column(db.String(43), nullable=True) # Destination IP/CIDR
    
    # Protocol and port filtering
    protocol = db.Column(db.Enum(Protocol), default=Protocol.ANY)
    port_range = db.Column(db.String(20), default='any')  # '80', '80-443', 'any'
    
    # Rule management
    priority = db.Column(db.Integer, default=100, nullable=False)  # Lower = higher priority
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_template = db.Column(db.Boolean, default=False, nullable=False)  # For predefined templates
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship to Peer with better performance
    peer = db.relationship('Peer', 
                          backref=db.backref('firewall_rules', 
                                            lazy='dynamic',
                                            cascade='all, delete-orphan', 
                                            order_by='FirewallRule.priority'))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_firewall_rule_peer', 'peer_id'),
        Index('idx_firewall_rule_priority', 'priority'),
        Index('idx_firewall_rule_active', 'is_active'),
        Index('idx_firewall_rule_type', 'rule_type'),
    )
    
    def __repr__(self):
        return f'<FirewallRule {self.name} for Peer {self.peer_id}: {self.action.value}>'
    
    @property
    def is_peer_to_peer_rule(self):
        """Check if this rule affects peer-to-peer communication"""
        return self.rule_type == RuleType.PEER_COMM
    
    @property
    def is_internet_rule(self):
        """Check if this rule affects internet access"""
        return self.rule_type == RuleType.INTERNET
    
    @property
    def is_port_rule(self):
        """Check if this rule is port-specific"""
        return self.port_range != 'any'
    
    @property
    def formatted_target(self):
        """Get human-readable target description"""
        if self.rule_type == RuleType.INTERNET:
            return 'Internet (0.0.0.0/0)'
        elif self.rule_type == RuleType.PEER_COMM:
            return 'Other VPN Peers'
        elif self.destination:
            return self.destination
        else:
            return 'Any'
    
    def to_iptables_rule(self, peer_ip, vpn_interface='wg0'):
        """Convert this rule to iptables command"""
        # Enhanced iptables rule generation
        base_rule = f"iptables -A FORWARD -s {peer_ip}/32"
        
        if self.destination:
            base_rule += f" -d {self.destination}"
        
        if self.protocol != Protocol.ANY:
            base_rule += f" -p {self.protocol.value}"
        
        if self.port_range != 'any' and self.protocol in [Protocol.TCP, Protocol.UDP]:
            base_rule += f" --dport {self.port_range}"
        
        if self.rule_type == RuleType.INTERNET:
            base_rule += f" -o !{vpn_interface}"
        else:
            base_rule += f" -i {vpn_interface}"
        
        base_rule += f" -j {self.action.value}"
        base_rule += f" -m comment --comment \"Rule:{self.name}\""
        
        return base_rule


class FirewallTemplate(db.Model):
    __tablename__ = 'firewall_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template identification
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), default='custom')  # 'basic', 'advanced', 'custom'
    
    # Template management
    is_system = db.Column(db.Boolean, default=False, nullable=False)  # System templates can't be deleted
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    usage_count = db.Column(db.Integer, default=0, nullable=False)    # How many peers use this template
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_template_name', 'name'),
        Index('idx_template_system', 'is_system'),
        Index('idx_template_active', 'is_active'),
    )
    
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
    
    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        db.session.commit()


class FirewallTemplateRule(db.Model):
    """Individual rules that belong to a template - better than JSON storage"""
    __tablename__ = 'firewall_template_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('firewall_templates.id', ondelete='CASCADE'), nullable=False)
    
    # Rule definition
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    rule_type = db.Column(db.Enum(RuleType), nullable=False)
    action = db.Column(db.Enum(RuleAction), nullable=False)
    
    # Network targets
    source = db.Column(db.String(43), nullable=True)
    destination = db.Column(db.String(43), nullable=True)
    
    # Protocol and port filtering
    protocol = db.Column(db.Enum(Protocol), default=Protocol.ANY)
    port_range = db.Column(db.String(20), default='any')
    
    # Rule order within template
    order = db.Column(db.Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship
    template = db.relationship('FirewallTemplate', 
                              backref=db.backref('rules', 
                                                lazy='dynamic',
                                                cascade='all, delete-orphan',
                                                order_by='FirewallTemplateRule.order'))
    
    # Indexes
    __table_args__ = (
        Index('idx_template_rule_template', 'template_id'),
        Index('idx_template_rule_order', 'order'),
    )
    
    def __repr__(self):
        return f'<FirewallTemplateRule {self.name} in {self.template_id}>'


class AuditLog(db.Model):
    """Audit log for tracking all database changes"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.Enum(AuditAction), nullable=False)
    
    # Changes tracking
    old_values = db.Column(db.Text, nullable=True)  # JSON
    new_values = db.Column(db.Text, nullable=True)  # JSON
    
    # User context (if available)
    user_id = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Timestamp
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Indexes for queries
    __table_args__ = (
        Index('idx_audit_table_record', 'table_name', 'record_id'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_user', 'user_id'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.action.value} on {self.table_name}:{self.record_id}>'
    
    @classmethod
    def log_change(cls, table_name, record_id, action, old_values=None, new_values=None, user_id=None, ip_address=None, user_agent=None):
        """Log a database change"""
        log_entry = cls(
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry


class PeerStatistics(db.Model):
    """Statistics and monitoring data for peers"""
    __tablename__ = 'peer_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('peers.id', ondelete='CASCADE'), nullable=False)
    
    # Connection statistics
    last_handshake = db.Column(db.DateTime, nullable=True)
    bytes_sent = db.Column(db.BigInteger, default=0, nullable=False)
    bytes_received = db.Column(db.BigInteger, default=0, nullable=False)
    connection_count = db.Column(db.Integer, default=0, nullable=False)
    last_endpoint = db.Column(db.String(255), nullable=True)
    
    # Performance metrics
    avg_latency_ms = db.Column(db.Float, nullable=True)
    packet_loss_percent = db.Column(db.Float, nullable=True)
    
    # Time window for this statistic
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    window_start = db.Column(db.DateTime, nullable=True)
    window_end = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    peer = db.relationship('Peer', 
                          backref=db.backref('statistics', 
                                            lazy='dynamic',
                                            cascade='all, delete-orphan',
                                            order_by='PeerStatistics.recorded_at.desc()'))
    
    # Indexes
    __table_args__ = (
        Index('idx_stats_peer', 'peer_id'),
        Index('idx_stats_recorded', 'recorded_at'),
        Index('idx_stats_handshake', 'last_handshake'),
    )
    
    def __repr__(self):
        return f'<PeerStatistics for Peer {self.peer_id} at {self.recorded_at}>'
    
    @classmethod
    def get_latest_for_peer(cls, peer_id):
        """Get the latest statistics for a peer"""
        return cls.query.filter_by(peer_id=peer_id).order_by(cls.recorded_at.desc()).first()


class Migration(db.Model):
    """Track database migrations and schema versions"""
    __tablename__ = 'migrations'
    
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    checksum = db.Column(db.String(64), nullable=True)  # For integrity verification
    
    # Indexes
    __table_args__ = (
        Index('idx_migration_version', 'version'),
        Index('idx_migration_applied', 'applied_at'),
    )
    
    def __repr__(self):
        return f'<Migration {self.version}>'
    
    @classmethod
    def is_applied(cls, version):
        """Check if a migration version has been applied"""
        return cls.query.filter_by(version=version).first() is not None
    
    @classmethod
    def get_latest(cls):
        """Get the latest applied migration"""
        return cls.query.order_by(cls.applied_at.desc()).first()


# Validation event listeners
@event.listens_for(Peer.public_key, 'set')
def validate_public_key(target, value, oldvalue, initiator):
    """Validate WireGuard public key format"""
    if value and (len(value) != 44 or not re.match(r'^[A-Za-z0-9+/]{43}=$', value)):
        raise ValueError("Invalid WireGuard public key format. Must be 44 characters base64.")

@event.listens_for(Peer.preshared_key, 'set')
def validate_preshared_key(target, value, oldvalue, initiator):
    """Validate WireGuard preshared key format"""
    if value and (len(value) != 44 or not re.match(r'^[A-Za-z0-9+/]{43}=$', value)):
        raise ValueError("Invalid WireGuard preshared key format. Must be 44 characters base64.")

@event.listens_for(Peer.assigned_ip, 'set')
def validate_assigned_ip(target, value, oldvalue, initiator):
    """Validate IP address format"""
    if value:
        try:
            # Remove /32 suffix if present for validation
            ip_only = value.split('/')[0]
            ipaddress.ip_address(ip_only)
        except ValueError:
            raise ValueError(f"Invalid IP address format: {value}")

@event.listens_for(AllowedIP.ip_network, 'set')
def validate_ip_network(target, value, oldvalue, initiator):
    """Validate IP network CIDR format"""
    if value:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise ValueError(f"Invalid IP network format: {value}")

@event.listens_for(Peer.name, 'set')
def validate_peer_name(target, value, oldvalue, initiator):
    """Validate peer name format"""
    if value and not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValueError("Peer name can only contain letters, numbers, hyphens, and underscores.")

@event.listens_for(Peer.persistent_keepalive, 'set')
def validate_keepalive(target, value, oldvalue, initiator):
    """Validate persistent keepalive value"""
    if value is not None and (value < 0 or value > 65535):
        raise ValueError("Persistent keepalive must be between 0 and 65535 seconds.")

@event.listens_for(FirewallRule.port_range, 'set')
def validate_port_range(target, value, oldvalue, initiator):
    """Validate port range format"""
    if value and value != 'any':
        # Multiple ports (e.g., "80,443,8080")
        if ',' in value:
            ports = value.split(',')
            for port in ports:
                port = port.strip()
                try:
                    port_num = int(port)
                    if not (1 <= port_num <= 65535):
                        raise ValueError(f"Port {port} must be between 1 and 65535")
                except ValueError:
                    raise ValueError(f"Invalid port in list: {port}")
        # Port range (e.g., "80-443")
        elif '-' in value:
            try:
                start, end = value.split('-')
                start_port = int(start.strip())
                end_port = int(end.strip())
                if not (1 <= start_port <= 65535 and 1 <= end_port <= 65535 and start_port <= end_port):
                    raise ValueError("Invalid port range")
            except ValueError:
                raise ValueError(f"Invalid port range format: {value}")
        # Single port
        else:
            try:
                port = int(value.strip())
                if not (1 <= port <= 65535):
                    raise ValueError("Port must be between 1 and 65535")
            except ValueError:
                raise ValueError(f"Invalid port format: {value}")