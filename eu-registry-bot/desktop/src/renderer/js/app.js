/**
 * EU Registry Bot - Desktop Application JavaScript
 */

console.log('=== APP.JS LOADED ===');

// API Base URL
let API_URL = 'http://localhost:5000';

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('=== DOMContentLoaded ===');
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
    console.log('=== validateCertificate CALLED ===');
    alert('validateCertificate clicked!');

    const path = document.getElementById('cert-path').value;
    const password = document.getElementById('cert-password').value;

    console.log('cert-path:', path);
    console.log('cert-password:', password ? '[hidden]' : '[empty]');

    if (!path) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    try {
        console.log('Calling API...');
        const data = await apiCall('/api/certificate/info', 'POST', { path, password });
        console.log('API response:', data);
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
    }
}

async function validateBatchCertificate() {
    const path = document.getElementById('batch-cert-path').value;
    const password = document.getElementById('batch-cert-password').value;

    if (!path) {
        showToast('Please select a certificate file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/certificate/info', 'POST', { path, password });
        const infoDiv = document.getElementById('batch-cert-info');
        infoDiv.style.display = 'block';

        if (data.error) {
            infoDiv.className = 'cert-info invalid';
            infoDiv.innerHTML = `<p>❌ ${data.error}</p>`;
        } else {
            infoDiv.className = `cert-info ${data.is_valid ? 'valid' : 'invalid'}`;
            infoDiv.innerHTML = `
                <p><strong>Subject:</strong> ${data.subject}</p>
                <p><strong>Valid Until:</strong> ${new Date(data.valid_until).toLocaleDateString()}</p>
                <p><strong>Status:</strong> ${data.is_valid ? '✅ Valid' : '❌ Expired'}</p>
            `;
        }
    } catch (error) {
        showToast('Failed to validate certificate', 'error');
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
    const certPath = document.getElementById('batch-cert-path').value;
    const certPassword = document.getElementById('batch-cert-password').value;
    const batchFile = document.getElementById('batch-file').value;
    const country = document.getElementById('batch-country').value;
    const headless = document.getElementById('batch-headless').checked;
    const skipCompleted = document.getElementById('batch-skip-completed').checked;

    if (!certPath || !batchFile) {
        showToast('Please select both certificate and data file', 'warning');
        return;
    }

    try {
        const data = await apiCall('/api/excel/batch', 'POST', {
            excel_path: batchFile,
            certificate_path: certPath,
            certificate_password: certPassword,
            country: country,
            headless: headless,
            skip_completed: skipCompleted,
        });

        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast('Batch processing started!', 'success');
            navigateTo('dashboard');
        }
    } catch (error) {
        showToast('Failed to start batch processing', 'error');
    }
}

// =============================================================================
// Batch Results
// =============================================================================

let currentResultsMode = 'single';
let currentBatchFile = null;
let currentBatchPage = 1;

function setResultsMode(mode) {
    currentResultsMode = mode;

    // Update toggle buttons
    document.getElementById('results-mode-single').classList.toggle('active', mode === 'single');
    document.getElementById('results-mode-batch').classList.toggle('active', mode === 'batch');

    // Show/hide containers
    document.getElementById('single-results-container').style.display = mode === 'single' ? 'block' : 'none';
    document.getElementById('batch-results-container').style.display = mode === 'batch' ? 'block' : 'none';

    // Load data
    if (mode === 'batch') {
        loadBatchResults();
    }
}

async function loadBatchResults() {
    try {
        const data = await apiCall('/api/batch-results');
        const tbody = document.querySelector('#batch-results-table tbody');

        if (!data.batch_results || data.batch_results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No batch results found. Run a batch process first.</td></tr>';
            return;
        }

        tbody.innerHTML = data.batch_results.map(result => {
            const date = result.timestamp ? new Date(result.timestamp).toLocaleString() : '-';
            const successRate = result.total_records > 0
                ? ((result.successful / result.total_records) * 100).toFixed(1)
                : 0;

            return `
                <tr>
                    <td>${date}</td>
                    <td><span class="country-badge">${getCountryFlag(result.country)} ${result.country}</span></td>
                    <td>${result.total_records.toLocaleString()}</td>
                    <td><span class="status-badge success">${result.successful.toLocaleString()} (${successRate}%)</span></td>
                    <td><span class="status-badge ${result.failed > 0 ? 'error' : ''}">${result.failed.toLocaleString()}</span></td>
                    <td>${result.records_per_second} rec/s</td>
                    <td>
                        <button class="btn btn-primary" onclick="viewBatchDetail('${result.filename}')">View All</button>
                        <button class="btn btn-secondary" onclick="downloadBatchCSV('${result.filename}')">CSV</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load batch results:', error);
        showToast('Failed to load batch results', 'error');
    }
}

async function viewBatchDetail(filename) {
    currentBatchFile = filename;
    currentBatchPage = 1;

    try {
        showToast('Loading batch details...', 'info');

        const data = await apiCall(`/api/batch-results/${filename}`);

        // Hide list, show detail
        document.getElementById('batch-results-list').style.display = 'none';
        document.getElementById('batch-result-detail').style.display = 'block';

        // Update title
        const date = data.timestamp ? new Date(data.timestamp).toLocaleString() : '';
        document.getElementById('batch-detail-title').textContent =
            `${getCountryFlag(data.country)} ${data.country.toUpperCase()} - ${date}`;

        // Update stats
        document.getElementById('detail-total').textContent = data.total_records.toLocaleString();
        document.getElementById('detail-success').textContent = data.successful.toLocaleString();
        document.getElementById('detail-failed').textContent = data.failed.toLocaleString();
        document.getElementById('detail-speed').textContent = data.records_per_second;

        // Load records
        displayBatchRecords(data.results);

    } catch (error) {
        console.error('Failed to load batch detail:', error);
        showToast('Failed to load batch details', 'error');
    }
}

function displayBatchRecords(records, page = 1) {
    const perPage = 100;
    const start = (page - 1) * perPage;
    const end = start + perPage;
    const paginated = records.slice(start, end);
    const totalPages = Math.ceil(records.length / perPage);

    const tbody = document.getElementById('batch-detail-body');

    if (paginated.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No records found</td></tr>';
    } else {
        tbody.innerHTML = paginated.map((record, idx) => `
            <tr>
                <td>${start + idx + 1}</td>
                <td>${record.name}</td>
                <td><span class="status-badge ${record.success ? 'success' : 'error'}">${record.success ? '✓ Success' : '✗ Failed'}</span></td>
                <td>${record.reference_number || record.error || '-'}</td>
            </tr>
        `).join('');
    }

    // Update pagination
    const pagination = document.getElementById('batch-pagination');
    if (totalPages > 1) {
        let paginationHtml = '';

        if (page > 1) {
            paginationHtml += `<button class="btn btn-secondary" onclick="changeBatchPage(${page - 1})">← Prev</button> `;
        }

        paginationHtml += `<span style="margin: 0 15px;">Page ${page} of ${totalPages} (${records.length.toLocaleString()} records)</span>`;

        if (page < totalPages) {
            paginationHtml += ` <button class="btn btn-secondary" onclick="changeBatchPage(${page + 1})">Next →</button>`;
        }

        pagination.innerHTML = paginationHtml;
    } else {
        pagination.innerHTML = `<span>${records.length.toLocaleString()} records</span>`;
    }

    // Store records for pagination
    window.currentBatchRecords = records;
}

function changeBatchPage(page) {
    currentBatchPage = page;
    displayBatchRecords(window.currentBatchRecords, page);
}

async function searchBatchRecords() {
    const query = document.getElementById('batch-search-input').value.toLowerCase();

    if (!window.currentBatchRecords) return;

    if (!query) {
        displayBatchRecords(window.currentBatchRecords, 1);
        return;
    }

    const filtered = window.currentBatchRecords.filter(r =>
        r.name && r.name.toLowerCase().includes(query)
    );

    displayBatchRecords(filtered, 1);
}

function closeBatchDetail() {
    document.getElementById('batch-results-list').style.display = 'block';
    document.getElementById('batch-result-detail').style.display = 'none';
    currentBatchFile = null;
    window.currentBatchRecords = null;
}

function downloadBatchCSV(filename) {
    // Get CSV filename from JSON filename
    const csvFilename = filename.replace('.json', '.csv');
    showToast(`CSV file: data/output/${csvFilename}`, 'info');
}
