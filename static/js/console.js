/* Console/Terminal JavaScript Functions */

// Global variables
window.currentIptablesRules = null;
window.currentQRCode = null;
window.currentPeerName = null;

// iptables Console Functions
function displayIptablesRules(rules) {
    const content = document.getElementById('iptablesContent');
    
    let html = '<div class="terminal-prompt">root@wireguard-server:~# </div>';
    html += '<span class="terminal-path">./generate-iptables.sh</span><br><br>';
    
    rules.forEach((rule, index) => {
        if (rule.startsWith('#')) {
            html += `<div class="console-line comment" onclick="copyIptableLine(this, ${index})">${rule}</div>`;
        } else if (rule.trim() === '') {
            html += '<br>';
        } else {
            html += `<div class="console-line rule-command" onclick="copyIptableLine(this, ${index})">${rule}</div>`;
        }
    });
    
    html += '<br><div class="terminal-prompt">root@wireguard-server:~# </div>';
    html += '<span class="text-success">✓ iptables rules generated successfully</span>';
    
    content.innerHTML = html;
}

function copyIptableLine(element, index) {
    const rule = window.currentIptablesRules[index];
    if (rule && rule.trim() !== '' && !rule.startsWith('#')) {
        copyToClipboard(rule, element);
        
        // Visual feedback
        element.classList.add('copied');
        setTimeout(() => {
            element.classList.remove('copied');
        }, 500);
        
        // Show toast notification
        showToast(`Copied: ${rule.substring(0, 50)}${rule.length > 50 ? '...' : ''}`, 'success');
    }
}

function copyAllIptablesRules() {
    if (!window.currentIptablesRules || window.currentIptablesRules.length === 0) {
        showToast('No rules to copy', 'warning');
        return;
    }
    
    const scriptContent = generateIptablesScript(window.currentIptablesRules);
    
    navigator.clipboard.writeText(scriptContent).then(() => {
        showToast(`Copied all ${window.currentIptablesRules.length} iptables rules to clipboard`, 'success');
    }).catch(err => {
        console.error('Failed to copy rules:', err);
        showToast('Failed to copy rules to clipboard', 'error');
    });
}

function downloadIptablesRules() {
    if (!window.currentIptablesRules || window.currentIptablesRules.length === 0) {
        showToast('No rules to download', 'warning');
        return;
    }
    
    const scriptContent = generateIptablesScript(window.currentIptablesRules);
    const peerName = getPeerName();
    
    const blob = new Blob([scriptContent], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${peerName}_iptables_rules.sh`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    showToast(`Downloaded iptables script: ${peerName}_iptables_rules.sh`, 'success');
}

function generateIptablesScript(rules) {
    const peerName = getPeerName();
    const timestamp = new Date().toISOString();
    
    let script = `#!/bin/bash
# iptables rules for WireGuard peer: ${peerName}
# Generated on: ${timestamp}
# 
# Usage: sudo ./$(basename "$0")
# 
# This script applies iptables rules for the specific peer.
# Make sure to review the rules before applying them.

set -e  # Exit on error

echo "Applying iptables rules for peer: ${peerName}"
echo "Generated on: ${timestamp}"
echo ""

`;

    rules.forEach(rule => {
        if (rule.startsWith('#')) {
            script += `${rule}\n`;
        } else if (rule.trim() !== '') {
            script += `echo "Executing: ${rule}"\n`;
            script += `${rule}\n`;
        }
        script += '\n';
    });

    script += `
echo ""
echo "✓ All iptables rules applied successfully"
echo "Current FORWARD chain rules:"
iptables -L FORWARD -n --line-numbers
`;

    return script;
}

function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 3000);
}

// Utility function to get peer name from different contexts
function getPeerName() {
    // Try to get from form input (create/edit)
    const nameInput = document.getElementById('name');
    if (nameInput && nameInput.value) {
        return nameInput.value;
    }
    
    // Try to get from window variable (show page)
    if (window.currentPeerName) {
        return window.currentPeerName;
    }
    
    // Try to get from page title or heading
    const heading = document.querySelector('h1');
    if (heading) {
        const match = heading.textContent.match(/(?:for|:)\s*([^-\s]+)/);
        if (match) {
            return match[1].trim();
        }
    }
    
    return 'UnknownPeer';
}