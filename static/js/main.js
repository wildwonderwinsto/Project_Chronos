// Main Dashboard Controller

let currentTab = 'overview';
let statsInterval = null;
let logsInterval = null;
let terminalInterval = null;
let chartInterval = null;

// Switch tabs
function switchTab(tab) {
    currentTab = tab;
    
    // Hide all tabs
    document.querySelectorAll('[id^="tab-"]').forEach(el => el.classList.add('hidden'));
    
    // Show selected tab
    document.getElementById(`tab-${tab}`).classList.remove('hidden');
    
    // Update button states
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    // Clear all intervals
    clearAllIntervals();
    
    // Start appropriate intervals for this tab
    if (tab === 'overview') {
        startOverviewUpdates();
    } else if (tab === 'logs') {
        startLogsUpdates();
    } else if (tab === 'terminal') {
        startTerminalUpdates();
    } else if (tab === 'images') {
        startImagesUpdates();
    } else if (tab === 'emails') {
        startEmailsUpdates();
    } else if (tab === 'admin') {
        startAdminUpdates();
    }
}

function clearAllIntervals() {
    if (statsInterval) clearInterval(statsInterval);
    if (logsInterval) clearInterval(logsInterval);
    if (terminalInterval) clearInterval(terminalInterval);
    if (chartInterval) clearInterval(chartInterval);
}

function startOverviewUpdates() {
    loadOverviewTab();
    loadStats();
    loadRecentLogs();
    loadChart();
    
    statsInterval = setInterval(loadStats, 2000);
    logsInterval = setInterval(loadRecentLogs, 3000);
    chartInterval = setInterval(loadChart, 10000);
}

function startLogsUpdates() {
    loadLogsTab();
    searchLogs();
    logsInterval = setInterval(searchLogs, 5000);
}

function startTerminalUpdates() {
    loadTerminalTab();
    loadLiveTerminal();
    terminalInterval = setInterval(loadLiveTerminal, 1000);
}

function startImagesUpdates() {
    loadImagesTab();
    loadImages();
    logsInterval = setInterval(loadImages, 10000);
}

function startEmailsUpdates() {
    loadEmailsTab();
    loadEmails();
    loadCurrentEmails();
    logsInterval = setInterval(() => {
        loadEmails();
        loadCurrentEmails();
    }, 5000);
}

function startAdminUpdates() {
    loadAdminTab();
    loadProxyStats();
    logsInterval = setInterval(loadProxyStats, 5000);
}

// Load stats with change detection
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        // Update status
        document.getElementById('bot-status').textContent = data.bot_status;
        document.getElementById('current-mode').textContent = `Mode: ${data.current_mode}`;
        
        const indicator = document.getElementById('status-indicator');
        indicator.className = 'status-dot';
        if (data.bot_status === 'RUNNING') indicator.classList.add('status-running');
        else if (data.bot_status === 'PANIC_MODE') indicator.classList.add('status-panic');
        else indicator.classList.add('status-paused');

        // Update with change detection
        updateWithHighlight('total-attempts', data.total_attempts.toLocaleString(), 'card-attempts');
        updateWithHighlight('success-rate', data.success_rate + '%', 'card-success');
        updateWithHighlight('entries-24h', data.entries_last_24h.toLocaleString(), 'card-24h');
        updateWithHighlight('entries-per-hour', data.entries_per_hour.toFixed(2), 'card-frequency');

        if (document.getElementById('bot-status-detail')) {
            document.getElementById('bot-status-detail').textContent = data.bot_status;
            document.getElementById('current-mode-detail').textContent = data.current_mode;
            document.getElementById('consecutive-failures').textContent = data.consecutive_failures;
            document.getElementById('target-frequency').textContent = (data.target_frequency || 0).toFixed(2) + '/hr';
            document.getElementById('next-run').textContent = formatRelativeTime(data.next_run_time);
            document.getElementById('last-attempt').textContent = formatRelativeTime(data.last_attempt_time);

            updateWithHighlight('total-successes', data.total_successes.toLocaleString());
            updateWithHighlight('total-failures', data.total_failures.toLocaleString());
            updateWithHighlight('successes-24h', data.successes_last_24h.toLocaleString());
        }

        updateTimestamp();
        setConnectionStatus(true);

    } catch (error) {
        console.error('Error loading stats:', error);
        setConnectionStatus(false);
    }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    startOverviewUpdates();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    clearAllIntervals();
});