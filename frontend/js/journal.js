/* ============================================
   journal.js - Trade Journal Page
   ============================================ */

const Journal = (() => {
  let initialized = false;
  let pnlChartInstance = null;
  let editingTradeId = null;

  // ---- Mock Trade Data ----
  let trades = [
    {
      id: 1, code: '2330', name: '台積電', direction: 'LONG',
      buyPrice: 545, buyTime: '2026-03-10T09:15',
      sellPrice: 592, sellTime: '2026-04-02T13:20',
      shares: 2000, notes: '布林下軌買入，突破中軌加碼',
      status: 'closed'
    },
    {
      id: 2, code: '2454', name: '聯發科', direction: 'LONG',
      buyPrice: 1220, buyTime: '2026-03-18T10:30',
      sellPrice: 1185, sellTime: '2026-03-28T11:00',
      shares: 500, notes: '跌破停損線出場',
      status: 'stoploss'
    },
    {
      id: 3, code: '2317', name: '鴻海', direction: 'LONG',
      buyPrice: 165, buyTime: '2026-04-05T09:05',
      sellPrice: 182, sellTime: '2026-04-25T14:15',
      shares: 5000, notes: '觸及布林上軌附近出場',
      status: 'closed'
    },
    {
      id: 4, code: '2881', name: '富邦金', direction: 'LONG',
      buyPrice: 84.5, buyTime: '2026-04-15T09:30',
      sellPrice: null, sellTime: null,
      shares: 10000, notes: '布林帶收縮後突破買入，持續觀察',
      status: 'holding'
    },
    {
      id: 5, code: '3008', name: '大立光', direction: 'LONG',
      buyPrice: 2080, buyTime: '2026-04-22T10:15',
      sellPrice: 2180, sellTime: '2026-05-08T13:45',
      shares: 300, notes: '突破上軌後回測中軌入場',
      status: 'closed'
    },
    {
      id: 6, code: '2303', name: '聯電', direction: 'LONG',
      buyPrice: 48.5, buyTime: '2026-04-28T09:10',
      sellPrice: 53.2, sellTime: '2026-05-12T14:00',
      shares: 10000, notes: '%B指標顯示超賣區進場',
      status: 'closed'
    },
    {
      id: 7, code: '2308', name: '台達電', direction: 'LONG',
      buyPrice: 370, buyTime: '2026-05-01T09:20',
      sellPrice: 355, sellTime: '2026-05-10T10:30',
      shares: 2000, notes: '假突破出場，止損',
      status: 'stoploss'
    },
    {
      id: 8, code: '2886', name: '兆豐金', direction: 'LONG',
      buyPrice: 43.8, buyTime: '2026-05-05T09:45',
      sellPrice: null, sellTime: null,
      shares: 15000, notes: '下軌支撐位入場，配合量能放大',
      status: 'holding'
    },
    {
      id: 9, code: '2412', name: '中華電', direction: 'LONG',
      buyPrice: 128, buyTime: '2026-05-08T10:00',
      sellPrice: 135, sellTime: '2026-05-18T13:30',
      shares: 3000, notes: '防禦型標的布林策略',
      status: 'closed'
    },
    {
      id: 10, code: '2382', name: '廣達', direction: 'LONG',
      buyPrice: 298, buyTime: '2026-05-12T09:30',
      sellPrice: null, sellTime: null,
      shares: 2000, notes: 'AI概念股布林通道突破',
      status: 'holding'
    },
    {
      id: 11, code: '2891', name: '中信金', direction: 'LONG',
      buyPrice: 32.5, buyTime: '2026-05-14T09:15',
      sellPrice: 34.2, sellTime: '2026-05-20T14:00',
      shares: 20000, notes: '短線布林波段操作',
      status: 'closed'
    },
    {
      id: 12, code: '2357', name: '華碩', direction: 'LONG',
      buyPrice: 510, buyTime: '2026-05-15T10:00',
      sellPrice: 495, sellTime: '2026-05-19T11:30',
      shares: 1000, notes: '趨勢反轉訊號出場',
      status: 'stoploss'
    }
  ];

  function init() {
    if (!initialized) {
      initialized = true;
    }
    render();
    renderPnlChart();
    updateSummary();
  }

  function calculatePnl(trade) {
    if (trade.sellPrice && trade.buyPrice) {
      return (trade.sellPrice - trade.buyPrice) * trade.shares;
    }
    return null;
  }

  function calculateReturnPct(trade) {
    if (trade.sellPrice && trade.buyPrice) {
      return ((trade.sellPrice - trade.buyPrice) / trade.buyPrice * 100).toFixed(2);
    }
    return null;
  }

  function updateSummary() {
    const closedTrades = trades.filter(t => t.status !== 'holding');
    const totalTrades = trades.length;
    const winners = closedTrades.filter(t => {
      const pnl = calculatePnl(t);
      return pnl !== null && pnl > 0;
    });
    const winRate = closedTrades.length > 0
      ? ((winners.length / closedTrades.length) * 100).toFixed(1)
      : '0.0';

    let totalPnl = 0;
    let totalReturnSum = 0;
    let returnCount = 0;
    closedTrades.forEach(t => {
      const pnl = calculatePnl(t);
      const ret = calculateReturnPct(t);
      if (pnl !== null) totalPnl += pnl;
      if (ret !== null) {
        totalReturnSum += parseFloat(ret);
        returnCount++;
      }
    });

    const avgReturn = returnCount > 0 ? (totalReturnSum / returnCount).toFixed(1) : '0.0';

    document.getElementById('jn-total-trades').textContent = totalTrades;
    document.getElementById('jn-win-rate').textContent = winRate + '%';
    document.getElementById('jn-total-pnl').textContent = (totalPnl >= 0 ? '+' : '') + '$' + totalPnl.toLocaleString();
    document.getElementById('jn-avg-return').textContent = (avgReturn >= 0 ? '+' : '') + avgReturn + '%';

    // Color the P&L stat
    const pnlEl = document.getElementById('jn-total-pnl');
    pnlEl.style.color = totalPnl >= 0 ? 'var(--green)' : 'var(--red)';
  }

  function render() {
    const tbody = document.getElementById('jn-trade-tbody');
    if (!tbody) return;

    tbody.innerHTML = trades.map(t => {
      const pnl = calculatePnl(t);
      const returnPct = calculateReturnPct(t);
      const isProfit = pnl !== null && pnl >= 0;

      const statusMap = {
        holding: { badge: 'badge-hold', text: '🟡 持有中', label: '持有中' },
        closed: { badge: 'badge-closed', text: '🟢 已了結', label: '已了結' },
        stoploss: { badge: 'badge-stoploss', text: '🔴 停損', label: '停損' }
      };
      const status = statusMap[t.status] || statusMap.holding;

      return `
        <tr>
          <td><span class="badge ${status.badge}">${status.label}</span></td>
          <td>
            <strong>${t.code}</strong>
            <br><span style="font-size:0.75rem; color:var(--text-secondary)">${t.name}</span>
          </td>
          <td><span class="badge badge-buy">做多</span></td>
          <td style="font-variant-numeric:tabular-nums;">
            $${t.buyPrice.toLocaleString()}
            <br><span style="font-size:0.7rem; color:var(--text-muted)">${formatDateTime(t.buyTime)}</span>
          </td>
          <td style="font-variant-numeric:tabular-nums;">
            ${t.sellPrice ? '$' + t.sellPrice.toLocaleString() : '<span style="color:var(--text-dim)">—</span>'}
            ${t.sellTime ? '<br><span style="font-size:0.7rem; color:var(--text-muted)">' + formatDateTime(t.sellTime) + '</span>' : ''}
          </td>
          <td style="font-variant-numeric:tabular-nums;">${t.shares.toLocaleString()}</td>
          <td style="color: ${pnl !== null ? (isProfit ? 'var(--green)' : 'var(--red)') : 'var(--text-dim)'}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${pnl !== null ? ((isProfit ? '+' : '') + '$' + pnl.toLocaleString()) : '—'}
          </td>
          <td style="color: ${returnPct !== null ? (parseFloat(returnPct) >= 0 ? 'var(--green)' : 'var(--red)') : 'var(--text-dim)'}; font-weight:600; font-variant-numeric:tabular-nums;">
            ${returnPct !== null ? ((parseFloat(returnPct) >= 0 ? '+' : '') + returnPct + '%') : '—'}
          </td>
          <td style="max-width:150px; font-size:0.78rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${t.notes}">
            ${t.notes}
          </td>
          <td>
            <div style="display:flex; gap:0.35rem;">
              <button class="btn btn-sm btn-ghost" onclick="Journal.openEditModal(${t.id})" title="編輯">✏️</button>
              <button class="btn btn-sm btn-ghost" onclick="Journal.deleteTrade(${t.id})" title="刪除" style="color:var(--red)">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  function formatDateTime(dtStr) {
    if (!dtStr) return '';
    const d = new Date(dtStr);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  }

  function renderPnlChart() {
    const canvas = document.getElementById('jn-pnl-chart');
    if (!canvas) return;
    if (pnlChartInstance) pnlChartInstance.destroy();

    // Build cumulative P&L from closed trades sorted by sell date
    const closedTrades = trades
      .filter(t => t.sellTime && t.sellPrice)
      .sort((a, b) => new Date(a.sellTime) - new Date(b.sellTime));

    let cumPnl = 0;
    const labels = ['起始'];
    const data = [0];

    closedTrades.forEach(t => {
      const pnl = calculatePnl(t);
      if (pnl !== null) {
        cumPnl += pnl;
        const d = new Date(t.sellTime);
        labels.push(`${t.code} ${d.getMonth() + 1}/${d.getDate()}`);
        data.push(cumPnl);
      }
    });

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 250);
    gradient.addColorStop(0, cumPnl >= 0 ? 'rgba(0, 230, 118, 0.25)' : 'rgba(255, 82, 82, 0.25)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    pnlChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: '累積損益 (TWD)',
          data,
          borderColor: cumPnl >= 0 ? '#00e676' : '#ff5252',
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: data.map(v => v >= 0 ? '#00e676' : '#ff5252'),
          pointBorderColor: data.map(v => v >= 0 ? '#00e676' : '#ff5252'),
          pointHoverRadius: 7,
          pointHoverBackgroundColor: '#fff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(13, 19, 48, 0.95)',
            titleColor: '#e8eaf6',
            bodyColor: '#9fa8da',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            callbacks: {
              label: (ctx) => `累積損益: ${ctx.parsed.y >= 0 ? '+' : ''}$${ctx.parsed.y.toLocaleString()}`
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.03)' },
            ticks: {
              color: 'rgba(159,168,218,0.6)',
              font: { size: 10 },
              maxRotation: 45
            }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.03)' },
            ticks: {
              color: 'rgba(159,168,218,0.6)',
              font: { size: 10 },
              callback: (v) => (v >= 0 ? '+' : '') + '$' + (v / 1000).toFixed(0) + 'K'
            }
          }
        }
      }
    });
  }

  // ---- Modal Operations ----
  function openAddModal() {
    editingTradeId = null;
    document.getElementById('modal-title').textContent = '新增交易';
    clearModalForm();
    App.openModal();
  }

  function openEditModal(tradeId) {
    const trade = trades.find(t => t.id === tradeId);
    if (!trade) return;

    editingTradeId = tradeId;
    document.getElementById('modal-title').textContent = '編輯交易';

    document.getElementById('modal-stock-code').value = trade.code;
    document.getElementById('modal-stock-name').value = trade.name;
    document.getElementById('modal-buy-price').value = trade.buyPrice;
    document.getElementById('modal-buy-time').value = trade.buyTime || '';
    document.getElementById('modal-shares').value = trade.shares;
    document.getElementById('modal-sell-price').value = trade.sellPrice || '';
    document.getElementById('modal-sell-time').value = trade.sellTime || '';
    document.getElementById('modal-notes').value = trade.notes || '';

    App.openModal();
  }

  function clearModalForm() {
    document.getElementById('modal-stock-code').value = '';
    document.getElementById('modal-stock-name').value = '';
    document.getElementById('modal-buy-price').value = '';
    document.getElementById('modal-buy-time').value = '';
    document.getElementById('modal-shares').value = '1000';
    document.getElementById('modal-sell-price').value = '';
    document.getElementById('modal-sell-time').value = '';
    document.getElementById('modal-notes').value = '';
  }

  function saveTrade() {
    const code = document.getElementById('modal-stock-code').value.trim();
    const buyPrice = parseFloat(document.getElementById('modal-buy-price').value);
    const buyTime = document.getElementById('modal-buy-time').value;
    const shares = parseInt(document.getElementById('modal-shares').value);
    const sellPrice = document.getElementById('modal-sell-price').value ? parseFloat(document.getElementById('modal-sell-price').value) : null;
    const sellTime = document.getElementById('modal-sell-time').value || null;
    const notes = document.getElementById('modal-notes').value.trim();

    if (!code || isNaN(buyPrice) || isNaN(shares)) {
      App.toast('請填寫必要欄位', 'warning');
      return;
    }

    const name = App.state.stocks[code] || document.getElementById('modal-stock-name').value || '未知';

    let status = 'holding';
    if (sellPrice) {
      status = sellPrice < buyPrice ? 'stoploss' : 'closed';
    }

    if (editingTradeId) {
      // Update existing trade
      const idx = trades.findIndex(t => t.id === editingTradeId);
      if (idx !== -1) {
        trades[idx] = {
          ...trades[idx],
          code, name, buyPrice, buyTime, sellPrice, sellTime, shares, notes, status
        };
      }
      App.toast('交易紀錄已更新', 'success');
    } else {
      // Add new trade
      const newId = trades.length > 0 ? Math.max(...trades.map(t => t.id)) + 1 : 1;
      trades.push({
        id: newId, code, name, direction: 'LONG',
        buyPrice, buyTime, sellPrice, sellTime, shares, notes, status
      });
      App.toast('交易紀錄已新增', 'success');
    }

    App.closeModal();
    render();
    renderPnlChart();
    updateSummary();
  }

  function deleteTrade(tradeId) {
    if (!confirm('確定要刪除此交易紀錄嗎？')) return;
    trades = trades.filter(t => t.id !== tradeId);
    render();
    renderPnlChart();
    updateSummary();
    App.toast('交易紀錄已刪除', 'info');
  }

  // Auto-fill stock name on code input
  document.addEventListener('input', (e) => {
    if (e.target.id === 'modal-stock-code') {
      const code = e.target.value.trim();
      const name = App.state.stocks[code] || '';
      document.getElementById('modal-stock-name').value = name;
    }
  });

  return { init, render, openAddModal, openEditModal, saveTrade, deleteTrade };
})();
