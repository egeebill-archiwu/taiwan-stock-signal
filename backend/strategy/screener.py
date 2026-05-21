"""
台股布林通道交易訊號系統 - 市場篩選模組

批次掃描多檔股票，找出目前有買賣訊號的標的。
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from backend.data.fetcher import fetch_stock_data, get_all_twse_stock_ids
from backend.strategy.signal_detector import detect_all_signals, SignalResult

logger = logging.getLogger(__name__)


@dataclass
class ScreenerResult:
    """篩選結果"""
    stock_id: str
    signal_type: str       # "BUY" 或 "SELL"
    trend: str             # 趨勢方向
    price: float           # 觸發價格
    signal_date: date      # 訊號日期
    details: str = ""      # 詳細描述


def screen_stocks(
    stock_ids: Optional[list[str]] = None,
    period: str = "6mo",
    lookback_days: int = 5,
) -> list[ScreenerResult]:
    """
    掃描市場，找出有活躍訊號的股票

    會掃描指定的股票清單（或全部主要上市股票），
    找出在最近 N 個交易日內有產生買賣訊號的標的。

    Parameters
    ----------
    stock_ids : list[str], optional
        要掃描的股票代號清單，若為 None 則使用全部主要上市股票
    period : str
        資料擷取期間（用於計算指標）
    lookback_days : int
        只回傳最近 N 個交易日內的訊號

    Returns
    -------
    list[ScreenerResult]
        篩選結果列表，按訊號日期降冪排序
    """
    if stock_ids is None:
        stock_ids = get_all_twse_stock_ids()

    results: list[ScreenerResult] = []
    cutoff_date = date.today() - timedelta(days=lookback_days)
    total = len(stock_ids)

    for idx, sid in enumerate(stock_ids, 1):
        logger.info(f"掃描進度：{idx}/{total} - {sid}")

        try:
            df = fetch_stock_data(sid, period=period)
            if df.empty or len(df) < 25:
                # 資料不足，跳過（至少需要 BB_PERIOD + 幾天）
                continue

            signals = detect_all_signals(df)

            # 只保留最近的訊號
            recent_signals = [
                s for s in signals
                if s.date >= cutoff_date
            ]

            for signal in recent_signals:
                results.append(ScreenerResult(
                    stock_id=signal.stock_id,
                    signal_type=signal.signal_type,
                    trend=signal.trend_direction,
                    price=signal.price,
                    signal_date=signal.date,
                    details=signal.details,
                ))

        except Exception as e:
            logger.error(f"掃描 {sid} 時發生錯誤: {e}")
            continue

    # 按訊號日期降冪排序（最新的在前）
    results.sort(key=lambda r: r.signal_date, reverse=True)

    logger.info(f"市場掃描完成：掃描 {total} 檔，發現 {len(results)} 個訊號")
    return results
