// Emails Tab - Manage Email Configurations

function loadEmailsTab() {
    const container = document.getElementById('tab-emails');
    container.innerHTML = `
        <div class="space-y-6">
            
            <!-- Current Active Emails -->
            <div class="stat-card">
                <h2 class="text-xl font-bold mb-4">📧 Currently Active Email Accounts</h2>
                <p class="text-gray-400 text-sm mb-4">These emails are being used RIGHT NOW for persona generation</p>
                <div id="current-emails-display" class="space-y-2">
                    <p class="text-gray-400">Loading...</p>
                </div>
            </div>

            <!-- Email Management -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                <!-- All Configured Emails -->
                <div class="stat-card">
                    <h3 class="text-lg font-bold mb-4">All Configured Emails</h3>
                    <div id="email-list" class="space-y-2">
                        <p class="text-gray-400">Loading...</p>
                    </div>
                </div>

                <!-- Add New Email -->
                <div class="stat-card">
                    <h3 class="text-lg font-bold mb-4">Add New Email</h3>
                    <p class="text-xs text-gray-400 mb-4">Changes take effect immediately - no redeploy needed!</p>
                    <div class="space-y-3">
                        <input type="text" id="new-email-account" placeholder="Email account (e.g., UsersMaiI)" 
                            class="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500">
                        <select id="new-email-domain" class="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500">
                            <option value="">Select domain...</option>
                            <option value="gmail.com">gmail.com</option>
                            <option value="outlook.com">outlook.com</option>
                            <option value="yahoo.com">yahoo.com</option>
                            <option value="icloud.com">icloud.com</option>
                            <option value="protonmail.com">protonmail.com</option>
                        </select>
                        <input type="password" id="email-admin-password" placeholder="Admin password" 
                            class="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500">
                        <button onclick="addEmail()" 
                                class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-3 rounded font-semibold">
                            ➕ Add Email
                        </button>
                        <div id="email-result" class="mt-2"></div>
                    </div>
                </div>

            </div>

            <!-- Info Box -->
            <div class="stat-card bg-blue-900 bg-opacity-20 border-blue-700">
                <h3 class="text-lg font-bold mb-2">💡 How It Works</h3>
                <ul class="text-sm text-gray-300 space-y-2">
                    <li>• Personas use <span class="font-mono text-blue-400">account+alias@domain.com</span> format</li>
                    <li>• All emails route to your master accounts</li>
                    <li>• Multiple domains = better distribution</li>
                    <li>• Disable emails without deleting them</li>
                    <li>• Changes apply instantly to new personas</li>
                </ul>
            </div>

        </div>
    `;
}

async function loadCurrentEmails() {
    try {
        const response = await fetch('/api/emails/current');
        const data = await response.json();
        
        const container = document.getElementById('current-emails-display');
        
        if (Object.keys(data.active_emails).length === 0) {
            container.innerHTML = '<p class="text-red-400">⚠️ No active emails configured!</p>';
            return;
        }
        
        container.innerHTML = Object.entries(data.active_emails).map(([domain, account]) => `
            <div class="bg-green-900 bg-opacity-20 border border-green-700 rounded p-3 flex items-center gap-3">
                <div class="text-2xl">✅</div>
                <div class="flex-1">
                    <p class="font-mono text-green-400 font-semibold">${account}@${domain}</p>
                    <p class="text-xs text-gray-400">Active - being used for new personas</p>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading current emails:', error);
    }
}

async function loadEmails() {
    try {
        const response = await fetch('/api/emails');
        const data = await response.json();
        
        const container = document.getElementById('email-list');
        
        if (data.emails.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-center py-4">No emails configured</p>';
            return;
        }
        
        container.innerHTML = data.emails.map(email => {
            const statusClass = email.is_active ? 'text-green-400' : 'text-red-400';
            const statusIcon = email.is_active ? '✅' : '❌';
            const toggleText = email.is_active ? 'Disable' : 'Enable';
            
            return `
                <div class="bg-gray-700 rounded p-3 flex items-center justify-between">
                    <div>
                        <span class="font-mono">${email.email_account}@${email.domain}</span>
                        <span class="${statusClass} ml-2">${statusIcon}</span>
                    </div>
                    <div class="space-x-2">
                        <button onclick="toggleEmail('${email.domain}', ${!email.is_active})" 
                                class="text-yellow-400 hover:text-yellow-300 text-sm">
                            ${toggleText}
                        </button>
                        <button onclick="deleteEmail('${email.domain}')" 
                                class="text-red-400 hover:text-red-300 text-sm">
                            Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error loading emails:', error);
    }
}

async function addEmail() {
    const account = document.getElementById('new-email-account').value;
    const domain = document.getElementById('new-email-domain').value;
    const password = document.getElementById('email-admin-password').value;
    const resultDiv = document.getElementById('email-result');
    
    if (!account || !domain) {
        resultDiv.innerHTML = '<p class="text-red-400">Please fill in all fields</p>';
        return;
    }
    
    if (!password) {
        resultDiv.innerHTML = '<p class="text-red-400">Admin password required</p>';
        return;
    }
    
    try {
        const response = await fetch('/api/emails/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email_account: account, domain: domain, password: password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            resultDiv.innerHTML = '<p class="text-green-400">✅ ' + data.message + '</p>';
            document.getElementById('new-email-account').value = '';
            document.getElementById('new-email-domain').value = '';
            document.getElementById('email-admin-password').value = '';
            
            // Reload lists
            setTimeout(() => {
                loadEmails();
                loadCurrentEmails();
                resultDiv.innerHTML = '';
            }, 2000);
        } else {
            resultDiv.innerHTML = '<p class="text-red-400">❌ ' + data.error + '</p>';
        }
        
    } catch (error) {
        resultDiv.innerHTML = '<p class="text-red-400">❌ Error: ' + error.message + '</p>';
    }
}

async function toggleEmail(domain, active) {
    const password = prompt('Enter admin password:');
    if (!password) return;
    
    try {
        const response = await fetch('/api/emails/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain: domain, active: active, password: password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadEmails();
            loadCurrentEmails();
        } else {
            alert('Error: ' + data.error);
        }
        
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteEmail(domain) {
    if (!confirm(`Are you sure you want to delete ${domain}?`)) return;
    
    const password = prompt('Enter admin password:');
    if (!password) return;
    
    try {
        const response = await fetch('/api/emails/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain: domain, password: password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadEmails();
            loadCurrentEmails();
        } else {
            alert('Error: ' + data.error);
        }
        
    } catch (error) {
        alert('Error: ' + error.message);
    }
}