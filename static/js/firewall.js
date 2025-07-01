/* Firewall Rules Management JavaScript */

// Global variables
let firewallRuleCounter = 0;

const firewallTemplates = {
    unrestricted: {
        name: 'Unrestricted Access',
        rules: []
    },
    internet_only: {
        name: 'Internet Only',
        rules: [
            { name: 'Allow Internet', type: 'internet', action: 'ALLOW', destination: '0.0.0.0/0', protocol: 'any', port: 'any' },
            { name: 'Deny Peer Communication', type: 'peer_comm', action: 'DENY', destination: '10.0.0.0/24', protocol: 'any', port: 'any' }
        ]
    },
    restricted: {
        name: 'Restricted Access',
        rules: [
            { name: 'Allow DNS', type: 'port', action: 'ALLOW', destination: 'any', protocol: 'udp', port: '53' },
            { name: 'Allow HTTP/HTTPS', type: 'port', action: 'ALLOW', destination: 'any', protocol: 'tcp', port: '80,443' }
        ]
    },
    admin: {
        name: 'Administrator',
        rules: [
            { name: 'Allow All', type: 'custom', action: 'ALLOW', destination: '0.0.0.0/0', protocol: 'any', port: 'any' }
        ]
    },
    guest: {
        name: 'Guest Access',
        rules: [
            { name: 'Allow DNS', type: 'port', action: 'ALLOW', destination: 'any', protocol: 'udp', port: '53' },
            { name: 'Allow HTTP/HTTPS', type: 'port', action: 'ALLOW', destination: 'any', protocol: 'tcp', port: '80,443' },
            { name: 'Deny Peer Communication', type: 'peer_comm', action: 'DENY', destination: '10.0.0.0/24', protocol: 'any', port: 'any' },
            { name: 'Deny SSH', type: 'port', action: 'DENY', destination: 'any', protocol: 'tcp', port: '22' }
        ]
    }
};

function applyFirewallTemplate() {
    const templateSelect = document.getElementById('firewall_template');
    const templateKey = templateSelect.value;
    
    if (!templateKey) return;
    
    const template = firewallTemplates[templateKey];
    if (!template) return;
    
    // Clear existing rules
    document.getElementById('firewall-rules-container').innerHTML = '';
    firewallRuleCounter = 0;
    
    // Add template rules
    template.rules.forEach(rule => {
        addFirewallRule(rule);
    });
    
    updateRulesSummary();
}

function addFirewallRule(ruleData = null) {
    const container = document.getElementById('firewall-rules-container');
    const ruleId = `firewall-rule-${firewallRuleCounter++}`;
    
    const rule = ruleData || {
        name: '',
        type: 'custom',
        action: 'ALLOW',
        destination: '',
        protocol: 'any',
        port: 'any'
    };
    
    const ruleElement = document.createElement('div');
    ruleElement.className = 'card mb-2';
    ruleElement.id = ruleId;
    
    ruleElement.innerHTML = `
        <div class="card-body">
            <div class="row g-2">
                <div class="col-md-3">
                    <label class="form-label small">Rule Name</label>
                    <input type="text" class="form-control form-control-sm" 
                           name="firewall_rule_names[]" 
                           value="${rule.name}" 
                           placeholder="e.g., Allow DNS">
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Action</label>
                    <select class="form-select form-select-sm" name="firewall_rule_actions[]">
                        <option value="ALLOW" ${rule.action === 'ALLOW' ? 'selected' : ''}>🟢 Allow</option>
                        <option value="DENY" ${rule.action === 'DENY' ? 'selected' : ''}>🔴 Deny</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Type</label>
                    <select class="form-select form-select-sm" name="firewall_rule_types[]" onchange="updateRuleFields('${ruleId}')">
                        <option value="custom" ${rule.type === 'custom' ? 'selected' : ''}>Custom</option>
                        <option value="internet" ${rule.type === 'internet' ? 'selected' : ''}>Internet</option>
                        <option value="peer_comm" ${rule.type === 'peer_comm' ? 'selected' : ''}>Peer Comm</option>
                        <option value="port" ${rule.type === 'port' ? 'selected' : ''}>Port Filter</option>
                        <option value="subnet" ${rule.type === 'subnet' ? 'selected' : ''}>Subnet</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Destination</label>
                    <input type="text" class="form-control form-control-sm" 
                           name="firewall_rule_destinations[]" 
                           value="${rule.destination}" 
                           placeholder="IP/CIDR or 'any'">
                </div>
                <div class="col-md-1">
                    <label class="form-label small">Protocol</label>
                    <select class="form-select form-select-sm" name="firewall_rule_protocols[]">
                        <option value="any" ${rule.protocol === 'any' ? 'selected' : ''}>Any</option>
                        <option value="tcp" ${rule.protocol === 'tcp' ? 'selected' : ''}>TCP</option>
                        <option value="udp" ${rule.protocol === 'udp' ? 'selected' : ''}>UDP</option>
                        <option value="icmp" ${rule.protocol === 'icmp' ? 'selected' : ''}>ICMP</option>
                    </select>
                </div>
                <div class="col-md-1">
                    <label class="form-label small">Port</label>
                    <input type="text" class="form-control form-control-sm" 
                           name="firewall_rule_ports[]" 
                           value="${rule.port}" 
                           placeholder="any">
                </div>
                <div class="col-md-1">
                    <label class="form-label small">Action</label>
                    <button type="button" class="btn btn-outline-danger btn-sm w-100" 
                            onclick="removeFirewallRule('${ruleId}')" title="Remove Rule">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    container.appendChild(ruleElement);
    updateRulesSummary();
}

function removeFirewallRule(ruleId) {
    const rule = document.getElementById(ruleId);
    if (rule) {
        rule.remove();
        updateRulesSummary();
    }
}

function updateRuleFields(ruleId) {
    const ruleElement = document.getElementById(ruleId);
    const typeSelect = ruleElement.querySelector('select[name="firewall_rule_types[]"]');
    const destinationInput = ruleElement.querySelector('input[name="firewall_rule_destinations[]"]');
    
    const type = typeSelect.value;
    
    switch(type) {
        case 'internet':
            destinationInput.value = '0.0.0.0/0';
            destinationInput.placeholder = 'Internet (0.0.0.0/0)';
            break;
        case 'peer_comm':
            destinationInput.value = '10.0.0.0/24';
            destinationInput.placeholder = 'VPN Subnet';
            break;
        case 'subnet':
            destinationInput.value = '';
            destinationInput.placeholder = 'e.g., 192.168.1.0/24';
            break;
        default:
            destinationInput.placeholder = 'IP/CIDR or "any"';
    }
    
    updateRulesSummary();
}

function updateRulesSummary() {
    const rules = document.querySelectorAll('#firewall-rules-container .card');
    const summaryDiv = document.getElementById('rules-summary');
    
    if (rules.length === 0) {
        summaryDiv.innerHTML = '<p class="mb-0 text-muted">No firewall rules configured - peer will have unrestricted access</p>';
        return;
    }
    
    let allowRules = 0;
    let denyRules = 0;
    
    rules.forEach(rule => {
        const action = rule.querySelector('select[name="firewall_rule_actions[]"]').value;
        if (action === 'ALLOW') allowRules++;
        else denyRules++;
    });
    
    summaryDiv.innerHTML = `
        <div class="row">
            <div class="col-6">
                <span class="badge bg-success">${allowRules} Allow Rules</span>
            </div>
            <div class="col-6">
                <span class="badge bg-danger">${denyRules} Deny Rules</span>
            </div>
        </div>
        <small class="text-muted">Total: ${rules.length} firewall rules configured</small>
    `;
}