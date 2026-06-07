const BACKEND_URL = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
    ? 'http://127.0.0.1:5000'
    : '';

// Global variables
window.csrfToken = '';
window.currentUser = null;

// 1. Theme Management (Light/Dark Mode) - Run immediately
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    // Theme toggle button listener (will be bound after layout injection or on login page)
    bindThemeToggle();

    // Auto-run authorization flow
    checkAuthAndInit();
});

function bindThemeToggle() {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        const themeIcon = themeToggleBtn.querySelector('i');
        const isDark = document.body.classList.contains('dark-theme');
        if (themeIcon) {
            themeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        }

        // Remove existing listeners by cloning
        const newBtn = themeToggleBtn.cloneNode(true);
        themeToggleBtn.parentNode.replaceChild(newBtn, themeToggleBtn);

        newBtn.addEventListener('click', () => {
            document.body.classList.toggle('dark-theme');
            const nowDark = document.body.classList.contains('dark-theme');
            localStorage.setItem('theme', nowDark ? 'dark' : 'light');
            const icon = newBtn.querySelector('i');
            if (icon) {
                icon.className = nowDark ? 'fas fa-sun' : 'fas fa-moon';
            }
        });
    }
}

// 2. Auth Flow Check
async function checkAuthAndInit() {
    const currentPath = window.location.pathname;
    const isGuestPage = currentPath.endsWith('login.html') || currentPath.endsWith('register.html');

    try {
        // Fetch CSRF Token first
        const csrfResp = await fetch(`${BACKEND_URL}/api/csrf-token`, { credentials: 'include' });
        if (csrfResp.ok) {
            const csrfData = await csrfResp.json();
            window.csrfToken = csrfData.csrf_token;
        }

        // Fetch Auth Status
        const authResp = await fetch(`${BACKEND_URL}/api/auth/status`, { credentials: 'include' });
        const authData = await authResp.json();

        if (authData.authenticated) {
            window.currentUser = {
                username: authData.username,
                email: authData.email
            };

            if (isGuestPage) {
                // Logged in user shouldn't be on guest pages
                window.location.href = 'dashboard.html';
                return;
            }

            // Inject layout if it exists and show content
            if (window.initLayout) {
                window.initLayout();
            }

            // Show page content
            const pageContent = document.getElementById('page-content');
            if (pageContent) {
                pageContent.style.display = 'block';
            }

            // Dispatch custom event that auth and layout are ready
            document.dispatchEvent(new CustomEvent('appReady'));
        } else {
            if (!isGuestPage && !currentPath.endsWith('index.html') && currentPath !== '/' && currentPath !== '') {
                // Not logged in user trying to access app pages
                window.location.href = 'login.html';
            } else if (isGuestPage) {
                // Guest is fine on guest pages
                const pageContent = document.getElementById('page-content');
                if (pageContent) {
                    pageContent.style.display = 'block';
                }
            } else {
                // If it is index.html, redirect to login
                window.location.href = 'login.html';
            }
        }
    } catch (err) {
        console.error('Error initialization:', err);
        showToast('Connection Error', 'Failed to connect to backend REST API.', 'danger');
    }
}

// 3. Global API Fetch Wrapper
async function apiFetch(endpoint, options = {}) {
    // Append credentials for session cookies
    options.credentials = 'include';

    // Setup Headers
    options.headers = options.headers || {};

    // Add CSRF Token header for state-changing operations
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        if (window.csrfToken) {
            options.headers['X-CSRFToken'] = window.csrfToken;
        }
        // If sending JSON data, set Content-Type header (but don't overwrite if it's FormData/Uploads)
        if (options.body && !(options.body instanceof FormData) && !options.headers['Content-Type']) {
            options.headers['Content-Type'] = 'application/json';
        }
    }

    const url = endpoint.startsWith('http') ? endpoint : `${BACKEND_URL}${endpoint}`;

    try {
        const response = await fetch(url, options);
        if (response.status === 401) {
            // Unauthorized session expiry redirect
            const isGuestPage = window.location.pathname.endsWith('login.html') || window.location.pathname.endsWith('register.html');
            if (!isGuestPage) {
                window.location.href = 'login.html';
            }
        }
        return response;
    } catch (err) {
        console.error(`API Fetch Error on ${endpoint}:`, err);
        showToast('API Connection Error', 'Failed to communicate with API server.', 'danger');
        throw err;
    }
}

// 4. Custom Toast Notification API
function showToast(title, message, type = 'info') {
    let container = document.querySelector('.toast-container-custom');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container-custom';
        document.body.appendChild(container);
    }

    // Determine icon and color
    let iconClass = 'fas fa-info-circle text-info';
    if (type === 'success') {
        iconClass = 'fas fa-check-circle text-success';
    } else if (type === 'danger' || type === 'error') {
        iconClass = 'fas fa-exclamation-circle text-danger';
    } else if (type === 'warning') {
        iconClass = 'fas fa-exclamation-triangle text-warning';
    }

    const toast = document.createElement('div');
    toast.className = 'toast-custom';
    toast.innerHTML = `
        <div class="toast-icon">
            <i class="${iconClass}"></i>
        </div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <p class="toast-message">${message}</p>
        </div>
        <button class="toast-close"><i class="fas fa-times"></i></button>
    `;

    container.appendChild(toast);

    // Add close action
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    });

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// 5. CSV File Parsing, Deduplication & Previews
function parseCSVFile(file, onProgress, onComplete, onError) {
    const reader = new FileReader();

    reader.onload = function (e) {
        const text = e.target.result;
        const lines = text.split(/\r\n|\n/);
        if (lines.length === 0 || lines[0].trim() === '') {
            onError("CSV file is empty.");
            return;
        }

        // Parse headers
        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        const emailIndex = headers.indexOf('email');
        const nameIndex = headers.indexOf('name');

        if (emailIndex === -1) {
            onError("Required 'email' column not found in headers. Header row must contain 'email'.");
            return;
        }

        const contacts = [];
        const duplicates = [];
        const invalid = [];
        const seenEmails = new Set();

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        // Process rows
        for (let i = 1; i < lines.length; i++) {
            const rowText = lines[i].trim();
            if (rowText === '') continue; // Skip empty lines

            // Simple split by comma
            const cols = rowText.split(',').map(c => c.trim());
            const email = cols[emailIndex];
            const name = nameIndex !== -1 && cols[nameIndex] ? cols[nameIndex] : '';

            if (!email) continue;

            // Validate email format
            const isValidEmail = emailRegex.test(email);

            if (!isValidEmail) {
                invalid.push({ email, name, rowNum: i + 1, error: 'Invalid format' });
            } else if (seenEmails.has(email)) {
                duplicates.push({ email, name, rowNum: i + 1 });
            } else {
                seenEmails.add(email);
                contacts.push({ email, name });
            }

            if (onProgress && i % 10 === 0) {
                onProgress(Math.round((i / lines.length) * 100));
            }
        }

        onComplete({
            contacts,
            duplicates,
            invalid,
            totalRows: lines.length - 1
        });
    };

    reader.onerror = function () {
        onError("Failed to read the file.");
    };

    reader.readAsText(file);
}

// 6. Campaign Automation controls helper
async function setCampaignStatus(campaignId, status) {
    try {
        const response = await apiFetch(`/api/campaigns/${campaignId}/status`, {
            method: 'POST',
            body: JSON.stringify({ status })
        });

        const data = await response.json();
        if (response.ok) {
            showToast('Success', `Campaign is now ${status}.`, 'success');
            return data;
        } else {
            showToast('Error', data.message || `Failed to update status to ${status}.`, 'error');
            return null;
        }
    } catch (e) {
        showToast('Error', `Server connection lost: ${e.message}`, 'error');
        return null;
    }
}
