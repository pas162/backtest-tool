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
    runBacktestBtn: document.getElementById('runBacktestBtn'),
    status: document.getElementById('status'),
    progressSection: document.getElementById('progressSection'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
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
    // Backtest Settings
    initialCapital: document.getElementById('initialCapital'),
    leverage: document.getElementById('leverage'),
    positionSize: document.getElementById('positionSize'),
    commission: document.getElementById('commission'),
};

// Strategy parameters
const paramInputs = {
    ema1_length: document.getElementById('ema1_length'),
    ema2_length: document.getElementById('ema2_length'),
    st_length: document.getElementById('st_length'),
    st_multiplier: document.getElementById('st_multiplier'),
    stop_loss_pct: document.getElementById('stop_loss_pct'),
    take_profit_pct: document.getElementById('take_profit_pct'),
};

/**
 * Show progress bar
 */
function showProgress(text, percent = 0) {
    elements.progressSection.style.display = 'block';
    elements.progressText.textContent = text;
    elements.progressFill.style.width = `${percent}%`;
}

/**
 * Hide progress bar
 */
function hideProgress() {
    elements.progressSection.style.display = 'none';
}

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
    const strategy = elements.strategy.value;

    // ML strategy has its own parameters
    if (strategy === 'ml_xgboost') {
        return {
            buy_threshold: 0.60,
            sell_threshold: 0.40,
            stop_loss_pct: 5.0,
            take_profit_pct: 10.0,
        };
    }

    // VWAP SuperTrend EMA strategy
    const baseParams = {
        ema1_length: parseInt(paramInputs.ema1_length.value),
        ema2_length: parseInt(paramInputs.ema2_length.value),
        st_length: parseInt(paramInputs.st_length.value),
        st_multiplier: parseFloat(paramInputs.st_multiplier.value),
    };

    return baseParams;
}

/**
 * Run backtest (auto-fetches data if needed)
 */
async function runBacktest() {
    elements.runBacktestBtn.disabled = true;
    hideStatus();

    try {
        // Step 1: Show progress - Fetching data
        showProgress('📥 Fetching data from Binance (if needed)...', 10);

        // Simulate progress while waiting
        let progress = 10;
        const progressInterval = setInterval(() => {
            if (progress < 90) {
                progress += Math.random() * 5;
                const stage = progress < 40 ? 'Fetching data...' :
                    progress < 70 ? 'Running backtest...' :
                        'Calculating metrics...';
                showProgress(`⏳ ${stage}`, Math.min(progress, 90));
            }
        }, 500);

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
                initial_capital: parseFloat(elements.initialCapital.value),
                leverage: parseFloat(elements.leverage.value),
                position_size: parseFloat(elements.positionSize.value),
                commission: parseFloat(elements.commission.value) / 100,  // Convert % to decimal
            }),
        });

        clearInterval(progressInterval);

        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage = 'Unknown error';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText.substring(0, 100);
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();

        // Step 3: Complete
        showProgress('✅ Backtest complete!', 100);

        setTimeout(() => {
            hideProgress();
            displayResults(data);
            showStatus(`✅ Completed! ${data.trades.length} trades found.`, 'success');
        }, 500);

    } catch (error) {
        hideProgress();
        showStatus(`❌ Error: ${error.message}`, 'error');
    } finally {
        elements.runBacktestBtn.disabled = false;
    }
}

/**
 * Display backtest results
 */
function displayResults(data) {
    updateMetrics(data.metrics);
    drawEquityCurve(data.equity_curve);
    populateTradesTable(data.trades);
}

/**
 * Update metrics cards
 */
function updateMetrics(metrics) {
    const formatPct = (val) => val != null ? `${val.toFixed(2)}%` : '-';
    const formatNum = (val) => val != null ? val.toFixed(2) : '-';

    elements.returnPct.textContent = formatPct(metrics.return_pct);
    elements.returnPct.className = `metric-value ${metrics.return_pct >= 0 ? 'positive' : 'negative'}`;

    elements.winRate.textContent = formatPct(metrics.win_rate_pct);
    elements.winRate.className = `metric-value ${metrics.win_rate_pct >= 50 ? 'positive' : 'negative'}`;

    elements.maxDrawdown.textContent = formatPct(metrics.max_drawdown_pct);
    elements.maxDrawdown.className = 'metric-value negative';

    elements.totalTrades.textContent = metrics.total_trades || '0';

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
        Plotly.purge('equityChart');
        return;
    }

    const timestamps = equityCurve.map(p => p.timestamp);
    const equity = equityCurve.map(p => p.equity);

    const trace = {
        x: timestamps,
        y: equity,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#238636', width: 2 },
        fill: 'tozeroy',
        fillcolor: 'rgba(35, 134, 54, 0.1)',
    };

    const layout = {
        paper_bgcolor: '#21262d',
        plot_bgcolor: '#21262d',
        font: { color: '#c9d1d9' },
        margin: { l: 60, r: 30, t: 20, b: 40 },
        xaxis: { gridcolor: '#30363d', tickformat: '%Y-%m-%d' },
        yaxis: { gridcolor: '#30363d', tickprefix: '$' },
        hovermode: 'x unified',
    };

    Plotly.newPlot('equityChart', [trace], layout, { responsive: true, displayModeBar: false });
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

    elements.tradesBody.innerHTML = trades.slice(0, 50).map(trade => `
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
                ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(1)}%
            </td>
        </tr>
    `).join('');

    if (trades.length > 50) {
        elements.tradesBody.innerHTML += `
            <tr><td colspan="7" class="no-data">... and ${trades.length - 50} more trades</td></tr>
        `;
    }
}

/**
 * Format datetime for display
 */
function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
        ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    elements.runBacktestBtn.addEventListener('click', runBacktest);

    // Set default dates (last 7 days for faster testing)
    const today = new Date();
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(today.getDate() - 7);

    elements.endDate.value = today.toISOString().split('T')[0];
    elements.startDate.value = oneWeekAgo.toISOString().split('T')[0];

    // Show/hide SL/TP based on selected strategy
    toggleSlTpFields();
});

/**
 * Toggle params visibility based on selected strategy
 */
function toggleSlTpFields() {
    const strategy = elements.strategy.value;
    const vwapParams = document.getElementById('vwapParams');
    const mlParams = document.getElementById('mlParams');

    if (strategy === 'ml_xgboost') {
        // ML strategy - hide VWAP params, show ML message
        if (vwapParams) vwapParams.style.display = 'none';
        if (mlParams) mlParams.style.display = 'grid';
    } else {
        // VWAP strategy - show VWAP params, hide ML message
        if (vwapParams) vwapParams.style.display = 'grid';
        if (mlParams) mlParams.style.display = 'none';
    }
}

