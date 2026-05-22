/* ============================================
   app.js - Main Application Controller
   台股布林訊號系統 v2.0 - 真實 API 版本
   ============================================ */

const App = (() => {
  // ---- Configuration ----
  // apiBase 用空字串表示相對路徑，這樣手機和雲端都能正確存取 API
  const CONFIG = {
    apiBase: '',   // 用相對路徑，自動對應任何伺服器 IP / 雲端網址
    refreshInterval: 30000,
    version: '2.1.0'
  };

  // ---- Global State ----
  const state = {
    currentPage: 'dashboard',
    settings: {},
    stocks: {
      '2330': '台積電', '2454': '聯發科', '2317': '鴻海',
      '2881': '富邦金', '3008': '大立光', '2303': '聯電',
      '2412': '中華電', '2882': '國泰金', '2891': '中信金',
      '1301': '台塑', '2886': '兆豐金', '3711': '日月光投控',
      '2308': '台達電', '2002': '中鋼', '1303': '南亞',
      '2884': '玉山金', '2357': '華碩', '2382': '廣達',
      '6505': '台塑化', '2892': '第一金', '2379': '瑞昱',
      '2395': '研華', '2408': '南亞科', '2474': '可成',
      '3045': '台灣大', '4904': '遠傳', '6415': '矽力-KY'
    },
    apiConnected: false,
    dashboardSignals: []
  };

  // ---- Page Titles ----
  const pageTitles = {
    dashboard: '儀表板',
    screener: '訊號篩選',
    analysis: '個股分析',
    backtest: '回測中心',
    journal: '交易紀錄',
    settings: '設定'
  };

  // ---- Init ----
  async function init() {
    loadSettings();
    setupRouter();
    setupSidebar();
    startClock();
    registerSW();

    handleRoute();

    // 更新載入畫面文字，提示使用者伺服器可能需要時間喚醒
    const loadingText = document.querySelector('.loading-text');
    if (loadingText) {
      loadingText.innerHTML = '正在連線後端伺服器...<br><small style="font-size:0.75rem; color:rgba(255,255,255,0.5); display:block; margin-top:8px;">(免費雲端主機喚醒中，首次載入可能需要 30 秒，請稍候)</small>';
    }

    // 設定定時器：如果 8 秒內沒連上，先關閉載入畫面並提示使用者
    let loadingScreenHidden = false;
    const hideTimeout = setTimeout(() => {
      if (!loadingScreenHidden) {
        const ls = document.getElementById('loading-screen');
        if (ls) ls.classList.add('hidden');
        loadingScreenHidden = true;
        toast('後端伺服器正在喚醒中，部分功能可能暫時無法使用，請稍候...', 'warning');
      }
    }, 8000);

    try {
      await checkApiConnection();
      if (state.apiConnected) {
        clearTimeout(hideTimeout);
        if (!loadingScreenHidden) {
          const ls = document.getElementById('loading-screen');
          if (ls) ls.classList.add('hidden');
          loadingScreenHidden = true;
          toast('伺服器連線成功！', 'success');
        }
      }
    } catch (e) {
      console.warn('[Init] API Check Error:', e);
    }

    console.log('[App] 台股布林訊號系統已啟動 v' + CONFIG.version);
  }

  // ---- API Connection Check ----
  async function checkApiConnection() {
    const res = await apiFetch('/health');
    const dot = document.querySelector('.status-dot');
    const txt = document.querySelector('.status-text');
    if (res) {
      state.apiConnected = true;
      if (dot) { dot.classList.remove('offline'); dot.classList.add('live'); }
      if (txt) txt.textContent = '後端連線中';
    } else {
      state.apiConnected = false;
      if (dot) { dot.classList.remove('live'); dot.classList.add('offline'); }
      if (txt) txt.textContent = '後端未連線';
    }
  }

  // ---- Router ----
  function setupRouter() {
    window.addEventListener('hashchange', handleRoute);
  }

  function handleRoute() {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    navigateTo(hash);
  }

  function navigateTo(page) {
    if (!pageTitles[page]) page = 'dashboard';

    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    const targetPage = document.getElementById('page-' + page);
    if (targetPage) {
      targetPage.classList.add('active');
      const inner = targetPage.querySelector('.page-inner');
      if (inner) {
        inner.classList.remove('fade-in');
        void inner.offsetWidth;
        inner.classList.add('fade-in');
      }
    }

    document.getElementById('page-title').textContent = pageTitles[page] || page;
    state.currentPage = page;

    switch (page) {
      case 'dashboard': initDashboard(); break;
      case 'screener': if (typeof Screener !== 'undefined') Screener.init(); break;
      case 'backtest': if (typeof Backtest !== 'undefined') Backtest.init(); break;
      case 'journal': if (typeof Journal !== 'undefined') Journal.init(); break;
      case 'settings': initSettings(); break;
    }

    closeMobileSidebar();
  }

  // ---- Sidebar ----
  function setupSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    const mobileBtn = document.getElementById('mobile-menu-btn');

    toggle.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
    mobileBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
      toggleBackdrop(sidebar.classList.contains('mobile-open'));
    });

    const backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';
    backdrop.id = 'sidebar-backdrop';
    backdrop.addEventListener('click', closeMobileSidebar);
    document.body.appendChild(backdrop);
  }

  function closeMobileSidebar() {
    document.getElementById('sidebar').classList.remove('mobile-open');
    toggleBackdrop(false);
  }

  function toggleBackdrop(show) {
    const backdrop = document.getElementById('sidebar-backdrop');
    if (backdrop) backdrop.classList.toggle('visible', show);
  }

  // ---- Clock ----
  function startClock() {
    function update() {
      const now = new Date();
      const str = now.toLocaleString('zh-TW', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false
      });
      const el = document.getElementById('topbar-clock');
      if (el) el.textContent = str;
    }
    update();
    setInterval(update, 1000);
  }

  // ---- Service Worker ----
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
  }

  // ---- API Helper ----
  async function apiFetch(endpoint, options = {}) {
    const url = CONFIG.apiBase + endpoint;
    try {
      const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('[API]', endpoint, err.message);
      return null;
    }
  }

  // ---- Toast Notifications ----
  function toast(message, type = 'info') {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-message">${message}</span>
    `;
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add('removing');
      setTimeout(() => el.remove(), 300);
    }, 3500);
  }

  // ---- Modal ----
  function openModal() { document.getElementById('modal-overlay').classList.add('open'); }
  function closeModal() { document.getElementById('modal-overlay').classList.remove('open'); }

  // ---- Dashboard ----
  async function initDashboard() {
    renderTrendChart();
    renderPnlChart();

    // 嘗試從後端取得最新訊號
    if (state.apiConnected || true) {
      const data = await apiFetch('/api/journal/stats');
      if (data) {
        updateDashboardStats(data);
      }
    }
    renderDashboardSignals();
  }

  function updateDashboardStats(data) {
    const stats = data.statistics || {};
    if (stats.total_pnl !== undefined) {
      const el = document.getElementById('dash-total-pnl');
      if (el) {
        const pnl = stats.total_pnl;
        el.textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toLocaleString();
        el.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';
      }
    }
    if (stats.win_rate !== undefined) {
      const el = document.getElementById('dash-win-rate');
      if (el) el.textContent = (stats.win_rate * 100).toFixed(1) + '%';
    }
  }

  function renderDashboardSignals() {
    const list = document.getElementById('dash-signal-list');
    if (!list) return;
    // 顯示提示訊息，引導用戶使用個股分析查詢真實訊號
    list.innerHTML = `
      <div style="padding:1rem; text-align:center; color:var(--text-secondary);">
        <div style="font-size:2rem; margin-bottom:0.5rem;">📊</div>
        <div style="margin-bottom:0.5rem;">前往「個股分析」查詢真實訊號</div>
        <div style="font-size:0.78rem; color:var(--text-muted);">資料來源：Yahoo Finance 即時行情</div>
        <button class="btn btn-sm btn-primary" style="margin-top:0.75rem"
          onclick="window.location.hash='analysis'">前往個股分析</button>
      </div>
    `;

    const tbody = document.getElementById('dash-top-performers');
    if (tbody) {
      tbody.innerHTML = `
        <tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:1rem">
          請先在個股分析頁面查詢股票，歷史訊號將顯示於此
        </td></tr>
      `;
    }
  }

  function refreshSignals() {
    toast('重新整理中...', 'info');
    checkApiConnection().then(() => {
      initDashboard();
      toast('已更新', 'success');
    });
  }

  let trendChartInstance = null;
  function renderTrendChart() {
    const canvas = document.getElementById('dash-trend-chart');
    if (!canvas) return;
    if (trendChartInstance) trendChartInstance.destroy();
    const ctx = canvas.getContext('2d');
    trendChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['上升趨勢', '下降趨勢', '盤整'],
        datasets: [{ data: [0, 0, 0],
          backgroundColor: ['rgba(0,230,118,0.8)', 'rgba(255,82,82,0.8)', 'rgba(92,107,192,0.5)'],
          borderColor: ['rgba(0,230,118,1)', 'rgba(255,82,82,1)', 'rgba(92,107,192,1)'],
          borderWidth: 2, hoverOffset: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(13,19,48,0.95)', titleColor: '#e8eaf6',
            bodyColor: '#9fa8da', borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1, cornerRadius: 8, padding: 12,
            callbacks: { label: (c) => ` ${c.label}: ${c.parsed} 檔` }
          }
        }
      }
    });
    const legendEl = document.getElementById('dash-trend-legend');
    if (legendEl) {
      legendEl.innerHTML = `
        <div class="trend-legend-item"><div class="trend-legend-dot" style="background:var(--green)"></div>使用個股分析取得真實趨勢</div>
      `;
    }
  }

  let pnlChartInstance = null;
  function renderPnlChart() {
    const canvas = document.getElementById('dash-pnl-chart');
    if (!canvas) return;
    if (pnlChartInstance) pnlChartInstance.destroy();
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(0,212,255,0.3)');
    gradient.addColorStop(1, 'rgba(0,212,255,0)');
    pnlChartInstance = new Chart(ctx, {
      type: 'line',
      data: { labels: ['等待交易紀錄...'], datasets: [{ label: '累積損益', data: [0],
        borderColor: '#00d4ff', backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.4,
        pointRadius: 0 }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: 'rgba(159,168,218,0.6)', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: 'rgba(159,168,218,0.6)', font: { size: 10 },
            callback: (v) => '$' + (v / 1000).toFixed(0) + 'K' } }
        }
      }
    });
  }

  // ---- Settings Page ----
  function initSettings() {
    const s = state.settings;
    // 如果沒有儲存的 API 網址，則根據當前網域自動推導預設值
    const defaultApiUrl = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? 'http://localhost:8000'
      : window.location.origin;

    setVal('set-api-url', s.apiUrl !== undefined ? s.apiUrl : defaultApiUrl);
    setVal('set-bb-period', s.bbPeriod || 20);
    setVal('set-bb-std', s.bbStd || 2.0);
    setVal('set-refresh-interval', s.refreshInterval || 30);
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }

  function loadSettings() {
    try {
      const raw = localStorage.getItem('bb-signal-settings');
      if (raw) {
        state.settings = JSON.parse(raw);
      }
    } catch (e) {}

    // 動態判斷 API Base URL，避免手機或雲端連線到錯誤的 localhost
    const hostname = window.location.hostname;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';

    if (state.settings.apiUrl) {
      const url = state.settings.apiUrl;
      const isUrlLocal = url.includes('localhost') || url.includes('127.0.0.1');

      if (!isLocalhost && isUrlLocal) {
        // 如果是在行動裝置或雲端存取，但設定值是 localhost，則忽略設定改用相對路徑
        CONFIG.apiBase = '';
      } else {
        CONFIG.apiBase = url;
      }
    } else {
      CONFIG.apiBase = '';
    }
  }

  return {
    init, navigateTo, apiFetch, toast, openModal, closeModal,
    refreshSignals, checkApiConnection, state, CONFIG
  };
})();

/* ---- Settings Module ---- */
const Settings = (() => {
  function testConnection() {
    const url = document.getElementById('set-api-url').value;
    App.toast('測試連線中...', 'info');
    fetch(url + '/health', { signal: AbortSignal.timeout(5000) })
      .then(res => {
        if (res.ok) App.toast('連線成功！後端伺服器運行正常', 'success');
        else App.toast('伺服器回應異常: HTTP ' + res.status, 'warning');
      })
      .catch(() => App.toast('無法連接後端，請確認服務是否啟動', 'error'));
  }

  function save() {
    const apiUrlInput = document.getElementById('set-api-url').value.trim();
    const settings = {
      apiUrl: apiUrlInput,
      bbPeriod: parseInt(document.getElementById('set-bb-period').value),
      bbStd: parseFloat(document.getElementById('set-bb-std').value),
      maType: document.getElementById('set-ma-type').value,
      desktopNotify: document.getElementById('set-desktop-notify').checked,
      soundNotify: document.getElementById('set-sound-notify').checked,
      refreshInterval: parseInt(document.getElementById('set-refresh-interval').value),
      candleConvention: document.getElementById('set-candle-convention').value,
      chartPeriod: parseInt(document.getElementById('set-chart-period').value)
    };
    App.state.settings = settings;

    // 動態設定 CONFIG.apiBase，防止在非本機環境下存取 localhost
    const hostname = window.location.hostname;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
    const isUrlLocal = settings.apiUrl.includes('localhost') || settings.apiUrl.includes('127.0.0.1');

    if (!isLocalhost && isUrlLocal) {
      App.CONFIG.apiBase = '';
    } else {
      App.CONFIG.apiBase = settings.apiUrl;
    }

    localStorage.setItem('bb-signal-settings', JSON.stringify(settings));
    localStorage.setItem('bb-api-url', settings.apiUrl);
    App.toast('設定已儲存', 'success');
  }

  function reset() {
    localStorage.removeItem('bb-signal-settings');
    localStorage.removeItem('bb-api-url');
    App.state.settings = {};
    
    const defaultApiUrl = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? 'http://localhost:8000'
      : window.location.origin;

    setVal('set-api-url', defaultApiUrl);
    setVal('set-api-key', '');
    setVal('set-bb-period', 20);
    setVal('set-bb-std', 2.0);
    document.getElementById('set-ma-type').value = 'SMA';
    document.getElementById('set-desktop-notify').checked = true;
    document.getElementById('set-sound-notify').checked = false;
    setVal('set-refresh-interval', 30);
    document.getElementById('set-candle-convention').value = 'TW';
    document.getElementById('set-chart-period').value = 90;
    
    App.CONFIG.apiBase = ''; // 重置為預設相對路徑
    App.toast('設定已重置', 'info');
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }

  return { testConnection, save, reset };
})();

/* ============================================
   Analysis Module - 真實 API 版本
   從後端取得真實股價 + 指標 + 訊號
   ============================================ */
const Analysis = (() => {
  let currentStock = null;
  let chartInstance = null;
  let currentPeriod = '6mo';

  const periodMap = {
    '30': '1mo', '90': '3mo', '180': '6mo', '365': '1y', '730': '2y'
  };

  function searchStock() {
    const input = document.getElementById('analysis-search').value.trim();
    if (!input) { App.toast('請輸入股票代碼', 'warning'); return; }
    const code = input.split(' ')[0].replace(/\D/g, '');
    if (!code) { App.toast('請輸入有效的股票代碼', 'warning'); return; }
    loadStock(code);
  }

  async function loadStock(code) {
    // 支援有或沒有 .TW 後綴
    const cleanCode = code.replace(/\.TW(O)?$/i, '');
    const name = App.state.stocks[cleanCode] || `${cleanCode}`;

    currentStock = { code: cleanCode, name };
    document.getElementById('analysis-search').value = `${cleanCode} ${name}`;

    App.toast(`載入 ${cleanCode} ${name} 中...`, 'info');

    // Show loading state
    document.getElementById('analysis-stock-header').style.display = 'flex';
    document.getElementById('analysis-chart-card').style.display = 'block';
    document.getElementById('analysis-details').style.display = 'grid';
    document.getElementById('analysis-price').textContent = '載入中...';

    await Promise.all([
      fetchAndRenderChart(cleanCode),
      fetchAndRenderSignals(cleanCode)
    ]);
  }

  // ── 取得股價資料並繪製圖表 ──────────────────────────────
  async function fetchAndRenderChart(code) {
    const container = document.getElementById('analysis-chart-container');
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">資料載入中...</div>';

    const data = await App.apiFetch(`/api/stock/${code}/data?period=${currentPeriod}`);

    if (!data || !data.data || data.data.length === 0) {
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red)">⚠️ 無法取得股價資料，請確認股票代碼是否正確</div>';
      App.toast(`無法取得 ${code} 資料`, 'error');
      return;
    }

    const rows = data.data;
    const lastRow = rows[rows.length - 1];
    const prevRow = rows.length > 1 ? rows[rows.length - 2] : lastRow;

    // ── 更新股票標頭資訊（真實價格！）──
    const close = lastRow.close;
    const prevClose = prevRow.close;
    const changeAbs = (close - prevClose).toFixed(2);
    const changePct = ((close - prevClose) / prevClose * 100).toFixed(2);
    const isUp = close >= prevClose;

    document.getElementById('analysis-code').textContent = code;
    document.getElementById('analysis-name').textContent = App.state.stocks[code] || code;
    document.getElementById('analysis-price').textContent = close.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const changeEl = document.getElementById('analysis-change');
    changeEl.textContent = `${isUp ? '+' : ''}${changeAbs} (${isUp ? '+' : ''}${changePct}%)`;
    changeEl.className = `stock-change ${isUp ? 'up' : 'down'}`;

    // ── 繪製 K 線圖（真實資料）──
    const candles = rows
      .filter(r => r.open && r.high && r.low && r.close && r.date)
      .map(r => ({
        time: r.date.substring(0, 10),   // YYYY-MM-DD
        open: r.open,
        high: r.high,
        low: r.low,
        close: r.close,
        volume: r.volume || 0
      }));

    // 布林通道資料（來自後端已計算）
    const bbData = rows.filter(r => r.BBU && r.BBM && r.BBL && r.date).map(r => ({
      time: r.date.substring(0, 10),
      upper: r.BBU,
      middle: r.BBM,
      lower: r.BBL
    }));

    const maData = rows.filter(r => r.MA && r.date).map(r => ({
      time: r.date.substring(0, 10),
      value: r.MA
    }));

    if (typeof StockChart !== 'undefined') {
      container.innerHTML = '';
      chartInstance = StockChart.createStockChart('analysis-chart-container', candles);
      if (bbData.length > 0) {
        StockChart.addBollingerBandsFromData(chartInstance, bbData);
      } else {
        StockChart.addBollingerBands(chartInstance, candles);
      }
      if (maData.length > 0) {
        StockChart.addMAFromData(chartInstance, maData, '#b388ff');
      }
    }

    // ── 更新布林指標數值 ──
    renderIndicators(lastRow);

    App.toast(`${code} 資料載入完成（${rows.length} 天）`, 'success');
  }

  // ── 取得訊號並標示在圖上 ──────────────────────────────
  async function fetchAndRenderSignals(code) {
    const sigData = await App.apiFetch(`/api/stock/${code}/signals?period=${currentPeriod}`);

    const signalBadge = document.getElementById('analysis-signal-badge');
    const trendBadge = document.getElementById('analysis-trend-badge');

    if (!sigData) {
      signalBadge.textContent = '無法取得訊號';
      signalBadge.className = 'badge';
      return;
    }

    const signals = sigData.signals || [];
    const signalCount = sigData.signal_count || 0;

    // 最新訊號
    const latestSignal = signals.length > 0 ? signals[signals.length - 1] : null;

    if (latestSignal) {
      signalBadge.textContent = latestSignal.signal_type === 'BUY' ? '買入訊號' : '賣出訊號';
      signalBadge.className = `badge ${latestSignal.signal_type === 'BUY' ? 'badge-buy' : 'badge-sell'}`;

      const trendLabels = { UPTREND: '上升趨勢', DOWNTREND: '下降趨勢', SIDEWAYS: '盤整' };
      trendBadge.textContent = trendLabels[latestSignal.trend_direction] || '判斷中';
      trendBadge.className = `badge badge-${(latestSignal.trend_direction || 'sideways').toLowerCase()}`;
    } else {
      signalBadge.textContent = `無訊號（共掃描 ${currentPeriod}）`;
      signalBadge.className = 'badge';
      trendBadge.textContent = '趨勢判斷中';
      trendBadge.className = 'badge';
    }

    // 把訊號標記加到圖上
    if (chartInstance && signals.length > 0 && typeof StockChart !== 'undefined') {
      const markers = signals.map(s => ({
        time: s.date,
        position: s.signal_type === 'BUY' ? 'belowBar' : 'aboveBar',
        color: s.signal_type === 'BUY' ? '#00e676' : '#ff5252',
        shape: s.signal_type === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: s.signal_type === 'BUY' ? '買' : '賣'
      }));
      StockChart.addSignalMarkers(chartInstance, markers);
    }

    // 歷史訊號列表
    renderSignalHistory(signals);
  }

  function renderIndicators(row) {
    const grid = document.getElementById('analysis-bb-indicators');
    if (!grid) return;

    const close = row.close || 0;
    const upper = row.BBU || (close * 1.06);
    const middle = row.BBM || close;
    const lower = row.BBL || (close * 0.94);
    const ma = row.MA || close;
    const bandwidth = upper > 0 ? ((upper - lower) / middle * 100).toFixed(2) : '--';
    const pbr = (upper - lower) > 0 ? (((close - lower) / (upper - lower)) * 100).toFixed(1) : '--';
    const trend = row.trend || '--';
    const trendLabels = { UPTREND: '⬆️ 上升趨勢', DOWNTREND: '⬇️ 下降趨勢', SIDEWAYS: '➡️ 盤整' };

    grid.innerHTML = `
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--red)">${upper ? upper.toLocaleString('zh-TW', {minimumFractionDigits:2,maximumFractionDigits:2}) : '--'}</div>
        <div class="indicator-label">上軌 (BBU)</div>
      </div>
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--gold)">${middle ? middle.toLocaleString('zh-TW', {minimumFractionDigits:2,maximumFractionDigits:2}) : '--'}</div>
        <div class="indicator-label">中軌 (MA20)</div>
      </div>
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--green)">${lower ? lower.toLocaleString('zh-TW', {minimumFractionDigits:2,maximumFractionDigits:2}) : '--'}</div>
        <div class="indicator-label">下軌 (BBL)</div>
      </div>
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--purple)">${ma ? ma.toLocaleString('zh-TW', {minimumFractionDigits:2,maximumFractionDigits:2}) : '--'}</div>
        <div class="indicator-label">MA10</div>
      </div>
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--cyan)">${bandwidth}%</div>
        <div class="indicator-label">布林帶寬</div>
      </div>
      <div class="indicator-item">
        <div class="indicator-value" style="color:var(--gold)">${pbr}%</div>
        <div class="indicator-label">%B 指標</div>
      </div>
      <div class="indicator-item" style="grid-column:span 2">
        <div class="indicator-value" style="font-size:0.9rem">${trendLabels[trend] || trend}</div>
        <div class="indicator-label">趨勢判斷</div>
      </div>
    `;
  }

  function renderSignalHistory(signals) {
    const tbody = document.getElementById('analysis-signal-history');
    if (!tbody) return;

    if (!signals || signals.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:1rem">
        此期間無訊號<br><small>可嘗試延長查詢期間（1Y 或 2Y）</small>
      </td></tr>`;
      return;
    }

    // 顯示最近 10 個訊號，由新到舊
    const sorted = [...signals].reverse().slice(0, 10);
    tbody.innerHTML = sorted.map(s => {
      const trendLabels = { UPTREND: '上升', DOWNTREND: '下降', SIDEWAYS: '盤整' };
      return `
        <tr>
          <td>${s.date}</td>
          <td><span class="badge ${s.signal_type === 'BUY' ? 'badge-buy' : 'badge-sell'}">${s.signal_type === 'BUY' ? '買入' : '賣出'}</span></td>
          <td style="font-variant-numeric:tabular-nums">$${s.price.toLocaleString('zh-TW', {minimumFractionDigits:2,maximumFractionDigits:2})}</td>
          <td style="color:var(--text-secondary);font-size:0.78rem">${trendLabels[s.trend_direction] || s.trend_direction}</td>
        </tr>
      `;
    }).join('');
  }

  // ── 切換時間區間 ──────────────────────────────────────
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('#analysis-period-btns .btn-filter');
    if (!btn) return;
    document.querySelectorAll('#analysis-period-btns .btn-filter').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPeriod = periodMap[btn.dataset.period] || '6mo';
    if (currentStock) loadStock(currentStock.code);
  });

  return { searchStock, loadStock };
})();
