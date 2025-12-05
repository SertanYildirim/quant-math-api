import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import datetime
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="QuantMath Terminal", layout="wide", page_icon="📈")

# --- API URL MANAGEMENT ---
try:
    if "API_URL" in st.secrets:
        raw_url = st.secrets["API_URL"]
        clean_url = raw_url.strip().strip('"').strip("'").rstrip('/')
        if not clean_url.startswith("http"):
            clean_url = f"https://{clean_url}"
        BASE_URL = clean_url
    else:
        BASE_URL = "http://127.0.0.1:8000"

    if "API_KEY" in st.secrets:
        API_KEY = st.secrets["API_KEY"]
    else:
        API_KEY = "demo-key"

except Exception:
    BASE_URL = "http://127.0.0.1:8000"
    API_KEY = "demo-key"

API_URL = f"{BASE_URL}/analyze"

# --- HEADER ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.markdown("## ⚡")
with col_title:
    st.title("QuantMath: Real-Time Algorithmic Trader")
    st.caption(f"**Status:** 🟢 {status_msg if 'status_msg' in locals() else 'Active'}")

st.markdown("---")

# --- 🔑 GÜVENLİK AYARLARI ---
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "x-api-key": API_KEY 
}

# --- 1. BINANCE API (KRİPTO İÇİN - ÇOK HIZLI VE LİMİTSİZ) ---
def get_binance_data(symbol, interval, limit=200):
    """
    Binance Public API kullanarak veri çeker. (API Key gerekmez)
    """
    # Binance sembol formatı: BTC-USD -> BTCUSDT
    binance_symbol = symbol.replace("-", "").replace("USD", "USDT")
    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # DataFrame oluştur
        df = pd.DataFrame(data, columns=[
            "Open Time", "Open", "High", "Low", "Close", "Volume",
            "Close Time", "Quote Asset Volume", "Number of Trades",
            "Taker Buy Base Asset Volume", "Taker Buy Quote Asset Volume", "Ignore"
        ])
        
        # Tipleri düzelt
        df["Date"] = pd.to_datetime(df["Open Time"], unit="ms")
        numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, axis=1)
        
        # Sütun adlarını standardize et
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        
    except Exception as e:
        # st.error(f"Binance Error: {e}")
        return None

# --- 2. YAHOO FINANCE (HİSSE İÇİN - CACHED) ---
@st.cache_data(ttl=600, show_spinner=False)
def get_yahoo_data(symbol, period, interval):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return None
        return df.reset_index()
    except:
        return None

# --- 3. GENEL VERİ GETİRİCİ ---
def get_market_data(asset_type, symbol, period, interval):
    if asset_type == "Crypto":
        # Kripto için önce Binance dene (Hızlı), olmazsa Yahoo'ya düş
        df = get_binance_data(symbol, interval, limit=300)
        if df is not None and not df.empty:
            return df
        else:
            return get_yahoo_data(symbol, period, interval)
    else:
        # Hisse/Forex için Yahoo kullan
        return get_yahoo_data(symbol, period, interval)

# --- HELPER: API FETCH ---
def fetch_data(url, payload):
    try:
        requests.get(BASE_URL, headers=BROWSER_HEADERS, timeout=2)
    except: pass

    try:
        response = requests.post(url, json=payload, headers=BROWSER_HEADERS, timeout=45)
        if response.status_code == 200: return response.json()
        return None
    except:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Market Data Settings")
    
    asset_type = st.radio("Asset Type", ["Crypto", "Stocks", "Forex"], horizontal=True)
    
    if asset_type == "Crypto":
        symbol = st.selectbox("Select Symbol", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "AVAX-USD"])
    elif asset_type == "Stocks":
        symbol = st.selectbox("Select Symbol", ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"])
    else:
        symbol = st.selectbox("Select Symbol", ["EURUSD=X", "GBPUSD=X", "JPY=X"])

    st.markdown("---")
    
    # Binance ve Yahoo interval formatları genelde uyumludur (15m, 1h, 1d)
    interval = st.selectbox("Timeframe", ["15m", "30m", "1h", "4h", "1d"], index=2)
    
    # Period sadece Yahoo için geçerli, Binance limit kullanır
    if asset_type != "Crypto":
        period = st.selectbox("Data Period", ["1mo", "3mo", "1y"], index=0)
        period_code = period.split(" ")[0]
    else:
        period_code = "N/A (Binance Limit)"

    st.markdown("---")
    
    if st.button("🚀 Analyze Market", type="primary"):
        st.session_state['run_analysis'] = True

# --- MAIN PROCESS ---
if st.session_state.get('run_analysis', False):
    
    with st.spinner(f"Fetching data for {symbol}..."):
        
        # Veriyi Çek
        df = get_market_data(asset_type, symbol, period_code if asset_type != "Crypto" else None, interval)
        
        if df is None or df.empty:
            st.error(f"Data fetch failed for '{symbol}'. API Limits or Invalid Symbol.")
            st.stop()

        if len(df) < 50:
             st.warning("Insufficient data. Results might be inaccurate.")

        # Tarih sütunu standardizasyonu (Binance 'Date', Yahoo 'Date' veya 'Datetime')
        date_col = "Date" if "Date" in df.columns else "Datetime"
        df['timestamp_str'] = df[date_col].astype(str)
        
        # Payload Hazırla
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "timestamp": str(row['timestamp_str']),
                "open": row['Open'], "high": row['High'], "low": row['Low'], "close": row['Close'], "volume": row['Volume']
            })
        
        payload = {"symbol": symbol, "interval": interval, "data": candles}
        
        # API'ye Gönder
        result = fetch_data(API_URL, payload)
        
        if result:
            sig = result['signal']
            color = {"STRONG_BUY": "green", "BUY": "#90EE90", "NEUTRAL": "gray", "SELL": "#F08080", "STRONG_SELL": "red"}.get(sig, "gray")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Asset", result['symbol'])
            c2.metric("Last Price", f"${result['last_price']:.2f}")
            c3.metric("RSI (14)", result.get('indicators', {}).get('RSI', 0))
            c4.markdown(f"<div style='text-align:center; border:2px solid {color}; padding:5px; border-radius:10px;'><h3 style='color:{color}; margin:0;'>{sig}</h3></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader(f"📊 {symbol} Chart")
            
            # Grafik
            df['EMA20'] = df['Close'].ewm(span=20).mean()
            df['EMA50'] = df['Close'].ewm(span=50).mean()
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df[date_col], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Bar(x=df[date_col], y=df['Volume'], marker_color='rgba(100, 100, 250, 0.5)', name='Volume'), row=2, col=1)
            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("🔍 API Response"): st.json(result)
        else:
            st.error("Backend Error. Try again.")
