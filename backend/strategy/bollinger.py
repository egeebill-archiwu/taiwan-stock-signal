"""
台股布林通道交易訊號系統 - 布林通道計算模組

改用純 pandas 計算，不依賴 pandas-ta / numba，
確保在所有 Python 版本（3.10~3.13）都能正常運作。
"""

import logging

import pandas as pd

from backend.config import BB_PERIOD, BB_STD, MA_PERIOD

logger = logging.getLogger(__name__)


def calculate_bollinger(
    df: pd.DataFrame,
    period: int = BB_PERIOD,
    std: float = BB_STD,
) -> pd.DataFrame:
    """
    計算布林通道指標（純 pandas 實作，無外部依賴）

    在 DataFrame 中加入 BBL（下軌）、BBM（中軌）、BBU（上軌）欄位。
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算布林通道")
        return df

    df = df.copy()

    # 中軌 = SMA(close, period)
    df["BBM"] = df["close"].rolling(window=period).mean()

    # 標準差
    rolling_std = df["close"].rolling(window=period).std(ddof=0)

    # 上軌 / 下軌
    df["BBU"] = df["BBM"] + std * rolling_std
    df["BBL"] = df["BBM"] - std * rolling_std

    logger.info(f"布林通道計算完成 (period={period}, std={std})")
    return df


def calculate_ma(
    df: pd.DataFrame,
    period: int = MA_PERIOD,
) -> pd.DataFrame:
    """
    計算簡單移動平均線 SMA（純 pandas）
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算均線")
        return df

    df = df.copy()
    df["MA"] = df["close"].rolling(window=period).mean()

    logger.info(f"移動平均線計算完成 (period={period})")
    return df


def calculate_bandwidth(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算布林帶寬 = (BBU - BBL) / BBM * 100
    """
    if df.empty:
        return df

    required_cols = ["BBU", "BBL", "BBM"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"缺少必要欄位 {missing}，請先計算布林通道")
        return df

    df = df.copy()
    df["bandwidth"] = df.apply(
        lambda row: ((row["BBU"] - row["BBL"]) / row["BBM"] * 100)
        if pd.notna(row["BBM"]) and row["BBM"] != 0
        else 0.0,
        axis=1,
    )

    logger.info("布林帶寬計算完成")
    return df


def add_all_indicators(
    df: pd.DataFrame,
    bb_period: int = BB_PERIOD,
    bb_std: float = BB_STD,
    ma_period: int = MA_PERIOD,
) -> pd.DataFrame:
    """一次計算所有技術指標（布林通道 + 均線 + 帶寬）"""
    df = calculate_bollinger(df, period=bb_period, std=bb_std)
    df = calculate_ma(df, period=ma_period)
    df = calculate_bandwidth(df)
    return df
