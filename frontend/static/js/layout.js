// Reusable Sidebar & Navbar injector
window.initLayout = function() {
    const appContainer = document.getElementById('app-container');
    if (!appContainer) {
        console.warn('app-container element not found. Cannot inject layout.');
        return;
    }
    
    // Determine active page based on pathname
    const path = window.location.pathname;
    let activePage = 'dashboard';
    if (path.endsWith('upload.html')) activePage = 'upload';
    else if (path.endsWith('send_email.html')) activePage = 'send_email';
    else if (path.endsWith('composer.html')) activePage = 'composer';
    else if (path.endsWith('templates.html')) activePage = 'templates';
    else if (path.endsWith('logs.html')) activePage = 'logs';
    else if (path.endsWith('settings.html')) activePage = 'settings';
    
    // Page Title
    let pageTitle = 'Dashboard';
    if (activePage === 'upload') pageTitle = 'Upload CSV Contacts';
    else if (activePage === 'send_email') pageTitle = 'Send Single Email';
    else if (activePage === 'composer') pageTitle = 'Email Composer';
    else if (activePage === 'templates') pageTitle = 'Template Library';
    else if (activePage === 'logs') pageTitle = 'Delivery Logs';
    else if (activePage === 'settings') pageTitle = 'SMTP Settings';
    
    // User Initials
    const username = window.currentUser ? window.currentUser.username : 'User';
    const firstLetter = username[0].toUpperCase();
    
    // Create new layout
    appContainer.innerHTML = `
        <!-- Sidebar Navigation -->
        <aside class="sidebar">
            <div class="sidebar-brand">
                <img src="static/images/logo.png" alt="Logo" style="height: 32px; width: 32px; object-fit: contain;">
                <h3>MAIL SARTHI</h3>
            </div>
            
            <ul class="sidebar-menu">
                <li class="sidebar-item ${activePage === 'dashboard' ? 'active' : ''}">
                    <a href="dashboard.html" class="sidebar-link">
                        <i class="fas fa-chart-pie"></i>
                        <span>Dashboard</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'upload' ? 'active' : ''}">
                    <a href="upload.html" class="sidebar-link">
                        <i class="fas fa-file-csv"></i>
                        <span>Upload CSV</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'send_email' ? 'active' : ''}">
                    <a href="send_email.html" class="sidebar-link">
                        <i class="fas fa-envelope"></i>
                        <span>Send Single Email</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'composer' ? 'active' : ''}">
                    <a href="composer.html" class="sidebar-link">
                        <i class="fas fa-pen-nib"></i>
                        <span>Email Composer</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'templates' ? 'active' : ''}">
                    <a href="templates.html" class="sidebar-link">
                        <i class="fas fa-folder-open"></i>
                        <span>Template Library</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'logs' ? 'active' : ''}">
                    <a href="logs.html" class="sidebar-link">
                        <i class="fas fa-history"></i>
                        <span>Delivery Logs</span>
                    </a>
                </li>
                <li class="sidebar-item ${activePage === 'settings' ? 'active' : ''}">
                    <a href="settings.html" class="sidebar-link">
                        <i class="fas fa-cog"></i>
                        <span>SMTP Settings</span>
                    </a>
                </li>
            </ul>
            
            <div class="sidebar-footer">
                <div class="d-flex align-items-center justify-content-between">
                    <div>
                        <div class="fw-semibold text-white text-truncate" style="max-width: 140px;" id="sidebarUsername">${username}</div>
                        <small class="text-muted">Campaign Admin</small>
                    </div>
                    <a href="#" class="text-danger" id="logoutBtn" title="Logout">
                        <i class="fas fa-sign-out-alt fa-lg"></i>
                    </a>
                </div>
            </div>
        </aside>

        <!-- Main Content Panel -->
        <div class="main-content">
            <header class="top-navbar">
                <div class="d-flex align-items-center gap-3">
                    <button class="mobile-toggle" id="sidebarToggleBtn">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h4 class="mb-0 fw-bold text-truncate" style="max-width: 250px;">
                        ${pageTitle}
                    </h4>
                </div>
                
                <div class="d-flex align-items-center gap-3">
                    <button class="theme-toggle-btn" id="themeToggleBtn" title="Toggle Theme">
                        <i class="fas fa-moon"></i>
                    </button>
                    <div class="dropdown">
                        <button class="btn btn-link text-decoration-none dropdown-toggle text-secondary d-flex align-items-center gap-2 p-0" type="button" id="userMenu" data-bs-toggle="dropdown" aria-expanded="false">
                            <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; font-size: 0.85rem;">
                                ${firstLetter}
                            </div>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end shadow border-0 mt-2" aria-labelledby="userMenu">
                            <li><h6 class="dropdown-header">Logged in as ${username}</h6></li>
                            <li><a class="dropdown-item" href="settings.html"><i class="fas fa-cog me-2"></i> Settings</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-danger" href="#" id="menuLogoutBtn"><i class="fas fa-sign-out-alt me-2"></i> Logout</a></li>
                        </ul>
                    </div>
                </div>
            </header>
            
            <main class="page-wrapper" id="main-content-wrapper">
                <!-- Content will be moved here -->
            </main>
        </div>
    `;
    
    // Reparent #page-content to main-content-wrapper to avoid duplicates and preserve DOM event bindings
    const pageContent = document.getElementById('page-content');
    if (pageContent) {
        const wrapper = document.getElementById('main-content-wrapper');
        if (wrapper) {
            wrapper.appendChild(pageContent);
            pageContent.style.display = 'block';
        }
    }
    
    // Bind Theme Toggle since the theme toggle button has been newly generated in DOM
    if (window.bindThemeToggle) {
        window.bindThemeToggle();
    }
    
    // Bind Mobile Sidebar Toggle
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const sidebar = document.querySelector('.sidebar');
    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('open');
        });
        
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && e.target !== sidebarToggleBtn) {
                sidebar.classList.remove('open');
            }
        });
    }
    
    // Bind Logout handlers
    const handleLogout = async (e) => {
        e.preventDefault();
        try {
            const resp = await apiFetch('/api/auth/logout', { method: 'POST' });
            if (resp.ok) {
                showToast('Success', 'Logged out successfully.', 'success');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 500);
            } else {
                const data = await resp.json();
                showToast('Error', data.message || 'Logout failed.', 'danger');
            }
        } catch (err) {
            console.error('Logout error:', err);
        }
    };
    
    const logoutBtn = document.getElementById('logoutBtn');
    const menuLogoutBtn = document.getElementById('menuLogoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
    if (menuLogoutBtn) menuLogoutBtn.addEventListener('click', handleLogout);
};
