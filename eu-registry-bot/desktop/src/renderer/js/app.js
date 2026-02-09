/**
 * EU Registry Bot - Desktop Application JavaScript
 */

// API Base URL
let API_URL = 'http://localhost:5000';

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
    // Get API URL from Electron
    if (window.electronAPI) {
        API_URL = await window.electronAPI.getApiUrl();
    }

    // Setup navigation
    setupNavigation();

    // Check API status
    checkApiStatus();
    setInterval(checkApiStatus, 5000);

    // Load initial data
    loadDashboard();

    // Setup form handlers
    setupFormHandlers();

    // Poll for status updates
    setInterval(pollStatus, 2000);
});

// =============================================================================
// Navigation
// =============================================================================

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(pageName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === pageName);
    });

    // Update pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.toggle('active', page.id === `page-${pageName}`);
    });

    // Load page data
    switch (pageName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'applications':
            loadApplications();
            break;
        case 'results':
            loadResults();
            break;
        case 'scheduler':
            loadSchedulerStatus();
            break;
    }
}

// =============================================================================
// API Communication
// =============================================================================

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_URL}${endpoint}`, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function checkApiStatus() {
    const statusIndicator = document.getElementById('api-status');
    const dot = statusIndicator.querySelector('.status-dot');
    const text = statusIndicator.querySelector('.status-text');

    try {
        await apiCall('/api/health');
        dot.classList.add('connected');
        dot.classList.remove('error');
        text.textContent = 'Connected';
    } catch (error) {
        dot.classList.remove('connected');
        dot.classList.add('error');
        text.textContent = 'Disconnected';
    }
}

// =============================================================================
// Dashboard
// =============================================================================

async function loadDashboard() {
    try {
        // Load stats
        const [apps, results, status] = await Promise.all([
            apiCall('/api/applications'),
            apiCall('/api/results'),
            apiCall('/api/status'),
        ]);

        // Update stats
        document.getElementById('stat-pending').textContent = apps.applications?.length || 0;

        const submitted = results.results?.filter(r => r.status === 'submitted').length || 0;
        const failed = results.results?.filter(r => r.status === 'failed').length || 0;
        document.getElementById('stat-submitted').textContent = submitted;
        document.getElementById('stat-failed').textContent = failed;

        // Update status
        updateBotStatus(status);

        // Load logs
        loadLogs();
    } catch (error) {
        console.error('Failed to load dashboard:', error);
    }
}

function updateBotStatus(status) {
    const statusDisplay = document.getElementById('bot-status');
    const badge = statusDisplay.querySelector('.status-badge');
    const taskDiv = document.getElementById('current-task');

    badge.className = `status-badge ${status.status}`;
    badge.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);

    if (status.status === 'running' && status.current_task) {
        taskDiv.style.display = 'block';
        taskDiv.querySelector('.task-text').textContent = status.current_task;
        taskDiv.querySelector('.progress-fill').style.width = `${status.progress}%`;
    } else {
        taskDiv.style.display = 'none';
    }
}

async function loadLogs() {
    try {
        const data = await apiCall('/api/logs?limit=10');
        const container = document.getElementById('recent-logs');

        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<p class="empty-state">No recent activity</p>';
            return;
        }

        container.innerHTML = data.logs.map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString();
            return `
                <div class="log-entry ${log.level}">
                    <span class="log-time">${time}</span>
                    <span class="log-message">${log.message}</span>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

async function pollStatus() {
    try {
        const status = await apiCall('/api/status');
        updateBotStatus(status);

        if (status.status === 'running') {
            loadLogs();
        }
    } catch (error) {
        // Ignore polling errors
    }
}

// =============================================================================
// Applications
// =============================================================================

async function loadApplications() {
    try {
        const data = await apiCall('/api/applications');
        const tbody = document.querySelector('#applications-table tbody');

        if (!data.applications || data.applications.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No applications found. Create a sample to get started.</td></tr>';
            return;
        }

        tbody.innerHTML = data.applications.map(app => `
            <tr>
                <td>${app.file.split('/').pop()}</td>
                <td><span class="country-badge">${getCountryFlag(app.country)} ${app.country}</span></td>
                <td>${app.applicant}</td>
                <td>${app.description}</td>
                <td>
                    <button class="btn btn-secondary" onclick="submitApplication('${app.file}')">Submit</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Failed to load applications:', error);
        showToast('Failed to load applications', 'error');
    }
}

function getCountryFlag(country) {
    const flags = {
        portugal: '🇵🇹',
        france: '🇫🇷',
    };
    return flags[country] || '🏳️';
}

async function createSampleApplication() {
    try {
        await apiCall('/api/applications/sample', 'POST', { country: 'portugal' });
        await apiCall('/api/applications/sample', 'POST', { country: 'france' });
        showToast('Sample applications created', 'success');
        loadApplications();
    } catch (error) {
        showToast('Failed to create samples', 'error');
    }
}

function submitApplication(filePath) {
    document.getElementById('app-file').value = filePath;
    navigateTo('submit');
}

// =============================================================================
// Results
// =============================================================================

async function loadResults() {
    try {
        const data = await apiCall('/api/results');
        const tbody = document.querySelector('#results-table tbody');

        if (!data.results || data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No results yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.results.map(result => {
            const date = result.submitted_at ? new Date(result.submitted_at).toLocaleString() : '-';
            const statusClass = result.status === 'submitted' ? 'success' : (result.status === 'failed' ? 'error' : '');

            return `
                <tr>
                    <td>${date}</td>
                    <td><span class="country-badge">${getCountryFlag(result.country)} ${result.country}</span></td>
                    <td><span class="status-badge ${statusClass}">${result.status}</span></td>
                    <td>${result.reference || '-'}</td>
                    <td>
                        <button class="btn btn-secondary" onclick="viewResult('${result.filename}')">View</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load results:', error);
        showToast('Failed to load results', 'error');
    }
}

async function viewResult(filename) {
    try {
        const data = await apiCall(`/api/results/${filename}`);
        showModal('Submission Result', `
            <div class="cert-info ${data.status === 'submitted' ? 'valid' : 'invalid'}">
                <p><strong>Status:</strong> ${data.status}</p>
                <p><strong>Country:</strong> ${data.country}</p>
                <p><strong>Portal:</strong> ${data.portal}</p>
                ${data.reference_number ? `<p><strong>Reference:</strong> ${data.reference_number}</p>` : ''}
                ${data.error_message ? `<p><strong>Error:</strong> ${data.error_message}</p>` : ''}
                ${data.submitted_at ? `<p><strong>Submitted:</strong> ${new Date(data.submitted_at).toLocaleString()}</p>` : ''}
            </div>
            ${data.log_entries && data.log_entries.length > 0 ? `
                <h4 style="margin-top: 20px; margin-bottom: 10px;">Log Entries</h4>
                <div class="logs-container">
                    ${data.log_entries.map(log => `<div class="log-entry">${log}</div>`).join('')}
                </div>
            ` : ''}
        `);
    } catch (error) {
        showToast('Failed to load result details', 'error');
    }
}

// =============================================================================
// Submission Form
// =============================================================================

function setupFormHandlers() {
    document.getElementById('submit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleSubmission();
    });
}

async function selectCertificate() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Certificates', extensions: ['p12', 'pfx'] }]
        });
        if (path) {
            document.getElementById('cert-path').value = path;
        }
    }
}

async function selectApplication() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Applications', extensions: ['yaml', 'yml', 'json'] }]
        });
        if (path) {
            document.getElementById('app-file').value = path;
        }
    }
}

async function validateCertificate() {
    const path = document.getElementById('cert-path').value;
    const password = document.getElementById('cert-password').value;

    if (!path) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/certificate/info', 'POST', { path, password });
        const infoDiv = document.getElementById('cert-info');
        infoDiv.style.display = 'block';

        if (data.error) {
            infoDiv.className = 'cert-info invalid';
            infoDiv.innerHTML = `<p>❌ ${data.error}</p>`;
        } else {
            infoDiv.className = `cert-info ${data.is_valid ? 'valid' : 'invalid'}`;
            infoDiv.innerHTML = `
                <p><strong>Subject:</strong> ${data.subject}</p>
                <p><strong>Valid Until:</strong> ${new Date(data.valid_until).toLocaleDateString()}</p>
                <p><strong>Days Until Expiry:</strong> ${data.days_until_expiry}</p>
                <p><strong>Status:</strong> ${data.is_valid ? '✅ Valid' : '❌ Expired'}</p>
            `;
        }
    } catch (error) {
        showToast('Failed to validate certificate', 'error');
    }
}

async function validateApplication() {
    const path = document.getElementById('app-file').value;

    if (!path) {
        showToast('Please select an application file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/applications/validate', 'POST', { file: path });
        const resultDiv = document.getElementById('app-validation');
        resultDiv.style.display = 'block';

        if (data.valid) {
            resultDiv.className = 'validation-result valid';
            resultDiv.innerHTML = '<p>✅ Application is valid</p>';
        } else {
            resultDiv.className = 'validation-result invalid';
            resultDiv.innerHTML = `
                <p>❌ Validation Errors:</p>
                <ul>${data.errors.map(e => `<li>${e}</li>`).join('')}</ul>
            `;
        }
    } catch (error) {
        showToast('Failed to validate application', 'error');
    }
}

async function handleSubmission() {
    const certPath = document.getElementById('cert-path').value;
    const certPassword = document.getElementById('cert-password').value;
    const appFile = document.getElementById('app-file').value;
    const headless = document.getElementById('headless-mode').checked;

    if (!certPath || !appFile) {
        showToast('Please select both certificate and application file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/submit', 'POST', {
            application: appFile,
            certificate_path: certPath,
            certificate_password: certPassword,
            headless: headless,
        });

        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast('Submission started', 'success');
            navigateTo('dashboard');
        }
    } catch (error) {
        showToast('Failed to start submission', 'error');
    }
}

// =============================================================================
// Scheduler
// =============================================================================

async function loadSchedulerStatus() {
    try {
        const data = await apiCall('/api/scheduler/status');
        const statusDiv = document.getElementById('scheduler-status');
        const badge = statusDiv.querySelector('.status-badge');

        badge.className = `status-badge ${data.active ? 'active' : 'inactive'}`;
        badge.textContent = data.active ? 'Active' : 'Inactive';
    } catch (error) {
        console.error('Failed to load scheduler status:', error);
    }
}

async function selectSchedulerCert() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Certificates', extensions: ['p12', 'pfx'] }]
        });
        if (path) {
            document.getElementById('schedule-cert').value = path;
        }
    }
}

async function startScheduler() {
    const hour = parseInt(document.getElementById('schedule-hour').value);
    const minute = parseInt(document.getElementById('schedule-minute').value);
    const certPath = document.getElementById('schedule-cert').value;
    const certPassword = document.getElementById('schedule-password').value;

    if (!certPath) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/scheduler/start', 'POST', {
            hour,
            minute,
            certificate_path: certPath,
            certificate_password: certPassword,
        });

        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(`Scheduler started: ${data.schedule}`, 'success');
            loadSchedulerStatus();
        }
    } catch (error) {
        showToast('Failed to start scheduler', 'error');
    }
}

async function stopScheduler() {
    try {
        await apiCall('/api/scheduler/stop', 'POST');
        showToast('Scheduler stopped', 'success');
        loadSchedulerStatus();
    } catch (error) {
        showToast('Failed to stop scheduler', 'error');
    }
}

// =============================================================================
// Settings
// =============================================================================

async function selectDefaultCert() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Certificates', extensions: ['p12', 'pfx'] }]
        });
        if (path) {
            document.getElementById('default-cert').value = path;
        }
    }
}

// =============================================================================
// Toast Notifications
// =============================================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// =============================================================================
// Modal
// =============================================================================

function showModal(title, content) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = content;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// Close modal on overlay click
document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'modal-overlay') {
        closeModal();
    }
});
