/**
 * GupShup Admin Panel API Manager
 * 
 * Comprehensive JavaScript module for handling all admin panel API interactions,
 * real-time updates, and AJAX operations with proper error handling and security.
 */

class AdminAPI {
    constructor() {
        this.baseURL = '/admin-panel/api/';
        this.csrfToken = this.getCSRFToken();
        this.defaultTimeout = 30000; // 30 seconds
        this.retryAttempts = 3;
        this.retryDelay = 1000; // 1 second
        
        // Real-time update settings
        this.liveUpdatesEnabled = false;
        this.liveUpdateInterval = 30000; // 30 seconds
        this.lastUpdateTimestamp = null;
        this.liveUpdateTimer = null;
        
        // Request queue for rate limiting
        this.requestQueue = [];
        this.maxConcurrentRequests = 5;
        this.activeRequests = 0;
        
        // Initialize error handling
        this.setupGlobalErrorHandling();
        
        // Initialize CSRF token refresh
        this.setupCSRFRefresh();
    }
    
    /**
     * Get CSRF token from cookie or meta tag
     */
    getCSRFToken() {
        let token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        
        if (!token) {
            // Try to get from cookie
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'csrftoken') {
                    token = value;
                    break;
                }
            }
        }
        
        return token;
    }
    
    /**
     * Setup global error handling for admin API
     */
    setupGlobalErrorHandling() {
        window.addEventListener('unhandledrejection', (event) => {
            if (event.reason && event.reason.isAdminAPIError) {
                this.handleAPIError(event.reason);
                event.preventDefault();
            }
        });
    }
    
    /**
     * Setup CSRF token refresh mechanism
     */
    setupCSRFRefresh() {
        setInterval(() => {
            this.csrfToken = this.getCSRFToken();
        }, 300000); // Refresh every 5 minutes
    }
    
    /**
     * Make authenticated AJAX request with retry logic
     */
    async makeRequest(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : this.baseURL + endpoint.replace(/^\//, '');
        
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.csrfToken
            },
            timeout: this.defaultTimeout,
            credentials: 'same-origin'
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        // Merge headers properly
        if (options.headers) {
            finalOptions.headers = { ...defaultOptions.headers, ...options.headers };
        }
        
        return this.requestWithRetry(url, finalOptions);
    }
    
    /**
     * Request with retry logic and queue management
     */
    async requestWithRetry(url, options, attempt = 1) {
        try {
            // Wait for available slot in request queue
            await this.waitForRequestSlot();
            
            this.activeRequests++;
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), options.timeout);
            
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            this.activeRequests--;
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Handle authentication errors
            if (!data.success && data.redirect && data.redirect.includes('login')) {
                this.handleAuthenticationError();
                throw new APIError('Authentication required', 'AUTH_REQUIRED', data);
            }
            
            return data;
            
        } catch (error) {
            this.activeRequests--;
            
            if (attempt < this.retryAttempts && !this.isNonRetryableError(error)) {
                console.warn(`Request failed (attempt ${attempt}/${this.retryAttempts}):`, error.message);
                await this.delay(this.retryDelay * attempt);
                return this.requestWithRetry(url, options, attempt + 1);
            }
            
            const apiError = new APIError(error.message, 'REQUEST_FAILED', error);
            apiError.isAdminAPIError = true;
            throw apiError;
        }
    }
    
    /**
     * Wait for available request slot
     */
    async waitForRequestSlot() {
        return new Promise((resolve) => {
            if (this.activeRequests < this.maxConcurrentRequests) {
                resolve();
            } else {
                const checkSlot = () => {
                    if (this.activeRequests < this.maxConcurrentRequests) {
                        resolve();
                    } else {
                        setTimeout(checkSlot, 100);
                    }
                };
                checkSlot();
            }
        });
    }
    
    /**
     * Check if error should not be retried
     */
    isNonRetryableError(error) {
        const nonRetryableErrors = [
            'AUTH_REQUIRED',
            'PERMISSION_DENIED',
            'VALIDATION_ERROR',
            'NOT_FOUND'
        ];
        
        return nonRetryableErrors.includes(error.code) || 
               error.message.includes('400') || 
               error.message.includes('401') || 
               error.message.includes('403') || 
               error.message.includes('404');
    }
    
    /**
     * Utility delay function
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // ================================
    // Dashboard and Statistics API
    // ================================
    
    /**
     * Get dashboard statistics
     */
    async getDashboardStats(days = 7, forceRefresh = false) {
        const params = new URLSearchParams({
            days: days.toString(),
            refresh: forceRefresh.toString()
        });
        
        return this.makeRequest(`dashboard/stats/?${params}`);
    }
    
    /**
     * Get analytics data
     */
    async getAnalytics(type = 'comprehensive', days = 30) {
        const params = new URLSearchParams({
            type,
            days: days.toString()
        });
        
        return this.makeRequest(`analytics/?${params}`);
    }
    
    // ================================
    // User Management API
    // ================================
    
    /**
     * Search users with filters
     */
    async searchUsers(filters = {}) {
        const params = new URLSearchParams();
        
        Object.keys(filters).forEach(key => {
            if (filters[key] !== '' && filters[key] !== null && filters[key] !== undefined) {
                params.append(key, filters[key]);
            }
        });
        
        return this.makeRequest(`users/search/?${params}`);
    }
    
    /**
     * Get user details
     */
    async getUserDetails(userId) {
        return this.makeRequest(`users/${userId}/`);
    }
    
    /**
     * Get user activity timeline
     */
    async getUserTimeline(userId, days = 30, page = 1) {
        const params = new URLSearchParams({
            days: days.toString(),
            page: page.toString()
        });
        
        return this.makeRequest(`users/${userId}/timeline/?${params}`);
    }
    
    // ================================
    // Content Moderation API
    // ================================
    
    /**
     * Get moderation queue
     */
    async getModerationQueue(filters = {}) {
        const params = new URLSearchParams();
        
        const defaultFilters = {
            status: 'pending',
            content_type: 'all',
            severity: 'all',
            page: 1,
            per_page: 20
        };
        
        const finalFilters = { ...defaultFilters, ...filters };
        
        Object.keys(finalFilters).forEach(key => {
            params.append(key, finalFilters[key]);
        });
        
        return this.makeRequest(`moderation/queue/?${params}`);
    }
    
    /**
     * Take moderation action
     */
    async takeModerationAction(moderationId, action, reason = '') {
        return this.makeRequest('moderation/queue/', {
            method: 'POST',
            body: JSON.stringify({
                moderation_id: moderationId,
                action,
                reason
            })
        });
    }
    
    // ================================
    // Bulk Operations API
    // ================================
    
    /**
     * Perform bulk actions
     */
    async performBulkAction(actionType, targetType, targetIds, params = {}) {
        return this.makeRequest('bulk-actions/', {
            method: 'POST',
            body: JSON.stringify({
                action_type: actionType,
                target_type: targetType,
                target_ids: targetIds,
                params
            })
        });
    }
    
    /**
     * Bulk ban users
     */
    async bulkBanUsers(userIds, banType = 'temporary', duration = 7, reason = '', publicReason = '') {
        return this.performBulkAction('ban', 'users', userIds, {
            ban_type: banType,
            duration,
            reason,
            public_reason: publicReason
        });
    }
    
    /**
     * Bulk warn users
     */
    async bulkWarnUsers(userIds, warningType = 'general', severity = 'medium', title = '', message = '') {
        return this.performBulkAction('warn', 'users', userIds, {
            warning_type: warningType,
            severity,
            title,
            message
        });
    }
    
    /**
     * Bulk moderate content
     */
    async bulkModerateContent(moderationIds, action, reason = '') {
        return this.performBulkAction(action, 'moderation', moderationIds, {
            reason
        });
    }
    
    // ================================
    // Export API
    // ================================
    
    /**
     * Export data
     */
    async exportData(type = 'analytics', format = 'json', days = 30) {
        const params = new URLSearchParams({
            type,
            format,
            days: days.toString()
        });
        
        const response = await this.makeRequest(`export/?${params}`);
        
        // Handle file download for CSV exports
        if (format === 'csv') {
            this.downloadFile(response, `${type}_export.csv`, 'text/csv');
        }
        
        return response;
    }
    
    /**
     * Download file from response
     */
    downloadFile(data, filename, mimeType) {
        const blob = new Blob([data], { type: mimeType });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    }
    
    // ================================
    // Real-time Updates API
    // ================================
    
    /**
     * Start live updates
     */
    startLiveUpdates(callback) {
        this.liveUpdatesEnabled = true;
        this.liveUpdateCallback = callback;
        
        // Get initial updates
        this.fetchLiveUpdates();
        
        // Set up periodic updates
        this.liveUpdateTimer = setInterval(() => {
            if (this.liveUpdatesEnabled) {
                this.fetchLiveUpdates();
            }
        }, this.liveUpdateInterval);
        
        console.log('Admin live updates started');
    }
    
    /**
     * Stop live updates
     */
    stopLiveUpdates() {
        this.liveUpdatesEnabled = false;
        
        if (this.liveUpdateTimer) {
            clearInterval(this.liveUpdateTimer);
            this.liveUpdateTimer = null;
        }
        
        console.log('Admin live updates stopped');
    }
    
    /**
     * Fetch live updates
     */
    async fetchLiveUpdates() {
        try {
            const params = new URLSearchParams();
            
            if (this.lastUpdateTimestamp) {
                params.append('last_update', this.lastUpdateTimestamp);
            }
            
            const response = await this.makeRequest(`live-updates/?${params}`);
            
            if (response.success) {
                this.lastUpdateTimestamp = response.data.timestamp;
                
                if (this.liveUpdateCallback) {
                    this.liveUpdateCallback(response.data);
                }
            }
            
        } catch (error) {
            console.error('Failed to fetch live updates:', error);
            
            // Reduce update frequency on errors
            this.liveUpdateInterval = Math.min(this.liveUpdateInterval * 1.5, 300000); // Max 5 minutes
        }
    }
    
    // ================================
    // Error Handling
    // ================================
    
    /**
     * Handle API errors
     */
    handleAPIError(error) {
        console.error('Admin API Error:', error);
        
        // Show user-friendly error messages
        const errorMessages = {
            'AUTH_REQUIRED': 'Your session has expired. Please login again.',
            'PERMISSION_DENIED': 'You do not have permission to perform this action.',
            'RATE_LIMIT_EXCEEDED': 'Too many requests. Please wait and try again.',
            'VALIDATION_ERROR': 'Invalid data provided.',
            'SERVER_ERROR': 'Server error occurred. Please try again later.',
            'NETWORK_ERROR': 'Network connection error. Please check your connection.'
        };
        
        const message = errorMessages[error.code] || error.message || 'An unexpected error occurred.';
        
        this.showNotification(message, 'error');
        
        // Handle specific error types
        if (error.code === 'AUTH_REQUIRED') {
            this.handleAuthenticationError();
        }
    }
    
    /**
     * Handle authentication errors
     */
    handleAuthenticationError() {
        this.stopLiveUpdates();
        
        // Show login modal or redirect
        this.showNotification('Session expired. Redirecting to login...', 'warning');
        
        setTimeout(() => {
            window.location.href = '/admin-panel/login/';
        }, 3000);
    }
    
    /**
     * Show notification to user
     */
    showNotification(message, type = 'info') {
        // Display notification using toastr library
        if (typeof toastr !== 'undefined') {
            toastr[type](message);
            return;
        }
        
        // Fallback to browser alert
        alert(`${type.toUpperCase()}: ${message}`);
    }
    
    // ================================
    // Utility Methods
    // ================================
    
    /**
     * Format date for display
     */
    formatDate(dateString, format = 'datetime') {
        const date = new Date(dateString);
        
        if (format === 'date') {
            return date.toLocaleDateString();
        } else if (format === 'time') {
            return date.toLocaleTimeString();
        } else if (format === 'relative') {
            return this.getRelativeTime(date);
        } else {
            return date.toLocaleString();
        }
    }
    
    /**
     * Get relative time string
     */
    getRelativeTime(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) {
            return `${days} day${days > 1 ? 's' : ''} ago`;
        } else if (hours > 0) {
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else if (minutes > 0) {
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        } else {
            return 'Just now';
        }
    }
    
    /**
     * Debounce function calls
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle function calls
     */
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

/**
 * Custom API Error class
 */
class APIError extends Error {
    constructor(message, code, data = null) {
        super(message);
        this.name = 'APIError';
        this.code = code;
        this.data = data;
        this.isAdminAPIError = true;
    }
}

/**
 * Admin Panel UI Helper
 */
class AdminUI {
    constructor(api) {
        this.api = api;
        this.loadingElements = new Set();
        this.modals = {};
    }
    
    /**
     * Show loading state on element
     */
    showLoading(elementSelector, text = 'Loading...') {
        const element = document.querySelector(elementSelector);
        if (!element) return;
        
        element.classList.add('loading');
        element.disabled = true;
        
        // Store original text
        if (!element.dataset.originalText) {
            element.dataset.originalText = element.textContent || element.innerHTML;
        }
        
        element.textContent = text;
        this.loadingElements.add(element);
    }
    
    /**
     * Hide loading state on element
     */
    hideLoading(elementSelector) {
        const element = document.querySelector(elementSelector);
        if (!element) return;
        
        element.classList.remove('loading');
        element.disabled = false;
        
        if (element.dataset.originalText) {
            element.textContent = element.dataset.originalText;
            delete element.dataset.originalText;
        }
        
        this.loadingElements.delete(element);
    }
    
    /**
     * Update dashboard statistics display
     */
    updateDashboardStats(stats) {
        // Update real-time stats
        if (stats.real_time) {
            Object.keys(stats.real_time).forEach(key => {
                const element = document.querySelector(`[data-stat="${key}"]`);
                if (element) {
                    element.textContent = this.formatNumber(stats.real_time[key]);
                }
            });
        }
        
        // Update charts if they exist
        this.updateCharts(stats);
    }
    
    /**
     * Update chart displays
     */
    updateCharts(data) {
        // Update user growth chart
        if (data.user_analytics && window.userGrowthChart) {
            window.userGrowthChart.update(data.user_analytics);
        }
        
        // Update engagement chart
        if (data.engagement_metrics && window.engagementChart) {
            window.engagementChart.update(data.engagement_metrics);
        }
        
        // Update geographic chart
        if (data.geographic_data && window.geographicChart) {
            window.geographicChart.update(data.geographic_data);
        }
    }
    
    /**
     * Format numbers for display
     */
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    /**
     * Show confirmation modal
     */
    showConfirmModal(title, message, onConfirm, onCancel = null) {
        const modalHtml = `
            <div class="modal fade" id="confirmModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" id="confirmAction">Confirm</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal
        const existingModal = document.getElementById('confirmModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        
        // Set up event handlers
        document.getElementById('confirmAction').addEventListener('click', () => {
            modal.hide();
            if (onConfirm) onConfirm();
        });
        
        if (onCancel) {
            document.getElementById('confirmModal').addEventListener('hidden.bs.modal', onCancel);
        }
        
        modal.show();
    }
}

// Initialize global admin API instance
window.adminAPI = new AdminAPI();
window.adminUI = new AdminUI(window.adminAPI);

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AdminAPI, AdminUI, APIError };
}

console.log('Admin Panel API module loaded successfully');