from app import db
from app.models import Peer
import os
import re
import ipaddress

def generate_wg0_conf():
    server_private_key = os.getenv("SERVER_PRIVATE_KEY")
    server_ip = os.getenv("SERVER_IP")
    listen_port = os.getenv("LISTEN_PORT")

    config = f"""[Interface]
Address = {server_ip}
PrivateKey = {server_private_key}
ListenPort = {listen_port}
"""

    # Only include active peers
    peers = Peer.query.filter_by(is_active=True).all()
    for peer in peers:
        config += f"""
# Peer: {peer.id}, {peer.name}
[Peer]
PublicKey = {peer.public_key}
PresharedKey = {peer.preshared_key}
AllowedIPs = {peer.combined_allowed_ips}
PersistentKeepalive = {peer.persistent_keepalive if peer.persistent_keepalive else 25}
"""
        if peer.endpoint:
            config += f"Endpoint = {peer.endpoint}\n"
        if peer.persistent_keepalive:
            config += f"PersistentKeepalive = {peer.persistent_keepalive}\n"

    with open("wg0.conf", "w") as f:
        f.write(config)

    return "wg0.conf generated successfully."

def get_next_available_ip(subnet=None):
    """Get the next available IP address in the VPN subnet"""
    if not subnet:
        subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        raise ValueError(f"Invalid subnet: {subnet}")
    
    # Get all assigned IPs from database
    assigned_ips = set()
    peers = Peer.query.all()
    for peer in peers:
        if hasattr(peer, 'assigned_ip') and peer.assigned_ip:
            try:
                assigned_ips.add(ipaddress.ip_address(peer.assigned_ip))
            except ValueError:
                continue
    
    # Reserve first IP for server (usually .1)
    server_ip = network.network_address + 1
    assigned_ips.add(server_ip)
    
    # Find the lowest available IP
    for ip in network.hosts():
        if ip not in assigned_ips:
            return str(ip)
    
    raise ValueError(f"No available IP addresses in subnet {subnet}")

def validate_additional_ips(ips_string):
    """Validate additional allowed IPs string"""
    if not ips_string or not ips_string.strip():
        return []
    
    errors = []
    valid_ips = []
    
    # Split by comma and clean whitespace
    ip_list = [ip.strip() for ip in ips_string.split(',') if ip.strip()]
    
    for ip in ip_list:
        try:
            # Check if it's a valid IP network (with or without CIDR)
            if '/' not in ip:
                # Assume /32 for single IPs
                ip = f"{ip}/32"
            
            network = ipaddress.ip_network(ip, strict=False)
            valid_ips.append(str(network))
        except ValueError:
            errors.append(f"Invalid IP or CIDR notation: {ip}")
    
    if errors:
        raise ValueError("; ".join(errors))
    
    return valid_ips

def validate_allowed_ip_network(ip_network, peer_id=None, vpn_subnet=None):
    """
    Validate a single allowed IP network
    Returns (is_valid, error_message)
    """
    from app.models import Peer, AllowedIP
    
    try:
        # Parse the IP network
        network = ipaddress.ip_network(ip_network, strict=False)
    except ValueError:
        return False, f"Invalid IP network format: {ip_network}"
    
    # Get VPN subnet
    if not vpn_subnet:
        vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    try:
        vpn_network = ipaddress.ip_network(vpn_subnet, strict=False)
    except ValueError:
        return False, f"Invalid VPN subnet configuration: {vpn_subnet}"
    
    # Check if IP is in VPN subnet (not allowed for user-defined IPs)
    if network.overlaps(vpn_network):
        return False, f"IP network {ip_network} overlaps with VPN subnet {vpn_subnet}. User-defined IPs must be outside the VPN subnet."
    
    # Check for overlaps with other peers' allowed IPs
    peers = Peer.query.all()
    for peer in peers:
        if peer_id and peer.id == peer_id:
            continue  # Skip current peer when editing
            
        # Check assigned IP
        if peer.assigned_ip:
            try:
                peer_assigned = ipaddress.ip_network(f"{peer.assigned_ip}/32")
                if network.overlaps(peer_assigned):
                    return False, f"IP network {ip_network} overlaps with peer '{peer.name}' assigned IP {peer.assigned_ip}"
            except ValueError:
                pass
        
        # Check allowed IP ranges
        for allowed_ip in peer.allowed_ip_ranges:
            try:
                existing_network = ipaddress.ip_network(allowed_ip.ip_network, strict=False)
                if network.overlaps(existing_network):
                    return False, f"IP network {ip_network} overlaps with peer '{peer.name}' allowed IP {allowed_ip.ip_network}"
            except ValueError:
                continue
    
    return True, ""

def validate_multiple_allowed_ips(ip_networks, peer_id=None):
    """
    Validate multiple IP networks and check for conflicts
    Returns (all_valid, error_messages_list)
    """
    errors = []
    vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    # Check each IP individually
    for ip_network in ip_networks:
        if not ip_network.strip():
            continue
            
        is_valid, error = validate_allowed_ip_network(ip_network.strip(), peer_id, vpn_subnet)
        if not is_valid:
            errors.append(error)
    
    # Check for overlaps within the same peer's IPs
    networks = []
    for ip_network in ip_networks:
        if not ip_network.strip():
            continue
        try:
            network = ipaddress.ip_network(ip_network.strip(), strict=False)
            networks.append((network, ip_network.strip()))
        except ValueError:
            continue
    
    # Check for self-overlaps
    for i, (net1, ip1) in enumerate(networks):
        for j, (net2, ip2) in enumerate(networks):
            if i >= j:
                continue
            if net1.overlaps(net2):
                errors.append(f"IP networks {ip1} and {ip2} overlap with each other")
    
    return len(errors) == 0, errors

def get_all_used_networks():
    """Get all currently used IP networks in the system"""
    from app.models import Peer, AllowedIP
    
    used_networks = []
    vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    # Add VPN subnet
    try:
        used_networks.append(ipaddress.ip_network(vpn_subnet))
    except ValueError:
        pass
    
    # Add all peer assigned IPs
    peers = Peer.query.all()
    for peer in peers:
        if peer.assigned_ip:
            try:
                used_networks.append(ipaddress.ip_network(f"{peer.assigned_ip}/32"))
            except ValueError:
                continue
        
        # Add allowed IP ranges
        for allowed_ip in peer.allowed_ip_ranges:
            try:
                used_networks.append(ipaddress.ip_network(allowed_ip.ip_network))
            except ValueError:
                continue
    
    return used_networks


def validate_peer_data(data, peer_id=None):
    """
    Validate peer data for creation or update
    Returns list of validation errors
    """
    errors = []
    
    # Check required fields
    required_fields = ['name', 'public_key', 'allowed_ips']
    for field in required_fields:
        if not data.get(field) or not data.get(field).strip():
            errors.append(f'{field.replace("_", " ").title()} is required')
    
    # Validate name
    if data.get('name'):
        name = data['name'].strip()
        if len(name) < 1:
            errors.append('Name cannot be empty')
        elif len(name) > 50:
            errors.append('Name cannot be longer than 50 characters')
        elif not re.match(r'^[a-zA-Z0-9_-]+$', name):
            errors.append('Name can only contain letters, numbers, hyphens and underscores')
    
    # Validate WireGuard public key format
    if data.get('public_key'):
        public_key = data['public_key'].strip()
        if not re.match(r'^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$', public_key):
            errors.append('Invalid WireGuard public key format')
    
    # Validate allowed IPs (CIDR notation)
    if data.get('allowed_ips'):
        allowed_ips = data['allowed_ips'].strip()
        try:
            # Check if it's a valid IP network
            ipaddress.ip_network(allowed_ips, strict=False)
        except ValueError:
            errors.append('Invalid IP address or CIDR notation in Allowed IPs')
    
    # Validate endpoint format (optional)
    if data.get('endpoint') and data['endpoint'].strip():
        endpoint = data['endpoint'].strip()
        # Check for host:port format
        if not re.match(r'^[a-zA-Z0-9.-]+:\d+$', endpoint):
            errors.append('Endpoint must be in format host:port (e.g., example.com:51820)')
        else:
            # Validate port range
            try:
                port = int(endpoint.split(':')[-1])
                if port < 1 or port > 65535:
                    errors.append('Endpoint port must be between 1 and 65535')
            except ValueError:
                errors.append('Invalid port in endpoint')
    
    # Validate persistent keepalive (optional)
    if data.get('persistent_keepalive'):
        try:
            keepalive = int(data['persistent_keepalive'])
            if keepalive < 0 or keepalive > 65535:
                errors.append('Persistent keepalive must be between 0 and 65535')
        except (ValueError, TypeError):
            errors.append('Persistent keepalive must be a valid number')
    
    return errors

def validate_wireguard_key(key):
    """Validate WireGuard key format"""
    if not key:
        return False
    return bool(re.match(r'^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$', key))

def is_valid_ip_network(network):
    """Check if string is valid IP network in CIDR notation"""
    try:
        ipaddress.ip_network(network, strict=False)
        return True
    except ValueError:
        return False
