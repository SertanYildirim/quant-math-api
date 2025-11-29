from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import pandas_ta as ta
import numpy as np

app = FastAPI(
    title="QuantMath API",
    description="Financial Technical Analysis & Signal Generator",
    version="1.0.0"
)


# --- 1. Veri Modeli (Gelen İstek Tipi) ---
class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class AnalysisRequest(BaseModel):
    symbol: str
    interval: str
    data: List[Candle]


# --- 2. Yardımcı Fonksiyon: Analiz Motoru (DÜZELTİLMİŞ HALİ) ---
def calculate_indicators(df: pd.DataFrame):
    # Pandas TA'nın çakışmasını önlemek için standart ta.fonksiyon() yöntemini kullanıyoruz

    # RSI (14)
    # Eğer veri yetmezse NaN döner, hata vermez
    df['RSI'] = ta.rsi(df['close'], length=14)

    # MACD (12, 26, 9)
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # Bollinger Bands (20, 2)
    bbands = ta.bbands(df['close'], length=20, std=2)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)

    # SMA (Hareketli Ortalamalar)
    # df.ta.sma yerine ta.sma kullanarak seriyi garantiye alıyoruz
    df['SMA_50'] = ta.sma(df['close'], length=50)
    df['SMA_200'] = ta.sma(df['close'], length=200)

    # NaN değerleri (Hesaplanamayan ilk mumlar) temizle veya 0 yap
    df = df.fillna(0)

    return df


# --- 3. Sinyal Mantığı ---
def generate_signal(row):
    score = 0

    # RSI Kontrolü
    if row['RSI'] < 30:
        score += 1  # Alım Bölgesi
    elif row['RSI'] > 70:
        score -= 1  # Satış Bölgesi

    # Trend Kontrolü (Fiyat 50 günlük ortalamanın üstünde mi?)
    # NaN kontrolü yapalım
    if pd.notna(row['SMA_50']):
        if row['close'] > row['SMA_50']:
            score += 1
        elif row['close'] < row['SMA_50']:
            score -= 1

    # Karar Mekanizması
    if score >= 2:
        return "STRONG_BUY"
    elif score == 1:
        return "BUY"
    elif score == -1:
        return "SELL"
    elif score <= -2:
        return "STRONG_SELL"
    else:
        return "NEUTRAL"


# --- 4. Endpoint ---
@app.post("/analyze")
def analyze_market(request: AnalysisRequest):
    try:
        # Gelen veriyi DataFrame'e çevir
        data_list = [c.dict() for c in request.data]
        df = pd.DataFrame(data_list)

        # En az 50 mum verisi lazım ki indikatörler hesaplanabilsin
        if len(df) < 50:
            raise HTTPException(status_code=400, detail="Yetersiz veri. En az 50 mum verisi gerekli.")

        # Hesapla
        df = calculate_indicators(df)

        # Son satırı al (En güncel durum)
        last_row = df.iloc[-1]

        # Sinyal üret
        signal = generate_signal(last_row)

        # MACD sütun isimleri dinamik olabilir, o yüzden güvenli çekelim
        macd_val = last_row.get('MACD_12_26_9')
        if pd.isna(macd_val): macd_val = 0.0

        return {
            "symbol": request.symbol,
            "last_price": last_row['close'],
            "indicators": {
                "RSI": round(last_row['RSI'], 2) if pd.notna(last_row['RSI']) else None,
                "MACD": round(macd_val, 4),
                "SMA_50": round(last_row['SMA_50'], 2) if pd.notna(last_row['SMA_50']) else None
            },
            "signal": signal,
            "analysis_time": "Real-time"
        }

    except Exception as e:
        # Hata olursa detayını görelim
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return {"status": "Active", "message": "QuantMath API is running!"}