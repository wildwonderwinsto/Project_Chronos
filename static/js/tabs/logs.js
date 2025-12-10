// Logs Tab - Detailed Log Viewing

function loadLogsTab() {
    const container = document.getElementById('tab-logs');
    container.innerHTML = `
        <!-- Search & Filters -->
        <div class="stat-card mb-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <input type="text" id="search-input" placeholder="Search by name or email..." 
                       class="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500">
                <select id="status-filter" class="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500">
                    <option value="">All Statuses</option>
                    <option value="SUCCESS">Success Only</option>
                    <option value="FAILED">Failed Only</option>
                    <option value="INITIATED">Initiated Only</option>
                </select>
                <button onclick="searchLogs()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded font-semibold">
                    🔍 Search
                </button>
            </div>
        </div>

        <!-- Logs Table -->
        <div class="stat-card">
            <h2 class="text-xl font-bold mb-4">All Attempts (<span id="log-count">0</span>)</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="text-gray-400 border-b border-gray-700">
                            <th class="text-left py-2">Time</th>
                            <th class="text-left py-2">Name</th>
                            <th class="text-left py-2">Email</th>
                            <th class="text-center py-2">Status</th>
                            <th class="text-left py-2">Proxy Location</th>
                            <th class="text-left py-2">Error</th>
                        </tr>
                    </thead>
                    <tbody id="logs-table">
                        <tr>
                            <td colspan="6" class="text-center text-gray-400 py-8">Loading...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

async function searchLogs() {
    try {
        const search = document.getElementById('search-input').value;
        const status = document.getElementById('status-filter').value;
        
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (status) params.append('status', status);
        params.append('limit', 100);
        
        const response = await fetch(`/api/search-logs?${params}`);
        const data = await response.json();

        document.getElementById('log-count').textContent = data.count;

        const tbody = document.getElementById('logs-table');
        
        if (data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-gray-400 py-8">No logs found</td></tr>';
            return;
        }

        tbody.innerHTML = data.logs.map(log => `
            <tr class="border-b border-gray-700 hover:bg-gray-700">
                <td class="py-2 text-xs">${formatDate(log.timestamp)}</td>
                <td class="py-2">${log.persona_name || '-'}</td>
                <td class="py-2 text-xs">${log.persona_email || '-'}</td>
                <td class="py-2 text-center">
                    <span class="${log.status === 'SUCCESS' ? 'text-green-400' : log.status === 'FAILED' ? 'text-red-400' : 'text-yellow-400'}">
                        ${log.status}
                    </span>
                </td>
                <td class="py-2 text-xs">${log.proxy_city ? `${log.proxy_city}, ${log.proxy_state}` : '-'}</td>
                <td class="py-2 text-xs text-red-400">${log.error_message || '-'}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error searching logs:', error);
    }
}