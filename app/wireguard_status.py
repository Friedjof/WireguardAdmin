#!/usr/bin/env python3
"""
WireGuard Status Parser
Extracts connection information from 'wg show' command
"""

import subprocess
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional


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
                    
                    # Determine if peer is connected (handshake within last 3 minutes)
                    if peers[current_peer]['latest_handshake']:
                        time_diff = datetime.now(timezone.utc) - peers[current_peer]['latest_handshake']
                        peers[current_peer]['is_connected'] = time_diff.total_seconds() < 180
                        peers[current_peer]['connection_duration_seconds'] = time_diff.total_seconds() if peers[current_peer]['is_connected'] else 0
                        print(f"    🔗 Connection status: {'✅ Connected' if peers[current_peer]['is_connected'] else '❌ Disconnected'} (handshake {int(time_diff.total_seconds())}s ago)")
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
            # Consider connected if handshake was within last 3 minutes
            peer_data['is_connected'] = time_diff.total_seconds() < 180
            
            # Extract client IP from endpoint if available
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
    Get WireGuard status for specified interface
    
    Returns peer connection information from 'wg show'
    """
    try:
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
        print(f"📊 Parsed {len(parsed_data)} peers from WireGuard output")
        
        return parsed_data
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
        # Other errors
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