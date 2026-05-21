/* ============================================
   chart.js - K-Line Chart with Lightweight Charts
   Taiwan Convention: Red = UP, Green = DOWN
   ============================================ */

const StockChart = (() => {
  let activeChart = null;
  let activeCandleSeries = null;
  let resizeObserver = null;

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

  // ---- Create Stock Chart ----
  function createStockChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    container.innerHTML = '';

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

    // Volume histogram
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

    // Fit content
    chart.timeScale().fitContent();

    // Resize handler
    resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    activeChart = chart;
    activeCandleSeries = candleSeries;

    return { chart, candleSeries, volumeSeries };
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
      text: m.text || '',
      size: 1.5
    })));
  }

  // ---- Cleanup ----
  function destroy() {
    if (activeChart) {
      activeChart.remove();
      activeChart = null;
      activeCandleSeries = null;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
  }

  return {
    createStockChart,
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
