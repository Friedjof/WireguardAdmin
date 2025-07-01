/* QR Code Management JavaScript */

// QR Code Functions
function showQRCode(peerId = null) {
    const modal = new bootstrap.Modal(document.getElementById('qrCodeModal'));
    const qrContainer = document.getElementById('qrCodeContainer');
    const downloadBtn = document.querySelector('button[onclick="downloadQRCode()"]');
    
    // Show loading state
    qrContainer.innerHTML = `
        <div class="d-flex justify-content-center align-items-center" style="height: 300px;">
            <div class="text-muted">
                <i class="fas fa-spinner fa-spin fa-2x mb-3"></i>
                <p>Generating QR Code...</p>
            </div>
        </div>
    `;
    
    modal.show();
    
    // Get peer ID from various sources
    if (!peerId) {
        peerId = getPeerId();
    }
    
    if (!peerId) {
        qrContainer.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Cannot generate QR code: Peer not found or not yet created.
            </div>
        `;
        return;
    }
    
    // Fetch QR code from backend
    fetch(`/peers/${peerId}/qrcode`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                qrContainer.innerHTML = `
                    <img src="${data.qr_code}" alt="QR Code" class="img-fluid" style="max-width: 300px;">
                `;
                if (downloadBtn) downloadBtn.disabled = false;
                
                // Store QR code data for download
                window.currentQRCode = data.qr_code;
                window.currentPeerName = data.peer_name;
            } else {
                qrContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error generating QR code: ${data.message}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            qrContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Failed to generate QR code. Please try again.
                </div>
            `;
        });
}

function downloadQRCode() {
    if (!window.currentQRCode || !window.currentPeerName) {
        alert('No QR code available to download. Please generate QR code first.');
        return;
    }
    
    try {
        // Create download link
        const link = document.createElement('a');
        link.href = window.currentQRCode;
        link.download = `${window.currentPeerName}_qrcode.png`;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Download error:', error);
        alert('Error downloading QR code. Please try again.');
    }
}

// Utility function to get peer ID from different contexts
function getPeerId() {
    // Try to get from URL path
    const path = window.location.pathname;
    const match = path.match(/\/peers\/(\d+)/);
    if (match) {
        return match[1];
    }
    
    // Try to get from data attribute
    const peerElement = document.querySelector('[data-peer-id]');
    if (peerElement) {
        return peerElement.dataset.peerId;
    }
    
    // Try to get from form action URL
    const form = document.querySelector('form');
    if (form && form.action) {
        const actionMatch = form.action.match(/\/peers\/(\d+)/);
        if (actionMatch) {
            return actionMatch[1];
        }
    }
    
    return null;
}