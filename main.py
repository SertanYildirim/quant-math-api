from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
import pandas_ta as ta
import numpy as np

app = FastAPI(
    title="QuantMath API",
    description="Financial Technical Analysis & Signal Generator",
    version="2.1.0"
)

# CORS (Tüm kaynaklara açık)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def calculate_indicators(df: pd.DataFrame):
    # RSI
    df['RSI'] = ta.rsi(df['close'], length=14)

    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # Bollinger
    bbands = ta.bbands(df['close'], length=20, std=2)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)

    # SMA
    sma50 = ta.sma(df['close'], length=50)
    df['SMA_50'] = sma50 if sma50 is not None else 0

    return df.fillna(0)


def generate_signal(row):
    score = 0

    # NaN kontrolü ve Float dönüşümü
    rsi = float(row.get('RSI', 50))
    close = float(row['close'])
    sma50 = float(row.get('SMA_50', 0))

    if rsi < 30:
        score += 1
    elif rsi > 70:
        score -= 1

    if close > sma50 and sma50 > 0:
        score += 1
    elif close < sma50 and sma50 > 0:
        score -= 1

    # MACD
    macd_col = 'MACD_12_26_9'
    signal_col = 'MACDs_12_26_9'

    if macd_col in row and signal_col in row:
        if row[macd_col] > row[signal_col]:
            score += 0.5
        elif row[macd_col] < row[signal_col]:
            score -= 0.5

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


@app.post("/analyze")
def analyze_market(request: AnalysisRequest):
    try:
        data_list = [c.dict() for c in request.data]
        df = pd.DataFrame(data_list)

        if len(df) < 20:
            raise HTTPException(status_code=400, detail="Not enough data.")

        df = calculate_indicators(df)
        last_row = df.iloc[-1]

        # Sonuçları JSON uyumlu hale getir (float() dönüşümü önemli)
        result = {
            "symbol": request.symbol,
            "last_price": float(last_row['close']),
            "timestamp": str(last_row['timestamp']),
            "indicators": {
                "RSI": round(float(last_row.get('RSI', 0)), 2),
                "MACD": round(float(last_row.get('MACD_12_26_9', 0)), 4),
                "SMA_50": round(float(last_row.get('SMA_50', 0)), 2),
            },
            "signal": generate_signal(last_row)
        }
        return result

    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return {"status": "Active", "service": "QuantMath Financial API v2"}