"""
台股布林通道交易訊號系統 - 趨勢分析模組

透過布林中軌斜率、收盤價與中軌的相對位置、帶寬變化等指標，
判斷目前股價所處的趨勢狀態：上升趨勢、下降趨勢或盤整。
"""

import logging

import numpy as np
import pandas as pd

from backend.config import TREND_LOOKBACK, BANDWIDTH_EXPANDING_THRESHOLD

logger = logging.getLogger(__name__)


def analyze_trend(
    df: pd.DataFrame,
    lookback: int = TREND_LOOKBACK,
    idx: int = -1,
) -> str:
    """
    分析指定位置的趨勢狀態

    判斷邏輯：
    - UPTREND（上升趨勢）：中軌在過去 N 天上升、收盤價 > 中軌、帶寬擴張或穩定
    - DOWNTREND（下降趨勢）：中軌在過去 N 天下降、收盤價 < 中軌、帶寬擴張或穩定
    - SIDEWAYS（盤整）：其他情況

    Parameters
    ----------
    df : pd.DataFrame
        必須包含 'close', 'BBM', 'bandwidth' 欄位
    lookback : int
        回顧天數，預設 5
    idx : int
        分析的索引位置，預設 -1（最新一筆）

    Returns
    -------
    str
        'UPTREND'、'DOWNTREND' 或 'SIDEWAYS'
    """
    required_cols = ["close", "BBM", "bandwidth"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"缺少必要欄位 {missing}，無法分析趨勢")
        return "SIDEWAYS"

    # 確保有足夠的資料
    if len(df) < lookback + 1:
        logger.warning(f"資料筆數不足 ({len(df)} < {lookback + 1})，無法分析趨勢")
        return "SIDEWAYS"

    # 將負數索引轉為正數
    if idx < 0:
        idx = len(df) + idx

    # 確保索引範圍合法
    if idx < lookback or idx >= len(df):
        return "SIDEWAYS"

    # 取得分析區間的資料
    current_close = df.iloc[idx]["close"]
    current_bbm = df.iloc[idx]["BBM"]
    current_bandwidth = df.iloc[idx]["bandwidth"]

    # 檢查 NaN
    if pd.isna(current_close) or pd.isna(current_bbm) or pd.isna(current_bandwidth):
        return "SIDEWAYS"

    # === 判斷中軌斜率方向 ===
    bbm_values = df.iloc[idx - lookback: idx + 1]["BBM"].dropna().values
    if len(bbm_values) < 2:
        return "SIDEWAYS"

    # 用線性回歸斜率判斷趨勢方向
    x = np.arange(len(bbm_values))
    slope = np.polyfit(x, bbm_values, 1)[0]

    # 斜率門檻（以中軌均值的百分比表示，避免絕對值問題）
    bbm_mean = np.mean(bbm_values)
    if bbm_mean == 0:
        return "SIDEWAYS"

    slope_pct = slope / bbm_mean * 100  # 每日變化百分比

    # === 判斷帶寬變化 ===
    bw_values = df.iloc[idx - lookback: idx + 1]["bandwidth"].dropna().values
    if len(bw_values) >= 2:
        bw_change = bw_values[-1] - bw_values[0]
    else:
        bw_change = 0.0

    bandwidth_expanding = bw_change >= BANDWIDTH_EXPANDING_THRESHOLD

    # === 綜合判斷 ===
    # 上升趨勢：中軌上升 + 收盤價在中軌之上 + 帶寬擴張或穩定
    if slope_pct > 0.01 and current_close > current_bbm and bandwidth_expanding:
        return "UPTREND"

    # 下降趨勢：中軌下降 + 收盤價在中軌之下 + 帶寬擴張或穩定
    if slope_pct < -0.01 and current_close < current_bbm and bandwidth_expanding:
        return "DOWNTREND"

    return "SIDEWAYS"


def add_trend_column(
    df: pd.DataFrame,
    lookback: int = TREND_LOOKBACK,
) -> pd.DataFrame:
    """
    為 DataFrame 的每一列加入趨勢判斷欄位 'trend'

    Parameters
    ----------
    df : pd.DataFrame
        必須包含 'close', 'BBM', 'bandwidth' 欄位
    lookback : int
        回顧天數

    Returns
    -------
    pd.DataFrame
        加入 'trend' 欄位後的 DataFrame
    """
    df = df.copy()
    trends = []

    for i in range(len(df)):
        if i < lookback:
            trends.append("SIDEWAYS")
        else:
            trend = analyze_trend(df, lookback=lookback, idx=i)
            trends.append(trend)

    df["trend"] = trends
    logger.info(f"趨勢欄位計算完成 (lookback={lookback})")
    return df
