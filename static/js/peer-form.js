/* Peer Form Management JavaScript */

// Global variables
let ipFieldCounter = 0;

// IP Management Functions
function addIpField(value = '', description = '') {
    const container = document.getElementById('allowed-ips-container');
    const fieldId = `ip-field-${ipFieldCounter++}`;
    
    const fieldGroup = document.createElement('div');
    fieldGroup.className = 'ip-input-group mb-2';
    fieldGroup.id = fieldId;
    
    fieldGroup.innerHTML = `
        <div class="row g-2">
            <div class="col-8">
                <input type="text" 
                       class="form-control ip-network-input" 
                       name="allowed_ip_networks[]" 
                       placeholder="e.g., 192.168.1.0/24, 172.16.0.0/16"
                       value="${value}"
                       onblur="validateIpField(this)">
                <div class="invalid-feedback"></div>
            </div>
            <div class="col-3">
                <input type="text" 
                       class="form-control" 
                       name="allowed_ip_descriptions[]" 
                       placeholder="Description (optional)"
                       value="${description}">
            </div>
            <div class="col-1">
                <button type="button" class="btn btn-outline-danger btn-sm w-100" onclick="removeIpField('${fieldId}')" title="Remove">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;
    
    container.appendChild(fieldGroup);
}

function removeIpField(fieldId) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.remove();
    }
}

function validateIpField(input) {
    const value = input.value.trim();
    const feedback = input.parentNode.querySelector('.invalid-feedback');
    
    // Clear previous validation
    input.classList.remove('is-valid', 'is-invalid');
    feedback.textContent = '';
    
    if (!value) {
        return; // Empty is allowed
    }
    
    // Basic CIDR validation
    const cidrPattern = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}$/;
    const ipPattern = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
    
    if (!cidrPattern.test(value) && !ipPattern.test(value)) {
        input.classList.add('is-invalid');
        feedback.textContent = 'Use CIDR notation (e.g., 192.168.1.0/24) or single IP';
        return false;
    }
    
    // Validate IP parts
    const parts = value.split('/')[0].split('.');
    for (let part of parts) {
        const num = parseInt(part);
        if (num < 0 || num > 255) {
            input.classList.add('is-invalid');
            feedback.textContent = 'Invalid IP address';
            return false;
        }
    }
    
    // Validate CIDR prefix if present
    if (value.includes('/')) {
        const prefix = parseInt(value.split('/')[1]);
        if (prefix < 0 || prefix > 32) {
            input.classList.add('is-invalid');
            feedback.textContent = 'CIDR prefix must be between 0 and 32';
            return false;
        }
    }
    
    // Check for VPN subnet overlap (basic check)
    const vpnSubnet = getVpnSubnet();
    if (value.startsWith('10.0.0.') && vpnSubnet.startsWith('10.0.0.')) {
        input.classList.add('is-invalid');
        feedback.textContent = 'IP cannot be in VPN subnet (' + vpnSubnet + ')';
        return false;
    }
    
    input.classList.add('is-valid');
    return true;
}

// Form Validation Functions
function validateForm() {
    const name = document.getElementById('name').value;
    const publicKey = document.getElementById('public_key').value;
    const endpoint = document.getElementById('endpoint')?.value;
    const keepalive = document.getElementById('persistent_keepalive')?.value;
    
    let errors = [];
    
    // Validate name
    if (!name.match(/^[a-zA-Z0-9_-]+$/)) {
        errors.push('Name can only contain letters, numbers, hyphens and underscores');
    }
    
    // Validate public key
    if (publicKey.length !== 44 || !publicKey.match(/^[A-Za-z0-9+/]{43}=$/)) {
        errors.push('Invalid WireGuard public key format');
    }
    
    // Validate endpoint (if provided)
    if (endpoint && !endpoint.match(/^[a-zA-Z0-9.-]+:\d+$/)) {
        errors.push('Endpoint should be in format hostname:port');
    }
    
    // Validate keepalive (if provided)
    if (keepalive && (isNaN(keepalive) || keepalive < 0 || keepalive > 65535)) {
        errors.push('Persistent keepalive should be a number between 0 and 65535');
    }
    
    // Validate all IP fields
    const ipInputs = document.querySelectorAll('.ip-network-input');
    ipInputs.forEach(input => {
        if (input.value.trim() && !validateIpField(input)) {
            errors.push('Fix IP validation errors');
        }
    });
    
    if (errors.length === 0) {
        alert('✅ All fields look valid!');
    } else {
        alert('❌ Validation errors:\n\n' + errors.join('\n'));
    }
}

function validateField(field) {
    const fieldName = field.id;
    const value = field.value.trim();
    let isValid = true;
    let message = '';
    
    switch(fieldName) {
        case 'name':
            isValid = value.match(/^[a-zA-Z0-9_-]+$/);
            message = isValid ? '' : 'Only letters, numbers, hyphens and underscores allowed';
            break;
        case 'public_key':
            isValid = value.length === 44 && value.match(/^[A-Za-z0-9+/]{43}=$/);
            message = isValid ? '' : 'Invalid WireGuard public key format';
            break;
        case 'endpoint':
            if (value) {
                isValid = value.match(/^[a-zA-Z0-9.-]+:\d+$/);
                message = isValid ? '' : 'Use format hostname:port';
            }
            break;
        case 'persistent_keepalive':
            if (value) {
                const num = parseInt(value);
                isValid = !isNaN(num) && num >= 0 && num <= 65535;
                message = isValid ? '' : 'Must be between 0 and 65535';
            }
            break;
    }
    
    // Update field styling
    field.classList.remove('is-valid', 'is-invalid');
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) feedback.remove();
    
    if (value && !isValid) {
        field.classList.add('is-invalid');
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'invalid-feedback';
        feedbackDiv.textContent = message;
        field.parentNode.appendChild(feedbackDiv);
    } else if (value) {
        field.classList.add('is-valid');
    }
}

// Utility Functions
function getVpnSubnet() {
    // Try to get from a hidden field or data attribute
    const subnetElement = document.querySelector('[data-vpn-subnet]');
    if (subnetElement) {
        return subnetElement.dataset.vpnSubnet;
    }
    return '10.0.0.0/24'; // Default fallback
}

function refreshIP() {
    const ipInput = document.getElementById('assigned_ip');
    const refreshBtn = ipInput?.nextElementSibling?.querySelector('i');
    
    if (!ipInput) return;
    
    // Show loading state
    ipInput.value = 'Loading...';
    if (refreshBtn) refreshBtn.classList.add('fa-spin');
    
    // Fetch next available IP
    fetch('/api/v1/next-ip')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                ipInput.value = data.ip;
            } else {
                ipInput.value = 'Error loading IP';
                console.error('Error:', data.message);
            }
        })
        .catch(error => {
            console.error('Fetch error:', error);
            ipInput.value = 'Error loading IP';
        })
        .finally(() => {
            if (refreshBtn) refreshBtn.classList.remove('fa-spin');
        });
}

// Key Generation (Mock for create page)
function generateKeyPair() {
    // This is a simplified mock - real implementation would generate actual WireGuard keys
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let privateKey = '';
    let publicKey = '';
    
    // Generate 44-character base64 strings (simplified mock)
    for (let i = 0; i < 43; i++) {
        privateKey += chars.charAt(Math.floor(Math.random() * chars.length));
        publicKey += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    privateKey += '=';
    publicKey += '=';
    
    document.getElementById('generatedPrivateKey').value = privateKey;
    document.getElementById('generatedPublicKey').value = publicKey;
    document.getElementById('generatedKeys').classList.remove('d-none');
    
    // Show alert
    const alert = document.createElement('div');
    alert.className = 'alert alert-warning alert-dismissible fade show mt-2';
    alert.innerHTML = `
        <i class="fas fa-exclamation-triangle me-1"></i>
        <strong>Mock Keys Generated!</strong> In production, use real WireGuard commands to generate secure keys.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.getElementById('generatedKeys').appendChild(alert);
}