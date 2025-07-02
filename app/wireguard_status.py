#!/usr/bin/env python3
"""
WireGuard Status Parser
Extracts connection information from 'wg show' command
"""

import subprocess
import re
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Configuration - Following Go wireguard-ui reference: 3-minute handshake rule
HANDSHAKE_TIMEOUT = int(os.getenv('WG_HANDSHAKE_TIMEOUT', '180'))  # 3 minutes = 180 seconds
PING_TIMEOUT = float(os.getenv('WG_PING_TIMEOUT', '0.5'))  # seconds  
ENABLE_PING_CHECK = os.getenv('WG_ENABLE_PING_CHECK', 'false').lower() == 'true'  # Disabled by default
ENABLE_CONNTRACK = os.getenv('WG_ENABLE_CONNTRACK', 'false').lower() == 'true'  # Optional enhancement


def parse_latest_handshakes(output: str) -> Dict[str, datetime]:
    """
    Parse 'wg show interface latest-handshakes' output
    Format: public_key<tab>timestamp_seconds
    """
    print(f"🔍 Parsing latest-handshakes output: '{output.strip()}'")
    handshakes = {}
    
    if not output.strip():
        print(f"  ⚠️ Empty latest-handshakes output")
        return handshakes
    
    for line in output.strip().split('\n'):
        line = line.strip()
        if line and '\t' in line:
            try:
                public_key, timestamp_str = line.split('\t', 1)
                public_key = public_key.strip()
                timestamp_str = timestamp_str.strip()
                print(f"  🔍 Parsing line: key='{public_key[:20]}...', timestamp='{timestamp_str}'")
                
                timestamp = int(timestamp_str)
                if timestamp > 0:  # 0 means never
                    handshakes[public_key] = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    print(f"  🤝 {public_key[:20]}... handshake: {handshakes[public_key]} (Unix: {timestamp})")
                else:
                    print(f"  🤝 {public_key[:20]}... no handshake (timestamp=0)")
            except (ValueError, IndexError) as e:
                print(f"  ⚠️ Error parsing handshake line '{line}': {e}")
        elif line:
            print(f"  ⚠️ Line without tab separator: '{line}'")
    
    print(f"🔍 Parsed {len(handshakes)} handshakes from latest-handshakes")
    return handshakes


def check_peer_connectivity(peer_ip: str, timeout: float = 0.5) -> bool:
    """
    Check if a peer is reachable via ping
    
    Args:
        peer_ip: IP address to ping
        timeout: Ping timeout in seconds
        
    Returns:
        True if peer responds to ping, False otherwise
    """
    try:
        # Use ping with short timeout for quick response
        result = subprocess.run(
            ['ping', '-c', '1', '-W', str(int(timeout * 1000)), peer_ip],
            capture_output=True,
            timeout=timeout + 0.5  # Slightly longer timeout for the process
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False
    except Exception:
        return False


def get_conntrack_connections(interface_port: int = 51820) -> Dict[str, Dict]:
    """
    Get active WireGuard connections from conntrack table
    This is much more accurate than handshake parsing
    """
    print(f"🔍 Checking conntrack for active WireGuard connections on port {interface_port}...")
    connections = {}
    
    try:
        # Get UDP connections on WireGuard port
        result = subprocess.run(
            ['conntrack', '-L', '-p', 'udp', '--dport', str(interface_port)],
            capture_output=True, text=True, timeout=3
        )
        
        if result.returncode == 0:
            print(f"📊 Conntrack query successful, parsing {len(result.stdout.strip().split(chr(10)))} entries...")
            
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        # Parse conntrack line format:
                        # udp 17 118 src=192.168.3.54 dst=172.24.0.2 sport=54186 dport=51820 src=172.24.0.2 dst=192.168.3.54 sport=51820 dport=54186 [ASSURED] mark=0 use=1
                        
                        # Extract connection info
                        parts = line.split()
                        if len(parts) < 6:
                            continue
                            
                        # Get timeout (connection age)
                        timeout = int(parts[2]) if parts[2].isdigit() else 0
                        
                        # Extract IPs and ports
                        src_ip = None
                        src_port = None
                        dst_ip = None
                        dst_port = None
                        is_assured = '[ASSURED]' in line
                        
                        for part in parts:
                            if part.startswith('src='):
                                if src_ip is None:  # First src is the original source
                                    src_ip = part.split('=')[1]
                            elif part.startswith('sport='):
                                if src_port is None:  # First sport is original source port
                                    src_port = int(part.split('=')[1])
                            elif part.startswith('dst='):
                                if dst_ip is None:  # First dst is original destination
                                    dst_ip = part.split('=')[1]
                            elif part.startswith('dport='):
                                if dst_port is None:  # First dport is original destination port
                                    dst_port = int(part.split('=')[1])
                        
                        # Store connection info keyed by client IP
                        if src_ip and dst_port == interface_port:
                            connections[src_ip] = {
                                'client_ip': src_ip,
                                'client_port': src_port,
                                'server_ip': dst_ip,
                                'server_port': dst_port,
                                'timeout_seconds': timeout,
                                'is_assured': is_assured,
                                'is_active': is_assured and timeout > 0,
                                'connection_age_seconds': timeout
                            }
                            print(f"  📡 Found connection: {src_ip}:{src_port} -> {dst_ip}:{dst_port} (age: {timeout}s, assured: {is_assured})")
                            
                    except (ValueError, IndexError) as e:
                        print(f"  ⚠️ Error parsing conntrack line: {e}")
                        continue
        else:
            print(f"⚠️ Conntrack query failed: {result.stderr}")
            
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ Conntrack not available or timeout: {e}")
    except Exception as e:
        print(f"❌ Unexpected error with conntrack: {e}")
    
    print(f"🔍 Found {len(connections)} active conntrack connections")
    return connections


def enhance_connectivity_detection(peer_data: Dict[str, Dict], interface: str = 'wg0') -> Dict[str, Dict]:
    """
    Optional enhanced connectivity detection - only runs if features are enabled
    Primary method is simple 3-minute handshake rule
    """
    if not (ENABLE_CONNTRACK or ENABLE_PING_CHECK):
        print(f"🔬 Enhanced detection disabled, using simple handshake rule only")
        return peer_data
        
    print(f"🔬 Enhanced connectivity detection starting (conntrack={ENABLE_CONNTRACK}, ping={ENABLE_PING_CHECK})...")
    
    # Optional Method 1: Conntrack for real-time connection tracking
    conntrack_connections = {}
    if ENABLE_CONNTRACK:
        conntrack_connections = get_conntrack_connections()
    
    # Optional Method 2: Enhanced ping testing
    for public_key, peer in peer_data.items():
        if not peer.get('endpoint'):
            continue
            
        client_ip = peer.get('client_ip')
        
        # Add conntrack data if enabled
        if ENABLE_CONNTRACK and client_ip and client_ip in conntrack_connections:
            conn_info = conntrack_connections[client_ip]
            peer['conntrack_active'] = conn_info['is_active']
            peer['conntrack_age'] = conn_info['connection_age_seconds']
            peer['conntrack_assured'] = conn_info['is_assured']
            print(f"  🎯 {public_key[:20]}... conntrack: {'✅ Active' if conn_info['is_active'] else '❌ Inactive'} (age: {conn_info['connection_age_seconds']}s)")
        else:
            peer['conntrack_active'] = False
            peer['conntrack_age'] = None
            peer['conntrack_assured'] = False
        
        # Add ping data if enabled (only for debugging, not used in primary logic)
        if ENABLE_PING_CHECK and client_ip:
            external_reachable = check_peer_connectivity(client_ip, PING_TIMEOUT)
            peer['external_ping'] = external_reachable
            print(f"  🏓 {public_key[:20]}... ping test: {'✅ Reachable' if external_reachable else '❌ Unreachable'}")
        else:
            peer['external_ping'] = False
    
    print(f"🔬 Enhanced connectivity detection completed")
    return peer_data


def parse_transfer_stats(output: str) -> Dict[str, bool]:
    """Parse transfer statistics to detect recent activity"""
    transfer_data = {}
    for line in output.strip().split('\n'):
        if '\t' in line:
            try:
                parts = line.split('\t')
                if len(parts) >= 3:
                    public_key = parts[0]
                    rx_bytes = int(parts[1]) if parts[1] != '(none)' else 0
                    tx_bytes = int(parts[2]) if parts[2] != '(none)' else 0
                    # Consider active if any data transferred
                    transfer_data[public_key] = (rx_bytes > 0 or tx_bytes > 0)
            except (ValueError, IndexError):
                pass
    return transfer_data


def parse_allowed_ips(output: str) -> Dict[str, List[str]]:
    """Parse allowed IPs output"""
    allowed_data = {}
    for line in output.strip().split('\n'):
        if '\t' in line:
            try:
                public_key, ips_str = line.split('\t', 1)
                allowed_data[public_key] = ips_str.strip().split(',') if ips_str.strip() else []
            except (ValueError, IndexError):
                pass
    return allowed_data


def parse_wg_show_output(output: str) -> Dict[str, Dict]:
    """
    Parse wg show output and return peer connection information
    
    Returns:
    {
        'public_key': {
            'endpoint': '192.168.1.100:12345',
            'allowed_ips': ['10.0.0.2/32'],
            'latest_handshake': datetime_object,
            'transfer_rx': bytes_received,
            'transfer_tx': bytes_sent,
            'persistent_keepalive': seconds,
            'is_connected': True/False
        }
    }
    """
    print(f"🔍 Parsing WireGuard output ({len(output)} chars)...")
    peers = {}
    current_peer = None
    
    for line in output.strip().split('\n'):
        line = line.strip()
        
        if line.startswith('peer:'):
            # New peer entry
            public_key = line.split('peer:')[1].strip()
            current_peer = public_key
            print(f"  📋 Found peer: {public_key[:20]}...")
            peers[current_peer] = {
                'endpoint': None,
                'allowed_ips': [],
                'latest_handshake': None,
                'transfer_rx': 0,
                'transfer_tx': 0,
                'persistent_keepalive': None,
                'is_connected': False
            }
            
        elif current_peer and line.startswith('endpoint:'):
            endpoint = line.split('endpoint:')[1].strip()
            peers[current_peer]['endpoint'] = endpoint
            print(f"    🌐 Endpoint: {endpoint}")
            
        elif current_peer and line.startswith('allowed ips:'):
            allowed_ips = line.split('allowed ips:')[1].strip()
            if allowed_ips:
                peers[current_peer]['allowed_ips'] = [ip.strip() for ip in allowed_ips.split(',')]
            
        elif current_peer and line.startswith('latest handshake:'):
            handshake_str = line.split('latest handshake:')[1].strip()
            print(f"    🤝 Latest handshake: {handshake_str}")
            if handshake_str and handshake_str != '(none)':
                try:
                    # Parse different handshake formats
                    if 'ago' in handshake_str:
                        # Format: "1 minute, 23 seconds ago"
                        peers[current_peer]['latest_handshake'] = parse_relative_time(handshake_str)
                    else:
                        # Absolute timestamp format
                        peers[current_peer]['latest_handshake'] = datetime.now(timezone.utc)
                    
                    # Initial handshake parsing - detailed connection logic happens later
                    print(f"    🔗 Handshake parsed successfully")
                except Exception as e:
                    print(f"    ⚠️ Error parsing handshake: {e}")
            else:
                print(f"    🤝 No handshake data available")
            
        elif current_peer and line.startswith('transfer:'):
            transfer_str = line.split('transfer:')[1].strip()
            # Format: "1.23 MiB received, 456.78 KiB sent"
            print(f"    📊 Transfer: {transfer_str}")
            if transfer_str:
                rx, tx = parse_transfer_data(transfer_str)
                peers[current_peer]['transfer_rx'] = rx
                peers[current_peer]['transfer_tx'] = tx
                print(f"    📥 RX: {rx} bytes, 📤 TX: {tx} bytes")
                
        elif current_peer and line.startswith('persistent keepalive:'):
            keepalive_str = line.split('persistent keepalive:')[1].strip()
            if keepalive_str and keepalive_str != 'off':
                try:
                    # Extract seconds from "every 25 seconds"
                    seconds = int(re.search(r'(\d+)', keepalive_str).group(1))
                    peers[current_peer]['persistent_keepalive'] = seconds
                except:
                    pass
    
    # Final processing and connection status determination
    print(f"🔧 Post-processing {len(peers)} peers...")
    for peer_key, peer_data in peers.items():
        print(f"  📋 Processing peer: {peer_key[:20]}...")
        
        if peer_data['latest_handshake']:
            time_diff = datetime.now(timezone.utc) - peer_data['latest_handshake']
            # Consider connected if handshake was within configured timeout
            handshake_recent = time_diff.total_seconds() < HANDSHAKE_TIMEOUT
            
            # Extract client IP from endpoint first
            client_ip = None
            if peer_data['endpoint']:
                try:
                    # Endpoint format is typically "IP:PORT"
                    client_ip = peer_data['endpoint'].split(':')[0]
                    peer_data['client_ip'] = client_ip
                    print(f"    🏠 Client IP extracted: {client_ip}")
                except:
                    peer_data['client_ip'] = None
                    print(f"    ⚠️ Could not extract client IP from endpoint: {peer_data['endpoint']}")
            else:
                peer_data['client_ip'] = None
                print(f"    ❌ No endpoint available")
            
            # Additional connectivity check via ping if enabled and IP is available
            ping_reachable = False
            if ENABLE_PING_CHECK and client_ip:
                ping_reachable = check_peer_connectivity(client_ip, PING_TIMEOUT)
                print(f"    🏓 Ping test to {client_ip}: {'✅ Reachable' if ping_reachable else '❌ Unreachable'}")
            
            # Simple 3-minute handshake rule (following Go wireguard-ui reference)
            # A peer is connected if last handshake was within timeout period
            peer_data['is_connected'] = handshake_recent
            peer_data['connection_method'] = 'handshake_3min_rule'
            peer_data['handshake_minutes_ago'] = time_diff.total_seconds() / 60.0
            
            # Optional: Enhanced detection with conntrack if enabled
            if ENABLE_CONNTRACK and not handshake_recent:
                conntrack_active = peer_data.get('conntrack_active', False)
                conntrack_assured = peer_data.get('conntrack_assured', False)
                if conntrack_assured or conntrack_active:
                    peer_data['is_connected'] = True
                    peer_data['connection_method'] = f'conntrack_override_{conntrack_assured and "assured" or "active"}'
            
            # Optional: Ping fallback if enabled  
            if ENABLE_PING_CHECK and not peer_data['is_connected'] and ping_reachable:
                peer_data['is_connected'] = True
                peer_data['connection_method'] = 'ping_fallback'
            
            print(f"    📊 Simple connection logic: handshake_age={peer_data['handshake_minutes_ago']:.1f}min, handshake_recent={handshake_recent}, method={peer_data['connection_method']}, final={peer_data['is_connected']}")
                
            # Calculate connection duration (approximate)
            peer_data['connection_duration_seconds'] = time_diff.total_seconds()
            print(f"    ⏱️ Final connection status: {'✅ Connected' if peer_data['is_connected'] else '❌ Disconnected'}")
        else:
            peer_data['is_connected'] = False
            peer_data['client_ip'] = None
            peer_data['connection_duration_seconds'] = None
            print(f"    ❌ No handshake - marked as disconnected")
    
    return peers


def parse_relative_time(time_str: str) -> datetime:
    """Parse relative time like '2 minutes, 30 seconds ago'"""
    now = datetime.now(timezone.utc)
    total_seconds = 0
    
    # Extract time components
    time_parts = time_str.lower().replace('ago', '').strip()
    
    # Parse different time units
    patterns = [
        (r'(\d+)\s*second', 1),
        (r'(\d+)\s*minute', 60),
        (r'(\d+)\s*hour', 3600),
        (r'(\d+)\s*day', 86400),
    ]
    
    for pattern, multiplier in patterns:
        matches = re.findall(pattern, time_parts)
        for match in matches:
            total_seconds += int(match) * multiplier
    
    return now - timedelta(seconds=total_seconds)


def parse_transfer_data(transfer_str: str) -> tuple:
    """Parse transfer data like '1.23 MiB received, 456.78 KiB sent'"""
    rx_bytes = 0
    tx_bytes = 0
    
    # Extract received data
    rx_match = re.search(r'([\d.]+)\s*([KMGT]?i?B)\s*received', transfer_str)
    if rx_match:
        value, unit = rx_match.groups()
        rx_bytes = convert_to_bytes(float(value), unit)
    
    # Extract sent data
    tx_match = re.search(r'([\d.]+)\s*([KMGT]?i?B)\s*sent', transfer_str)
    if tx_match:
        value, unit = tx_match.groups()
        tx_bytes = convert_to_bytes(float(value), unit)
    
    return rx_bytes, tx_bytes


def convert_to_bytes(value: float, unit: str) -> int:
    """Convert data size to bytes"""
    unit = unit.upper()
    multipliers = {
        'B': 1,
        'KB': 1000, 'KIB': 1024,
        'MB': 1000**2, 'MIB': 1024**2,
        'GB': 1000**3, 'GIB': 1024**3,
        'TB': 1000**4, 'TIB': 1024**4,
    }
    return int(value * multipliers.get(unit, 1))


def get_wireguard_status(interface: str = 'wg0') -> Dict[str, Dict]:
    """
    Get WireGuard status for specified interface with enhanced connectivity detection
    
    Returns peer connection information from 'wg show' + additional checks
    """
    try:
        print(f"🔍 Executing: wg show {interface} latest-handshakes", flush=True)
        # Use 'latest-handshakes' for more precise timing info
        result = subprocess.run(
            ['wg', 'show', interface, 'latest-handshakes'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse latest-handshakes output first
            handshake_data = parse_latest_handshakes(result.stdout)
            print(f"📋 Latest handshakes: {handshake_data}")
        else:
            handshake_data = {}
        
        # Now get full status
        print(f"🔍 Executing: wg show {interface}", flush=True)
        result = subprocess.run(
            ['wg', 'show', interface],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ WireGuard command successful, output length: {len(result.stdout)} chars")
        if result.stdout.strip():
            print(f"📋 WireGuard output preview:\n{result.stdout[:200]}{'...' if len(result.stdout) > 200 else ''}")
        else:
            print("⚠️ WireGuard output is empty - no active peers or interface not configured")
        
        parsed_data = parse_wg_show_output(result.stdout)
        
        # Merge precise handshake data
        for public_key, peer_data in parsed_data.items():
            if public_key in handshake_data:
                peer_data['latest_handshake'] = handshake_data[public_key]
                print(f"📊 Updated handshake for {public_key[:20]}... with precise timestamp")
        
        print(f"📊 Parsed {len(parsed_data)} peers from WireGuard output")
        
        # Additional connectivity verification using WireGuard-specific methods
        enhanced_data = enhance_connectivity_detection(parsed_data, interface)
        
        return enhanced_data
    except subprocess.CalledProcessError as e:
        print(f"❌ WireGuard command failed (exit code {e.returncode}): {e.stderr}")
        print(f"   Interface '{interface}' might not exist or wg command failed")
        return {}
    except FileNotFoundError:
        print("❌ WireGuard command 'wg' not found in PATH")
        print("   Make sure WireGuard tools are installed")
        return {}
    except Exception as e:
        print(f"❌ Unexpected error getting WireGuard status: {e}")
        return {}


def get_peer_connection_status(public_key: str, interface: str = 'wg0') -> Dict:
    """
    Get connection status for a specific peer by public key
    
    Returns:
    {
        'is_connected': bool,
        'endpoint': str or None,
        'latest_handshake': datetime or None,
        'transfer_rx': int (bytes),
        'transfer_tx': int (bytes),
        'persistent_keepalive': int or None
    }
    """
    wg_status = get_wireguard_status(interface)
    return wg_status.get(public_key, {
        'is_connected': False,
        'endpoint': None,
        'latest_handshake': None,
        'transfer_rx': 0,
        'transfer_tx': 0,
        'persistent_keepalive': None
    })


def format_bytes(bytes_count: int) -> str:
    """Format bytes to human readable string"""
    if bytes_count == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_count)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def format_time_ago(dt: datetime) -> str:
    """Format datetime to 'X minutes ago' string"""
    if not dt:
        return "Never"
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    
    if diff.total_seconds() < 60:
        return "Just now"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} min ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = int(diff.total_seconds() / 86400)
        return f"{days}d ago"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if not seconds or seconds < 0:
        return "0s"
    
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"


# Fix import for timedelta
from datetime import timedelta

if __name__ == "__main__":
    # Test the parser
    status = get_wireguard_status()
    for public_key, peer_data in status.items():
        print(f"Peer: {public_key[:20]}...")
        print(f"  Connected: {peer_data['is_connected']}")
        print(f"  Endpoint: {peer_data['endpoint']}")
        print(f"  Handshake: {format_time_ago(peer_data['latest_handshake'])}")
        print(f"  RX: {format_bytes(peer_data['transfer_rx'])}")
        print(f"  TX: {format_bytes(peer_data['transfer_tx'])}")
        print()