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

        console.log(`API Call: ${method} ${API_URL}${endpoint}`);

        const response = await fetch(`${API_URL}${endpoint}`, options);

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`API HTTP Error: ${response.status} - ${errorText}`);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const result = await response.json();
        console.log('API Response:', result);
        return result;
    } catch (error) {
        console.error('API Error:', error);

        // Check if it's a network error (API not running)
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            throw new Error('Cannot connect to API server. Make sure the server is running.');
        }

        throw error;
    }
}

let apiConnected = false;

async function checkApiStatus() {
    const statusIndicator = document.getElementById('api-status');
    const dot = statusIndicator.querySelector('.status-dot');
    const text = statusIndicator.querySelector('.status-text');

    try {
        await apiCall('/api/health');
        dot.classList.add('connected');
        dot.classList.remove('error');
        text.textContent = 'Connected';

        // Only show toast on reconnection
        if (!apiConnected) {
            apiConnected = true;
            showToast('API server connected', 'success');
        }
    } catch (error) {
        dot.classList.remove('connected');
        dot.classList.add('error');
        text.textContent = 'Disconnected';

        // Show warning toast on disconnection
        if (apiConnected) {
            apiConnected = false;
            showToast('API server disconnected! Buttons will not work.', 'error');
        }
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
    } else {
        // Fallback: prompt for manual input
        const path = prompt('Enter certificate path (e.g., ./certificates/bionatur.p12):');
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
    console.log('validateCertificate called');

    const pathEl = document.getElementById('cert-path');
    const passwordEl = document.getElementById('cert-password');

    if (!pathEl) {
        console.error('cert-path element not found');
        showToast('Form element not found', 'error');
        return;
    }

    const path = pathEl.value;
    const password = passwordEl ? passwordEl.value : '';

    console.log('Certificate path:', path);

    if (!path) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    showToast('Validating certificate...', 'info');

    try {
        console.log('Calling API:', API_URL + '/api/certificate/info');
        const data = await apiCall('/api/certificate/info', 'POST', { path, password });
        console.log('API response:', data);

        const infoDiv = document.getElementById('cert-info');
        if (!infoDiv) {
            console.error('cert-info element not found');
            return;
        }
        infoDiv.style.display = 'block';

        if (data.error) {
            infoDiv.className = 'cert-info invalid';
            infoDiv.innerHTML = `<p>❌ ${data.error}</p>`;
            showToast(data.error, 'error');
        } else {
            infoDiv.className = `cert-info ${data.is_valid ? 'valid' : 'invalid'}`;
            infoDiv.innerHTML = `
                <p><strong>Subject:</strong> ${data.subject}</p>
                <p><strong>Valid Until:</strong> ${new Date(data.valid_until).toLocaleDateString()}</p>
                <p><strong>Days Until Expiry:</strong> ${data.days_until_expiry}</p>
                <p><strong>Status:</strong> ${data.is_valid ? '✅ Valid' : '❌ Expired'}</p>
            `;
            showToast('Certificate validated successfully', 'success');
        }
    } catch (error) {
        console.error('Certificate validation error:', error);
        showToast('Failed to validate certificate: ' + error.message, 'error');
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

// =============================================================================
// Batch Processing
// =============================================================================

let currentSubmitMode = 'single';

function setSubmitMode(mode) {
    currentSubmitMode = mode;

    // Update toggle buttons
    document.getElementById('mode-single').classList.toggle('active', mode === 'single');
    document.getElementById('mode-batch').classList.toggle('active', mode === 'batch');

    // Show/hide forms
    document.getElementById('single-form-container').style.display = mode === 'single' ? 'block' : 'none';
    document.getElementById('batch-form-container').style.display = mode === 'batch' ? 'block' : 'none';
}

async function selectBatchCertificate() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Certificates', extensions: ['p12', 'pfx'] }]
        });
        if (path) {
            document.getElementById('batch-cert-path').value = path;
        }
    } else {
        // Fallback: prompt for manual input
        const path = prompt('Enter certificate path (e.g., ./certificates/bionatur.p12):');
        if (path) {
            document.getElementById('batch-cert-path').value = path;
        }
    }
}

async function validateBatchCertificate() {
    console.log('validateBatchCertificate called');

    const pathEl = document.getElementById('batch-cert-path');
    const passwordEl = document.getElementById('batch-cert-password');

    if (!pathEl) {
        console.error('batch-cert-path element not found');
        showToast('Form element not found', 'error');
        return;
    }

    const path = pathEl.value;
    const password = passwordEl ? passwordEl.value : '';

    console.log('Certificate path:', path);

    if (!path) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    showToast('Validating certificate...', 'info');

    try {
        console.log('Calling API:', API_URL + '/api/certificate/info');
        const data = await apiCall('/api/certificate/info', 'POST', { path, password });
        console.log('API response:', data);

        const infoDiv = document.getElementById('batch-cert-info');
        if (!infoDiv) {
            console.error('batch-cert-info element not found');
            return;
        }
        infoDiv.style.display = 'block';

        if (data.error) {
            infoDiv.className = 'cert-info invalid';
            infoDiv.innerHTML = `<p>❌ ${data.error}</p>`;
            showToast(data.error, 'error');
        } else {
            infoDiv.className = `cert-info ${data.is_valid ? 'valid' : 'invalid'}`;
            infoDiv.innerHTML = `
                <p><strong>Subject:</strong> ${data.subject}</p>
                <p><strong>Valid Until:</strong> ${new Date(data.valid_until).toLocaleDateString()}</p>
                <p><strong>Status:</strong> ${data.is_valid ? '✅ Valid' : '❌ Expired'}</p>
            `;
            showToast('Certificate validated successfully', 'success');
        }
    } catch (error) {
        console.error('Certificate validation error:', error);
        showToast('Failed to validate certificate: ' + error.message, 'error');
    }
}

async function selectBatchFile() {
    if (window.electronAPI) {
        const path = await window.electronAPI.selectFile({
            filters: [{ name: 'Data Files', extensions: ['xlsx', 'xls', 'csv', 'docx'] }]
        });
        if (path) {
            document.getElementById('batch-file').value = path;
        }
    } else {
        // Fallback: prompt for manual input
        const path = prompt('Enter data file path (e.g., ./data/input/municipalities.xlsx):');
        if (path) {
            document.getElementById('batch-file').value = path;
        }
    }
}

async function previewBatchFile() {
    const path = document.getElementById('batch-file').value;

    if (!path) {
        showToast('Please select a data file first', 'warning');
        return;
    }

    try {
        // Check Excel support
        const supportData = await apiCall('/api/excel/support');
        if (!supportData.supported) {
            showToast('Excel support not available. Please install openpyxl.', 'error');
            return;
        }

        showToast('Loading file preview...', 'info');

        const data = await apiCall('/api/excel/preview', 'POST', { path });

        if (data.error) {
            showToast(data.error, 'error');
            return;
        }

        // Show preview section
        const previewDiv = document.getElementById('batch-preview');
        previewDiv.style.display = 'block';

        // Update info
        document.getElementById('batch-file-info').textContent =
            `File: ${path.split('/').pop() || path.split('\\').pop()} | Format: ${data.summary.format || 'Excel'}`;

        // Update stats
        document.getElementById('batch-total').textContent = data.total_records;
        document.getElementById('batch-pending').textContent = data.status_counts.pending;
        document.getElementById('batch-completed').textContent = data.status_counts.completed;

        // Update preview table
        const tbody = document.getElementById('batch-preview-body');
        if (data.preview_records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No records found</td></tr>';
        } else {
            tbody.innerHTML = data.preview_records.slice(0, 20).map((record, idx) => `
                <tr>
                    <td>${idx + 1}</td>
                    <td>${record.name}</td>
                    <td>${record.province || '-'}</td>
                    <td><span class="status-badge ${record.status}">${record.status}</span></td>
                </tr>
            `).join('');

            if (data.total_records > 20) {
                tbody.innerHTML += `
                    <tr>
                        <td colspan="4" class="empty-state">
                            ... and ${data.total_records - 20} more records
                        </td>
                    </tr>
                `;
            }
        }

        showToast(`Loaded ${data.total_records} records`, 'success');
    } catch (error) {
        console.error('Preview error:', error);
        showToast('Failed to preview file', 'error');
    }
}

// Setup batch form handler
document.addEventListener('DOMContentLoaded', () => {
    const batchForm = document.getElementById('batch-form');
    if (batchForm) {
        batchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleBatchSubmission();
        });
    }
});

async function handleBatchSubmission() {
    console.log('handleBatchSubmission called');

    const certPathEl = document.getElementById('batch-cert-path');
    const certPasswordEl = document.getElementById('batch-cert-password');
    const batchFileEl = document.getElementById('batch-file');
    const countryEl = document.getElementById('batch-country');
    const headlessEl = document.getElementById('batch-headless');
    const skipCompletedEl = document.getElementById('batch-skip-completed');

    // Check elements exist
    if (!certPathEl || !batchFileEl) {
        console.error('Form elements not found');
        showToast('Form elements not found', 'error');
        return;
    }

    const certPath = certPathEl.value;
    const certPassword = certPasswordEl ? certPasswordEl.value : '';
    const batchFile = batchFileEl.value;
    const country = countryEl ? countryEl.value : 'portugal';
    const headless = headlessEl ? headlessEl.checked : true;
    const skipCompleted = skipCompletedEl ? skipCompletedEl.checked : true;

    console.log('Batch params:', { certPath, batchFile, country, headless, skipCompleted });

    if (!certPath || !batchFile) {
        showToast('Please select both certificate and data file', 'warning');
        return;
    }

    showToast('Starting batch processing...', 'info');

    try {
        console.log('Calling API:', API_URL + '/api/excel/batch');
        const data = await apiCall('/api/excel/batch', 'POST', {
            excel_path: batchFile,
            certificate_path: certPath,
            certificate_password: certPassword,
            country: country,
            headless: headless,
            skip_completed: skipCompleted,
        });

        console.log('API response:', data);

        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast('Batch processing started!', 'success');
            navigateTo('dashboard');
        }
    } catch (error) {
        console.error('Batch submission error:', error);
        showToast('Failed to start batch processing: ' + error.message, 'error');
    }
}

// =============================================================================
// Diagnostic Functions (for troubleshooting)
// =============================================================================

async function runDiagnostics() {
    console.log('=== EU Registry Bot Diagnostics ===');
    console.log('API_URL:', API_URL);
    console.log('electronAPI available:', !!window.electronAPI);

    // Test API connection
    console.log('\n1. Testing API connection...');
    try {
        const health = await fetch(`${API_URL}/api/health`);
        const data = await health.json();
        console.log('   API Health:', data);
    } catch (e) {
        console.error('   API Error:', e.message);
        console.log('   -> API server may not be running!');
    }

    // Check form elements
    console.log('\n2. Checking form elements...');
    const elements = [
        'cert-path', 'cert-password', 'cert-info',
        'batch-cert-path', 'batch-cert-password', 'batch-cert-info',
        'batch-file', 'batch-country', 'batch-form'
    ];
    elements.forEach(id => {
        const el = document.getElementById(id);
        console.log(`   ${id}: ${el ? 'OK' : 'NOT FOUND'}`);
    });

    // Check functions
    console.log('\n3. Checking functions...');
    console.log('   validateCertificate:', typeof validateCertificate);
    console.log('   validateBatchCertificate:', typeof validateBatchCertificate);
    console.log('   handleBatchSubmission:', typeof handleBatchSubmission);

    console.log('\n=== End Diagnostics ===');
    showToast('Diagnostics complete - check browser console (F12)', 'info');
}

// Make diagnostic function available globally
window.runDiagnostics = runDiagnostics;
