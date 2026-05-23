"""
台股均線糾結突破交易策略模組

定義：
1. 均線糾結：日線(MA5)、週線(MA10)、月線(MA20)、季線(MA60)分散度在 4% 以內。
2. 買入訊號：近期（5天內）均線糾結，今日收盤為紅K（收盤 > 開盤）且突破所有四條均線，且前一日未突破。
3. 賣出訊號：收盤價跌破月線(MA20)。
4. 趨勢判定：以季線(MA60)為基礎。若收盤價 > MA60 且 MA60 上升，為 UPTREND；若收盤價 < MA60 且 MA60 下降，為 DOWNTREND；其餘為 SIDEWAYS。
"""

import logging
from dataclasses import dataclass
from datetime import date as date_type
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MASignalResult:
    date: date_type
    stock_id: str
    signal_type: str           # "BUY" 或 "SELL"
    price: float               # 觸發價格
    trend_direction: str       # 趨勢方向
    details: str = ""          # 描述

def calculate_ma_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算均線糾結策略所需指標"""
    if df.empty or len(df) < 60:
        return df
        
    df = df.copy()
    
    # 1. 計算均線
    df["MA5"] = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["MA20"] = df["close"].rolling(20).mean()
    df["MA60"] = df["close"].rolling(60).mean()
    
    # 2. 計算均線分散度 (Dispersion)
    # 取四條均線的最大與最小值
    ma_cols = ["MA5", "MA10", "MA20", "MA60"]
    ma_max = df[ma_cols].max(axis=1)
    ma_min = df[ma_cols].min(axis=1)
    df["ma_dispersion"] = (ma_max - ma_min) / ma_min * 100.0
    
    # 是否糾結 (4% 以內)
    df["is_entangled"] = df["ma_dispersion"] <= 4.0
    
    # 3. 趨勢判定 (基於季線 MA60)
    df["ma60_slope"] = df["MA60"].diff(5) # 5天前至今日均線變化
    df["trend"] = "SIDEWAYS"
    
    for i in range(5, len(df)):
        row = df.iloc[i]
        if pd.isna(row["MA60"]) or pd.isna(row["ma60_slope"]):
            continue
            
        close = row["close"]
        ma60 = row["MA60"]
        slope = row["ma60_slope"]
        
        if close > ma60 and slope > 0:
            df.at[df.index[i], "trend"] = "UPTREND"
        elif close < ma60 and slope < 0:
            df.at[df.index[i], "trend"] = "DOWNTREND"

    # 計算 KD、MACD、RSI，使副圖表在此策略下亦能展示
    from backend.strategy.bollinger import calculate_kd, calculate_macd, calculate_rsi
    df = calculate_kd(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)

    return df

def detect_ma_signals(df: pd.DataFrame) -> list[MASignalResult]:
    """偵測均線糾結與突破訊號"""
    signals: list[MASignalResult] = []
    
    if df.empty or len(df) < 65:
        return signals
        
    df_ind = calculate_ma_indicators(df)
    stock_id = df_ind["stock_id"].iloc[0] if "stock_id" in df_ind.columns else "UNKNOWN"
    
    for i in range(60, len(df_ind)):
        row = df_ind.iloc[i]
        prev_row = df_ind.iloc[i - 1]
        
        if pd.isna(row["MA5"]) or pd.isna(row["MA10"]) or pd.isna(row["MA20"]) or pd.isna(row["MA60"]):
            continue
            
        close = row["close"]
        open_price = row["open"]
        trend = row["trend"]
        date_val = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        
        # 取得均線最大值
        ma_max = max(row["MA5"], row["MA10"], row["MA20"], row["MA60"])
        prev_ma_max = max(prev_row["MA5"], prev_row["MA10"], prev_row["MA20"], prev_row["MA60"])
        
        # 1. 偵測買入訊號：
        # - 近期 5 天內有過均線糾結 (is_entangled == True)
        recent_entangled = df_ind["is_entangled"].iloc[max(0, i-4):i+1].any()
        
        # - 今日收盤是紅K (close > open)
        is_red_k = close > open_price
        
        # - 今日收盤突破所有均線 (close > ma_max)
        is_breakout = close > ma_max
        
        # - 前一日未突破所有均線
        prev_not_breakout = prev_row["close"] <= prev_ma_max
        
        if recent_entangled and is_red_k and is_breakout and prev_not_breakout:
            disp = row["ma_dispersion"]
            trend_label = "上升趨勢" if trend == "UPTREND" else ("下降趨勢" if trend == "DOWNTREND" else "橫盤整理")
            details = f"買進訊號：均線糾結向上突破。4均線糾結分散度為 {disp:.2f}%，首根帶量紅K棒站上所有均線，當前大趨勢為 {trend_label}。"
            signals.append(MASignalResult(
                date=date_val,
                stock_id=stock_id,
                signal_type="BUY",
                price=close,
                trend_direction=trend,
                details=details
            ))
            continue
            
        # 2. 偵測賣出訊號：
        # - 收盤價跌破月線 (MA20)
        is_break_below_ma20 = close < row["MA20"] and prev_row["close"] >= prev_row["MA20"]
        
        if is_break_below_ma20:
            details = f"賣出訊號：股價向下破位，收盤價 {close:.2f} 跌破 20日月均線 ({row['MA20']:.2f})，趨勢轉弱建議獲利了結或停損。"
            signals.append(MASignalResult(
                date=date_val,
                stock_id=stock_id,
                signal_type="SELL",
                price=close,
                trend_direction=trend,
                details=details
            ))
            
    return signals
