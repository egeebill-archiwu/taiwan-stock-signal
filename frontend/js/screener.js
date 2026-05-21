/* ============================================
   screener.js - Signal Screener Page
   ============================================ */

const Screener = (() => {
  let initialized = false;
  let autoRefreshTimer = null;
  let currentFilters = { signal: 'ALL', trend: 'ALL' };

  // ---- Extended Mock Screener Data ----
  const mockScreenerData = [
    { code: '2330', name: '台積電', signal: 'BUY', trend: 'UPTREND', price: 595, change: 1.71, date: '2026-05-20', fresh: true },
    { code: '2454', name: '聯發科', signal: 'SELL', trend: 'DOWNTREND', price: 1280, change: -2.13, date: '2026-05-20', fresh: true },
    { code: '2317', name: '鴻海', signal: 'BUY', trend: 'UPTREND', price: 178, change: 0.85, date: '2026-05-20', fresh: true },
    { code: '2881', name: '富邦金', signal: 'BUY', trend: 'SIDEWAYS', price: 88.5, change: 0.34, date: '2026-05-19', fresh: false },
    { code: '3008', name: '大立光', signal: 'SELL', trend: 'DOWNTREND', price: 2150, change: -1.56, date: '2026-05-19', fresh: false },
    { code: '2303', name: '聯電', signal: 'BUY', trend: 'UPTREND', price: 52.3, change: 2.15, date: '2026-05-19', fresh: false },
    { code: '2412', name: '中華電', signal: 'BUY', trend: 'SIDEWAYS', price: 132, change: 0.12, date: '2026-05-18', fresh: false },
    { code: '2882', name: '國泰金', signal: 'SELL', trend: 'DOWNTREND', price: 65.2, change: -0.76, date: '2026-05-18', fresh: false },
    { code: '2891', name: '中信金', signal: 'BUY', trend: 'UPTREND', price: 33.8, change: 1.04, date: '2026-05-17', fresh: false },
    { code: '1301', name: '台塑', signal: 'SELL', trend: 'DOWNTREND', price: 73.5, change: -1.88, date: '2026-05-17', fresh: false },
    { code: '2308', name: '台達電', signal: 'BUY', trend: 'UPTREND', price: 385, change: 1.32, date: '2026-05-16', fresh: false },
    { code: '2886', name: '兆豐金', signal: 'BUY', trend: 'UPTREND', price: 45.6, change: 0.66, date: '2026-05-16', fresh: false },
    { code: '2357', name: '華碩', signal: 'SELL', trend: 'SIDEWAYS', price: 498, change: -0.42, date: '2026-05-16', fresh: false },
    { code: '2382', name: '廣達', signal: 'BUY', trend: 'UPTREND', price: 315, change: 3.28, date: '2026-05-15', fresh: false },
    { code: '3711', name: '日月光投控', signal: 'BUY', trend: 'UPTREND', price: 168, change: 1.45, date: '2026-05-15', fresh: false },
    { code: '2002', name: '中鋼', signal: 'SELL', trend: 'DOWNTREND', price: 25.3, change: -2.31, date: '2026-05-15', fresh: false },
    { code: '1303', name: '南亞', signal: 'SELL', trend: 'DOWNTREND', price: 58.7, change: -1.18, date: '2026-05-14', fresh: false },
    { code: '2884', name: '玉山金', signal: 'BUY', trend: 'SIDEWAYS', price: 29.4, change: 0.51, date: '2026-05-14', fresh: false },
    { code: '6505', name: '台塑化', signal: 'SELL', trend: 'DOWNTREND', price: 62.1, change: -1.74, date: '2026-05-14', fresh: false },
    { code: '2892', name: '第一金', signal: 'BUY', trend: 'UPTREND', price: 32.5, change: 0.93, date: '2026-05-13', fresh: false }
  ];

  function init() {
    if (!initialized) {
      setupFilters();
      initialized = true;
    }
    render();
  }

  function setupFilters() {
    // Signal filter buttons
    document.getElementById('screener-signal-filter').addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-filter');
      if (!btn) return;
      document.querySelectorAll('#screener-signal-filter .btn-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilters.signal = btn.dataset.value;
      render();
    });

    // Trend filter buttons
    document.getElementById('screener-trend-filter').addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-filter');
      if (!btn) return;
      document.querySelectorAll('#screener-trend-filter .btn-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilters.trend = btn.dataset.value;
      render();
    });

    // Auto-refresh toggle
    document.getElementById('screener-auto-refresh').addEventListener('change', (e) => {
      if (e.target.checked) {
        startAutoRefresh();
        App.toast('自動更新已啟用 (每30秒)', 'info');
      } else {
        stopAutoRefresh();
        App.toast('自動更新已停用', 'info');
      }
    });
  }

  function getFilteredData() {
    return mockScreenerData.filter(item => {
      if (currentFilters.signal !== 'ALL' && item.signal !== currentFilters.signal) return false;
      if (currentFilters.trend !== 'ALL' && item.trend !== currentFilters.trend) return false;
      return true;
    });
  }

  function render() {
    const filtered = getFilteredData();
    const tbody = document.getElementById('screener-tbody');
    const countBadge = document.getElementById('screener-count');

    if (countBadge) countBadge.textContent = filtered.length;

    if (!tbody) return;

    tbody.innerHTML = filtered.map(item => {
      const isUp = item.change >= 0;
      const signalClass = item.signal === 'BUY' ? 'badge-buy' : 'badge-sell';
      const signalText = item.signal === 'BUY' ? '買入' : '賣出';

      const trendMap = {
        UPTREND: { cls: 'badge-uptrend', text: '上升' },
        DOWNTREND: { cls: 'badge-downtrend', text: '下降' },
        SIDEWAYS: { cls: 'badge-sideways', text: '盤整' }
      };
      const trend = trendMap[item.trend] || trendMap.SIDEWAYS;

      const freshClass = item.fresh
        ? `fresh-signal ${item.signal === 'SELL' ? 'sell-signal' : ''}`
        : '';

      return `
        <tr class="table-row-clickable" onclick="window.location.hash='analysis'; setTimeout(() => Analysis.loadStock('${item.code}'), 300);">
          <td>
            <span class="signal-dot ${item.signal === 'BUY' ? 'buy' : 'sell'} ${freshClass}"
              style="display:inline-block; width:8px; height:8px; border-radius:50%; ${item.signal === 'BUY'
                ? 'background:var(--green); box-shadow:0 0 8px var(--green-glow);'
                : 'background:var(--red); box-shadow:0 0 8px var(--red-glow);'}">
            </span>
          </td>
          <td><strong>${item.code}</strong></td>
          <td>${item.name}</td>
          <td><span class="badge ${signalClass}">${signalText}</span></td>
          <td><span class="badge ${trend.cls}">${trend.text}</span></td>
          <td style="font-variant-numeric:tabular-nums;">$${item.price.toLocaleString()}</td>
          <td style="color: ${isUp ? 'var(--red)' : 'var(--green)'}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${isUp ? '+' : ''}${item.change}%
          </td>
          <td style="color:var(--text-secondary)">${item.date}</td>
          <td>
            <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); window.location.hash='analysis'; setTimeout(() => Analysis.loadStock('${item.code}'), 300);">
              📈 分析
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  function refresh() {
    App.toast('重新篩選中...', 'info');
    setTimeout(() => {
      render();
      App.toast('篩選結果已更新', 'success');
    }, 500);
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshTimer = setInterval(() => {
      render();
    }, 30000);
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  return { init, render, refresh };
})();
