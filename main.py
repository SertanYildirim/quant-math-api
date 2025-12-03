from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import pandas_ta as ta
import numpy as np

app = FastAPI(
    title="QuantMath API",
    description="Financial Technical Analysis & Signal Generator",
    version="2.0.0"
)

# --- CORS AYARLARI (Kritik!) ---
# Bu ayar, Streamlit Cloud gibi dış kaynakların bu API'ye erişmesine izin verir.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Güvenlik için canlıda spesifik domain yazılabilir, şimdilik '*' (herkes)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 1. Veri Modeli ---
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


# --- 2. Analiz Motoru ---
def calculate_indicators(df: pd.DataFrame):
    # RSI (14) - Seri döner
    df['RSI'] = ta.rsi(df['close'], length=14)

    # MACD - DataFrame dönebilir, sütunları birleştiriyoruz
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # Bollinger Bands
    bbands = ta.bbands(df['close'], length=20, std=2)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)

    # SMA - Sadece Series olarak alıp ekliyoruz (Güvenli Yöntem)
    sma50 = ta.sma(df['close'], length=50)
    df['SMA_50'] = sma50 if sma50 is not None else 0

    sma200 = ta.sma(df['close'], length=200)
    df['SMA_200'] = sma200 if sma200 is not None else 0

    return df.fillna(0)

# --- 3. Sinyal Mantığı ---
def generate_signal(row):
    score = 0

    # RSI Sinyali
    if row['RSI'] < 30:
        score += 1  # Aşırı Satım -> Al
    elif row['RSI'] > 70:
        score -= 1  # Aşırı Alım -> Sat

    # Trend Sinyali (Fiyat SMA50 üstünde mi?)
    if row['close'] > row['SMA_50']:
        score += 1
    elif row['close'] < row['SMA_50']:
        score -= 1

    # MACD Sinyali (MACD > Sinyal ise Al)
    # Sütun isimleri genellikle MACD_12_26_9 ve MACDs_12_26_9 olur
    macd_col = 'MACD_12_26_9'
    signal_col = 'MACDs_12_26_9'

    if macd_col in row and signal_col in row:
        if row[macd_col] > row[signal_col]:
            score += 0.5
        elif row[macd_col] < row[signal_col]:
            score -= 0.5

    # Karar
    if score >= 2:
        return "STRONG_BUY"
    elif score >= 1:
        return "BUY"
    elif score <= -2:
        return "STRONG_SELL"
    elif score <= -1:
        return "SELL"
    else:
        return "NEUTRAL"


# --- 4. Endpoint ---
@app.post("/analyze")
def analyze_market(request: AnalysisRequest):
    try:
        # JSON listesini DataFrame'e çevir
        data_list = [c.dict() for c in request.data]
        df = pd.DataFrame(data_list)

        if len(df) < 20:
            raise HTTPException(status_code=400, detail="Not enough data. Need at least 20 candles.")

        # Hesapla
        df = calculate_indicators(df)

        # Son durumu al
        last_row = df.iloc[-1]
        signal = generate_signal(last_row)

        # MACD sütunlarını güvenli çek
        macd_val = last_row.get('MACD_12_26_9', 0)
        macd_signal = last_row.get('MACDs_12_26_9', 0)

        return {
            "symbol": request.symbol,
            "last_price": last_row['close'],
            "timestamp": last_row['timestamp'],
            "indicators": {
                "RSI": round(last_row['RSI'], 2),
                "MACD": round(macd_val, 4),
                "MACD_Signal": round(macd_signal, 4),
                "SMA_50": round(last_row['SMA_50'], 2),
                "BB_Upper": round(last_row.get('BBU_20_2.0', 0), 2),
                "BB_Lower": round(last_row.get('BBL_20_2.0', 0), 2),
            },
            "signal": signal,
            "score": generate_signal(last_row)  # Skor mantığını göstermek için
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return {"status": "Active", "service": "QuantMath Financial API v2"}