/**
 * Configurable Status Refresh System
 * Triggers backend status updates via AJAX at configurable intervals
 * This ensures WebSocket data stays fresh and current
 * 
 * Configuration options (in priority order):
 * 1. Constructor parameter: new StatusRefresh(3000) // 3 seconds
 * 2. Data attribute: <body data-refresh-interval="2000"> // 2 seconds  
 * 3. URL parameter: ?refresh=10 // 10 seconds
 * 4. Default: 5 seconds
 */

class StatusRefresh {
    constructor(intervalMs = null) {
        // Get interval from data attribute, URL parameter, or default
        this.refreshInterval = this.getRefreshInterval(intervalMs);
        this.isActive = false;
        this.timer = null;
        
        console.log(`🔄 Status refresh system initialized (interval: ${this.refreshInterval}ms)`);
    }
    
    getRefreshInterval(overrideMs) {
        // Priority order: constructor parameter > data attribute > URL parameter > default
        if (overrideMs && overrideMs > 0) {
            return overrideMs;
        }
        
        // Check for data attribute on body element
        const bodyElement = document.body;
        if (bodyElement && bodyElement.dataset.refreshInterval) {
            const dataInterval = parseInt(bodyElement.dataset.refreshInterval);
            if (dataInterval > 0) {
                return dataInterval;
            }
        }
        
        // Check URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const urlInterval = urlParams.get('refresh');
        if (urlInterval) {
            const parsedInterval = parseInt(urlInterval) * 1000; // Convert seconds to ms
            if (parsedInterval > 0) {
                return parsedInterval;
            }
        }
        
        // Default: 5 seconds
        return 5000;
    }
    
    start() {
        if (this.isActive) {
            console.log('🔄 Status refresh already active');
            return;
        }
        
        this.isActive = true;
        console.log(`🔄 Starting status refresh every ${this.refreshInterval}ms`);
        
        // Immediate first refresh
        this.triggerRefresh();
        
        // Set up periodic refresh
        this.timer = setInterval(() => {
            this.triggerRefresh();
        }, this.refreshInterval);
    }
    
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this.isActive = false;
        console.log('🔄 Status refresh stopped');
    }
    
    setInterval(newIntervalMs) {
        if (newIntervalMs <= 0) {
            console.error('❌ Invalid interval:', newIntervalMs);
            return;
        }
        
        const wasActive = this.isActive;
        this.stop();
        this.refreshInterval = newIntervalMs;
        console.log(`🔄 Refresh interval changed to ${newIntervalMs}ms`);
        
        if (wasActive) {
            this.start();
        }
    }
    
    async triggerRefresh() {
        try {
            console.log('🔄 Triggering status refresh...');
            
            const response = await fetch('/api/v1/wireguard/refresh-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log(`✅ Status refresh success: ${data.connected_clients} WebSocket clients`);
            } else {
                console.error('❌ Status refresh failed:', response.status);
            }
        } catch (error) {
            console.error('❌ Status refresh error:', error);
        }
    }
}

// Global instance
window.statusRefresh = new StatusRefresh();

// Auto-start when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('📱 DOM ready, starting status refresh system');
    window.statusRefresh.start();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    window.statusRefresh.stop();
});