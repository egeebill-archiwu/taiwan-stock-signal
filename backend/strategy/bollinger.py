"""
台股布林通道交易訊號系統 - 布林通道計算模組

使用 pandas-ta 計算布林通道（上軌、中軌、下軌）、移動平均線及帶寬。
"""

import logging

import pandas as pd
import pandas_ta as ta

from backend.config import BB_PERIOD, BB_STD, MA_PERIOD

logger = logging.getLogger(__name__)


def calculate_bollinger(
    df: pd.DataFrame,
    period: int = BB_PERIOD,
    std: float = BB_STD,
) -> pd.DataFrame:
    """
    計算布林通道指標

    在 DataFrame 中加入 BBL（下軌）、BBM（中軌）、BBU（上軌）欄位。

    Parameters
    ----------
    df : pd.DataFrame
        必須包含 'close' 欄位的股價 DataFrame
    period : int
        布林通道計算週期，預設 20
    std : float
        標準差倍數，預設 2.0

    Returns
    -------
    pd.DataFrame
        加入 BBL、BBM、BBU 欄位後的 DataFrame
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算布林通道")
        return df

    df = df.copy()

    # 使用 pandas-ta 計算布林通道
    bbands = ta.bbands(df["close"], length=period, std=std)

    if bbands is None or bbands.empty:
        logger.warning("pandas-ta 布林通道計算結果為空")
        return df

    # pandas-ta 回傳欄位名稱格式：BBL_{period}_{std}, BBM_{period}_{std}, BBU_{period}_{std}
    std_str = str(std).replace(".", "")  # 例如 2.0 → "20"
    bbl_col = f"BBL_{period}_{std}"
    bbm_col = f"BBM_{period}_{std}"
    bbu_col = f"BBU_{period}_{std}"

    # 嘗試匹配欄位名稱（pandas-ta 版本可能有差異）
    bb_columns = bbands.columns.tolist()

    bbl_matched = [c for c in bb_columns if c.startswith("BBL")]
    bbm_matched = [c for c in bb_columns if c.startswith("BBM")]
    bbu_matched = [c for c in bb_columns if c.startswith("BBU")]

    if bbl_matched and bbm_matched and bbu_matched:
        df["BBL"] = bbands[bbl_matched[0]].values
        df["BBM"] = bbands[bbm_matched[0]].values
        df["BBU"] = bbands[bbu_matched[0]].values
    else:
        logger.error(f"無法辨識布林通道欄位，可用欄位: {bb_columns}")
        return df

    logger.info(f"布林通道計算完成 (period={period}, std={std})")
    return df


def calculate_ma(
    df: pd.DataFrame,
    period: int = MA_PERIOD,
) -> pd.DataFrame:
    """
    計算簡單移動平均線 (SMA)

    Parameters
    ----------
    df : pd.DataFrame
        必須包含 'close' 欄位的股價 DataFrame
    period : int
        移動平均線週期，預設 10

    Returns
    -------
    pd.DataFrame
        加入 MA 欄位後的 DataFrame
    """
    if df.empty or "close" not in df.columns:
        logger.warning("DataFrame 為空或缺少 close 欄位，無法計算均線")
        return df

    df = df.copy()
    df["MA"] = ta.sma(df["close"], length=period)

    logger.info(f"移動平均線計算完成 (period={period})")
    return df


def calculate_bandwidth(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算布林帶寬（Bandwidth）

    帶寬 = (上軌 - 下軌) / 中軌 * 100
    用於衡量波動程度，帶寬擴張代表波動加大。

    Parameters
    ----------
    df : pd.DataFrame
        必須包含 BBU、BBL、BBM 欄位的 DataFrame

    Returns
    -------
    pd.DataFrame
        加入 bandwidth 欄位後的 DataFrame
    """
    if df.empty:
        logger.warning("DataFrame 為空，無法計算帶寬")
        return df

    required_cols = ["BBU", "BBL", "BBM"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"缺少必要欄位 {missing}，請先計算布林通道")
        return df

    df = df.copy()
    # 避免除以零
    df["bandwidth"] = df.apply(
        lambda row: ((row["BBU"] - row["BBL"]) / row["BBM"] * 100)
        if row["BBM"] != 0
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
    """
    一次計算所有技術指標（布林通道 + 均線 + 帶寬）

    Parameters
    ----------
    df : pd.DataFrame
        原始股價 DataFrame
    bb_period : int
        布林通道週期
    bb_std : float
        布林通道標準差倍數
    ma_period : int
        均線週期

    Returns
    -------
    pd.DataFrame
        包含所有指標欄位的 DataFrame
    """
    df = calculate_bollinger(df, period=bb_period, std=bb_std)
    df = calculate_ma(df, period=ma_period)
    df = calculate_bandwidth(df)
    return df
