"""
台股布林通道交易訊號系統 - 訊號偵測模組

偵測買進與賣出訊號，需滿足趨勢前提條件。

台灣慣例：
- 紅 K（陽線）：收盤價 > 開盤價（看漲）
- 綠 K（陰線）：收盤價 < 開盤價（看跌）

買進訊號邏輯：
  前提：趨勢為 DOWNTREND，收盤價接近布林下軌
  訊號：連續 ≥ N 根綠 K 後，出現一根紅 K

賣出訊號邏輯：
  前提：趨勢為 UPTREND，收盤價接近布林上軌
  訊號：連續 ≥ N 根紅 K 後，出現一根綠 K，且收盤價 < MA10
"""

import logging
from dataclasses import dataclass, field
from datetime import date as date_type
from typing import Optional

import pandas as pd

from backend.config import (
    CONSECUTIVE_K_THRESHOLD,
    MA_PERIOD,
    NEAR_BAND_PCT,
)
from backend.strategy.bollinger import add_all_indicators
from backend.strategy.trend_analyzer import add_trend_column

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """訊號偵測結果"""
    date: date_type
    stock_id: str
    signal_type: str           # "BUY" 或 "SELL"
    price: float               # 觸發價格（收盤價）
    trend_direction: str       # 趨勢方向
    details: str = ""          # 訊號詳細描述


def _is_red_k(row: pd.Series) -> bool:
    """判斷是否為紅 K（陽線）：收盤 > 開盤"""
    return row["close"] > row["open"]


def _is_green_k(row: pd.Series) -> bool:
    """判斷是否為綠 K（陰線）：收盤 < 開盤"""
    return row["close"] < row["open"]


def _is_near_lower_band(row: pd.Series, threshold: float = NEAR_BAND_PCT) -> bool:
    """
    判斷收盤價是否接近布林下軌

    接近的定義：收盤價距下軌在 threshold 百分比以內，或收盤價已跌破下軌。
    """
    if pd.isna(row.get("BBL")) or row["BBL"] == 0:
        return False
    distance_pct = (row["close"] - row["BBL"]) / row["BBL"]
    return distance_pct <= threshold


def _is_near_upper_band(row: pd.Series, threshold: float = NEAR_BAND_PCT) -> bool:
    """
    判斷收盤價是否接近布林上軌

    接近的定義：收盤價距上軌在 threshold 百分比以內，或收盤價已突破上軌。
    """
    if pd.isna(row.get("BBU")) or row["BBU"] == 0:
        return False
    distance_pct = (row["BBU"] - row["close"]) / row["BBU"]
    return distance_pct <= threshold


def _count_consecutive_green_k(df: pd.DataFrame, end_idx: int) -> int:
    """
    從 end_idx 往前數連續綠 K 的數量（不含 end_idx 本身）
    """
    count = 0
    for i in range(end_idx - 1, -1, -1):
        if _is_green_k(df.iloc[i]):
            count += 1
        else:
            break
    return count


def _count_consecutive_red_k(df: pd.DataFrame, end_idx: int) -> int:
    """
    從 end_idx 往前數連續紅 K 的數量（不含 end_idx 本身）
    """
    count = 0
    for i in range(end_idx - 1, -1, -1):
        if _is_red_k(df.iloc[i]):
            count += 1
        else:
            break
    return count


def detect_buy_signal(
    df: pd.DataFrame,
    consecutive_k: int = CONSECUTIVE_K_THRESHOLD,
) -> list[SignalResult]:
    """
    偵測買進訊號

    條件：
    1. 趨勢為 DOWNTREND
    2. 收盤價接近布林下軌
    3. 前 N 根 K 棒為連續綠 K（下跌）
    4. 當根為紅 K（反轉信號）

    Parameters
    ----------
    df : pd.DataFrame
        包含完整指標的 DataFrame（需有 BBL, BBM, BBU, MA, bandwidth, trend 欄位）
    consecutive_k : int
        最少連續綠 K 數量

    Returns
    -------
    list[SignalResult]
        買進訊號列表
    """
    signals: list[SignalResult] = []

    if df.empty or len(df) < consecutive_k + 1:
        return signals

    stock_id = df["stock_id"].iloc[0] if "stock_id" in df.columns else "UNKNOWN"

    for i in range(consecutive_k + 1, len(df)):
        row = df.iloc[i]

        # 略過含 NaN 的列
        if pd.isna(row.get("BBL")) or pd.isna(row.get("trend")):
            continue

        # 條件 1：趨勢為下降趨勢
        if row["trend"] != "DOWNTREND":
            continue

        # 條件 2：收盤價接近布林下軌
        if not _is_near_lower_band(row):
            continue

        # 條件 3：前面有足夠的連續綠 K
        green_count = _count_consecutive_green_k(df, i)
        if green_count < consecutive_k:
            continue

        # 條件 4：當根為紅 K（反轉訊號）
        if not _is_red_k(row):
            continue

        # 取得日期
        signal_date = row["date"]
        if isinstance(signal_date, pd.Timestamp):
            signal_date = signal_date.date()

        details = (
            f"買進訊號：連續 {green_count} 根綠 K 後出現紅 K 反轉，"
            f"收盤價 {row['close']:.2f} 接近布林下軌 {row['BBL']:.2f}，"
            f"趨勢為下降趨勢"
        )

        signals.append(SignalResult(
            date=signal_date,
            stock_id=stock_id,
            signal_type="BUY",
            price=row["close"],
            trend_direction="DOWNTREND",
            details=details,
        ))

    logger.info(f"買進訊號偵測完成，共發現 {len(signals)} 個訊號")
    return signals


def detect_sell_signal(
    df: pd.DataFrame,
    consecutive_k: int = CONSECUTIVE_K_THRESHOLD,
    ma_period: int = MA_PERIOD,
) -> list[SignalResult]:
    """
    偵測賣出訊號

    條件：
    1. 趨勢為 UPTREND
    2. 收盤價接近布林上軌
    3. 前 N 根 K 棒為連續紅 K（上漲）
    4. 當根為綠 K（反轉信號）
    5. 收盤價 < MA10

    Parameters
    ----------
    df : pd.DataFrame
        包含完整指標的 DataFrame
    consecutive_k : int
        最少連續紅 K 數量
    ma_period : int
        均線週期（用於確認跌破均線）

    Returns
    -------
    list[SignalResult]
        賣出訊號列表
    """
    signals: list[SignalResult] = []

    if df.empty or len(df) < consecutive_k + 1:
        return signals

    stock_id = df["stock_id"].iloc[0] if "stock_id" in df.columns else "UNKNOWN"

    for i in range(consecutive_k + 1, len(df)):
        row = df.iloc[i]

        # 略過含 NaN 的列
        if pd.isna(row.get("BBU")) or pd.isna(row.get("trend")) or pd.isna(row.get("MA")):
            continue

        # 條件 1：趨勢為上升趨勢
        if row["trend"] != "UPTREND":
            continue

        # 條件 2：收盤價接近布林上軌
        if not _is_near_upper_band(row):
            continue

        # 條件 3：前面有足夠的連續紅 K
        red_count = _count_consecutive_red_k(df, i)
        if red_count < consecutive_k:
            continue

        # 條件 4：當根為綠 K（反轉訊號）
        if not _is_green_k(row):
            continue

        # 條件 5：收盤價跌破 MA
        if row["close"] >= row["MA"]:
            continue

        # 取得日期
        signal_date = row["date"]
        if isinstance(signal_date, pd.Timestamp):
            signal_date = signal_date.date()

        details = (
            f"賣出訊號：連續 {red_count} 根紅 K 後出現綠 K 反轉，"
            f"收盤價 {row['close']:.2f} 接近布林上軌 {row['BBU']:.2f}，"
            f"且收盤價跌破 MA{ma_period} ({row['MA']:.2f})，"
            f"趨勢為上升趨勢"
        )

        signals.append(SignalResult(
            date=signal_date,
            stock_id=stock_id,
            signal_type="SELL",
            price=row["close"],
            trend_direction="UPTREND",
            details=details,
        ))

    logger.info(f"賣出訊號偵測完成，共發現 {len(signals)} 個訊號")
    return signals


def detect_all_signals(
    df: pd.DataFrame,
    consecutive_k: int = CONSECUTIVE_K_THRESHOLD,
    ma_period: int = MA_PERIOD,
) -> list[SignalResult]:
    """
    偵測所有訊號（買進 + 賣出）

    會自動計算所有必要的技術指標與趨勢分析。

    Parameters
    ----------
    df : pd.DataFrame
        原始股價 DataFrame（至少需要 date, open, high, low, close, volume, stock_id）
    consecutive_k : int
        最少連續 K 棒數量
    ma_period : int
        均線週期

    Returns
    -------
    list[SignalResult]
        所有偵測到的訊號，按日期排序
    """
    if df.empty:
        return []

    # 計算所有指標
    df_with_indicators = add_all_indicators(df, ma_period=ma_period)

    # 加入趨勢欄位
    df_with_indicators = add_trend_column(df_with_indicators)

    # 偵測買賣訊號
    buy_signals = detect_buy_signal(df_with_indicators, consecutive_k=consecutive_k)
    sell_signals = detect_sell_signal(
        df_with_indicators, consecutive_k=consecutive_k, ma_period=ma_period
    )

    # 合併並排序
    all_signals = buy_signals + sell_signals
    all_signals.sort(key=lambda s: s.date)

    logger.info(
        f"訊號偵測完成：買進 {len(buy_signals)} 個、賣出 {len(sell_signals)} 個，"
        f"共 {len(all_signals)} 個訊號"
    )
    return all_signals


def prepare_dataframe_with_indicators(
    df: pd.DataFrame,
    token: Optional[str] = None,
    strategy: str = "bb"
) -> pd.DataFrame:
    """
    準備包含所有指標與趨勢的完整 DataFrame（供 API 回傳使用）

    Parameters
    ----------
    df : pd.DataFrame
        原始股價 DataFrame
    token : str, optional
        FinMind API Token
    strategy : str, optional
        策略類型

    Returns
    -------
    pd.DataFrame
        包含所有指標與籌碼數據的 DataFrame
    """
    if df.empty:
        return df

    if strategy == "ma_conv":
        from backend.strategy.ma_convergence import calculate_ma_indicators
        df = calculate_ma_indicators(df)
    else:
        df = add_all_indicators(df)
        df = add_trend_column(df)

    # 籌碼數據整合
    if "date" in df.columns:
        stock_id = df["stock_id"].iloc[0] if "stock_id" in df.columns else "UNKNOWN"
        start_date = df["date"].min().strftime("%Y-%m-%d")
        end_date = df["date"].max().strftime("%Y-%m-%d")

        from backend.data.chips import fetch_institutional_chips, get_deterministic_chip_flow
        
        # 取得真實籌碼資料
        chips_df = fetch_institutional_chips(stock_id, start_date, end_date, token=token)
        
        if chips_df is not None and not chips_df.empty:
            df = pd.merge(df, chips_df, on="date", how="left")
            
        # 確保籌碼欄位皆存在，若為空或合併失敗則透過演算法模擬
        chip_cols = ["foreign_net", "trust_net", "dealer_net", "major_net", "retail_net"]
        for col in chip_cols:
            if col not in df.columns:
                df[col] = None

        # 計算價格每日變動百分比以進行自適應偏置
        price_change = df["close"].pct_change().fillna(0.0) * 100.0

        for idx in range(len(df)):
            row = df.iloc[idx]
            if pd.isna(row["foreign_net"]) or pd.isna(row["trust_net"]):
                date_str = row["date"].strftime("%Y-%m-%d")
                vol = float(row["volume"])
                pct_change = float(price_change.iloc[idx])
                
                flow = get_deterministic_chip_flow(stock_id, date_str, vol, pct_change)
                
                df.at[idx, "foreign_net"] = flow["foreign_net"]
                df.at[idx, "trust_net"] = flow["trust_net"]
                df.at[idx, "dealer_net"] = flow["dealer_net"]
                df.at[idx, "major_net"] = flow["major_net"]
                df.at[idx, "retail_net"] = flow["retail_net"]

    return df

