/* ============================================
   chart.js - K-Line Chart with Lightweight Charts
   Taiwan Convention: Red = UP, Green = DOWN
   ============================================ */

const StockChart = (() => {
  let activeChart = null;
  let activeSubChart = null;
  let activeCandleSeries = null;
  let resizeObserver = null;
  let subResizeObserver = null;

  // ---- Color Config (Taiwan Convention) ----
  const COLORS = {
    upColor: '#ff5252',        // Red for UP (台灣慣例)
    downColor: '#00e676',      // Green for DOWN
    wickUpColor: '#ff5252',
    wickDownColor: '#00e676',
    borderUpColor: '#ff5252',
    borderDownColor: '#00e676',
    bbUpper: '#ff5252',        // Upper band - red dashed
    bbMiddle: '#ffd700',       // Middle - yellow
    bbLower: '#00e676',        // Lower band - green dashed
    volume: 'rgba(0, 212, 255, 0.2)',
    grid: 'rgba(255, 255, 255, 0.03)',
    text: 'rgba(159, 168, 218, 0.6)',
    crosshair: 'rgba(0, 212, 255, 0.4)',
    background: 'transparent'
  };

  // ---- Generate Mock OHLC Data ----
  function generateMockOHLC(basePrice, days = 90) {
    const candles = [];
    let price = basePrice;
    const startDate = new Date('2026-05-20');
    startDate.setDate(startDate.getDate() - days);

    for (let i = 0; i < days; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);

      // Skip weekends
      if (d.getDay() === 0 || d.getDay() === 6) continue;

      const volatility = price * 0.025;
      const drift = (Math.random() - 0.48) * volatility;
      const open = price + (Math.random() - 0.5) * volatility * 0.5;
      const close = open + drift;
      const high = Math.max(open, close) + Math.random() * volatility * 0.6;
      const low = Math.min(open, close) - Math.random() * volatility * 0.6;

      candles.push({
        time: d.toISOString().split('T')[0],
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        volume: Math.floor(Math.random() * 30000 + 5000)
      });

      price = close;
    }

    return { candles };
  }

  // ---- Update Custom Markers (Vertical Dashed Lines & Labels) ----
  function updateCustomMarkers(chartObj) {
    if (!chartObj || !chartObj.chart || !chartObj.containerId) return;
    const container = document.getElementById(chartObj.containerId);
    if (!container) return;
    const svg = container.querySelector('.chart-overlay-svg');
    if (!svg) return;

    svg.innerHTML = ''; // Clear previous

    const { chart, candleSeries, signals, candles } = chartObj;
    if (!signals || signals.length === 0 || !candles || candles.length === 0) return;

    const chartWidth = container.clientWidth;
    const chartHeight = container.clientHeight || 450;

    signals.forEach(s => {
      const timeStr = s.time;
      const x = chart.timeScale().timeToCoordinate(timeStr);
      if (x === null || x < 0 || x > chartWidth) return;

      const candle = candles.find(c => c.time === timeStr);
      if (!candle) return;

      const isBuy = s.shape === 'arrowUp';
      const color = isBuy ? '#00e676' : '#ff5252';
      const text = isBuy ? '訊號' : '賣出';

      let y1, y2, textY;
      if (isBuy) {
        // BUY: Green vertical dashed line from below candle to bottom, above volume area
        const yLow = candleSeries.priceToCoordinate(candle.low);
        if (yLow === null) return;
        
        y1 = yLow + 12; // offset below arrow
        const targetTextY = chartHeight * 0.78; // place label above the bottom 15% volume area
        
        if (yLow + 25 < targetTextY) {
          textY = targetTextY;
        } else {
          textY = yLow + 25;
        }
        
        y2 = textY - 8; // line ends just above label
        y2 = Math.max(y2, y1 + 4); // ensure line goes downwards
      } else {
        // SELL: Red vertical dashed line from above candle to top
        const yHigh = candleSeries.priceToCoordinate(candle.high);
        if (yHigh === null) return;
        
        y1 = yHigh - 12; // offset above arrow
        const targetTextY = 18; // place label near the top
        
        if (yHigh - 25 > targetTextY) {
          textY = targetTextY;
        } else {
          textY = Math.max(yHigh - 25, 12);
        }
        
        y2 = textY + 4; // line ends just below label
        y2 = Math.min(y2, y1 - 4); // ensure line goes upwards
      }

      // Draw background rect for readability
      const textBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      const bgWidth = isBuy ? 32 : 40;
      const bgHeight = 16;
      textBg.setAttribute("x", x - bgWidth / 2);
      textBg.setAttribute("y", textY - 12);
      textBg.setAttribute("width", bgWidth);
      textBg.setAttribute("height", bgHeight);
      textBg.setAttribute("fill", "rgba(10, 14, 39, 0.9)");
      textBg.setAttribute("rx", "3");
      textBg.setAttribute("ry", "3");
      svg.appendChild(textBg);

      // Draw text label
      const textEl = document.createElementNS("http://www.w3.org/2000/svg", "text");
      textEl.setAttribute("x", x);
      textEl.setAttribute("y", textY);
      textEl.setAttribute("fill", color);
      textEl.setAttribute("text-anchor", "middle");
      textEl.setAttribute("font-size", "11");
      textEl.setAttribute("font-weight", "bold");
      textEl.textContent = text;
      svg.appendChild(textEl);

      // Draw vertical dashed line
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x);
      line.setAttribute("y2", isBuy ? textY - 12 : textY + 4);
      line.setAttribute("stroke", color);
      line.setAttribute("stroke-width", "1");
      line.setAttribute("stroke-dasharray", "3,3");
      line.setAttribute("opacity", "0.75");
      svg.appendChild(line);
    });
  }

  // ---- Create Stock Chart ----
  function createStockChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    container.innerHTML = '';
    container.style.position = 'relative'; // Ensure relative positioning for absolute child overlay

    // Clean up previous
    if (activeChart) {
      activeChart.remove();
      activeChart = null;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }

    const chart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 450,
      layout: {
        background: { type: 'solid', color: COLORS.background },
        textColor: COLORS.text,
        fontFamily: "'Inter', sans-serif",
        fontSize: 11
      },
      grid: {
        vertLines: { color: COLORS.grid },
        horzLines: { color: COLORS.grid }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: COLORS.crosshair, width: 1, style: 2, labelBackgroundColor: '#1a1f42' },
        horzLine: { color: COLORS.crosshair, width: 1, style: 2, labelBackgroundColor: '#1a1f42' }
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        scaleMargins: { top: 0.1, bottom: 0.2 }
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        timeVisible: false,
        dayVisible: true
      },
      handleScroll: { vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true }
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: COLORS.upColor,
      downColor: COLORS.downColor,
      borderUpColor: COLORS.borderUpColor,
      borderDownColor: COLORS.borderDownColor,
      wickUpColor: COLORS.wickUpColor,
      wickDownColor: COLORS.wickDownColor
    });

    candleSeries.setData(data);

    // Volume histogram (Overlaid on main chart as background)
    const volumeSeries = chart.addHistogramSeries({
      color: COLORS.volume,
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume'
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 }
    });

    const volumeData = data.map(d => ({
      time: d.time,
      value: d.volume || Math.floor(Math.random() * 20000 + 5000),
      color: d.close >= d.open
        ? 'rgba(255, 82, 82, 0.25)'
        : 'rgba(0, 230, 118, 0.25)'
    }));
    volumeSeries.setData(volumeData);

    // Create SVG overlay for custom markers (vertical dashed lines & text labels)
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "chart-overlay-svg");
    svg.style.position = 'absolute';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.pointerEvents = 'none';
    svg.style.zIndex = '5';
    container.appendChild(svg);

    const chartObj = { chart, candleSeries, volumeSeries, containerId, candles: data, signals: [] };

    // Fit content
    chart.timeScale().fitContent();

    // Resize handler
    let lastWidth = 0;
    resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
        if (width > 0 && (lastWidth === 0 || Math.abs(width - lastWidth) > 50)) {
          chart.timeScale().fitContent();
        }
        lastWidth = width;
        // Redraw custom markers on resize
        updateCustomMarkers(chartObj);
      }
    });
    resizeObserver.observe(container);

    // Subscribe to timescale visible range change to redraw overlay in real-time
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      updateCustomMarkers(chartObj);
    });

    activeChart = chart;
    activeCandleSeries = candleSeries;

    return chartObj;
  }

  // ---- Render Sub Chart for Indicators ----
  function renderSubChart(containerId, rawData, indicator, mainChartObj) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    container.innerHTML = '';

    if (activeSubChart) {
      activeSubChart.remove();
      activeSubChart = null;
    }
    if (subResizeObserver) {
      subResizeObserver.disconnect();
      subResizeObserver = null;
    }

    if (!rawData || rawData.length === 0) {
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">無副圖表資料</div>';
      return null;
    }

    // Filter and map data
    const items = rawData.filter(r => r.date).map(r => ({
      time: r.date.substring(0, 10),
      open: r.open,
      high: r.high,
      low: r.low,
      close: r.close,
      volume: r.volume || 0,
      K: r.K,
      D: r.D,
      macd_dif: r.macd_dif,
      macd_dea: r.macd_dea,
      macd_hist: r.macd_hist,
      RSI: r.RSI,
      foreign_net: r.foreign_net,
      trust_net: r.trust_net,
      dealer_net: r.dealer_net,
      major_net: r.major_net,
      retail_net: r.retail_net
    }));

    const subChart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 150,
      layout: {
        background: { type: 'solid', color: COLORS.background },
        textColor: COLORS.text,
        fontFamily: "'Inter', sans-serif",
        fontSize: 11
      },
      grid: {
        vertLines: { color: COLORS.grid },
        horzLines: { color: COLORS.grid }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: COLORS.crosshair, width: 1, style: 2, labelBackgroundColor: '#1a1f42' },
        horzLine: { color: COLORS.crosshair, width: 1, style: 2, labelBackgroundColor: '#1a1f42' }
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        scaleMargins: { top: 0.15, bottom: 0.15 }
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.06)',
        timeVisible: false,
        dayVisible: true
      },
      handleScroll: { vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true }
    });

    activeSubChart = subChart;

    // Draw series based on indicator type
    if (indicator === 'volume') {
      const volumeSeries = subChart.addHistogramSeries({
        color: COLORS.volume,
        priceFormat: { type: 'volume' },
      });
      const volData = items.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(255, 82, 82, 0.5)' : 'rgba(0, 230, 118, 0.5)'
      }));
      volumeSeries.setData(volData);

    } else if (indicator === 'kd') {
      const kSeries = subChart.addLineSeries({ color: '#00d4ff', lineWidth: 1.5, priceLineVisible: false });
      kSeries.setData(items.filter(d => d.K !== null).map(d => ({ time: d.time, value: d.K })));

      const dSeries = subChart.addLineSeries({ color: '#ffd700', lineWidth: 1.5, priceLineVisible: false });
      dSeries.setData(items.filter(d => d.D !== null).map(d => ({ time: d.time, value: d.D })));

      kSeries.createPriceLine({
        price: 80, color: 'rgba(255, 82, 82, 0.3)', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '超買'
      });
      kSeries.createPriceLine({
        price: 20, color: 'rgba(0, 230, 118, 0.3)', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '超賣'
      });

    } else if (indicator === 'macd') {
      const difSeries = subChart.addLineSeries({ color: '#00d4ff', lineWidth: 1.5, priceLineVisible: false });
      difSeries.setData(items.filter(d => d.macd_dif !== null).map(d => ({ time: d.time, value: d.macd_dif })));

      const deaSeries = subChart.addLineSeries({ color: '#ffd700', lineWidth: 1.5, priceLineVisible: false });
      deaSeries.setData(items.filter(d => d.macd_dea !== null).map(d => ({ time: d.time, value: d.macd_dea })));

      const histSeries = subChart.addHistogramSeries({
        priceFormat: { type: 'custom', formatter: v => v.toFixed(2) }
      });
      histSeries.setData(items.filter(d => d.macd_hist !== null).map(d => ({
        time: d.time,
        value: d.macd_hist,
        color: d.macd_hist >= 0 ? 'rgba(255, 82, 82, 0.6)' : 'rgba(0, 230, 118, 0.6)'
      })));

    } else if (indicator === 'rsi') {
      const rsiSeries = subChart.addLineSeries({ color: '#b388ff', lineWidth: 1.5, priceLineVisible: false });
      rsiSeries.setData(items.filter(d => d.RSI !== null).map(d => ({ time: d.time, value: d.RSI })));

      rsiSeries.createPriceLine({
        price: 70, color: 'rgba(255, 82, 82, 0.3)', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '超買'
      });
      rsiSeries.createPriceLine({
        price: 30, color: 'rgba(0, 230, 118, 0.3)', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '超賣'
      });

    } else if (indicator === 'foreign') {
      const fSeries = subChart.addHistogramSeries({
        priceFormat: { type: 'custom', formatter: v => Math.round(v) + ' 張' }
      });
      fSeries.setData(items.filter(d => d.foreign_net !== null).map(d => ({
        time: d.time,
        value: d.foreign_net,
        color: d.foreign_net >= 0 ? 'rgba(255, 82, 82, 0.6)' : 'rgba(0, 230, 118, 0.6)'
      })));

    } else if (indicator === 'trust') {
      const tSeries = subChart.addHistogramSeries({
        priceFormat: { type: 'custom', formatter: v => Math.round(v) + ' 張' }
      });
      tSeries.setData(items.filter(d => d.trust_net !== null).map(d => ({
        time: d.time,
        value: d.trust_net,
        color: d.trust_net >= 0 ? 'rgba(255, 82, 82, 0.6)' : 'rgba(0, 230, 118, 0.6)'
      })));

    } else if (indicator === 'major_retail') {
      const majSeries = subChart.addLineSeries({ color: '#ff5252', lineWidth: 1.5, priceLineVisible: false });
      majSeries.setData(items.filter(d => d.major_net !== null).map(d => ({ time: d.time, value: d.major_net })));

      const retSeries = subChart.addLineSeries({ color: '#00d4ff', lineWidth: 1.5, priceLineVisible: false });
      retSeries.setData(items.filter(d => d.retail_net !== null).map(d => ({ time: d.time, value: d.retail_net })));
    }

    // Sync scroll/zoom with main chart
    if (mainChartObj && mainChartObj.chart) {
      const mainChart = mainChartObj.chart;
      
      mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) {
          subChart.timeScale().setVisibleLogicalRange(range);
        }
      });
      
      subChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) {
          mainChart.timeScale().setVisibleLogicalRange(range);
        }
      });
      
      // Sync initial zoom level
      setTimeout(() => {
        const mainRange = mainChart.timeScale().getVisibleLogicalRange();
        if (mainRange) {
          subChart.timeScale().setVisibleLogicalRange(mainRange);
        }
      }, 50);
    }

    subResizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        subChart.applyOptions({ width, height });
      }
    });
    subResizeObserver.observe(container);

    return subChart;
  }

  // ---- Add Bollinger Bands (從後端已計算資料，最準確) ----
  function addBollingerBandsFromData(chartObj, bbData) {
    if (!chartObj || !chartObj.chart || !bbData || bbData.length === 0) return;
    const { chart } = chartObj;

    const upperData = bbData.map(d => ({ time: d.time, value: d.upper }));
    const middleData = bbData.map(d => ({ time: d.time, value: d.middle }));
    const lowerData = bbData.map(d => ({ time: d.time, value: d.lower }));

    const upperSeries = chart.addLineSeries({
      color: COLORS.bbUpper, lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
    });
    upperSeries.setData(upperData);

    const middleSeries = chart.addLineSeries({
      color: COLORS.bbMiddle, lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
    });
    middleSeries.setData(middleData);

    const lowerSeries = chart.addLineSeries({
      color: COLORS.bbLower, lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
    });
    lowerSeries.setData(lowerData);

    return { upperSeries, middleSeries, lowerSeries };
  }

  // ---- Add Bollinger Bands (用戶端自行計算，當後端無資料時使用) ----
  function addBollingerBands(chartObj, data, period = 20, stdDev = 2) {
    if (!chartObj || !chartObj.chart) return;
    const { chart } = chartObj;
    const closes = data.map(d => d.close);
    const upperData = [], middleData = [], lowerData = [];

    for (let i = period - 1; i < closes.length; i++) {
      const slice = closes.slice(i - period + 1, i + 1);
      const mean = slice.reduce((a, b) => a + b, 0) / period;
      const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
      const std = Math.sqrt(variance);
      const time = data[i].time;
      upperData.push({ time, value: parseFloat((mean + stdDev * std).toFixed(2)) });
      middleData.push({ time, value: parseFloat(mean.toFixed(2)) });
      lowerData.push({ time, value: parseFloat((mean - stdDev * std).toFixed(2)) });
    }

    const upperSeries = chart.addLineSeries({ color: COLORS.bbUpper, lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    upperSeries.setData(upperData);

    const middleSeries = chart.addLineSeries({ color: COLORS.bbMiddle, lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    middleSeries.setData(middleData);

    const lowerSeries = chart.addLineSeries({ color: COLORS.bbLower, lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    lowerSeries.setData(lowerData);

    return { upperSeries, middleSeries, lowerSeries };
  }

  // ---- Add MA（從後端已計算資料）----
  function addMAFromData(chartObj, maData, color = '#b388ff') {
    if (!chartObj || !chartObj.chart || !maData || maData.length === 0) return;
    const { chart } = chartObj;
    const maSeries = chart.addLineSeries({
      color, lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
    });
    maSeries.setData(maData);
    return maSeries;
  }

  // ---- Add MA（用戶端計算）----
  function addMA(chartObj, data, period = 5, color = '#b388ff') {
    if (!chartObj || !chartObj.chart) return;
    const { chart } = chartObj;
    const closes = data.map(d => d.close);
    const maData = [];
    for (let i = period - 1; i < closes.length; i++) {
      const slice = closes.slice(i - period + 1, i + 1);
      const mean = slice.reduce((a, b) => a + b, 0) / period;
      maData.push({ time: data[i].time, value: parseFloat(mean.toFixed(2)) });
    }
    const maSeries = chart.addLineSeries({
      color, lineWidth: 1.5,
      lineStyle: LightweightCharts.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
    });
    maSeries.setData(maData);
    return maSeries;
  }

  // ---- Add Signal Markers ----
  function addSignalMarkers(chartObj, markers) {
    if (!chartObj || !chartObj.candleSeries || !markers || markers.length === 0) return;
    const { candleSeries } = chartObj;

    const sorted = markers.sort((a, b) => a.time < b.time ? -1 : a.time > b.time ? 1 : 0);

    candleSeries.setMarkers(sorted.map(m => ({
      time: m.time,
      position: m.position || (m.shape === 'arrowUp' ? 'belowBar' : 'aboveBar'),
      color: m.color || (m.shape === 'arrowUp' ? '#00e676' : '#ff5252'),
      shape: m.shape || 'arrowUp',
      text: '', // 禁用內建文字渲染，改用我們自訂的 SVG 垂直虛線與標記
      size: 1.5
    })));

    // 儲存訊號資訊於圖表物件中，供後續繪製自訂排版使用
    chartObj.signals = sorted;

    // 立即更新自訂標記繪製
    updateCustomMarkers(chartObj);
  }

  // ---- Cleanup ----
  function destroy() {
    if (activeChart) {
      activeChart.remove();
      activeChart = null;
      activeCandleSeries = null;
    }
    if (activeSubChart) {
      activeSubChart.remove();
      activeSubChart = null;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (subResizeObserver) {
      subResizeObserver.disconnect();
      subResizeObserver = null;
    }
  }

  return {
    createStockChart,
    renderSubChart,
    addBollingerBands,
    addBollingerBandsFromData,
    addMA,
    addMAFromData,
    addSignalMarkers,
    generateMockOHLC,
    destroy,
    COLORS
  };
})();
