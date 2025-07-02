/**
 * Live WireGuard Connection Status
 * Updates peer connection status in real-time
 */

class LiveStatusManager {
    constructor() {
        this.updateInterval = 5000; // Update every 5 seconds
        this.intervalId = null;
        this.isRunning = false;
        this.lastUpdate = null;
    }

    start() {
        if (this.isRunning) return;
        
        console.log('Starting live status updates...');
        this.isRunning = true;
        
        // Initial update
        this.updateStatus();
        
        // Set up periodic updates
        this.intervalId = setInterval(() => {
            this.updateStatus();
        }, this.updateInterval);
    }

    stop() {
        if (!this.isRunning) return;
        
        console.log('Stopping live status updates...');
        this.isRunning = false;
        
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/v1/wireguard/status');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updatePeerElements(data.data);
                this.updateSummary(data.total_peers, data.connected_peers);
                this.lastUpdate = new Date();
            } else {
                console.error('API error:', data.message);
                this.showError('Failed to get status updates');
            }
            
        } catch (error) {
            console.error('Failed to update status:', error);
            this.showError('Connection error');
        }
    }

    updatePeerElements(peerData) {
        Object.values(peerData).forEach(peer => {
            this.updatePeerStatus(peer);
        });
    }

    updatePeerStatus(peer) {
        const peerId = peer.peer_id;
        
        // Update connection dot
        const dot = document.getElementById(`connection-dot-${peerId}`);
        if (dot) {
            // Remove all status classes
            dot.classList.remove('connected', 'disconnected', 'checking');
            
            // Add appropriate class based on connection status
            if (peer.is_active && peer.is_connected) {
                dot.classList.add('connected');
                dot.title = `Connected - Last handshake: ${peer.latest_handshake}`;
            } else if (peer.is_active) {
                dot.classList.add('disconnected');
                dot.title = `Disconnected - Last handshake: ${peer.latest_handshake}`;
            } else {
                dot.classList.add('disconnected');
                dot.title = 'Peer is inactive';
            }
        }

        // Update connection text - simplified for peer list
        const text = document.getElementById(`connection-text-${peerId}`);
        if (text) {
            if (peer.is_active && peer.is_connected) {
                text.innerHTML = '<span class="text-success fw-bold">Connected</span>';
            } else if (peer.is_active) {
                text.innerHTML = '<span class="text-danger">Disconnected</span>';
            } else {
                text.innerHTML = '<span class="text-muted">Inactive</span>';
            }
        }

        // Update detailed connection info for peer detail page if present
        const detailedText = document.getElementById(`connection-text-detailed-${peerId}`);
        if (detailedText) {
            if (peer.is_active && peer.is_connected) {
                detailedText.innerHTML = `
                    <div class="connection-status-detail">
                        <span class="text-success fw-bold">Connected</span>
                        ${peer.client_ip ? `<br><small class="text-info">From: ${peer.client_ip}</small>` : ''}
                        ${peer.connection_duration ? `<br><small class="text-muted">Duration: ${peer.connection_duration}</small>` : ''}
                        ${peer.latest_handshake ? `<br><small class="text-muted">Last: ${peer.latest_handshake}</small>` : ''}
                    </div>
                `;
            } else if (peer.is_active) {
                detailedText.innerHTML = `
                    <div class="connection-status-detail">
                        <span class="text-danger">Disconnected</span>
                        ${peer.latest_handshake ? `<br><small class="text-muted">Last: ${peer.latest_handshake}</small>` : ''}
                        ${peer.client_ip ? `<br><small class="text-muted">Last IP: ${peer.client_ip}</small>` : ''}
                    </div>
                `;
            } else {
                detailedText.innerHTML = '<span class="text-muted">Inactive</span>';
            }
        }

        // Update transfer data if elements exist
        this.updateTransferData(peerId, peer);
        
        // Update client info section
        this.updateClientInfo(peerId, peer);
    }

    updateTransferData(peerId, peer) {
        const transferElement = document.getElementById(`transfer-${peerId}`);
        if (transferElement) {
            // Format transfer data more compactly
            const rxFormatted = this.formatTransferValue(peer.transfer_rx_formatted);
            const txFormatted = this.formatTransferValue(peer.transfer_tx_formatted);
            
            // Create tooltip with detailed info
            const tooltip = `Received: ${peer.transfer_rx_formatted} | Sent: ${peer.transfer_tx_formatted}`;
            
            // Determine layout based on combined length
            const combinedLength = rxFormatted.length + txFormatted.length;
            let layoutClass = '';
            
            if (combinedLength > 16) {
                layoutClass = 'ultra-compact';
            } else if (combinedLength > 12) {
                layoutClass = 'compact';
            }
            
            transferElement.innerHTML = `
                <div class="transfer-info ${layoutClass} transfer-tooltip" data-tooltip="${tooltip}">
                    <div class="transfer-row transfer-rx">
                        <span class="transfer-icon">↓</span>
                        <span class="transfer-value">${rxFormatted}</span>
                    </div>
                    <div class="transfer-row transfer-tx">
                        <span class="transfer-icon">↑</span>
                        <span class="transfer-value">${txFormatted}</span>
                    </div>
                </div>
            `;
        }
    }

    formatTransferValue(value) {
        // Make transfer values more compact
        if (value === '0 B' || value === '0' || !value) {
            return '--';
        }
        
        // Replace common units with shorter versions and optimize formatting
        let formatted = value
            .replace(' B', 'B')
            .replace(' KB', 'K')
            .replace(' MB', 'M')
            .replace(' GB', 'G')
            .replace(' TB', 'T')
            .replace('.0B', 'B')
            .replace('.0K', 'K')
            .replace('.0M', 'M')
            .replace('.0G', 'G')
            .replace('.0T', 'T');
        
        // For very large numbers, round to whole numbers
        if (formatted.includes('.') && (formatted.includes('G') || formatted.includes('T'))) {
            const match = formatted.match(/^(\d+)\.(\d+)([GT])$/);
            if (match) {
                const [, whole, decimal, unit] = match;
                if (decimal === '0' || parseInt(decimal) < 2) {
                    formatted = whole + unit;
                } else {
                    formatted = whole + '.' + decimal.charAt(0) + unit;
                }
            }
        }
        
        return formatted;
    }

    updateClientInfo(peerId, peer) {
        const clientInfoElement = document.getElementById(`client-info-${peerId}`);
        if (clientInfoElement) {
            if (peer.is_active && peer.is_connected) {
                clientInfoElement.innerHTML = `
                    <div class="client-info-detail">
                        ${peer.client_ip ? `<div class="client-ip"><i class="fas fa-globe me-1"></i>${peer.client_ip}</div>` : ''}
                        ${peer.connection_duration ? `<small class="text-muted">Connected: ${peer.connection_duration}</small>` : ''}
                        ${peer.endpoint ? `<br><small class="text-muted">Endpoint: ${peer.endpoint}</small>` : ''}
                    </div>
                `;
            } else if (peer.is_active) {
                clientInfoElement.innerHTML = `
                    <div class="client-info-detail">
                        <span class="text-muted">Disconnected</span>
                        ${peer.client_ip ? `<br><small class="text-muted">Last IP: ${peer.client_ip}</small>` : ''}
                        ${peer.latest_handshake ? `<br><small class="text-muted">${peer.latest_handshake}</small>` : ''}
                    </div>
                `;
            } else {
                clientInfoElement.innerHTML = '<small class="text-muted fst-italic">Inactive</small>';
            }
        }
    }

    updateSummary(totalPeers, connectedPeers) {
        // Update header stats if element exists
        const summaryElement = document.getElementById('connection-summary');
        if (summaryElement) {
            summaryElement.innerHTML = `
                <span class="badge bg-primary me-2">${totalPeers} Total</span>
                <span class="badge bg-success">${connectedPeers} Connected</span>
            `;
        }

        // Update page title with connection count
        document.title = `Peers (${connectedPeers}/${totalPeers} connected) - WireGuard Manager`;
    }

    showError(message) {
        // Set all dots to checking state to indicate issues
        document.querySelectorAll('.connection-dot').forEach(dot => {
            dot.classList.remove('connected', 'disconnected');
            dot.classList.add('checking');
            dot.title = message;
        });

        // Update connection texts
        document.querySelectorAll('.connection-text').forEach(text => {
            text.innerHTML = `<span class="text-warning">${message}</span>`;
        });
    }

    // Public method to manually refresh
    refresh() {
        this.updateStatus();
    }

    // Public method to check if running
    isActive() {
        return this.isRunning;
    }

    // Public method to get last update time
    getLastUpdate() {
        return this.lastUpdate;
    }
}

// Global instance
let liveStatusManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only start if we're on the peers page and there are peers
    if (document.querySelector('[data-peer-id]')) {
        liveStatusManager = new LiveStatusManager();
        liveStatusManager.start();
        
        console.log('Live status manager initialized');
    }
});

// Stop updates when page is hidden/unloaded
document.addEventListener('visibilitychange', function() {
    if (liveStatusManager) {
        if (document.hidden) {
            console.log('Page hidden, stopping live updates');
            liveStatusManager.stop();
        } else {
            console.log('Page visible, starting live updates');
            liveStatusManager.start();
        }
    }
});

window.addEventListener('beforeunload', function() {
    if (liveStatusManager) {
        liveStatusManager.stop();
    }
});

// Expose refresh function globally for manual triggering
window.refreshConnectionStatus = function() {
    if (liveStatusManager) {
        liveStatusManager.refresh();
    }
};

// Add connection summary to header if not exists
function addConnectionSummary() {
    const header = document.querySelector('h1');
    if (header && !document.getElementById('connection-summary')) {
        const summaryDiv = document.createElement('div');
        summaryDiv.id = 'connection-summary';
        summaryDiv.className = 'mt-2';
        header.parentNode.appendChild(summaryDiv);
    }
}

// Call on load
document.addEventListener('DOMContentLoaded', addConnectionSummary);