/* ============================================
   backtest.js - Backtesting Page
   ============================================ */

const Backtest = (() => {
  let initialized = false;
  let equityChartInstance = null;

  // ---- Mock Backtest Results ----
  const mockResults = {
    summary: {
      totalReturn: '+23.5%',
      winRate: '65.2%',
      maxDrawdown: '-8.3%',
      sharpeRatio: '1.85',
      totalTrades: 23,
      profitFactor: 2.14,
      avgWin: '+4.2%',
      avgLoss: '-2.1%'
    },
    trades: [
      { id: 1, type: 'LONG', buyDate: '2025-01-15', buyPrice: 545, sellDate: '2025-02-10', sellPrice: 578, pnl: 33000, returnPct: 6.06 },
      { id: 2, type: 'LONG', buyDate: '2025-02-24', buyPrice: 560, sellDate: '2025-03-12', sellPrice: 548, pnl: -12000, returnPct: -2.14 },
      { id: 3, type: 'LONG', buyDate: '2025-03-25', buyPrice: 535, sellDate: '2025-04-15', sellPrice: 570, pnl: 35000, returnPct: 6.54 },
      { id: 4, type: 'LONG', buyDate: '2025-04-28', buyPrice: 582, sellDate: '2025-05-16', sellPrice: 575, pnl: -7000, returnPct: -1.20 },
      { id: 5, type: 'LONG', buyDate: '2025-05-28', buyPrice: 568, sellDate: '2025-06-18', sellPrice: 590, pnl: 22000, returnPct: 3.87 },
      { id: 6, type: 'LONG', buyDate: '2025-07-02', buyPrice: 585, sellDate: '2025-07-22', sellPrice: 610, pnl: 25000, returnPct: 4.27 },
      { id: 7, type: 'LONG', buyDate: '2025-08-05', buyPrice: 605, sellDate: '2025-08-20', sellPrice: 595, pnl: -10000, returnPct: -1.65 },
      { id: 8, type: 'LONG', buyDate: '2025-09-01', buyPrice: 588, sellDate: '2025-09-19', sellPrice: 618, pnl: 30000, returnPct: 5.10 },
      { id: 9, type: 'LONG', buyDate: '2025-10-07', buyPrice: 610, sellDate: '2025-10-28', sellPrice: 598, pnl: -12000, returnPct: -1.97 },
      { id: 10, type: 'LONG', buyDate: '2025-11-10', buyPrice: 592, sellDate: '2025-12-02', sellPrice: 622, pnl: 30000, returnPct: 5.07 },
      { id: 11, type: 'LONG', buyDate: '2025-12-15', buyPrice: 615, sellDate: '2026-01-08', sellPrice: 608, pnl: -7000, returnPct: -1.14 },
      { id: 12, type: 'LONG', buyDate: '2026-01-20', buyPrice: 600, sellDate: '2026-02-10', sellPrice: 635, pnl: 35000, returnPct: 5.83 },
      { id: 13, type: 'LONG', buyDate: '2026-02-24', buyPrice: 628, sellDate: '2026-03-14', sellPrice: 615, pnl: -13000, returnPct: -2.07 },
      { id: 14, type: 'LONG', buyDate: '2026-03-25', buyPrice: 608, sellDate: '2026-04-10', sellPrice: 640, pnl: 32000, returnPct: 5.26 },
      { id: 15, type: 'LONG', buyDate: '2026-04-21', buyPrice: 632, sellDate: '2026-05-08', sellPrice: 595, pnl: -37000, returnPct: -5.85 }
    ],
    equityCurve: []
  };

  // Generate equity curve from trades
  function generateEquityCurve() {
    const curve = [];
    let equity = 1000000;
    const startDate = new Date('2025-01-01');

    for (let i = 0; i < 350; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      if (d.getDay() === 0 || d.getDay() === 6) continue;

      // Random walk with slight upward bias
      const dailyReturn = (Math.random() - 0.46) * 0.012;
      equity *= (1 + dailyReturn);

      curve.push({
        date: `${d.getMonth() + 1}/${d.getDate()}`,
        fullDate: d.toISOString().split('T')[0],
        value: Math.round(equity)
      });
    }

    mockResults.equityCurve = curve;
  }

  function init() {
    if (!initialized) {
      generateEquityCurve();
      initialized = true;
    }
  }

  function run() {
    const stockCode = document.getElementById('bt-stock-code').value.trim();
    const startDate = document.getElementById('bt-start-date').value;
    const endDate = document.getElementById('bt-end-date').value;
    const bbPeriod = document.getElementById('bt-bb-period').value;
    const bbStd = document.getElementById('bt-bb-std').value;
    const capital = document.getElementById('bt-capital').value;

    if (!stockCode) {
      App.toast('請輸入股票代碼', 'warning');
      return;
    }

    const stockName = App.state.stocks[stockCode];
    if (!stockName) {
      App.toast(`找不到股票代碼 ${stockCode}`, 'error');
      return;
    }

    App.toast(`正在回測 ${stockCode} ${stockName}...`, 'info');

    // Simulate loading
    const btn = document.getElementById('bt-run-btn');
    btn.disabled = true;
    btn.textContent = '⏳ 回測中...';

    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = '🚀 開始回測';

      // Show results
      document.getElementById('bt-results').style.display = 'block';

      // Update summary
      document.getElementById('bt-total-return').textContent = mockResults.summary.totalReturn;
      document.getElementById('bt-win-rate').textContent = mockResults.summary.winRate;
      document.getElementById('bt-max-dd').textContent = mockResults.summary.maxDrawdown;
      document.getElementById('bt-sharpe').textContent = mockResults.summary.sharpeRatio;

      // Render charts and tables
      renderEquityCurve();
      renderTradeTable();

      // Scroll to results
      document.getElementById('bt-results').scrollIntoView({ behavior: 'smooth', block: 'start' });

      App.toast(`${stockCode} ${stockName} 回測完成！`, 'success');
    }, 1500);
  }

  function renderEquityCurve() {
    const canvas = document.getElementById('bt-equity-chart');
    if (!canvas) return;
    if (equityChartInstance) equityChartInstance.destroy();

    const data = mockResults.equityCurve;
    const labels = data.map(d => d.date);
    const values = data.map(d => d.value);

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(0, 230, 118, 0.25)');
    gradient.addColorStop(0.5, 'rgba(0, 212, 255, 0.1)');
    gradient.addColorStop(1, 'rgba(0, 212, 255, 0.0)');

    equityChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: '權益 (TWD)',
          data: values,
          borderColor: '#00e676',
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#00e676'
        }, {
          label: '基準線',
          data: new Array(values.length).fill(1000000),
          borderColor: 'rgba(255, 255, 255, 0.15)',
          borderWidth: 1,
          borderDash: [5, 5],
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: 'rgba(159, 168, 218, 0.6)',
              font: { family: "'Inter', sans-serif", size: 11 },
              usePointStyle: true,
              pointStyle: 'line',
              padding: 20
            }
          },
          tooltip: {
            backgroundColor: 'rgba(13, 19, 48, 0.95)',
            titleColor: '#e8eaf6',
            bodyColor: '#9fa8da',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            callbacks: {
              label: (ctx) => {
                if (ctx.datasetIndex === 0) {
                  const val = ctx.parsed.y;
                  const pnl = val - 1000000;
                  const pct = ((pnl / 1000000) * 100).toFixed(2);
                  return `權益: $${val.toLocaleString()} (${pnl >= 0 ? '+' : ''}${pct}%)`;
                }
                return `初始資金: $1,000,000`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.03)' },
            ticks: {
              color: 'rgba(159,168,218,0.6)',
              font: { size: 10 },
              maxTicksLimit: 12
            }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.03)' },
            ticks: {
              color: 'rgba(159,168,218,0.6)',
              font: { size: 10 },
              callback: (v) => '$' + (v / 1000000).toFixed(2) + 'M'
            }
          }
        }
      }
    });
  }

  function renderTradeTable() {
    const tbody = document.getElementById('bt-trade-tbody');
    if (!tbody) return;

    tbody.innerHTML = mockResults.trades.map(t => {
      const isProfit = t.pnl >= 0;
      return `
        <tr>
          <td>${t.id}</td>
          <td><span class="badge badge-buy">做多</span></td>
          <td>${t.buyDate}</td>
          <td style="font-variant-numeric:tabular-nums;">$${t.buyPrice.toLocaleString()}</td>
          <td>${t.sellDate}</td>
          <td style="font-variant-numeric:tabular-nums;">$${t.sellPrice.toLocaleString()}</td>
          <td style="color: ${isProfit ? 'var(--green)' : 'var(--red)'}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${isProfit ? '+' : ''}$${t.pnl.toLocaleString()}
          </td>
          <td style="color: ${isProfit ? 'var(--green)' : 'var(--red)'}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${isProfit ? '+' : ''}${t.returnPct}%
          </td>
        </tr>
      `;
    }).join('');
  }

  return { init, run };
})();
