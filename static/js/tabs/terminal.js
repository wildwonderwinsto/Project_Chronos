// Terminal Tab - Live Log Stream

function loadTerminalTab() {
    const container = document.getElementById('tab-terminal');
    container.innerHTML = `
        <div class="stat-card">
            <h2 class="text-xl font-bold mb-4">💻 Live Terminal Output</h2>
            <div class="log-terminal" id="terminal-output">
                <div class="log-line log-INFO">Waiting for bot activity...</div>
            </div>
        </div>
    `;
}

async function loadLiveTerminal() {
    try {
        const response = await fetch('/api/live-logs');
        const data = await response.json();

        const terminal = document.getElementById('terminal-output');
        const shouldScroll = terminal.scrollHeight - terminal.scrollTop === terminal.clientHeight;
        
        terminal.innerHTML = data.logs.map(log => {
            const levelClass = `log-${log.level}`;
            return `<div class="log-line ${levelClass}">[${new Date(log.timestamp).toLocaleTimeString()}] ${log.message}</div>`;
        }).join('');
        
        if (shouldScroll) {
            terminal.scrollTop = terminal.scrollHeight;
        }

    } catch (error) {
        console.error('Error loading terminal:', error);
    }
}