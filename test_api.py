import requests
import random
import datetime

# API Adresi (Senin bilgisayarın)
URL = "http://127.0.0.1:8000/analyze"

# --- 1. Sahte Borsa Verisi Üret (100 Mum) ---
# Rastgele fiyatlar oluşturuyoruz ki analiz yapabilsin
data = []
price = 100.0
base_time = datetime.datetime.now()

print("📊 Sahte piyasa verisi üretiliyor...")

for i in range(100):
    # Fiyatı rastgele biraz artır veya azalt
    change = random.uniform(-2.0, 2.5)
    price += change

    # Mum verisi (OHLCV formatında)
    candle = {
        "timestamp": (base_time + datetime.timedelta(minutes=i * 15)).strftime("%Y-%m-%d %H:%M:%S"),
        "open": round(price, 2),
        "high": round(price + random.uniform(0.1, 1.0), 2),
        "low": round(price - random.uniform(0.1, 1.0), 2),
        "close": round(price + random.uniform(-0.5, 0.5), 2),
        "volume": random.randint(100, 5000)
    }
    data.append(candle)

# --- 2. API'ye İstek Gönder ---
payload = {
    "symbol": "BTC/USD",
    "interval": "15m",
    "data": data
}

print(f"🚀 API'ye istek gönderiliyor: {URL}")

try:
    response = requests.post(URL, json=payload)

    if response.status_code == 200:
        result = response.json()
        print("\n✅ BAŞARILI! İşte API Cevabı:")
        print("-" * 30)
        print(f"Sembol:      {result['symbol']}")
        print(f"Son Fiyat:   {result['last_price']}")
        print(f"RSI Değeri:  {result['indicators']['RSI']}")
        print(f"MACD:        {result['indicators']['MACD']}")
        print(f"Sinyal:      👉 {result['signal']} 👈")
        print("-" * 30)
    else:
        print(f"❌ HATA: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Bağlantı Hatası: {e}")
    print("Emin misin? 'uvicorn main:app --reload' komutu çalışıyor mu?")