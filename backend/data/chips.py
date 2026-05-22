"""
台股布林通道交易訊號系統 - 籌碼面資料模組

串接 FinMind API v4 取得三大法人買賣超數據，並提供基於成交量與漲跌幅的自適應模擬演算法作為備用。
"""

import logging
import hashlib
import requests
import pandas as pd
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def get_deterministic_chip_flow(
    stock_id: str,
    date_str: str,
    volume: float,
    price_change_pct: float
) -> Dict[str, float]:
    """
    自適應模擬演算法：根據個股每日成交量與漲跌幅，計算出高度真實且穩定的模擬籌碼流向。
    
    使用 MD5 雜湊確保同一日期、同一股票代碼產生的數值完全一致（不會因重新整理而跳動）。
    """
    # 建立確定性的種子值 (0.0 ~ 1.0)
    h = hashlib.md5(f"{stock_id}_{date_str}".encode()).hexdigest()
    seed1 = int(h[0:8], 16) / 0xffffffff
    seed2 = int(h[8:16], 16) / 0xffffffff
    seed3 = int(h[16:24], 16) / 0xffffffff
    
    # 漲跌幅影響因子 (漲越多，法人買超概率越大；跌越多，賣超概率越大)
    # 漲跌幅限制為 -10% ~ +10%，對應偏置為 -1.0 ~ +1.0
    bias = max(-1.0, min(1.0, price_change_pct / 8.0))
    
    # 換算為張數 (1 張 = 1000 股)
    volume_lots = volume / 1000.0
    
    # 1. 外資 (佔比最大，對漲跌幅最敏感，約佔成交量 5%~25%)
    foreign_factor = (seed1 - 0.5) * 1.5 + bias * 0.8
    foreign_factor = max(-1.0, min(1.0, foreign_factor))
    foreign_net = round(volume_lots * 0.15 * foreign_factor, 1)
    
    # 2. 投信 (操作穩健，佔成交量約 1%~8%)
    trust_factor = (seed2 - 0.5) * 1.0 + bias * 0.4
    trust_factor = max(-1.0, min(1.0, trust_factor))
    trust_net = round(volume_lots * 0.04 * trust_factor, 1)
    
    # 3. 自營商 (操作短線，約佔成交量 1%~5%)
    dealer_factor = (seed3 - 0.5) * 0.8 + bias * 0.2
    dealer_factor = max(-1.0, min(1.0, dealer_factor))
    dealer_net = round(volume_lots * 0.02 * dealer_factor, 1)
    
    # 4. 大戶合計 (三大法人合計)
    major_net = round(foreign_net + trust_net + dealer_net, 1)
    
    # 5. 散戶流向 (通常與三大法人反向對立)
    retail_net = -major_net
    
    return {
        "foreign_net": foreign_net,
        "trust_net": trust_net,
        "dealer_net": dealer_net,
        "major_net": major_net,
        "retail_net": retail_net
    }


def fetch_institutional_chips(
    stock_id: str,
    start_date: str,
    end_date: str,
    token: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    從 FinMind API 擷取三大法人買賣超資料
    """
    clean_id = stock_id.replace(".TW", "").replace(".TWO", "").strip()
    
    payload = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": clean_id,
        "start_date": start_date,
        "end_date": end_date
    }
    
    headers = {}
    if token:
        payload["token"] = token
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        logger.info(f"正在從 FinMind 取得 {clean_id} 的法人買賣超數據 ({start_date} ~ {end_date})...")
        response = requests.post(FINMIND_API_URL, data=payload, headers=headers, timeout=8)
        
        if response.status_code != 200:
            logger.warning(f"FinMind API 回應錯誤狀態碼: {response.status_code}")
            return None
            
        res_json = response.json()
        if res_json.get("status") != 200:
            logger.warning(f"FinMind API 錯誤訊息: {res_json.get('msg')}")
            return None
            
        data = res_json.get("data", [])
        if not data:
            logger.info(f"FinMind 未回傳 {clean_id} 的任何籌碼資料")
            return None
            
        df = pd.DataFrame(data)
        
        # 整理欄位
        df["date"] = pd.to_datetime(df["date"])
        df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
        df["net"] = (df["buy"] - df["sell"]) / 1000.0  # 換算成「張」
        
        # 依據 date 及 name 分組彙整
        # name 種類可能包括: Foreign_Investor, Investment_Trust, Dealer, Dealer_Self, Dealer_Hedging
        # 我們將它們歸類為外資 (foreign)、投信 (trust) 以及自營商 (dealer)
        pivot_df = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").fillna(0)
        
        # 建立一個乾淨的 DataFrame，確保需要的欄位存在
        chips_df = pd.DataFrame(index=pivot_df.index)
        
        # 外資合計
        foreign_cols = [c for c in pivot_df.columns if "Foreign" in c or "外" in c]
        chips_df["foreign_net"] = pivot_df[foreign_cols].sum(axis=1) if foreign_cols else 0.0
        
        # 投信
        trust_cols = [c for c in pivot_df.columns if "Trust" in c or "投" in c]
        chips_df["trust_net"] = pivot_df[trust_cols].sum(axis=1) if trust_cols else 0.0
        
        # 自營商
        dealer_cols = [c for c in pivot_df.columns if "Dealer" in c or "自" in c]
        chips_df["dealer_net"] = pivot_df[dealer_cols].sum(axis=1) if dealer_cols else 0.0
        
        # 大戶合計 (三大法人)
        chips_df["major_net"] = chips_df["foreign_net"] + chips_df["trust_net"] + chips_df["dealer_net"]
        
        # 散戶估計 (與法人反向)
        chips_df["retail_net"] = -chips_df["major_net"]
        
        chips_df = chips_df.reset_index()
        chips_df["date"] = chips_df["date"].dt.tz_localize(None).dt.normalize()
        
        logger.info(f"成功解析 FinMind 法人籌碼資料共 {len(chips_df)} 筆")
        return chips_df
        
    except Exception as e:
        logger.error(f"取得 FinMind 籌碼資料時發生異常: {e}")
        return None
