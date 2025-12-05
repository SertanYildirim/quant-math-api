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
except Exception:
    BASE_URL = "http://127.0.0.1:8000"

API_URL = f"{BASE_URL}/analyze"

# --- HEADER ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.markdown("## ⚡")
with col_title:
    st.title("QuantMath: Real-Time Algorithmic Trader")
    status_msg = "Cloud Connection" if "127.0.0.1" not in BASE_URL else "Local Connection"
    st.caption(f"**Status:** 🟢 {status_msg}")

st.markdown("---")

# --- 🔑 GÜVENLİK AYARLARI ---
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    API_KEY = "demo-key"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "x-api-key": API_KEY 
}

# --- HELPER: MARKET DATA CACHING (RATE LIMIT ÇÖZÜMÜ) ---
# ttl=600: Veriyi 10 dakika (600 saniye) boyunca hafızada tut. 
# Yahoo'ya 10 dakikada bir sadece 1 kere gider.
@st.cache_data(ttl=600, show_spinner=False)
def get_market_data(symbol, period, interval):
    """
    Yahoo Finance verisini çeker ve önbelleğe alır.
    Hata alırsa 3 kere tekrar dener (Retry Logic).
    """
    retries = 3
    for i in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                return None
            
            return df
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                time.sleep(2 * (i + 1)) # 2sn, 4sn, 6sn bekle (Exponential Backoff)
                continue
            else:
                return None # Başka hataysa direkt dön
    return None

# --- HELPER: API FETCH ---
def fetch_data(url, payload):
    try:
        requests.get(BASE_URL, headers=BROWSER_HEADERS, timeout=1) # Wake up
    except:
        pass

    try:
        response = requests.post(url, json=payload, headers=BROWSER_HEADERS, timeout=45)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Market Data Settings")
    
    asset_type = st.radio("Asset Type", ["Crypto", "Stocks", "Forex", "Custom"], horizontal=True)
    
    if asset_type == "Crypto":
        symbol = st.selectbox("Select Symbol", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "AVAX-USD"])
    elif asset_type == "Stocks":
        symbol = st.selectbox("Select Symbol", ["AAPL", "TSLA", "MSFT", "GOOGL", "NVDA", "AMZN"])
    elif asset_type == "Forex":
        symbol = st.selectbox("Select Symbol", ["EURUSD=X", "GBPUSD=X", "JPY=X", "TRY=X", "GC=F"])
    else:
        symbol = st.text_input("Enter Symbol", value="BTC-USD")

    st.markdown("---")
    
    period = st.selectbox("Data Period", ["1d (1 Day)", "5d (5 Days)", "1mo (1 Month)", "3mo (3 Months)", "1y (1 Year)"], index=2)
    period_code = period.split(" ")[0]
    
    if period_code == "1d": valid_intervals = ["1m", "2m", "5m", "15m", "30m", "1h"]
    elif period_code == "5d": valid_intervals = ["5m", "15m", "30m", "1h"]
    elif period_code == "1mo": valid_intervals = ["15m", "30m", "1h", "1d"]
    else: valid_intervals = ["1d", "1wk"]
    
    # Default index ayarı (Listenin dışına taşmaması için kontrol)
    default_ix = 0
    if "1d" in valid_intervals: default_ix = valid_intervals.index("1d")
    if len(valid_intervals) <= default_ix: default_ix = 0

    interval = st.selectbox("Timeframe", valid_intervals, index=default_ix)
    
    if st.button("🚀 Analyze Market", type="primary"):
        st.session_state['run_analysis'] = True
        # Yeni analizde cache'i temizle ki taze veri gelsin
        # st.cache_data.clear() # İsteğe bağlı: Çok sık limit yiyorsan bunu kapalı tut

# --- MAIN PROCESS ---
if st.session_state.get('run_analysis', False):
    
    with st.spinner(f"Fetching market data for {symbol}..."):
        
        # 1. VERİYİ ÖNBELLEKTEN VEYA YAHOO'DAN ÇEK
        df = get_market_data(symbol, period_code, interval)
        
        if df is None or df.empty:
            st.error(f"⚠️ Data fetch failed or rate limited for '{symbol}'.")
            st.info("Please wait a few seconds or try a different asset.")
            st.stop()

        # Veri Yetersizliği Kontrolü
        if len(df) < 50:
             st.warning("Insufficient data for accurate analysis. Try increasing the Data Period.")

        # Veri Hazırlığı
        df = df.reset_index()
        date_col = None
        for col in df.columns:
            if "Date" in col or "Datetime" in col:
                date_col = col
                break
        
        if not date_col:
            st.error("Date column error.")
            st.stop()

        df['timestamp_str'] = df[date_col].astype(str)
        
        # Payload
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "timestamp": str(row['timestamp_str']),
                "open": row['Open'],
                "high": row['High'],
                "low": row['Low'],
                "close": row['Close'],
                "volume": row['Volume']
            })
        
        payload = {"symbol": symbol, "interval": interval, "data": candles}
        
        # 2. API'YE GÖNDER
        result = fetch_data(API_URL, payload)
        
        if result:
            sig = result['signal']
            color_map = {"STRONG_BUY": "green", "BUY": "#90EE90", "NEUTRAL": "gray", "SELL": "#F08080", "STRONG_SELL": "red"}
            color = color_map.get(sig, "gray")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Asset", result['symbol'], f"{period_code}")
            c2.metric("Last Price", f"${result['last_price']:.2f}")
            
            rsi_val = result.get('indicators', {}).get('RSI', 0)
            c3.metric("RSI (14)", rsi_val)
            
            c4.markdown(f"""
                <div style="text-align: center; border: 2px solid {color}; padding: 5px; border-radius: 10px; background-color: rgba(0,0,0,0.2);">
                    <h3 style="color:{color}; margin:0; font-size: 1.2rem;">{sig}</h3>
                    <small>AI Signal</small>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # CHARTING
            st.subheader(f"📊 {symbol} Analysis")
            
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df[date_col], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Bar(x=df[date_col], y=df['Volume'], marker_color='rgba(100, 100, 250, 0.5)', name='Volume'), row=2, col=1)

            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("🔍 Raw API Response"):
                st.json(result)
        else:
            st.error("Backend Connection Failed or Timeout.")
