# -*- coding: utf-8 -*-
"""驗證買賣訊號邏輯是否正確"""
import requests

def test_signals(stock_id, stock_name, period='2y'):
    r = requests.get(f'http://localhost:8000/api/stock/{stock_id}/signals?period={period}')
    data = r.json()
    count = data['signal_count']
    print(f'\n{"="*50}')
    print(f'{stock_id} {stock_name}  ({period}) - 訊號數: {count}')
    print(f'{"="*50}')
    if count == 0:
        print('  (此期間無符合條件的訊號)')
    for s in data['signals']:
        sig = '🟢 買入' if s['signal_type'] == 'BUY' else '🔴 賣出'
        trend = {'UPTREND': '⬆上升', 'DOWNTREND': '⬇下降', 'SIDEWAYS': '➡盤整'}.get(s['trend_direction'], s['trend_direction'])
        print(f"  {s['date']} {sig} @ {s['price']:.0f}元  趨勢:{trend}")
        print(f"    說明: {s['details']}")

# 測試主要股票
test_signals('2330', '台積電', '2y')
test_signals('2454', '聯發科', '2y')
test_signals('2317', '鴻海',   '2y')
test_signals('2303', '聯電',   '2y')

print('\n\n=== 策略說明 ===')
print('買入條件: ① 下降趨勢  ② 收盤接近布林下軌(5%內)  ③ 連續≥3根綠K  ④ 出現紅K')
print('賣出條件: ① 上升趨勢  ② 收盤接近布林上軌(5%內)  ③ 連續≥3根紅K  ④ 出現綠K且跌破MA10')
