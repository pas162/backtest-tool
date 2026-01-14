/**
 * Backtest Platform - Frontend Application
 */

const API_BASE = '/api';

// DOM Elements
const elements = {
    symbol: document.getElementById('symbol'),
    timeframe: document.getElementById('timeframe'),
    startDate: document.getElementById('startDate'),
    endDate: document.getElementById('endDate'),
    strategy: document.getElementById('strategy'),
    fetchDataBtn: document.getElementById('fetchDataBtn'),
    runBacktestBtn: document.getElementById('runBacktestBtn'),
    status: document.getElementById('status'),
    // Metrics
    returnPct: document.getElementById('returnPct'),
    winRate: document.getElementById('winRate'),
    maxDrawdown: document.getElementById('maxDrawdown'),
    totalTrades: document.getElementById('totalTrades'),
    sharpeRatio: document.getElementById('sharpeRatio'),
    profitFactor: document.getElementById('profitFactor'),
    // Chart & Table
    equityChart: document.getElementById('equityChart'),
    tradesBody: document.getElementById('tradesBody'),
};

// Strategy parameters
const paramInputs = {
    ema1_length: document.getElementById('ema1_length'),
    ema2_length: document.getElementById('ema2_length'),
    st_length: document.getElementById('st_length'),
    st_multiplier: document.getElementById('st_multiplier'),
};

/**
 * Show status message
 */
function showStatus(message, type = 'loading') {
    elements.status.textContent = message;
    elements.status.className = `status-box ${type}`;
}

/**
 * Hide status message
 */
function hideStatus() {
    elements.status.className = 'status-box';
}

/**
 * Get strategy parameters from inputs
 */
function getStrategyParams() {
    return {
        ema1_length: parseInt(paramInputs.ema1_length.value),
        ema2_length: parseInt(paramInputs.ema2_length.value),
        st_length: parseInt(paramInputs.st_length.value),
        st_multiplier: parseFloat(paramInputs.st_multiplier.value),
    };
}

/**
 * Fetch data from Binance
 */
async function fetchData() {
    showStatus('Fetching data from Binance...', 'loading');
    elements.fetchDataBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/data/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: elements.symbol.value,
                timeframe: elements.timeframe.value,
                start_date: elements.startDate.value,
                end_date: elements.endDate.value,
            }),
        });

        const data = await response.json();
        
        if (response.ok) {
            showStatus(`✅ Fetched ${data.candles_count} candles`, 'success');
        } else {
            showStatus(`❌ Error: ${data.detail || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showStatus(`❌ Error: ${error.message}`, 'error');
    } finally {
        elements.fetchDataBtn.disabled = false;
    }
}

/**
 * Run backtest
 */
async function runBacktest() {
    showStatus('Running backtest...', 'loading');
    elements.runBacktestBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/backtest/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: elements.symbol.value,
                timeframe: elements.timeframe.value,
                start_date: elements.startDate.value,
                end_date: elements.endDate.value,
                strategy: elements.strategy.value,
                params: getStrategyParams(),
            }),
        });

        const data = await response.json();

        if (response.ok) {
            displayResults(data);
            showStatus('✅ Backtest completed!', 'success');
        } else {
            showStatus(`❌ Error: ${data.detail || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showStatus(`❌ Error: ${error.message}`, 'error');
    } finally {
        elements.runBacktestBtn.disabled = false;
    }
}

/**
 * Display backtest results
 */
function displayResults(data) {
    // Update metrics
    updateMetrics(data.metrics);
    
    // Draw equity curve
    drawEquityCurve(data.equity_curve);
    
    // Populate trades table
    populateTradesTable(data.trades);
}

/**
 * Update metrics cards
 */
function updateMetrics(metrics) {
    const formatPct = (val) => val ? `${val.toFixed(2)}%` : '-';
    const formatNum = (val) => val ? val.toFixed(2) : '-';

    elements.returnPct.textContent = formatPct(metrics.return_pct);
    elements.returnPct.className = `metric-value ${metrics.return_pct >= 0 ? 'positive' : 'negative'}`;

    elements.winRate.textContent = formatPct(metrics.win_rate_pct);
    elements.winRate.className = `metric-value ${metrics.win_rate_pct >= 50 ? 'positive' : 'negative'}`;

    elements.maxDrawdown.textContent = formatPct(metrics.max_drawdown_pct);
    elements.maxDrawdown.className = 'metric-value negative';

    elements.totalTrades.textContent = metrics.total_trades || '-';

    elements.sharpeRatio.textContent = formatNum(metrics.sharpe_ratio);
    elements.sharpeRatio.className = `metric-value ${metrics.sharpe_ratio >= 1 ? 'positive' : ''}`;

    elements.profitFactor.textContent = formatNum(metrics.profit_factor);
    elements.profitFactor.className = `metric-value ${metrics.profit_factor >= 1 ? 'positive' : 'negative'}`;
}

/**
 * Draw equity curve with Plotly
 */
function drawEquityCurve(equityCurve) {
    if (!equityCurve || equityCurve.length === 0) {
        return;
    }

    const timestamps = equityCurve.map(p => p.timestamp);
    const equity = equityCurve.map(p => p.equity);

    const trace = {
        x: timestamps,
        y: equity,
        type: 'scatter',
        mode: 'lines',
        line: {
            color: '#238636',
            width: 2,
        },
        fill: 'tozeroy',
        fillcolor: 'rgba(35, 134, 54, 0.1)',
    };

    const layout = {
        paper_bgcolor: '#21262d',
        plot_bgcolor: '#21262d',
        font: { color: '#c9d1d9' },
        margin: { l: 60, r: 30, t: 20, b: 40 },
        xaxis: {
            gridcolor: '#30363d',
            tickformat: '%Y-%m-%d',
        },
        yaxis: {
            gridcolor: '#30363d',
            tickprefix: '$',
        },
        hovermode: 'x unified',
    };

    const config = {
        responsive: true,
        displayModeBar: false,
    };

    Plotly.newPlot('equityChart', [trace], layout, config);
}

/**
 * Populate trades table
 */
function populateTradesTable(trades) {
    if (!trades || trades.length === 0) {
        elements.tradesBody.innerHTML = `
            <tr><td colspan="7" class="no-data">No trades executed</td></tr>
        `;
        return;
    }

    elements.tradesBody.innerHTML = trades.map(trade => `
        <tr>
            <td>${formatDateTime(trade.entry_time)}</td>
            <td>${formatDateTime(trade.exit_time)}</td>
            <td class="side-${trade.side}">${trade.side.toUpperCase()}</td>
            <td>$${trade.entry_price.toFixed(2)}</td>
            <td>$${trade.exit_price.toFixed(2)}</td>
            <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                ${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}
            </td>
            <td class="${trade.pnl_pct >= 0 ? 'positive' : 'negative'}">
                ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%
            </td>
        </tr>
    `).join('');
}

/**
 * Format datetime for display
 */
function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    elements.fetchDataBtn.addEventListener('click', fetchData);
    elements.runBacktestBtn.addEventListener('click', runBacktest);
    
    // Set default dates
    const today = new Date();
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(today.getMonth() - 6);
    
    elements.endDate.value = today.toISOString().split('T')[0];
    elements.startDate.value = sixMonthsAgo.toISOString().split('T')[0];
});
