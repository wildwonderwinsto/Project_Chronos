// Utility Functions for Dashboard

// Format date from ISO string
function formatDate(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Format relative time
function formatRelativeTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    
    if (seconds < 10) return 'Just now';
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// Highlight element when value changes
function highlightChange(elementId, cardId = null) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.add('updated');
        setTimeout(() => element.classList.remove('updated'), 500);
    }
    
    if (cardId) {
        const card = document.getElementById(cardId);
        if (card) {
            card.classList.add('pulse');
            setTimeout(() => card.classList.remove('pulse'), 500);
        }
    }
}

// Update element with change detection
function updateWithHighlight(elementId, newValue, cardId = null) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const oldValue = element.textContent;
    if (oldValue !== newValue && oldValue !== '-') {
        highlightChange(elementId, cardId);
    }
    element.textContent = newValue;
}

// Update timestamp
function updateTimestamp() {
    const el = document.getElementById('last-updated');
    if (el) {
        el.textContent = new Date().toLocaleTimeString();
    }
}

// Show connection status
function setConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
        statusEl.textContent = connected ? 'Connected' : 'Disconnected';
        statusEl.className = connected ? 'text-green-400' : 'text-red-400';
    }
}

// Image modal functions
function createImageModal() {
    const modal = document.createElement('div');
    modal.id = 'image-modal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="modal-close" onclick="closeImageModal()">&times;</span>
            <img id="modal-image" src="" alt="Full size image">
        </div>
    `;
    document.body.appendChild(modal);
    
    // Close on outside click
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeImageModal();
        }
    });
}

function openImageModal(imageSrc) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    if (modal && modalImg) {
        modalImg.src = imageSrc;
        modal.classList.add('active');
    }
}

function closeImageModal() {
    const modal = document.getElementById('image-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Initialize modal on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createImageModal);
} else {
    createImageModal();
}