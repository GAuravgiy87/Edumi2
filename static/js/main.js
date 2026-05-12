// Main JavaScript - Common functionality

// Confirm delete actions
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this?');
}

// Show/hide elements
function toggleElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    }
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Format time
function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;

    // Safe append - handle case where body might not be ready during Turbo transitions
    const target = document.body || document.documentElement;
    target.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS animations (using a unique name to avoid Turbo re-declaration issues)
(function initAnimations() {
    if (document.getElementById('edumi-animations')) return;
    
    const animationStyle = document.createElement('style');
    animationStyle.id = 'edumi-animations';
    animationStyle.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    
    // Safe append - handle case where head might not be ready
    var appended = false;
    if (document.head) {
        document.head.appendChild(animationStyle);
        appended = true;
    }
    if (!appended && document.documentElement) {
        document.documentElement.appendChild(animationStyle);
        appended = true;
    }
    if (!appended) {
        // Last resort - wait for DOMContentLoaded
        document.addEventListener('DOMContentLoaded', function() {
            if (document.head) document.head.appendChild(animationStyle);
            else document.documentElement.appendChild(animationStyle);
        });
    }
})();
