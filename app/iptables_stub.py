"""
Stub implementation for iptables functionality when python-iptables is not available
"""

def get_iptables_manager():
    """Return None when iptables is not available"""
    return None

class IptablesManagerStub:
    """Stub implementation that returns safe defaults"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def validate_access(self):
        return {"status": "error", "message": "iptables not available"}
    
    def backup_rules(self):
        return {"status": "error", "message": "iptables not available"}
    
    def get_current_rules(self):
        return {"status": "error", "message": "iptables not available"}
    
    def clear_wireguard_rules(self):
        return {"status": "error", "message": "iptables not available"}
    
    def apply_peer_rules(self, *args, **kwargs):
        return {"status": "error", "message": "iptables not available"}