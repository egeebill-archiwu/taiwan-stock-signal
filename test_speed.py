import requests
import time

print("開始測試市場篩選效能與快取...")

t0 = time.time()
r1 = requests.get('http://127.0.0.1:8000/api/screener').json()
t1 = time.time()
print(f"首次掃描 (無快取) 耗時: {t1 - t0:.2f} 秒")
print(f"掃描到的訊號數量: {len(r1.get('results', []))}")

t2 = time.time()
r2 = requests.get('http://127.0.0.1:8000/api/screener').json()
t3 = time.time()
print(f"二次讀取 (有快取) 耗時: {t3 - t2:.2f} 秒")
print(f"快取回傳的訊號數量: {len(r2.get('results', []))}")
