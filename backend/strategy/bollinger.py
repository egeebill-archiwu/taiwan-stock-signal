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


def calculate_kd(
    df: pd.DataFrame,
    period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    """
    計算 KD 指標（純 pandas）
    
    RSV = (Close - Low_9_min) / (High_9_max - Low_9_min) * 100
    K = (2/3) * K_prev + (1/3) * RSV
    D = (2/3) * D_prev + (1/3) * K
    """
    if df.empty or "close" not in df.columns or "high" not in df.columns or "low" not in df.columns:
        logger.warning("DataFrame 為空或缺少必要欄位，無法計算 KD")
        return df

    df = df.copy()
    if len(df) < period:
        df["K"] = 50.0
        df["D"] = 50.0
        return df

    low_min = df["low"].rolling(window=period).min()
    high_max = df["high"].rolling(window=period).max()
    
    # 避免分母為零
    diff = high_max - low_min
    rsv = ((df["close"] - low_min) / diff.replace(0, 1e-9)) * 100
    rsv = rsv.fillna(50.0)

    k_values = []
    d_values = []
    k_val = 50.0
    d_val = 50.0

    for r in rsv:
        k_val = (2 / 3) * k_val + (1 / 3) * r
        d_val = (2 / 3) * d_val + (1 / 3) * k_val
        k_values.append(k_val)
        d_values.append(d_val)

    df["K"] = k_values
    df["D"] = d_values
    logger.info("KD 指標計算完成")
    return df


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    計算 MACD 指標（純 pandas）
    
    DIF = EMA(12) - EMA(26)
    DEA = DIF 之 EMA(9)
    Hist = DIF - DEA
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算 MACD")
        return df

    df = df.copy()
    if len(df) < slow:
        df["macd_dif"] = 0.0
        df["macd_dea"] = 0.0
        df["macd_hist"] = 0.0
        return df

    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    
    df["macd_dif"] = ema_fast - ema_slow
    df["macd_dea"] = df["macd_dif"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd_dif"] - df["macd_dea"]
    
    logger.info("MACD 指標計算完成")
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    計算 RSI 指標（純 pandas，Wilder 均線平滑法）
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算 RSI")
        return df

    df = df.copy()
    if len(df) < period:
        df["RSI"] = 50.0
        return df

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder's smoothing RMA: ewm alpha = 1 / N
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))

    df["RSI"] = rsi.fillna(50.0)
    logger.info("RSI 指標計算完成")
    return df


def add_all_indicators(
    df: pd.DataFrame,
    bb_period: int = BB_PERIOD,
    bb_std: float = BB_STD,
    ma_period: int = MA_PERIOD,
) -> pd.DataFrame:
    """一次計算所有技術指標（布林通道 + 均線 + 帶寬 + KD + MACD + RSI）"""
    df = calculate_bollinger(df, period=bb_period, std=bb_std)
    df = calculate_ma(df, period=ma_period)
    df = calculate_bandwidth(df)
    df = calculate_kd(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    return df

