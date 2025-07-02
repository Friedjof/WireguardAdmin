# Advanced iptables Management with python-iptables

This document describes the new iptables management system implemented using the `python-iptables` library for direct manipulation of iptables rules.

## Overview

The new system provides:
- **Direct iptables manipulation** using `python-iptables` library instead of subprocess calls
- **Automatic fallback** to subprocess-based implementation if python-iptables is not available
- **Better error handling** and validation
- **More reliable rule management** with transaction-like operations
- **Custom WireGuard chain management** for better organization

## Architecture

### Components

1. **`app/iptables_manager.py`** - Main iptables management module
   - `IptablesManager` - Advanced implementation using python-iptables
   - `SubprocessIptablesManager` - Fallback implementation using subprocess
   - `get_iptables_manager()` - Factory function

2. **Updated `app/utils.py`** - Integration with existing codebase
   - All existing iptables functions now use the new manager
   - Backward compatibility maintained

### Key Features

#### 1. Python-iptables Integration
- Direct manipulation of iptables using C libraries
- No subprocess calls for rule manipulation
- Better performance and reliability

#### 2. Custom Chain Management
- Creates a dedicated `WIREGUARD_FORWARD` chain
- Better organization of WireGuard-related rules
- Easier cleanup and management

#### 3. Transaction Support
- Rules are applied atomically using table transactions
- Rollback capability on errors
- Consistent state management

#### 4. Intelligent Fallback
- Automatically detects if python-iptables is available
- Falls back to subprocess implementation if needed
- Transparent to the application layer

## Installation

### Dependencies

Add to `requirements.txt`:
```
python-iptables==1.0.1
```

### System Requirements

The python-iptables library requires:
- iptables installed on the system
- Root privileges or appropriate capabilities
- `libiptc.so` and `libxtables.so` libraries

### Docker Setup

For Docker environments, ensure the container has:
```dockerfile
# Install iptables
RUN apt-get update && apt-get install -y iptables

# Add capabilities for iptables manipulation
# --cap-add=NET_ADMIN when running the container
```

## Usage

### Basic Operations

```python
from app.iptables_manager import get_iptables_manager

# Get manager instance
manager = get_iptables_manager('wg0')

# Validate access
result = manager.validate_access()
print(result)

# Get current rules
rules = manager.get_current_rules()
print(rules)

# Apply peer rules (dry run)
result = manager.apply_peer_rules(peer_id=None, dry_run=True)
print(result)

# Apply actual rules
result = manager.apply_peer_rules(peer_id=1, dry_run=False)
print(result)

# Backup rules
backup = manager.backup_rules()
print(backup)
```

### Integration with Existing Code

All existing functions work the same way:

```python
from app.utils import (
    validate_iptables_access,
    get_current_iptables_rules,
    backup_iptables_rules,
    apply_iptables_rules
)

# These now use the new iptables manager internally
access = validate_iptables_access()
rules = get_current_iptables_rules()
backup = backup_iptables_rules()
result = apply_iptables_rules(peer_id=1, dry_run=True)
```

## Configuration

### Environment Variables

- `VPN_INTERFACE` - WireGuard interface name (default: `wg0`)
- `VPN_SUBNET` - VPN subnet CIDR (default: `10.0.0.0/24`)

### Logging

Enable logging to see detailed iptables operations:

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('app.iptables_manager')
logger.setLevel(logging.DEBUG)
```

## Rule Management

### Rule Types

The system supports these firewall rule types:

1. **Internet Access** (`internet`)
   - Controls access to external networks
   - Uses outbound interface filtering

2. **Peer Communication** (`peer_comm`)
   - Controls communication between VPN peers
   - Uses VPN subnet filtering

3. **Port Filtering** (`port`)
   - Controls access to specific ports/services
   - Supports TCP/UDP protocol filtering

4. **Subnet Access** (`subnet`)
   - Controls access to specific network subnets
   - Custom destination IP filtering

### Rule Application

Rules are applied in this order:

1. **Base Rules** - Allow established/related connections, loopback
2. **Peer-specific Rules** - Applied by priority for each peer
3. **Default Action** - Allow all (no custom rules) or Drop (with custom rules)

### Custom Chain Structure

```
INPUT chain:
├── Allow loopback traffic

FORWARD chain:
├── Allow established/related on wg0
├── Jump to WIREGUARD_FORWARD chain
└── ... other rules

WIREGUARD_FORWARD chain:
├── Peer 1 rules (by priority)
├── Peer 1 default action
├── Peer 2 rules (by priority)
├── Peer 2 default action
└── ...
```

## Testing

### Test Script

Run the included test script:

```bash
cd /path/to/vpn
python test_iptables.py
```

This tests:
- iptables manager initialization
- Access validation
- Rule generation (dry run)
- Backup functionality
- Integration with utils.py

### Manual Testing

1. **Check python-iptables availability:**
   ```python
   import iptc
   print("python-iptables is available")
   ```

2. **Test basic operations:**
   ```bash
   # From the web interface, try:
   # - Preview firewall rules
   # - Test apply rules (dry run)
   # - View current iptables rules
   ```

3. **Validate rule application:**
   ```bash
   # Check iptables directly
   sudo iptables -L FORWARD -n -v --line-numbers
   sudo iptables -L WIREGUARD_FORWARD -n -v --line-numbers 2>/dev/null || echo "Custom chain not created yet"
   ```

## Troubleshooting

### Common Issues

1. **"python-iptables not available"**
   - Install: `pip install python-iptables`
   - Check system dependencies: `libiptc.so`, `libxtables.so`

2. **"No iptables access"**
   - Run with root privileges: `sudo python app.py`
   - Add capabilities: `--cap-add=NET_ADMIN` for Docker

3. **"Failed to create WireGuard chain"**
   - Check iptables permissions
   - Verify no conflicting iptables rules

4. **Rules not applied**
   - Check logs for detailed error messages
   - Verify peer configuration in database
   - Test with dry run first

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('app.iptables_manager').setLevel(logging.DEBUG)
```

Check rule generation:

```python
from app.utils import generate_iptables_rules
rules = generate_iptables_rules()
for rule in rules:
    print(rule)
```

### Fallback Mode

If python-iptables fails, the system automatically falls back to subprocess-based implementation. Check logs for:

```
WARNING: Failed to initialize IptablesManager: ..., falling back to subprocess
```

## Security Considerations

1. **Root Privileges**: iptables manipulation requires root access
2. **Rule Validation**: All rules are validated before application
3. **Atomic Operations**: Rules are applied atomically to prevent inconsistent states
4. **Backup Creation**: Automatic backup creation before major changes
5. **Custom Chain Isolation**: WireGuard rules are isolated in custom chains

## Migration

### From Subprocess Implementation

The migration is transparent - no code changes needed. The system will:

1. Detect python-iptables availability
2. Use advanced implementation if available
3. Fall back to subprocess if needed
4. Maintain all existing API compatibility

### Rollback Plan

If issues occur:

1. **Remove python-iptables**: `pip uninstall python-iptables`
2. **System falls back** to subprocess implementation automatically
3. **No code changes** needed
4. **Restore from backup** if rules are corrupted

## Performance Benefits

- **Faster rule application** (no subprocess overhead)
- **Better error handling** (detailed C library errors)
- **Atomic operations** (transaction support)
- **Memory efficiency** (direct library calls)
- **Reduced system load** (no shell process spawning)

## Future Enhancements

- IPv6 support using `ip6tables`
- Advanced rule matching (connection tracking, etc.)
- Rule templates and bulk operations
- Integration with firewall management tools
- Automated rule optimization