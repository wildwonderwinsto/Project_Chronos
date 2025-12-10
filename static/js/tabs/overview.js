// Overview Tab - Main Statistics and Charts

let activityChart = null;

function loadOverviewTab() {
    const container = document.getElementById('tab-overview');
    container.innerHTML = `
        <!-- Stats Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            
            <div class="stat-card" id="card-attempts">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm uppercase">Total Attempts</p>
                        <p class="text-4xl font-bold mt-2 stat-value" id="total-attempts">-</p>
                    </div>
                    <div class="text-5xl">🎯</div>
                </div>
            </div>

            <div class="stat-card" id="card-success">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm uppercase">Success Rate</p>
                        <p class="text-4xl font-bold mt-2 text-green-400 stat-value" id="success-rate">-</p>
                    </div>
                    <div class="text-5xl">✅</div>
                </div>
            </div>

            <div class="stat-card" id="card-24h">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm uppercase">Last 24 Hours</p>
                        <p class="text-4xl font-bold mt-2 stat-value" id="entries-24h">-</p>
                    </div>
                    <div class="text-5xl">📊</div>
                </div>
            </div>

            <div class="stat-card" id="card-frequency">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-400 text-sm uppercase">Entries/Hour</p>
                        <p class="text-4xl font-bold mt-2 text-blue-400 stat-value" id="entries-per-hour">-</p>
                    </div>
                    <div class="text-5xl">⚡</div>
                </div>
            </div>

        </div>

        <!-- Chart -->
        <div class="stat-card mb-8">
            <h2 class="text-xl font-bold mb-4">📈 Activity (Last 24 Hours)</h2>
            <canvas id="activityChart" height="80"></canvas>
        </div>

        <!-- Two Column Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            <!-- Recent Logs -->
            <div class="stat-card">
                <h2 class="text-xl font-bold mb-4">📜 Recent Attempts</h2>
                <div class="space-y-2 max-h-96 overflow-y-auto" id="recent-logs">
                    <p class="text-gray-400 text-center py-8">Loading...</p>
                </div>
            </div>

            <!-- System Info -->
            <div class="space-y-4">
                
                <div class="stat-card">
                    <h2 class="text-xl font-bold mb-4">🤖 Bot Status</h2>
                    <div class="space-y-3">
                        <div class="flex justify-between">
                            <span class="text-gray-400">Status</span>
                            <span class="font-semibold" id="bot-status-detail">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Mode</span>
                            <span class="font-semibold" id="current-mode-detail">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Consecutive Failures</span>
                            <span class="font-semibold text-red-400" id="consecutive-failures">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Target Frequency</span>
                            <span class="font-semibold" id="target-frequency">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Next Run</span>
                            <span class="font-semibold text-blue-400" id="next-run">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Last Attempt</span>
                            <span class="font-semibold" id="last-attempt">-</span>
                        </div>
                    </div>
                </div>

                <div class="stat-card">
                    <h2 class="text-xl font-bold mb-4">📊 Overall Stats</h2>
                    <div class="space-y-3">
                        <div class="flex justify-between">
                            <span class="text-gray-400">Total Successes</span>
                            <span class="font-semibold text-green-400 stat-value" id="total-successes">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Total Failures</span>
                            <span class="font-semibold text-red-400 stat-value" id="total-failures">-</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Successes (24h)</span>
                            <span class="font-semibold text-green-400 stat-value" id="successes-24h">-</span>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    `;
}

async function loadRecentLogs() {
    try {
        const response = await fetch('/api/recent-logs');
        const data = await response.json();

        const container = document.getElementById('recent-logs');
        
        if (data.logs.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-center py-8">No attempts yet</p>';
            return;
        }

        container.innerHTML = data.logs.map(log => {
            const statusColor = log.status === 'SUCCESS' ? 'text-green-400' : 
                               log.status === 'FAILED' ? 'text-red-400' : 'text-yellow-400';
            const statusIcon = log.status === 'SUCCESS' ? '✅' : 
                              log.status === 'FAILED' ? '❌' : '⏳';
            
            return `
                <div class="bg-gray-700 rounded p-3 text-sm">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="font-semibold">${log.persona_name || 'Unknown'}</p>
                            <p class="text-gray-400 text-xs">${log.persona_email || ''}</p>
                        </div>
                        <span class="${statusColor} font-semibold">${statusIcon} ${log.status}</span>
                    </div>
                    <div class="mt-2 text-xs text-gray-400">
                        ${formatRelativeTime(log.timestamp)}
                        ${log.proxy_city ? `• ${log.proxy_city}, ${log.proxy_state}` : ''}
                    </div>
                    ${log.error_message ? `<p class="text-red-400 text-xs mt-1">${log.error_message}</p>` : ''}
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

async function loadChart() {
    try {
        const response = await fetch('/api/hourly-chart');
        const data = await response.json();

        const ctx = document.getElementById('activityChart').getContext('2d');

        if (activityChart) {
            activityChart.data.labels = data.labels.map(l => new Date(l).toLocaleTimeString('en-US', {hour: '2-digit'}));
            activityChart.data.datasets[0].data = data.successes;
            activityChart.data.datasets[1].data = data.failures;
            activityChart.update('none');
        } else {
            activityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels.map(l => new Date(l).toLocaleTimeString('en-US', {hour: '2-digit'})),
                    datasets: [
                        {
                            label: 'Success',
                            data: data.successes,
                            borderColor: 'rgb(34, 197, 94)',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            tension: 0.3
                        },
                        {
                            label: 'Failed',
                            data: data.failures,
                            borderColor: 'rgb(239, 68, 68)',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { labels: { color: '#fff' } } },
                    scales: {
                        y: { beginAtZero: true, ticks: { color: '#9ca3af' }, grid: { color: '#374151' } },
                        x: { ticks: { color: '#9ca3af' }, grid: { color: '#374151' } }
                    }
                }
            });
        }

    } catch (error) {
        console.error('Error loading chart:', error);
    }
}