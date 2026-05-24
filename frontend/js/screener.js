/* ============================================
   screener.js - Signal Screener Page
   台股布林訊號系統 - 實時 API 串接與更新
   ============================================ */

const Screener = (() => {
  let initialized = false;
  let autoRefreshTimer = null;
  let currentFilters = { signal: 'ALL', trend: 'ALL' };
  let screenerData = [];
  let isLoading = false;

  async function init() {
    if (!initialized) {
      setupFilters();
      initialized = true;
    }
    
    // 如果目前沒有資料，則顯示 Spinner 載入；如果有資料，先渲染並在背景靜態更新
    if (screenerData.length === 0) {
      await fetchData(false);
    } else {
      render();
      fetchData(false, true); // 背景靜態更新
    }
  }

  function setupFilters() {
    // 訊號篩選按鈕
    document.getElementById('screener-signal-filter').addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-filter');
      if (!btn) return;
      document.querySelectorAll('#screener-signal-filter .btn-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilters.signal = btn.dataset.value;
      render();
    });

    // 趨勢篩選按鈕
    document.getElementById('screener-trend-filter').addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-filter');
      if (!btn) return;
      document.querySelectorAll('#screener-trend-filter .btn-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilters.trend = btn.dataset.value;
      render();
    });

    // 自動更新開關
    const autoRefreshToggle = document.getElementById('screener-auto-refresh');
    if (autoRefreshToggle) {
      autoRefreshToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
          startAutoRefresh();
          App.toast('自動更新已啟用 (每30秒)', 'info');
        } else {
          stopAutoRefresh();
          App.toast('自動更新已停用', 'info');
        }
      });
    }
  }

  // ── 從後端取得篩選資料 ──────────────────────────────────
  async function fetchData(forceRefresh = false, isBackground = false) {
    if (isLoading) return;
    
    const refreshBtn = document.getElementById('screener-refresh-btn');
    const tbody = document.getElementById('screener-tbody');

    if (!isBackground) {
      isLoading = true;
      if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `<span>⏳</span> 掃描中...`;
      }
      
      // 顯示載入中的 Spinner 覆蓋
      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9" style="text-align:center; padding: 4rem 0;">
              <div class="loading-spinner" style="margin: 0 auto 1.25rem; width: 40px; height: 40px;"></div>
              <div style="color: var(--cyan); font-size: 0.95rem; font-weight: 500;">市場股票掃描中，請稍候...</div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">(首次掃描約需 3-5 秒，隨後將啟用 5 分鐘快取)</div>
            </td>
          </tr>
        `;
      }
    }

    try {
      const strategy = (App.state.settings && App.state.settings.activeStrategy) || 'bb';
      const res = await App.apiFetch(`/api/screener?force_refresh=${forceRefresh}&strategy=${strategy}`);
      if (res && res.results) {
        screenerData = res.results;
        
        // 更新最後更新時間
        const now = new Date();
        const formattedTime = now.toLocaleString('zh-TW', {
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit',
          hour12: false
        });
        
        const lastUpdatedEl = document.getElementById('screener-last-updated');
        if (lastUpdatedEl) {
          lastUpdatedEl.textContent = `最後更新：${formattedTime}`;
        }
      } else {
        if (!isBackground && tbody) {
          tbody.innerHTML = `
            <tr>
              <td colspan="9" style="text-align:center; color:var(--red); padding: 3rem 0;">
                ⚠️ 無法取得篩選結果，請確認後端服務已啟動。
              </td>
            </tr>
          `;
        }
        App.toast('掃描失敗，請確認後端連線', 'error');
      }
    } catch (err) {
      console.error('[Screener Fetch Error]', err);
      if (!isBackground && tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9" style="text-align:center; color:var(--red); padding: 3rem 0;">
              ⚠️ 掃描期間發生異常錯誤。
            </td>
          </tr>
        `;
      }
    } finally {
      if (!isBackground) {
        isLoading = false;
        if (refreshBtn) {
          refreshBtn.disabled = false;
          refreshBtn.innerHTML = `🔄 重新篩選`;
        }
      }
      render();
    }
  }

  function getFilteredData() {
    return screenerData.filter(item => {
      if (currentFilters.signal !== 'ALL' && item.signal_type !== currentFilters.signal) return false;
      if (currentFilters.trend !== 'ALL' && item.trend !== currentFilters.trend) return false;
      return true;
    });
  }

  function render() {
    const filtered = getFilteredData();
    
    // 儲存篩選後的股票 ID 列表，以利於「個股分析」頁面的左右鍵切換功能
    if (App.state) {
      App.state.screenerStockIds = filtered.map(item => item.stock_id);
    }

    const tbody = document.getElementById('screener-tbody');
    const countBadge = document.getElementById('screener-count');

    if (countBadge) countBadge.textContent = filtered.length;
    if (!tbody || isLoading) return;

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align:center; color:var(--text-secondary); padding: 3rem 0;">
            沒有符合當前篩選條件的訊號。
          </td>
        </tr>
      `;
      return;
    }

    // 找出結果中最晚（最新）的訊號日期作為判斷是否為新鮮訊號 (fresh) 的依據
    let latestDate = '';
    if (screenerData.length > 0) {
      latestDate = screenerData.reduce((max, r) => r.signal_date > max ? r.signal_date : max, '');
    }

    tbody.innerHTML = filtered.map(item => {
      const isBuy = item.signal_type === 'BUY';
      const signalClass = isBuy ? 'badge-buy' : 'badge-sell';
      const signalText = isBuy ? '買入' : '賣出';

      const trendMap = {
        UPTREND: { cls: 'badge-uptrend', text: '上升' },
        DOWNTREND: { cls: 'badge-downtrend', text: '下降' },
        SIDEWAYS: { cls: 'badge-sideways', text: '盤整' }
      };
      const trend = trendMap[item.trend] || { cls: 'badge-sideways', text: '盤整' };

      // 判斷是否為當日/最最新一天的訊號
      const isFresh = item.signal_date === latestDate;
      const freshClass = isFresh
        ? `fresh-signal ${!isBuy ? 'sell-signal' : ''}`
        : '';

      // 台灣股市漲跌顏色慣例：紅漲、綠跌、灰平
      const changeVal = item.change || 0.0;
      let changeColor = 'var(--text-secondary)';
      let changeText = '0.00%';
      if (changeVal > 0) {
        changeColor = 'var(--red)';
        changeText = `+${changeVal.toFixed(2)}%`;
      } else if (changeVal < 0) {
        changeColor = 'var(--green)';
        changeText = `${changeVal.toFixed(2)}%`;
      }

      return `
        <tr class="table-row-clickable" onclick="window.location.hash='analysis'; setTimeout(() => Analysis.loadStock('${item.stock_id}'), 300);">
          <td>
            <span class="signal-dot ${isBuy ? 'buy' : 'sell'} ${freshClass}"
              style="display:inline-block; width:8px; height:8px; border-radius:50%; ${isBuy
                ? 'background:var(--green); box-shadow:0 0 8px var(--green-glow);'
                : 'background:var(--red); box-shadow:0 0 8px var(--red-glow);'}">
            </span>
          </td>
          <td><strong>${item.stock_id}</strong></td>
          <td>${item.stock_name}</td>
          <td><span class="badge ${signalClass}">${signalText}</span></td>
          <td><span class="badge ${trend.cls}">${trend.text}</span></td>
          <td style="font-variant-numeric:tabular-nums;">$${item.price.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
          <td style="color: ${changeColor}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${changeText}
          </td>
          <td style="color:var(--text-secondary)">${item.signal_date}</td>
          <td>
            <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); window.location.hash='analysis'; setTimeout(() => Analysis.loadStock('${item.stock_id}'), 300);">
              📈 分析
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // 手動重新篩選
  function refresh() {
    App.toast('手動重新整理，開始強制掃描市場...', 'info');
    fetchData(true);
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    // 使用設定中的重新整理間隔，預設 30 秒
    const interval = (App.state.settings && App.state.settings.refreshInterval) || 30;
    autoRefreshTimer = setInterval(() => {
      fetchData(false, true); // 背景非強制刷新，讀取快取
    }, interval * 1000);
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  return { init, render, refresh };
})();
