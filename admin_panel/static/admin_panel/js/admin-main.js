/**
 * GupShup Admin Panel Main JavaScript
 * Version: 1.0.0
 * Core functionality for admin interface interactions
 */

class AdminPanel {
    constructor() {
        this.sidebar = null;
        this.mobileOverlay = null;
        this.isSidebarCollapsed = false;
        this.isMobile = window.innerWidth < 768;
        this.theme = localStorage.getItem('admin-theme') || 'light';
        
        this.init();
    }
    
    /**
     * Initialize admin panel
     */
    init() {
        this.setupDOMElements();
        this.setupEventListeners();
        this.setupTheme();
        this.setupSidebar();
        this.setupModals();
        this.setupTooltips();
        this.setupFormEnhancements();
        this.setupTableEnhancements();
        this.checkMobileView();
        
        // Initialize components
        this.initializeDataTables();
        this.initializeCharts();
        this.initializeNotifications();
        
        console.log('GupShup Admin Panel initialized');
    }
    
    /**
     * Setup DOM element references
     */
    setupDOMElements() {
        this.sidebar = document.querySelector('.admin-sidebar');
        this.main = document.querySelector('.admin-main');
        this.sidebarToggle = document.querySelector('.admin-sidebar-toggle');
        this.themeToggle = document.querySelector('.admin-theme-toggle');
        this.userMenu = document.querySelector('.admin-user-menu');
        this.searchInput = document.querySelector('.admin-search-input');
        
        // Create mobile overlay if it doesn't exist
        if (!document.querySelector('.admin-mobile-overlay')) {
            this.mobileOverlay = document.createElement('div');
            this.mobileOverlay.className = 'admin-mobile-overlay';
            document.body.appendChild(this.mobileOverlay);
        } else {
            this.mobileOverlay = document.querySelector('.admin-mobile-overlay');
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Window resize handler
        window.addEventListener('resize', this.debounce(() => {
            this.checkMobileView();
            this.handleWindowResize();
        }, 250));
        
        // Sidebar toggle
        if (this.sidebarToggle) {
            this.sidebarToggle.addEventListener('click', () => {
                this.toggleSidebar();
            });
        }
        
        // Mobile overlay click
        if (this.mobileOverlay) {
            this.mobileOverlay.addEventListener('click', () => {
                this.closeSidebar();
            });
        }
        
        // Theme toggle
        if (this.themeToggle) {
            this.themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }
        
        // User menu toggle
        if (this.userMenu) {
            const userButton = this.userMenu.querySelector('.admin-user-button');
            if (userButton) {
                userButton.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleUserMenu();
                });
            }
        }
        
        // Close dropdowns when clicking outside
        document.addEventListener('click', () => {
            this.closeAllDropdowns();
        });
        
        // Search functionality
        if (this.searchInput) {
            this.searchInput.addEventListener('input', this.debounce((e) => {
                this.handleGlobalSearch(e.target.value);
            }, 300));
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
        
        // Form validation
        document.addEventListener('submit', (e) => {
            this.handleFormSubmission(e);
        });
        
        // AJAX error handling
        window.addEventListener('unhandledrejection', (e) => {
            this.handleUnhandledError(e);
        });
    }
    
    /**
     * Setup theme handling
     */
    setupTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        
        // Update theme toggle icon
        if (this.themeToggle) {
            this.updateThemeToggleIcon();
        }
    }
    
    /**
     * Setup sidebar functionality
     */
    setupSidebar() {
        // Restore sidebar state from localStorage
        const sidebarState = localStorage.getItem('admin-sidebar-collapsed');
        if (sidebarState === 'true' && !this.isMobile) {
            this.collapseSidebar();
        }
        
        // Setup navigation active states
        this.setupNavigationActiveStates();
        
        // Setup sidebar tooltips for collapsed state
        this.setupSidebarTooltips();
    }
    
    /**
     * Setup navigation active states
     */
    setupNavigationActiveStates() {
        const navLinks = document.querySelectorAll('.admin-nav-link');
        const currentPath = window.location.pathname;
        
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentPath || (href !== '/' && currentPath.startsWith(href))) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }
    
    /**
     * Setup sidebar tooltips for collapsed state
     */
    setupSidebarTooltips() {
        const navLinks = document.querySelectorAll('.admin-nav-link');
        
        navLinks.forEach(link => {
            const text = link.querySelector('.admin-nav-text');
            if (text) {
                link.setAttribute('data-tooltip', text.textContent.trim());
            }
        });
    }
    
    /**
     * Setup modals
     */
    setupModals() {
        // Modal close functionality
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('admin-modal-backdrop')) {
                this.closeModal(e.target.querySelector('.admin-modal'));
            }
            
            if (e.target.classList.contains('admin-modal-close')) {
                const modal = e.target.closest('.admin-modal');
                this.closeModal(modal);
            }
        });
        
        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const openModal = document.querySelector('.admin-modal-backdrop.show');
                if (openModal) {
                    this.closeModal(openModal.querySelector('.admin-modal'));
                }
            }
        });
    }
    
    /**
     * Setup tooltips
     */
    setupTooltips() {
        const tooltipElements = document.querySelectorAll('[data-tooltip]');
        
        tooltipElements.forEach(element => {
            let tooltip = null;
            let timeoutId = null;
            
            element.addEventListener('mouseenter', () => {
                clearTimeout(timeoutId);
                
                if (!tooltip) {
                    tooltip = this.createTooltip(element.dataset.tooltip);
                    document.body.appendChild(tooltip);
                }
                
                this.positionTooltip(tooltip, element);
                
                timeoutId = setTimeout(() => {
                    tooltip.classList.add('show');
                }, 100);
            });
            
            element.addEventListener('mouseleave', () => {
                clearTimeout(timeoutId);
                
                if (tooltip) {
                    tooltip.classList.remove('show');
                    setTimeout(() => {
                        if (tooltip && tooltip.parentNode) {
                            tooltip.parentNode.removeChild(tooltip);
                            tooltip = null;
                        }
                    }, 200);
                }
            });
        });
    }
    
    /**
     * Setup form enhancements
     */
    setupFormEnhancements() {
        // Real-time validation
        const inputs = document.querySelectorAll('.admin-form-input, .admin-form-select, .admin-form-textarea');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });
            
            input.addEventListener('input', () => {
                this.clearFieldError(input);
            });
        });
        
        // File input enhancements
        const fileInputs = document.querySelectorAll('input[type="file"]');
        fileInputs.forEach(input => {
            this.enhanceFileInput(input);
        });
        
        // Form auto-save functionality
        const autoSaveForms = document.querySelectorAll('[data-autosave]');
        autoSaveForms.forEach(form => {
            this.setupAutoSave(form);
        });
    }
    
    /**
     * Setup table enhancements
     */
    setupTableEnhancements() {
        // Row selection
        const selectAllCheckboxes = document.querySelectorAll('.select-all-checkbox');
        selectAllCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.handleSelectAll(e.target);
            });
        });
        
        const rowCheckboxes = document.querySelectorAll('.row-select-checkbox');
        rowCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.handleRowSelection(e.target);
            });
        });
        
        // Sortable columns
        const sortableHeaders = document.querySelectorAll('.sortable-header');
        sortableHeaders.forEach(header => {
            header.addEventListener('click', () => {
                this.handleColumnSort(header);
            });
        });
    }
    
    /**
     * Check if we're in mobile view
     */
    checkMobileView() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth < 768;
        
        if (wasMobile !== this.isMobile) {
            this.handleMobileViewChange();
        }
    }
    
    /**
     * Handle mobile view changes
     */
    handleMobileViewChange() {
        if (this.isMobile) {
            // Mobile mode
            this.sidebar?.classList.remove('collapsed');
            this.main?.classList.remove('sidebar-collapsed');
            this.closeSidebar();
        } else {
            // Desktop mode
            const wasCollapsed = localStorage.getItem('admin-sidebar-collapsed') === 'true';
            if (wasCollapsed) {
                this.collapseSidebar();
            } else {
                this.expandSidebar();
            }
            this.hideMobileOverlay();
        }
    }
    
    /**
     * Toggle sidebar
     */
    toggleSidebar() {
        if (this.isMobile) {
            this.toggleMobileSidebar();
        } else {
            this.toggleDesktopSidebar();
        }
    }
    
    /**
     * Toggle mobile sidebar
     */
    toggleMobileSidebar() {
        const isOpen = this.sidebar?.classList.contains('open');
        
        if (isOpen) {
            this.closeSidebar();
        } else {
            this.openSidebar();
        }
    }
    
    /**
     * Toggle desktop sidebar
     */
    toggleDesktopSidebar() {
        if (this.isSidebarCollapsed) {
            this.expandSidebar();
        } else {
            this.collapseSidebar();
        }
    }
    
    /**
     * Open sidebar
     */
    openSidebar() {
        this.sidebar?.classList.add('open');
        this.showMobileOverlay();
        document.body.style.overflow = 'hidden';
    }
    
    /**
     * Close sidebar
     */
    closeSidebar() {
        this.sidebar?.classList.remove('open');
        this.hideMobileOverlay();
        document.body.style.overflow = '';
    }
    
    /**
     * Collapse sidebar
     */
    collapseSidebar() {
        this.sidebar?.classList.add('collapsed');
        this.main?.classList.add('sidebar-collapsed');
        this.isSidebarCollapsed = true;
        localStorage.setItem('admin-sidebar-collapsed', 'true');
    }
    
    /**
     * Expand sidebar
     */
    expandSidebar() {
        this.sidebar?.classList.remove('collapsed');
        this.main?.classList.remove('sidebar-collapsed');
        this.isSidebarCollapsed = false;
        localStorage.setItem('admin-sidebar-collapsed', 'false');
    }
    
    /**
     * Show mobile overlay
     */
    showMobileOverlay() {
        if (this.mobileOverlay) {
            this.mobileOverlay.classList.add('show');
        }
    }
    
    /**
     * Hide mobile overlay
     */
    hideMobileOverlay() {
        if (this.mobileOverlay) {
            this.mobileOverlay.classList.remove('show');
        }
    }
    
    /**
     * Toggle theme
     */
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('admin-theme', this.theme);
        this.updateThemeToggleIcon();
        
        // Trigger theme change event
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: this.theme }
        }));
    }
    
    /**
     * Update theme toggle icon
     */
    updateThemeToggleIcon() {
        const sunIcon = this.themeToggle?.querySelector('.icon-sun');
        const moonIcon = this.themeToggle?.querySelector('.icon-moon');
        
        if (this.theme === 'dark') {
            sunIcon?.style.setProperty('display', 'inline-block');
            moonIcon?.style.setProperty('display', 'none');
        } else {
            sunIcon?.style.setProperty('display', 'none');
            moonIcon?.style.setProperty('display', 'inline-block');
        }
    }
    
    /**
     * Toggle user menu
     */
    toggleUserMenu() {
        this.userMenu?.classList.toggle('show');
    }
    
    /**
     * Close all dropdowns
     */
    closeAllDropdowns() {
        const dropdowns = document.querySelectorAll('.admin-user-menu.show');
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    }
    
    /**
     * Handle global search
     */
    handleGlobalSearch(query) {
        if (query.length < 2) return;
        
        // Implement global search functionality
        console.log('Global search:', query);
        
        // Show search results dropdown
        this.showSearchResults(query);
    }
    
    /**
     * Show search results
     */
    showSearchResults(query) {
        // Implementation for search results dropdown
        // This would typically make an AJAX request to search endpoint
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            this.searchInput?.focus();
        }
        
        // Ctrl/Cmd + B for sidebar toggle
        if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            this.toggleSidebar();
        }
        
        // Ctrl/Cmd + Shift + T for theme toggle
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
            e.preventDefault();
            this.toggleTheme();
        }
    }
    
    /**
     * Handle form submission
     */
    handleFormSubmission(e) {
        const form = e.target;
        
        if (form.classList.contains('admin-form')) {
            const isValid = this.validateForm(form);
            
            if (!isValid) {
                e.preventDefault();
                this.showNotification('Please fix the errors in the form', 'error');
                return;
            }
            
            // Show loading state
            const submitButton = form.querySelector('[type="submit"]');
            if (submitButton) {
                this.setButtonLoading(submitButton, true);
            }
        }
    }
    
    /**
     * Handle unhandled errors
     */
    handleUnhandledError(e) {
        console.error('Unhandled error:', e.reason);
        this.showNotification('An unexpected error occurred', 'error');
    }
    
    /**
     * Handle window resize
     */
    handleWindowResize() {
        // Reposition modals if needed
        const openModals = document.querySelectorAll('.admin-modal-backdrop.show');
        openModals.forEach(modal => {
            // Modal repositioning logic if needed
        });
        
        // Update chart sizes
        if (window.Chart) {
            Object.values(Chart.instances).forEach(chart => {
                chart.resize();
            });
        }
    }
    
    // ===========================
    // Component Initialization
    // ===========================
    
    /**
     * Initialize DataTables
     */
    initializeDataTables() {
        if (typeof DataTable === 'undefined') return;
        
        const tables = document.querySelectorAll('.admin-datatable');
        tables.forEach(table => {
            if (!table.dataset.initialized) {
                this.setupDataTable(table);
                table.dataset.initialized = 'true';
            }
        });
    }
    
    /**
     * Setup individual DataTable
     */
    setupDataTable(table) {
        const options = {
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            order: [[0, 'desc']],
            dom: '<"admin-table-header"<"admin-table-filters"f><"admin-table-actions"B>>rtip',
            language: {
                search: '',
                searchPlaceholder: 'Search...',
                lengthMenu: 'Show _MENU_ entries',
                info: 'Showing _START_ to _END_ of _TOTAL_ entries',
                infoEmpty: 'No entries found',
                infoFiltered: '(filtered from _MAX_ total entries)',
                paginate: {
                    first: '«',
                    previous: '‹',
                    next: '›',
                    last: '»'
                }
            }
        };
        
        // Add export buttons if specified
        if (table.dataset.export) {
            options.buttons = [
                'copy', 'csv', 'excel', 'pdf', 'print'
            ];
        }
        
        new DataTable(table, options);
    }
    
    /**
     * Initialize charts
     */
    initializeCharts() {
        if (typeof Chart === 'undefined') return;
        
        // Set default Chart.js theme
        this.setChartTheme();
        
        // Initialize specific charts
        this.initializeDashboardCharts();
        this.initializeAnalyticsCharts();
    }
    
    /**
     * Set Chart.js theme
     */
    setChartTheme() {
        const isDark = this.theme === 'dark';
        
        Chart.defaults.color = isDark ? '#e5e7eb' : '#374151';
        Chart.defaults.borderColor = isDark ? '#374151' : '#e5e7eb';
        Chart.defaults.backgroundColor = isDark ? '#1f2937' : '#ffffff';
        
        // Listen for theme changes
        window.addEventListener('themeChanged', (e) => {
            this.setChartTheme();
            this.updateAllCharts();
        });
    }
    
    /**
     * Initialize dashboard charts
     */
    initializeDashboardCharts() {
        // User growth chart
        const userGrowthCanvas = document.getElementById('userGrowthChart');
        if (userGrowthCanvas) {
            window.userGrowthChart = this.createUserGrowthChart(userGrowthCanvas);
        }
        
        // Engagement chart
        const engagementCanvas = document.getElementById('engagementChart');
        if (engagementCanvas) {
            window.engagementChart = this.createEngagementChart(engagementCanvas);
        }
        
        // Geographic chart
        const geographicCanvas = document.getElementById('geographicChart');
        if (geographicCanvas) {
            window.geographicChart = this.createGeographicChart(geographicCanvas);
        }
    }
    
    /**
     * Initialize analytics charts
     */
    initializeAnalyticsCharts() {
        // Content performance chart
        const contentCanvas = document.getElementById('contentPerformanceChart');
        if (contentCanvas) {
            this.createContentPerformanceChart(contentCanvas);
        }
        
        // Hashtag trends chart
        const hashtagCanvas = document.getElementById('hashtagTrendsChart');
        if (hashtagCanvas) {
            this.createHashtagTrendsChart(hashtagCanvas);
        }
    }
    
    /**
     * Create user growth chart
     */
    createUserGrowthChart(canvas) {
        return new Chart(canvas, {
            type: 'line',
            data: {
                labels: [], // Will be populated via API
                datasets: [{
                    label: 'New Users',
                    data: [],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: true,
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        });
    }
    
    /**
     * Initialize notifications
     */
    initializeNotifications() {
        // Check if toastr is available
        if (typeof toastr !== 'undefined') {
            toastr.options = {
                closeButton: true,
                debug: false,
                newestOnTop: true,
                progressBar: true,
                positionClass: 'toast-top-right',
                preventDuplicates: false,
                onclick: null,
                showDuration: 300,
                hideDuration: 1000,
                timeOut: 5000,
                extendedTimeOut: 1000,
                showEasing: 'swing',
                hideEasing: 'linear',
                showMethod: 'fadeIn',
                hideMethod: 'fadeOut'
            };
        }
        
        // Setup notification container if toastr is not available
        if (typeof toastr === 'undefined') {
            this.createNotificationContainer();
        }
    }
    
    // ===========================
    // Utility Methods
    // ===========================
    
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
     * Show notification
     */
    showNotification(message, type = 'info', title = '') {
        if (typeof toastr !== 'undefined') {
            toastr[type](message, title);
        } else {
            this.showCustomNotification(message, type, title);
        }
    }
    
    /**
     * Show custom notification
     */
    showCustomNotification(message, type, title) {
        const container = document.getElementById('admin-notification-container');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.className = `admin-notification admin-notification-${type}`;
        notification.innerHTML = `
            ${title ? `<div class="admin-notification-title">${title}</div>` : ''}
            <div class="admin-notification-message">${message}</div>
            <button class="admin-notification-close">&times;</button>
        `;
        
        container.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
        
        // Manual close
        notification.querySelector('.admin-notification-close').addEventListener('click', () => {
            notification.remove();
        });
    }
    
    /**
     * Create notification container
     */
    createNotificationContainer() {
        if (document.getElementById('admin-notification-container')) return;
        
        const container = document.createElement('div');
        container.id = 'admin-notification-container';
        container.className = 'admin-notification-container';
        document.body.appendChild(container);
    }
    
    /**
     * Validate form
     */
    validateForm(form) {
        let isValid = true;
        const fields = form.querySelectorAll('.admin-form-input, .admin-form-select, .admin-form-textarea');
        
        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    /**
     * Validate individual field
     */
    validateField(field) {
        const value = field.value.trim();
        let isValid = true;
        let errorMessage = '';
        
        // Required field validation
        if (field.required && !value) {
            isValid = false;
            errorMessage = 'This field is required';
        }
        
        // Email validation
        if (field.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid email address';
            }
        }
        
        // Phone validation (Indian format)
        if (field.type === 'tel' && value) {
            const phoneRegex = /^[6-9]\d{9}$/;
            if (!phoneRegex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid 10-digit phone number';
            }
        }
        
        // Custom validation patterns
        if (field.pattern && value) {
            const pattern = new RegExp(field.pattern);
            if (!pattern.test(value)) {
                isValid = false;
                errorMessage = field.dataset.validationMessage || 'Invalid format';
            }
        }
        
        // Show/hide error
        if (isValid) {
            this.clearFieldError(field);
        } else {
            this.showFieldError(field, errorMessage);
        }
        
        return isValid;
    }
    
    /**
     * Show field error
     */
    showFieldError(field, message) {
        field.classList.add('error');
        
        // Remove existing error message
        const existingError = field.parentNode.querySelector('.admin-form-error');
        if (existingError) {
            existingError.remove();
        }
        
        // Add new error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'admin-form-error';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }
    
    /**
     * Clear field error
     */
    clearFieldError(field) {
        field.classList.remove('error');
        const errorDiv = field.parentNode.querySelector('.admin-form-error');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
    
    /**
     * Set button loading state
     */
    setButtonLoading(button, loading) {
        if (loading) {
            button.classList.add('loading');
            button.disabled = true;
            
            // Store original text
            if (!button.dataset.originalText) {
                button.dataset.originalText = button.textContent;
            }
            button.textContent = 'Loading...';
        } else {
            button.classList.remove('loading');
            button.disabled = false;
            
            // Restore original text
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    }
    
    /**
     * Create tooltip
     */
    createTooltip(text) {
        const tooltip = document.createElement('div');
        tooltip.className = 'admin-tooltip';
        tooltip.textContent = text;
        return tooltip;
    }
    
    /**
     * Position tooltip
     */
    positionTooltip(tooltip, element) {
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        tooltip.style.left = `${rect.left + (rect.width / 2) - (tooltipRect.width / 2)}px`;
        tooltip.style.top = `${rect.top - tooltipRect.height - 8}px`;
    }
    
    /**
     * Update all charts
     */
    updateAllCharts() {
        if (typeof Chart === 'undefined') return;
        
        Object.values(Chart.instances).forEach(chart => {
            chart.update();
        });
    }
}

// Initialize admin panel when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.adminPanel = new AdminPanel();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminPanel;
}

console.log('Admin Panel Main JavaScript loaded');