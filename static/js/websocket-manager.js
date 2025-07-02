/**
 * WebSocket Manager for Real-time VPN Status Updates
 * Replaces the HTTP polling with WebSocket connections
 */

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.trafficGraphs = new Map(); // Store Chart.js instances
    }

    connect() {
        if (this.socket && this.isConnected) return;
        
        console.log('🔌 Connecting to WebSocket...');
        
        // Include Socket.IO client from CDN
        if (typeof io === 'undefined') {
            console.error('❌ Socket.IO not loaded! Make sure to include the Socket.IO client library.');
            return;
        }
        
        // Create socket with explicit options for Docker environment
        this.socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            rememberUpgrade: false
        });
        this.setupEventHandlers();
    }

    setupEventHandlers() {
        this.socket.on('connect', () => {
            console.log('✅ WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.showConnectionStatus('connected');
        });

        this.socket.on('disconnect', () => {
            console.log('❌ WebSocket disconnected');
            this.isConnected = false;
            this.showConnectionStatus('disconnected');
            this.scheduleReconnect();
        });

        this.socket.on('connection_status', (data) => {
            console.log('Connection status:', data);
        });

        this.socket.on('peer_status_update', (data) => {
            if (data.status === 'success') {
                this.updatePeerElements(data.data);
                this.updateSummary(data.total_peers, data.connected_peers);
                this.updateTrafficGraphs(data.data);
            }
        });

        this.socket.on('peer_action_result', (data) => {
            this.handlePeerActionResult(data);
        });

        this.socket.on('peer_action_response', (data) => {
            console.log('Peer action response:', data);
        });
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            this.showConnectionStatus('failed');
            return;
        }

        this.reconnectAttempts++;
        console.log(`🔄 Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectDelay);
        
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // Max 30s
    }

    updatePeerElements(peerData) {
        Object.values(peerData).forEach(peer => {
            this.updatePeerStatus(peer);
            this.updatePeerRates(peer);
        });
    }

    updatePeerStatus(peer) {
        const peerId = peer.peer_id;
        
        // Update connection dot
        const dot = document.getElementById(`connection-dot-${peerId}`);
        if (dot) {
            dot.classList.remove('connected', 'disconnected', 'checking');
            
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

        // Update connection text
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

        // Update detailed connection info
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

        // Update transfer data
        this.updateTransferData(peerId, peer);
        
        // Update client info
        this.updateClientInfo(peerId, peer);
    }

    updatePeerRates(peer) {
        const peerId = peer.peer_id;
        
        // Update real-time rates display
        const ratesElement = document.getElementById(`traffic-rates-${peerId}`);
        if (ratesElement) {
            const rxRate = peer.rx_rate_formatted || '0 B/s';
            const txRate = peer.tx_rate_formatted || '0 B/s';
            
            ratesElement.innerHTML = `
                <div class="traffic-rates">
                    <div class="rate-item">
                        <span class="rate-icon text-primary">↓</span>
                        <span class="rate-value">${rxRate}</span>
                    </div>
                    <div class="rate-item">
                        <span class="rate-icon text-warning">↑</span>
                        <span class="rate-value">${txRate}</span>
                    </div>
                </div>
            `;
        }
    }

    updateTransferData(peerId, peer) {
        const transferElement = document.getElementById(`transfer-${peerId}`);
        if (transferElement) {
            const rxFormatted = this.formatTransferValue(peer.transfer_rx_formatted);
            const txFormatted = this.formatTransferValue(peer.transfer_tx_formatted);
            
            const tooltip = `Received: ${peer.transfer_rx_formatted} | Sent: ${peer.transfer_tx_formatted}`;
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

    updateTrafficGraphs(peerData) {
        Object.values(peerData).forEach(peer => {
            const peerId = peer.peer_id;
            const canvasId = `traffic-graph-${peerId}`;
            const canvas = document.getElementById(canvasId);
            
            if (!canvas) return;
            
            // Initialize chart if not exists
            if (!this.trafficGraphs.has(peerId)) {
                this.initTrafficGraph(peerId, canvas);
            }
            
            // Update chart data
            const chart = this.trafficGraphs.get(peerId);
            if (chart && peer.graph_data) {
                this.updateChartData(chart, peer.graph_data);
            }
        });
    }

    initTrafficGraph(peerId, canvas) {
        const ctx = canvas.getContext('2d');
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Download',
                    data: [],
                    borderColor: 'rgba(54, 162, 235, 0.3)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    borderWidth: 1,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 0
                }, {
                    label: 'Upload',
                    data: [],
                    borderColor: 'rgba(255, 193, 7, 0.3)',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    borderWidth: 1,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                scales: {
                    x: {
                        display: false,
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: false,
                        grid: {
                            display: false
                        },
                        beginAtZero: true
                    }
                },
                elements: {
                    line: {
                        borderWidth: 1
                    }
                }
            }
        });
        
        this.trafficGraphs.set(peerId, chart);
    }

    updateChartData(chart, graphData) {
        if (!graphData || !graphData.timestamps) return;
        
        // Convert timestamps to time labels (just show seconds)
        const labels = graphData.timestamps.map((timestamp, index) => {
            return `${index * 2}s`; // 2-second intervals
        });
        
        chart.data.labels = labels;
        chart.data.datasets[0].data = graphData.rx_rates || [];
        chart.data.datasets[1].data = graphData.tx_rates || [];
        
        chart.update('none'); // No animation for real-time updates
    }

    formatTransferValue(value) {
        if (value === '0 B' || value === '0' || !value) {
            return '--';
        }
        
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
        const summaryElement = document.getElementById('connection-summary');
        if (summaryElement) {
            summaryElement.innerHTML = `
                <span class="badge bg-primary me-2">${totalPeers} Total</span>
                <span class="badge bg-success">${connectedPeers} Connected</span>
            `;
        }

        document.title = `Peers (${connectedPeers}/${totalPeers} connected) - WireGuard Manager`;
    }

    handlePeerActionResult(data) {
        const peerId = data.peer_id;
        
        if (data.status === 'success') {
            // Update the toggle switch if it exists
            const toggle = document.getElementById(`peer-toggle-${peerId}`);
            if (toggle) {
                toggle.checked = data.is_active;
                toggle.disabled = false;
                
                const label = document.querySelector(`label[for="peer-toggle-${peerId}"] span`);
                if (label) {
                    if (data.is_active) {
                        label.textContent = 'Active';
                        label.className = 'text-success fw-bold';
                    } else {
                        label.textContent = 'Inactive';
                        label.className = 'text-warning fw-bold';
                    }
                }
            }
            
            this.showToast(data.message, 'success');
        } else {
            // Revert toggle on error
            const toggle = document.getElementById(`peer-toggle-${peerId}`);
            if (toggle) {
                toggle.checked = !toggle.checked;
                toggle.disabled = false;
            }
            
            this.showToast(data.message, 'danger');
        }
    }

    showConnectionStatus(status) {
        // Update all connection dots to show WebSocket status
        document.querySelectorAll('.connection-dot').forEach(dot => {
            if (status === 'disconnected') {
                dot.classList.add('checking');
                dot.title = 'WebSocket disconnected - trying to reconnect...';
            } else if (status === 'failed') {
                dot.classList.add('checking');
                dot.title = 'WebSocket connection failed';
            }
            // Connected status will be updated by normal peer status updates
        });
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }

    // Public methods for peer actions
    activatePeer(peerId) {
        if (this.isConnected) {
            this.socket.emit('peer_action', {
                peer_id: peerId,
                action: 'activate'
            });
        }
    }

    deactivatePeer(peerId) {
        if (this.isConnected) {
            this.socket.emit('peer_action', {
                peer_id: peerId,
                action: 'deactivate'
            });
        }
    }

    requestStatusUpdate() {
        if (this.isConnected) {
            this.socket.emit('request_status_update');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
        
        // Cleanup charts
        this.trafficGraphs.forEach(chart => {
            chart.destroy();
        });
        this.trafficGraphs.clear();
    }
}

// Global WebSocket manager instance
let wsManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only start if we're on a page with peers
    if (document.querySelector('[data-peer-id]') || document.querySelector('.connection-dot')) {
        wsManager = new WebSocketManager();
        wsManager.connect();
        
        console.log('🚀 WebSocket manager initialized');
    }
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (wsManager) {
        if (document.hidden) {
            console.log('📴 Page hidden');
            // Keep connection alive but could reduce update frequency
        } else {
            console.log('📱 Page visible');
            wsManager.requestStatusUpdate(); // Get immediate update
        }
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (wsManager) {
        wsManager.disconnect();
    }
});

// Expose for global access
window.wsManager = wsManager;