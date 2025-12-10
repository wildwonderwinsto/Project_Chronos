// Admin Tab - Database Management

function loadAdminTab() {
    const container = document.getElementById('tab-admin');
    container.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            <!-- Clear Database -->
            <div class="stat-card">
                <h2 class="text-xl font-bold mb-4 text-red-400">🗑️ Clear Database</h2>
                <p class="text-gray-400 mb-4">This will delete ALL attempt logs and reset statistics.</p>
                <input type="password" id="admin-password" placeholder="Enter admin password" 
                       class="w-full bg-gray-700 text-white px-4 py-2 rounded mb-4 border border-gray-600">
                <button onclick="clearDatabase()" 
                        class="w-full bg-red-600 hover:bg-red-700 px-4 py-3 rounded font-semibold">
                    ⚠️ CLEAR ALL DATA
                </button>
                <div id="clear-result" class="mt-4"></div>
            </div>

            <!-- Proxy Stats -->
            <div class="stat-card">
                <h2 class="text-xl font-bold mb-4">🌐 Proxy Usage</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-gray-400 border-b border-gray-700">
                                <th class="text-left py-2">IP</th>
                                <th class="text-left py-2">Location</th>
                                <th class="text-center py-2">Total</th>
                            </tr>
                        </thead>
                        <tbody id="admin-proxy-table">
                            <tr>
                                <td colspan="3" class="text-center text-gray-400 py-8">Loading...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    `;
}

async function clearDatabase() {
    const password = document.getElementById('admin-password').value;
    const resultDiv = document.getElementById('clear-result');
    
    if (!password) {
        resultDiv.innerHTML = '<p class="text-red-400">Please enter password</p>';
        return;
    }
    
    if (!confirm('Are you sure? This will delete ALL data!')) {
        return;
    }

    try {
        const response = await fetch('/api/clear-database', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });

        const data = await response.json();

        if (response.ok) {
            resultDiv.innerHTML = '<p class="text-green-400">✅ Database cleared successfully!</p>';
            setTimeout(() => location.reload(), 2000);
        } else {
            resultDiv.innerHTML = `<p class="text-red-400">❌ ${data.error}</p>`;
        }

    } catch (error) {
        resultDiv.innerHTML = `<p class="text-red-400">❌ Error: ${error.message}</p>`;
    }
}

async function loadProxyStats() {
    try {
        const response = await fetch('/api/proxy-stats');
        const data = await response.json();

        const tbody = document.getElementById('admin-proxy-table');
        
        if (data.proxies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-gray-400 py-8">No proxy data</td></tr>';
            return;
        }

        tbody.innerHTML = data.proxies.slice(0, 10).map(proxy => `
            <tr class="border-b border-gray-700">
                <td class="py-2 font-mono text-xs">${proxy.ip}</td>
                <td class="py-2">${proxy.city}, ${proxy.state}</td>
                <td class="py-2 text-center">${proxy.total}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading proxy stats:', error);
    }
}