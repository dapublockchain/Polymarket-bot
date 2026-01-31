document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const statusEl = document.getElementById('system-status');
    const uptimeEl = document.getElementById('uptime');
    const strategyEl = document.getElementById('strategy-name');
    const activePairsEl = document.getElementById('active-pairs');
    const logViewer = document.getElementById('log-viewer');
    const oppsList = document.getElementById('opps-list');

    // State
    let knownLogLines = new Set();

    // Fetch Status
    async function fetchStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();

            // Update Status Badge
            const statusText = statusEl.querySelector('.text');
            statusText.textContent = data.status.toUpperCase();

            if (data.status === '在线' || data.status === 'online') {
                statusEl.classList.add('online');
            } else {
                statusEl.classList.remove('online');
            }

            // Update Stats
            uptimeEl.textContent = data.uptime;
            strategyEl.textContent = data.strategy;
            activePairsEl.textContent = data.active_pairs;

        } catch (err) {
            console.error('获取状态时出错:', err);
            statusEl.classList.remove('online');
            statusEl.querySelector('.text').textContent = '离线';
        }
    }

    // Fetch Logs
    async function fetchLogs() {
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();

            // Check if we have new logs
            // Ideally backend returns IDs, but for file tailing we just replace/append
            // For simplicity, we'll clear and re-render if we suspect changes or just verify latest
            // A better approach is to append only new lines, but replacing content is easier for MVP

            logViewer.innerHTML = ''; // Clear for now to avoid duplicates in simple polling

            data.logs.forEach(line => {
                const div = document.createElement('div');
                div.className = 'log-line';
                // Basic syntax highlighting
                if (line.includes('INFO')) div.classList.add('info');
                if (line.includes('WARNING')) div.classList.add('warning');
                if (line.includes('ERROR')) div.classList.add('error');
                if (line.includes('SUCCESS') || line.includes('连接成功')) div.classList.add('success');

                div.textContent = line;
                logViewer.appendChild(div);
            });

            // Auto scroll to bottom
            logViewer.scrollTop = logViewer.scrollHeight;

        } catch (err) {
            console.error('获取日志时出错:', err);
        }
    }

    // Fetch Opportunities
    async function fetchOpportunities() {
        try {
            const res = await fetch('/api/opportunities');
            const data = await res.json();

            oppsList.innerHTML = '';

            if (data.opportunities.length === 0) {
                oppsList.innerHTML = '<div class="empty-state">尚未检测到套利机会。</div>';
                return;
            }

            data.opportunities.forEach(opp => {
                const item = document.createElement('div');
                item.className = 'opp-item';
                item.innerHTML = `
                    <div class="opp-header">
                        <span>${opp.timestamp}</span>
                        <span class="${opp.profit > 0 ? 'opp-profit' : ''}">${(opp.profit * 100).toFixed(2)}% 利润</span>
                    </div>
                    <div class="opp-title">${opp.pair}</div>
                    <div class="opp-details">
                        <div class="opp-detail-item">YES: <span>$${opp.yes_price}</span></div>
                        <div class="opp-detail-item">NO: <span>$${opp.no_price}</span></div>
                    </div>
                `;
                oppsList.appendChild(item);
            });

        } catch (err) {
            console.error('获取机会时出错:', err);
        }
    }

    // Initial load
    fetchStatus();
    fetchLogs();
    fetchOpportunities();

    // Polling
    setInterval(fetchStatus, 2000);
    setInterval(fetchLogs, 1000);
    setInterval(fetchOpportunities, 2000);
});
