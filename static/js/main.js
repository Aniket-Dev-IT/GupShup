/**
 * GupShup - Indian Social Media Platform
 * Main JavaScript functionality
 */

// Global utility functions
const GupShup = {
    // Initialize the application
    init: function() {
        this.setupCSRF();
        this.setupEventListeners();
        this.setupAnimations();
        console.log('GupShup initialized successfully! 🇮🇳');
    },

    // Setup CSRF token for AJAX requests
    setupCSRF: function() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        if (token) {
            window.csrfToken = token.value;
        }
    },

    // Setup global event listeners
    setupEventListeners: function() {
        // Handle form submissions with loading states
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', this.handleFormSubmission);
        });

        // Handle image modal functionality
        document.addEventListener('click', function(e) {
            if (e.target.dataset.toggle === 'modal') {
                GupShup.openModal(e.target.dataset.target);
            }
        });

        // Handle dropdown menus
        this.setupDropdowns();
    },

    // Handle form submission with loading states
    handleFormSubmission: function(e) {
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        
        if (submitBtn && !submitBtn.disabled) {
            const originalText = submitBtn.innerHTML || submitBtn.value;
            
            // Show loading state
            if (submitBtn.tagName === 'BUTTON') {
                submitBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm me-2"></i>Loading...';
            } else {
                submitBtn.value = 'Loading...';
            }
            
            submitBtn.disabled = true;
            
            // Restore original state after 5 seconds as fallback
            setTimeout(() => {
                if (submitBtn.tagName === 'BUTTON') {
                    submitBtn.innerHTML = originalText;
                } else {
                    submitBtn.value = originalText;
                }
                submitBtn.disabled = false;
            }, 5000);
        }
    },

    // Setup dropdown functionality
    setupDropdowns: function() {
        document.addEventListener('click', function(e) {
            // Close all dropdowns when clicking outside
            if (!e.target.closest('.dropdown')) {
                document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                    menu.classList.remove('show');
                });
            }
        });
    },

    // Setup scroll animations
    setupAnimations: function() {
        // Intersection Observer for scroll animations
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);

        // Observe elements with animation classes
        document.querySelectorAll('.fade-in, .slide-up').forEach(el => {
            observer.observe(el);
        });
    },

    // Show toast notification
    showToast: function(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${this.getAlertClass(type)} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; animation: slideInRight 0.3s ease;';
        
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="bi bi-${this.getIcon(type)} me-2"></i>
                ${message}
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    },

    // Get alert class for toast type
    getAlertClass: function(type) {
        const classes = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info'
        };
        return classes[type] || 'info';
    },

    // Get icon for toast type
    getIcon: function(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    },

    // Open image modal
    openImageModal: function(imageUrl) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content bg-transparent border-0">
                    <div class="modal-body p-0 text-center">
                        <button type="button" class="btn-close btn-close-white position-absolute top-0 end-0 m-3" onclick="this.closest('.modal').remove()"></button>
                        <img src="${imageUrl}" class="img-fluid rounded" alt="Image" style="max-height: 80vh; max-width: 100%;">
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Show modal with animation
        setTimeout(() => {
            modal.classList.add('show');
            modal.style.display = 'block';
            document.body.classList.add('modal-open');
        }, 10);
        
        // Handle backdrop click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.remove();
                document.body.classList.remove('modal-open');
            }
        });
    },

    // AJAX helper function
    ajax: function(url, options = {}) {
        const defaults = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.csrfToken || ''
            },
            credentials: 'same-origin'
        };
        
        const config = Object.assign(defaults, options);
        
        return fetch(url, config)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('AJAX Error:', error);
                this.showToast('Network error occurred', 'error');
                throw error;
            });
    },

    // Format numbers (e.g., 1000 -> 1K)
    formatNumber: function(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    },

    // Debounce function
    debounce: function(func, wait) {
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
};

// Social media specific functions
const Social = {
    // Toggle follow status
    toggleFollow: function(username, button) {
        if (!username || !button) return;
        
        const originalContent = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> Loading...';
        
        GupShup.ajax(`/social/follow/${username}/`, {
            method: 'POST'
        })
        .then(data => {
            if (data.success) {
                // Update button based on new state
                if (data.is_following) {
                    button.className = 'btn btn-outline-secondary';
                    button.innerHTML = '<i class="bi bi-person-check"></i> Following';
                } else if (data.is_pending) {
                    button.className = 'btn btn-warning';
                    button.innerHTML = '<i class="bi bi-clock"></i> Pending';
                } else {
                    button.className = 'btn btn-primary';
                    button.innerHTML = '<i class="bi bi-person-plus"></i> Follow';
                }
                
                GupShup.showToast(data.message, 'success');
            } else {
                button.innerHTML = originalContent;
                GupShup.showToast(data.message || 'An error occurred', 'error');
            }
        })
        .catch(() => {
            button.innerHTML = originalContent;
        })
        .finally(() => {
            button.disabled = false;
        });
    },

    // Like/unlike post
    toggleLike: function(postId, button) {
        if (!postId || !button) return;
        
        GupShup.ajax('/posts/api/like/', {
            method: 'POST',
            body: JSON.stringify({ post_id: postId })
        })
        .then(data => {
            if (data.success) {
                const icon = button.querySelector('i');
                const text = button.querySelector('.like-text');
                const countElement = document.getElementById(`like-count-${postId}`);
                
                if (data.liked) {
                    icon.className = 'bi bi-heart-fill';
                    text.textContent = 'Liked';
                    button.classList.add('active');
                } else {
                    icon.className = 'bi bi-heart';
                    text.textContent = 'Like';
                    button.classList.remove('active');
                }
                
                if (countElement) {
                    countElement.textContent = GupShup.formatNumber(data.like_count);
                }
            }
        })
        .catch(error => {
            console.error('Error toggling like:', error);
        });
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    GupShup.init();
});

// Make functions available globally
window.GupShup = GupShup;
window.Social = Social;
window.openImageModal = GupShup.openImageModal.bind(GupShup);
window.toggleFollow = Social.toggleFollow;
window.toggleLike = Social.toggleLike;

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .animate-in {
        animation: fadeInUp 0.6s ease forwards;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);