"""
Advanced iptables management using python-iptables library
Provides direct manipulation of iptables rules for WireGuard VPN management
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    import iptc
    IPTABLES_AVAILABLE = True
except ImportError:
    IPTABLES_AVAILABLE = False
    logging.warning("python-iptables not available, falling back to subprocess")

from app.models import Peer, FirewallRule


class IptablesManager:
    """
    Advanced iptables management using python-iptables
    """
    
    def __init__(self, vpn_interface: str = 'wg0'):
        self.vpn_interface = vpn_interface
        self.vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
        self.chain_name = "WIREGUARD_FORWARD"
        self.logger = logging.getLogger(__name__)
        
        if not IPTABLES_AVAILABLE:
            raise ImportError("python-iptables is required but not installed")
    
    def validate_access(self) -> Dict[str, str]:
        """Check if we have permission to modify iptables"""
        try:
            # Try to access the filter table
            table = iptc.Table(iptc.Table.FILTER)
            table.refresh()
            return {"status": "success", "message": "iptables access confirmed"}
        except iptc.ip4tc.IPTCError as e:
            return {"status": "error", "message": f"No iptables access: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Error checking iptables access: {str(e)}"}
    
    def backup_rules(self) -> Dict[str, str]:
        """Create a backup of current iptables rules"""
        try:
            import subprocess
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
    
    def get_current_rules(self) -> Dict[str, str]:
        """Get current iptables rules"""
        try:
            table = iptc.Table(iptc.Table.FILTER)
            table.refresh()
            
            forward_chain = iptc.Chain(table, "FORWARD")
            rules_output = []
            
            for i, rule in enumerate(forward_chain.rules, 1):
                rule_str = self._format_rule_for_display(rule, i)
                rules_output.append(rule_str)
            
            return {"status": "success", "rules": "\n".join(rules_output)}
        except Exception as e:
            return {"status": "error", "message": f"Error getting iptables rules: {str(e)}"}
    
    def _format_rule_for_display(self, rule: iptc.Rule, line_num: int) -> str:
        """Format an iptables rule for display"""
        try:
            # Get counters
            packets, bytes_count = rule.get_counters()
            
            # Get basic rule info
            target = rule.target.name if rule.target else "ACCEPT"
            protocol = rule.protocol if rule.protocol else "all"
            src = rule.src if rule.src else "0.0.0.0/0"
            dst = rule.dst if rule.dst else "0.0.0.0/0"
            
            # Get interfaces
            in_iface = rule.in_interface if rule.in_interface else "*"
            out_iface = rule.out_interface if rule.out_interface else "*"
            
            return f"{line_num:4} {packets:8} {bytes_count:8} {target:8} {protocol:4} {src:18} {dst:18} {in_iface:8} {out_iface:8}"
        except Exception:
            return f"{line_num:4} Error formatting rule"
    
    def create_wireguard_chain(self) -> bool:
        """Create a custom chain for WireGuard rules"""
        try:
            table = iptc.Table(iptc.Table.FILTER)
            table.autocommit = False
            
            # Check if chain already exists
            try:
                chain = iptc.Chain(table, self.chain_name)
                self.logger.info(f"Chain {self.chain_name} already exists")
            except iptc.ip4tc.IPTCError:
                # Chain doesn't exist, create it
                chain = table.create_chain(self.chain_name)
                self.logger.info(f"Created chain {self.chain_name}")
            
            table.commit()
            table.autocommit = True
            return True
        except Exception as e:
            self.logger.error(f"Error creating WireGuard chain: {e}")
            return False
    
    def clear_wireguard_rules(self) -> Dict[str, str]:
        """Clear all WireGuard-related rules"""
        try:
            table = iptc.Table(iptc.Table.FILTER)
            table.autocommit = False
            
            # Clear our custom chain if it exists
            try:
                chain = iptc.Chain(table, self.chain_name)
                chain.flush()
                self.logger.info(f"Flushed chain {self.chain_name}")
            except iptc.ip4tc.IPTCError:
                pass  # Chain doesn't exist
            
            # Remove WireGuard-related rules from FORWARD chain
            forward_chain = iptc.Chain(table, "FORWARD")
            rules_to_remove = []
            
            for rule in forward_chain.rules:
                # Check if rule is WireGuard-related
                if self._is_wireguard_rule(rule):
                    rules_to_remove.append(rule)
            
            for rule in rules_to_remove:
                forward_chain.delete_rule(rule)
            
            table.commit()
            table.autocommit = True
            
            return {"status": "success", "message": f"Cleared {len(rules_to_remove)} WireGuard rules"}
        except Exception as e:
            return {"status": "error", "message": f"Error clearing rules: {str(e)}"}
    
    def _is_wireguard_rule(self, rule: iptc.Rule) -> bool:
        """Check if a rule is WireGuard-related"""
        try:
            # Check interfaces
            if rule.in_interface == self.vpn_interface or rule.out_interface == self.vpn_interface:
                return True
            
            # Check for WireGuard subnet
            if self.vpn_subnet in str(rule.src) or self.vpn_subnet in str(rule.dst):
                return True
            
            # Check for comment containing our rule identifier
            for match in rule.matches:
                if match.name == "comment":
                    comment = getattr(match, 'comment', '')
                    if 'Rule:' in comment or 'WireGuard' in comment:
                        return True
            
            return False
        except Exception:
            return False
    
    def apply_peer_rules(self, peer_id: Optional[int] = None, dry_run: bool = False) -> Dict[str, any]:
        """Apply iptables rules for peers using python-iptables"""
        try:
            # Get peers to process
            if peer_id:
                peers = [Peer.query.get(peer_id)]
                peers = [p for p in peers if p is not None]
            else:
                peers = Peer.query.filter_by(is_active=True).all()
            
            if dry_run:
                # Generate rules for preview
                rules = self._generate_rules_preview(peers)
                return {"status": "success", "rules": rules, "message": "Dry run completed"}
            
            # Create WireGuard chain
            if not self.create_wireguard_chain():
                return {"status": "error", "message": "Failed to create WireGuard chain"}
            
            # Clear existing WireGuard rules
            clear_result = self.clear_wireguard_rules()
            if clear_result["status"] != "success":
                return clear_result
            
            # Apply new rules
            applied_count = 0
            table = iptc.Table(iptc.Table.FILTER)
            table.autocommit = False
            
            try:
                # Add base rules
                applied_count += self._add_base_rules(table)
                
                # Add peer-specific rules
                for peer in peers:
                    peer_rules = self._add_peer_rules(table, peer)
                    applied_count += peer_rules
                
                table.commit()
                table.autocommit = True
                
                return {
                    "status": "success",
                    "message": f"Applied {applied_count} iptables rules for {len(peers)} peers",
                    "applied_rules": applied_count
                }
            except Exception as e:
                table.autocommit = True
                return {"status": "error", "message": f"Error applying rules: {str(e)}"}
                
        except Exception as e:
            return {"status": "error", "message": f"Error in apply_peer_rules: {str(e)}"}
    
    def _generate_rules_preview(self, peers: List[Peer]) -> List[str]:
        """Generate a preview of iptables rules that would be applied"""
        rules = []
        
        # Base rules
        rules.extend([
            "# Base WireGuard rules",
            f"iptables -A FORWARD -i {self.vpn_interface} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
            f"iptables -A FORWARD -o {self.vpn_interface} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A OUTPUT -o lo -j ACCEPT",
            ""
        ])
        
        # Peer-specific rules
        for peer in peers:
            if not peer.assigned_ip:
                continue
            
            rules.append(f"# Rules for peer: {peer.name} ({peer.assigned_ip})")
            
            # Get firewall rules for this peer
            firewall_rules = FirewallRule.query.filter_by(
                peer_id=peer.id,
                is_active=True
            ).order_by(FirewallRule.priority).all()
            
            if not firewall_rules:
                # Default: Allow all traffic
                rules.extend([
                    f"iptables -A FORWARD -s {peer.assigned_ip}/32 -j ACCEPT",
                    f"iptables -A FORWARD -d {peer.assigned_ip}/32 -j ACCEPT"
                ])
            else:
                # Custom rules
                for rule in firewall_rules:
                    iptables_rule = self._convert_firewall_rule_to_iptables_preview(rule, peer.assigned_ip)
                    if iptables_rule:
                        rules.append(iptables_rule)
                
                # Default drop
                rules.extend([
                    f"iptables -A FORWARD -s {peer.assigned_ip}/32 -j DROP",
                    f"iptables -A FORWARD -d {peer.assigned_ip}/32 -j DROP"
                ])
            
            rules.append("")
        
        return rules
    
    def _convert_firewall_rule_to_iptables_preview(self, rule: FirewallRule, peer_ip: str) -> str:
        """Convert a FirewallRule to iptables command preview"""
        cmd_parts = ["iptables", "-A", "FORWARD"]
        
        # Source IP
        if rule.source:
            cmd_parts.extend(["-s", rule.source])
        else:
            cmd_parts.extend(["-s", f"{peer_ip}/32"])
        
        # Destination IP
        if rule.destination:
            cmd_parts.extend(["-d", rule.destination])
        elif rule.rule_type.value == 'internet':
            cmd_parts.extend(["-d", "0.0.0.0/0"])
        elif rule.rule_type.value == 'peer_comm':
            cmd_parts.extend(["-d", self.vpn_subnet])
        
        # Protocol
        if rule.protocol and rule.protocol.value != 'any':
            cmd_parts.extend(["-p", rule.protocol.value])
            
            # Port range
            if rule.port_range and rule.port_range != 'any' and rule.protocol.value in ['tcp', 'udp']:
                cmd_parts.extend(["--dport", rule.port_range])
        
        # Interface constraints
        if rule.rule_type.value == 'internet':
            cmd_parts.extend(["-o", f"!{self.vpn_interface}"])
        else:
            cmd_parts.extend(["-i", self.vpn_interface])
        
        # Action
        action = "ACCEPT" if rule.action.value == "ALLOW" else "DROP"
        cmd_parts.extend(["-j", action])
        
        # Comment
        cmd_parts.extend(["-m", "comment", "--comment", f"Rule:{rule.name}"])
        
        return " ".join(cmd_parts)
    
    def _add_base_rules(self, table: iptc.Table) -> int:
        """Add base WireGuard rules"""
        forward_chain = iptc.Chain(table, "FORWARD")
        input_chain = iptc.Chain(table, "INPUT")
        output_chain = iptc.Chain(table, "OUTPUT")
        
        rules_added = 0
        
        try:
            # Allow established and related connections on WireGuard interface
            rule1 = iptc.Rule()
            rule1.in_interface = self.vpn_interface
            rule1.create_match("conntrack").ctstate = "ESTABLISHED,RELATED"
            rule1.create_target("ACCEPT")
            forward_chain.insert_rule(rule1)
            rules_added += 1
            
            rule2 = iptc.Rule()
            rule2.out_interface = self.vpn_interface
            rule2.create_match("conntrack").ctstate = "ESTABLISHED,RELATED"
            rule2.create_target("ACCEPT")
            forward_chain.insert_rule(rule2)
            rules_added += 1
            
            # Allow loopback
            rule3 = iptc.Rule()
            rule3.in_interface = "lo"
            rule3.create_target("ACCEPT")
            input_chain.insert_rule(rule3)
            rules_added += 1
            
            rule4 = iptc.Rule()
            rule4.out_interface = "lo"
            rule4.create_target("ACCEPT")
            output_chain.insert_rule(rule4)
            rules_added += 1
            
        except Exception as e:
            self.logger.error(f"Error adding base rules: {e}")
        
        return rules_added
    
    def _add_peer_rules(self, table: iptc.Table, peer: Peer) -> int:
        """Add rules for a specific peer"""
        if not peer.assigned_ip:
            return 0
        
        forward_chain = iptc.Chain(table, "FORWARD")
        rules_added = 0
        
        try:
            # Get firewall rules for this peer
            firewall_rules = FirewallRule.query.filter_by(
                peer_id=peer.id,
                is_active=True
            ).order_by(FirewallRule.priority).all()
            
            if not firewall_rules:
                # Default: Allow all traffic for this peer
                rule1 = iptc.Rule()
                rule1.src = f"{peer.assigned_ip}/32"
                rule1.create_target("ACCEPT")
                rule1.create_match("comment").comment = f"Default-Allow:{peer.name}"
                forward_chain.insert_rule(rule1)
                rules_added += 1
                
                rule2 = iptc.Rule()
                rule2.dst = f"{peer.assigned_ip}/32"
                rule2.create_target("ACCEPT")
                rule2.create_match("comment").comment = f"Default-Allow:{peer.name}"
                forward_chain.insert_rule(rule2)
                rules_added += 1
            else:
                # Apply custom firewall rules
                for fw_rule in firewall_rules:
                    rule = self._create_iptables_rule_from_firewall_rule(fw_rule, peer.assigned_ip)
                    if rule:
                        forward_chain.insert_rule(rule)
                        rules_added += 1
                
                # Add default drop rule for this peer
                rule1 = iptc.Rule()
                rule1.src = f"{peer.assigned_ip}/32"
                rule1.create_target("DROP")
                rule1.create_match("comment").comment = f"Default-Drop:{peer.name}"
                forward_chain.insert_rule(rule1)
                rules_added += 1
                
                rule2 = iptc.Rule()
                rule2.dst = f"{peer.assigned_ip}/32"
                rule2.create_target("DROP")
                rule2.create_match("comment").comment = f"Default-Drop:{peer.name}"
                forward_chain.insert_rule(rule2)
                rules_added += 1
        
        except Exception as e:
            self.logger.error(f"Error adding rules for peer {peer.name}: {e}")
        
        return rules_added
    
    def _create_iptables_rule_from_firewall_rule(self, fw_rule: FirewallRule, peer_ip: str) -> Optional[iptc.Rule]:
        """Create an iptables Rule object from a FirewallRule"""
        try:
            rule = iptc.Rule()
            
            # Source IP
            if fw_rule.source:
                rule.src = fw_rule.source
            else:
                rule.src = f"{peer_ip}/32"
            
            # Destination IP
            if fw_rule.destination:
                rule.dst = fw_rule.destination
            elif fw_rule.rule_type.value == 'internet':
                rule.dst = "0.0.0.0/0"
            elif fw_rule.rule_type.value == 'peer_comm':
                rule.dst = self.vpn_subnet
            
            # Protocol
            if fw_rule.protocol and fw_rule.protocol.value != 'any':
                rule.protocol = fw_rule.protocol.value
                
                # Port range (only for TCP/UDP)
                if fw_rule.port_range and fw_rule.port_range != 'any' and fw_rule.protocol.value in ['tcp', 'udp']:
                    match = rule.create_match(fw_rule.protocol.value)
                    match.dport = fw_rule.port_range
            
            # Interface constraints
            if fw_rule.rule_type.value == 'internet':
                rule.out_interface = f"!{self.vpn_interface}"
            else:
                rule.in_interface = self.vpn_interface
            
            # Action
            action = "ACCEPT" if fw_rule.action.value == "ALLOW" else "DROP"
            rule.create_target(action)
            
            # Comment
            rule.create_match("comment").comment = f"Rule:{fw_rule.name}"
            
            return rule
        except Exception as e:
            self.logger.error(f"Error creating iptables rule from {fw_rule.name}: {e}")
            return None


# Fallback to subprocess-based implementation if python-iptables is not available
class SubprocessIptablesManager:
    """Fallback implementation using subprocess calls"""
    
    def __init__(self, vpn_interface: str = 'wg0'):
        self.vpn_interface = vpn_interface
        self.vpn_subnet = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    
    def validate_access(self) -> Dict[str, str]:
        """Check if we have permission to modify iptables"""
        import subprocess
        try:
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
    
    def backup_rules(self) -> Dict[str, str]:
        """Create a backup of current iptables rules"""
        import subprocess
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
    
    def get_current_rules(self) -> Dict[str, str]:
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
    
    def apply_peer_rules(self, peer_id: Optional[int] = None, dry_run: bool = False) -> Dict[str, any]:
        """Apply iptables rules using subprocess"""
        # This would use the existing subprocess-based implementation
        # Import and call the existing functions from utils.py
        from app.utils import generate_iptables_rules, apply_iptables_rules
        
        if dry_run:
            rules = generate_iptables_rules(peer_id)
            return {"status": "success", "rules": rules, "message": "Dry run completed"}
        else:
            return apply_iptables_rules(peer_id, dry_run)


# Factory function to get the appropriate manager
def get_iptables_manager(vpn_interface: str = 'wg0'):
    """Get the appropriate iptables manager based on availability"""
    if IPTABLES_AVAILABLE:
        try:
            return IptablesManager(vpn_interface)
        except Exception as e:
            logging.warning(f"Failed to initialize IptablesManager: {e}, falling back to subprocess")
            return SubprocessIptablesManager(vpn_interface)
    else:
        return SubprocessIptablesManager(vpn_interface)