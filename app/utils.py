from app import db
from app.models import Peer
import os
import re
import ipaddress
import qrcode
import io
import base64

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
"""
        if peer.endpoint:
            config += f"Endpoint = {peer.endpoint}\n"

        if peer.persistent_keepalive:
            config += f"PersistentKeepalive = {peer.persistent_keepalive}\n"
        else:
            config += "PersistentKeepalive = 25\n"  # Default to 25 seconds if not set

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

def generate_iptables_rules(peer_id=None, vpn_interface='wg0'):
    """Generate iptables rules for a specific peer or all peers"""
    from app.models import Peer, FirewallRule
    import subprocess
    
    rules = []
    
    # Base rules for WireGuard interface
    rules.extend([
        f"# Allow established and related connections",
        f"iptables -A FORWARD -i {vpn_interface} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        f"iptables -A FORWARD -o {vpn_interface} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        f"# Allow loopback",
        f"iptables -A INPUT -i lo -j ACCEPT",
        f"iptables -A OUTPUT -o lo -j ACCEPT"
    ])
    
    # Get peers to process
    if peer_id:
        peers = [Peer.query.get(peer_id)]
        peers = [p for p in peers if p is not None]
    else:
        peers = Peer.query.filter_by(is_active=True).all()
    
    for peer in peers:
        if not peer.assigned_ip:
            continue
            
        peer_ip = peer.assigned_ip
        rules.append(f"# Rules for peer: {peer.name} ({peer_ip})")
        
        # Get active firewall rules for this peer, sorted by priority
        firewall_rules = FirewallRule.query.filter_by(
            peer_id=peer.id, 
            is_active=True
        ).order_by(FirewallRule.priority).all()
        
        if not firewall_rules:
            # Default: Allow all traffic for peers without specific rules
            rules.append(f"iptables -A FORWARD -s {peer_ip}/32 -j ACCEPT")
            rules.append(f"iptables -A FORWARD -d {peer_ip}/32 -j ACCEPT")
        else:
            # Apply custom rules
            for rule in firewall_rules:
                iptables_rule = convert_firewall_rule_to_iptables(rule, peer_ip, vpn_interface)
                if iptables_rule:
                    rules.append(iptables_rule)
            
            # Add default drop rule at the end for this peer if there are custom rules
            rules.append(f"iptables -A FORWARD -s {peer_ip}/32 -j DROP")
            rules.append(f"iptables -A FORWARD -d {peer_ip}/32 -j DROP")
    
    return rules

def convert_firewall_rule_to_iptables(rule, peer_ip, vpn_interface='wg0'):
    """Convert a FirewallRule object to iptables command"""
    
    # Base command
    cmd_parts = ["iptables", "-A", "FORWARD"]
    
    # Source IP
    if rule.source:
        cmd_parts.extend(["-s", rule.source])
    else:
        cmd_parts.extend(["-s", f"{peer_ip}/32"])
    
    # Destination IP
    if rule.destination:
        cmd_parts.extend(["-d", rule.destination])
    elif rule.rule_type == 'internet':
        cmd_parts.extend(["-d", "0.0.0.0/0"])
    elif rule.rule_type == 'peer_comm':
        # Get VPN subnet for peer communication
        vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
        cmd_parts.extend(["-d", vpn_subnet])
    
    # Protocol
    if rule.protocol and rule.protocol != 'any':
        cmd_parts.extend(["-p", rule.protocol])
        
        # Port range (only for TCP/UDP)
        if rule.port_range and rule.port_range != 'any' and rule.protocol in ['tcp', 'udp']:
            if '-' in rule.port_range:
                # Port range (e.g., "80-443")
                cmd_parts.extend(["--dport", rule.port_range])
            else:
                # Single port
                cmd_parts.extend(["--dport", rule.port_range])
    
    # Interface constraints
    if rule.rule_type == 'internet':
        cmd_parts.extend(["-o", f"!{vpn_interface}"])  # Not going to VPN interface
    else:
        cmd_parts.extend(["-i", vpn_interface])  # Coming from VPN interface
    
    # Action
    action = "ACCEPT" if rule.action == "ALLOW" else "DROP"
    cmd_parts.extend(["-j", action])
    
    # Add comment
    cmd_parts.extend(["-m", "comment", "--comment", f"Rule:{rule.name}"])
    
    return " ".join(cmd_parts)

def apply_iptables_rules(peer_id=None, dry_run=False):
    """Apply iptables rules to the system"""
    import subprocess
    
    try:
        # Generate rules
        rules = generate_iptables_rules(peer_id)
        
        if dry_run:
            return {"status": "success", "rules": rules, "message": "Dry run completed"}
        
        # Clear existing VPN-related rules (be careful!)
        clear_commands = [
            "iptables -F FORWARD",  # Flush FORWARD chain
        ]
        
        # Apply clearing commands
        for cmd in clear_commands:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return {"status": "error", "message": f"Failed to clear rules: {result.stderr}"}
        
        # Apply new rules
        applied_rules = []
        for rule in rules:
            if rule.startswith('#'):
                continue  # Skip comments
            
            result = subprocess.run(rule.split(), capture_output=True, text=True, check=False)
            if result.returncode == 0:
                applied_rules.append(rule)
            else:
                return {
                    "status": "error", 
                    "message": f"Failed to apply rule: {rule}. Error: {result.stderr}",
                    "applied_rules": applied_rules
                }
        
        return {
            "status": "success", 
            "message": f"Applied {len(applied_rules)} iptables rules",
            "applied_rules": applied_rules
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error applying iptables rules: {str(e)}"}

def get_current_iptables_rules():
    """Get current iptables rules"""
    import subprocess
    
    try:
        result = subprocess.run(
            ["iptables", "-L", "FORWARD", "-n", "-v", "--line-numbers"], 
            capture_output=True, text=True, check=True
        )
        return {"status": "success", "rules": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Failed to get iptables rules: {e.stderr}"}
    except Exception as e:
        return {"status": "error", "message": f"Error getting iptables rules: {str(e)}"}

def validate_iptables_access():
    """Check if the application has permission to modify iptables"""
    import subprocess
    
    try:
        # Try to list rules (read-only test)
        result = subprocess.run(
            ["iptables", "-L", "-n"], 
            capture_output=True, text=True, check=True
        )
        return {"status": "success", "message": "iptables access confirmed"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"No iptables access: {e.stderr}"}
    except FileNotFoundError:
        return {"status": "error", "message": "iptables not found on system"}
    except Exception as e:
        return {"status": "error", "message": f"Error checking iptables access: {str(e)}"}

def backup_iptables_rules():
    """Create a backup of current iptables rules"""
    import subprocess
    from datetime import datetime
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"iptables_backup_{timestamp}.txt"
        
        result = subprocess.run(
            ["iptables-save"], 
            capture_output=True, text=True, check=True
        )
        
        with open(backup_file, 'w') as f:
            f.write(result.stdout)
        
        return {"status": "success", "backup_file": backup_file, "message": f"Backup saved to {backup_file}"}
    except Exception as e:
        return {"status": "error", "message": f"Error creating backup: {str(e)}"}

def restore_iptables_rules(backup_file):
    """Restore iptables rules from backup"""
    import subprocess
    
    try:
        if not os.path.exists(backup_file):
            return {"status": "error", "message": f"Backup file {backup_file} not found"}
        
        with open(backup_file, 'r') as f:
            backup_content = f.read()
        
        result = subprocess.run(
            ["iptables-restore"], 
            input=backup_content, text=True, 
            capture_output=True, check=True
        )
        
        return {"status": "success", "message": f"Rules restored from {backup_file}"}
    except Exception as e:
        return {"status": "error", "message": f"Error restoring rules: {str(e)}"}

def generate_peer_config_text(peer_id):
    """Generate WireGuard configuration text for a peer"""
    from app.models import Peer
    
    peer = Peer.query.get(peer_id)
    if not peer:
        raise ValueError(f"Peer with ID {peer_id} not found")
    
    server_public_key = os.getenv("SERVER_PUBLIC_KEY")
    server_ip = os.getenv("SERVER_IP")
    listen_port = os.getenv("LISTEN_PORT")
    
    # Build the address line with assigned IP and additional allowed IPs
    address_parts = []
    if peer.assigned_ip:
        address_parts.append(f"{peer.assigned_ip}/32")
    
    # Add additional allowed IP ranges if any
    if peer.allowed_ip_ranges:
        for allowed_ip in peer.allowed_ip_ranges:
            address_parts.append(allowed_ip.ip_network)
    
    address_line = ", ".join(address_parts) if address_parts else "10.0.0.0/32"
    
    config = f"""[Interface]
PrivateKey = <PLACEHOLDER_FOR_CLIENT_PRIVATE_KEY>
Address = {address_line}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {server_ip}:{listen_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = {peer.persistent_keepalive or 25}"""
    
    return config

def generate_qr_code(text, size=10, border=4):
    """Generate QR code for text and return as base64 encoded PNG"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=border,
        )
        qr.add_data(text)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        raise Exception(f"Error generating QR code: {str(e)}")

def generate_peer_qr_code(peer_id):
    """Generate QR code for peer configuration"""
    config_text = generate_peer_config_text(peer_id)
    return generate_qr_code(config_text)
