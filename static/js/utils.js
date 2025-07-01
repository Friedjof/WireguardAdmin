/* General Utility Functions */

// Clipboard functionality
function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text).then(function() {
        // Change button text temporarily
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i>';
        button.classList.add('btn-success');
        button.classList.remove('btn-outline-secondary', 'btn-outline-light');
        
        setTimeout(function() {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-secondary');
        }, 1000);
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        alert('Failed to copy to clipboard');
    });
}

// Preview iptables rules function (universal)
async function previewIptablesRules(peerId = null) {
    const modal = new bootstrap.Modal(document.getElementById('iptablesModal'));
    const content = document.getElementById('iptablesContent');
    
    // Show loading state
    content.innerHTML = `
        <div class="d-flex justify-content-center align-items-center" style="height: 400px;">
            <div class="text-muted">
                <i class="fas fa-spinner fa-spin fa-2x mb-3"></i>
                <p>Generating iptables rules...</p>
            </div>
        </div>
    `;
    
    modal.show();
    
    // Determine peer ID and context
    if (!peerId) {
        peerId = getPeerId();
    }
    
    if (peerId) {
        // Existing peer - fetch from backend
        try {
            const response = await fetch(`/api/v1/firewall/rules/generate?peer_id=${peerId}`);
            const data = await response.json();
            
            if (data.status === 'success') {
                displayIptablesRules(data.rules);
                window.currentIptablesRules = data.rules;
            } else {
                content.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error generating rules: ${data.message}
                    </div>
                `;
            }
        } catch (error) {
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error previewing rules: ${error.message}
                </div>
            `;
        }
    } else {
        // New peer - generate preview from form data
        generatePreviewFromForm(content);
    }
}

function generatePreviewFromForm(content) {
    const rules = document.querySelectorAll('#firewall-rules-container .card');
    
    if (rules.length === 0) {
        content.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                No firewall rules to preview. Add some rules first.
            </div>
        `;
        return;
    }
    
    // Generate preview from current form data
    const peerName = document.getElementById('name')?.value || 'NewPeer';
    const assignedIp = document.getElementById('assigned_ip')?.value || '10.0.0.X';
    
    let previewRules = [
        '# Allow established and related connections',
        'iptables -A FORWARD -i wg0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
        'iptables -A FORWARD -o wg0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
        '# Allow loopback',
        'iptables -A INPUT -i lo -j ACCEPT',
        'iptables -A OUTPUT -o lo -j ACCEPT',
        `# Rules for peer: ${peerName} (${assignedIp})`
    ];
    
    rules.forEach((rule, index) => {
        const name = rule.querySelector('input[name="firewall_rule_names[]"]').value || `Rule ${index + 1}`;
        const action = rule.querySelector('select[name="firewall_rule_actions[]"]').value;
        const type = rule.querySelector('select[name="firewall_rule_types[]"]').value;
        const destination = rule.querySelector('input[name="firewall_rule_destinations[]"]').value || 'any';
        const protocol = rule.querySelector('select[name="firewall_rule_protocols[]"]').value;
        const port = rule.querySelector('input[name="firewall_rule_ports[]"]').value || 'any';
        
        let iptableRule = `iptables -A FORWARD -s ${assignedIp}/32`;
        
        if (destination !== 'any') {
            iptableRule += ` -d ${destination}`;
        }
        
        if (protocol !== 'any') {
            iptableRule += ` -p ${protocol}`;
        }
        
        if (port !== 'any' && protocol !== 'icmp') {
            iptableRule += ` --dport ${port}`;
        }
        
        if (type === 'internet') {
            iptableRule += ' -o !wg0';
        } else {
            iptableRule += ' -i wg0';
        }
        
        iptableRule += ` -j ${action === 'ALLOW' ? 'ACCEPT' : 'DROP'}`;
        iptableRule += ` -m comment --comment "Rule:${name}"`;
        
        previewRules.push(iptableRule);
    });
    
    // Add default drop rules
    previewRules.push(`iptables -A FORWARD -s ${assignedIp}/32 -j DROP`);
    previewRules.push(`iptables -A FORWARD -d ${assignedIp}/32 -j DROP`);
    
    displayIptablesRules(previewRules);
    window.currentIptablesRules = previewRules;
}

// DOM Ready Functions
document.addEventListener('DOMContentLoaded', function() {
    // Initialize IP refresh functionality
    const ipInput = document.getElementById('assigned_ip');
    if (ipInput && (ipInput.value === 'Loading...' || !ipInput.value)) {
        refreshIP();
    }
    
    // Setup real-time validation
    const inputs = ['name', 'public_key', 'endpoint', 'persistent_keepalive'];
    inputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('blur', function() {
                validateField(this);
            });
        }
    });
    
    // Setup form submission validation
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // Validate all IP fields
            const ipInputs = document.querySelectorAll('.ip-network-input');
            let hasErrors = false;
            
            ipInputs.forEach(input => {
                if (input.value.trim() && !validateIpField(input)) {
                    hasErrors = true;
                }
            });
            
            if (hasErrors) {
                e.preventDefault();
                alert('Please fix the IP validation errors before submitting.');
                return;
            }
        });
    }
    
    // Highlight copyable elements on hover
    const copyButtons = document.querySelectorAll('button[onclick*="copyToClipboard"]');
    copyButtons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            const targetElement = this.closest('.d-flex') ? 
                this.closest('.d-flex').querySelector('code, span') : 
                this.closest('td') ? this.closest('td').querySelector('code') : null;
            if (targetElement) {
                targetElement.style.backgroundColor = 'rgba(13, 110, 253, 0.1)';
            }
        });
        button.addEventListener('mouseleave', function() {
            const targetElement = this.closest('.d-flex') ? 
                this.closest('.d-flex').querySelector('code, span') : 
                this.closest('td') ? this.closest('td').querySelector('code') : null;
            if (targetElement) {
                targetElement.style.backgroundColor = '';
            }
        });
    });
});