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
    st.caption(f"**Status:** 🟢 Connected")

st.markdown("---")

# --- SECURITY HEADERS ---
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "x-api-key": API_KEY 
}

# --- HELPER: RESAMPLING ENGINE ---
def resample_market_data(df, target_interval):
    """
    Yüksek çözünürlüklü veriyi hedef periyoda dönüştürür.
    """
    if df is None or df.empty: return None
    
    rule_map = {
        "1m": "1min", "5m": "5min", 
        "15m": "15min", "30m": "30min", 
        "1h": "1h", "90m": "90min", 
        "4h": "4h", "1d": "1D", "1wk": "1W"
    }
    
    rule = rule_map.get(target_interval)
    if not rule: return df 
    
    date_col = None
    for col in df.columns:
        if "Date" in col or "Datetime" in col:
            date_col = col
            break
    
    if not date_col: return df

    df_working = df.copy()
    if not isinstance(df_working.index, pd.DatetimeIndex):
        df_working = df_working.set_index(date_col)
    
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    
    final_agg = {k: v for k, v in agg_dict.items() if k in df_working.columns}
    
    try:
        df_resampled = df_working.resample(rule).agg(final_agg).dropna()
        return df_resampled.reset_index()
    except:
        return df

# --- 1. BINANCE API (CRYPTO - PRIMARY) ---
def get_binance_data(symbol, interval, limit=1000):
    binance_symbol = symbol.replace("-", "").replace("USD", "USDT")
    if binance_symbol == "DOGEUSDT": binance_symbol = "DOGEUSDT" 

    url = "https://api.binance.com/api/v3/klines"
    
    if interval == "90m": interval = "1h" 

    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=5) 
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            "Open Time", "Open", "High", "Low", "Close", "Volume",
            "Close Time", "Quote Asset Volume", "Number of Trades",
            "Taker Buy Base Asset Volume", "Taker Buy Quote Asset Volume", "Ignore"
        ])
        
        df["Date"] = pd.to_datetime(df["Open Time"], unit="ms")
        numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, axis=1)
        
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        
    except Exception as e:
        print(f"Binance Fetch Error: {e}") 
        return None

# --- 2. YAHOO FINANCE (STOCKS/FOREX + FALLBACK) ---
@st.cache_data(ttl=600, show_spinner=False)
def get_yahoo_data(symbol, period, interval):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return None
        return df.reset_index()
    except:
        return None

# --- 3. DATA ROUTER (DÜZELTİLDİ: UI Elemanı Kaldırıldı) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_base_market_data(asset_type, symbol, period, base_interval):
    
    if asset_type == "Crypto":
        # 1. Önce Binance'i dene
        df = get_binance_data(symbol, base_interval, limit=1000)
        
        # 2. Eğer Binance hata verirse Yahoo'ya düş
        if df is None or df.empty:
            # BURADAKİ 'st.toast' KALDIRILDI -> Cache Hatasını Çözen Yer
            return get_yahoo_data(symbol, period, base_interval)
            
        return df
    
    else:
        # Hisse/Forex için Yahoo
        return get_yahoo_data(symbol, period, base_interval)

# --- HELPER: API FETCH ---
def fetch_data(url, payload):
    try:
        requests.get(BASE_URL, headers=BROWSER_HEADERS, timeout=2) 
    except: pass

    try:
        response = requests.post(url, json=payload, headers=BROWSER_HEADERS, timeout=50)
        if response.status_code == 200: return response.json()
        return None
    except:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Market Data Settings")
    
    asset_type = st.radio("Asset Type", ["Crypto", "Stocks", "Forex"], horizontal=True)
    
    if asset_type == "Crypto":
        symbol = st.selectbox("Select Symbol", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "AVAX-USD", "DOGE-USD", "BNB-USD"])
    elif asset_type == "Stocks":
        symbol = st.selectbox("Select Symbol", ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN", "GOOGL"])
    else:
        symbol = st.selectbox("Select Symbol", ["EURUSD=X", "GBPUSD=X", "JPY=X", "TRY=X", "GC=F"])

    st.markdown("---")
    
    period = st.selectbox(
        "Data Period (Total History)", 
        ["1d (1 Day)", "5d (5 Days)", "1mo (1 Month)", "3mo (3 Months)", "1y (1 Year)"], 
        index=2
    )
    period_code = period.split(" ")[0]
    
    if period_code == "1d": 
        fetch_interval = "1m"
        view_options = ["1m", "5m", "15m", "30m", "1h"]
    elif period_code == "5d": 
        fetch_interval = "5m"
        view_options = ["5m", "15m", "30m", "1h"]
    elif period_code == "1mo": 
        fetch_interval = "15m"
        view_options = ["15m", "30m", "1h", "4h", "1d"]
    elif period_code == "3mo": 
        fetch_interval = "1h"
        view_options = ["1h", "4h", "1d"]
    else: 
        fetch_interval = "1d"
        view_options = ["1d", "1wk"]

    view_interval = st.selectbox("Analysis Timeframe (View)", view_options, index=0)
    
    if st.button("🚀 Analyze Market", type="primary"):
        st.session_state['run_analysis'] = True

# --- MAIN PROCESS ---
if st.session_state.get('run_analysis', False):
    
    source_name = "Binance API" if asset_type == "Crypto" else "Yahoo Finance"
    with st.spinner(f"Fetching high-res data from {source_name}..."):
        
        # 1. TABAN VERİ ÇEK
        df_base = get_base_market_data(asset_type, symbol, period_code, fetch_interval)
        
        if df_base is None or df_base.empty:
            st.error(f"Data fetch failed for '{symbol}'.")
            st.stop()

        # 2. RESAMPLING
        if view_interval != fetch_interval:
            df = resample_market_data(df_base, view_interval)
            if df is None:
                st.error("Resampling failed.")
                st.stop()
            st.toast(f"Processed: {fetch_interval} ➝ {view_interval}", icon="🔄")
        else:
            df = df_base

        if len(df) < 30:
             st.warning(f"Insufficient data points ({len(df)}). Try a smaller timeframe.")
        
        # Veri Hazırlığı
        if isinstance(df.index, pd.DatetimeIndex) and "Date" not in df.columns and "Datetime" not in df.columns:
            df = df.reset_index()

        date_col = None
        for col in df.columns:
            if "Date" in col or "Datetime" in col:
                date_col = col
                break
        
        if not date_col:
             st.error("Date column missing.")
             st.stop()

        df['timestamp_str'] = df[date_col].astype(str)
        
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "timestamp": str(row['timestamp_str']),
                "open": row['Open'], "high": row['High'], "low": row['Low'], "close": row['Close'], "volume": row['Volume']
            })
        
        payload = {"symbol": symbol, "interval": view_interval, "data": candles}
        
        # API'ye Gönder
        result = fetch_data(API_URL, payload)
        
        if result:
            sig = result['signal']
            color = {"STRONG_BUY": "green", "BUY": "#90EE90", "NEUTRAL": "gray", "SELL": "#F08080", "STRONG_SELL": "red"}.get(sig, "gray")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Asset", result['symbol'], f"{period_code}")
            c2.metric("Last Price", f"${result['last_price']:.2f}")
            c3.metric("RSI (14)", result.get('indicators', {}).get('RSI', 0))
            c4.markdown(f"<div style='text-align:center; border:2px solid {color}; padding:5px; border-radius:10px;'><h3 style='color:{color}; margin:0;'>{sig}</h3></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader(f"📊 {symbol} Chart ({view_interval})")
            
            df['EMA20'] = df['Close'].ewm(span=20).mean()
            df['EMA50'] = df['Close'].ewm(span=50).mean()
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df[date_col], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Bar(x=df[date_col], y=df['Volume'], marker_color='rgba(100, 100, 250, 0.5)', name='Volume'), row=2, col=1)
            
            fig.update_layout(
                height=600, xaxis_rangeslider_visible=False, template="plotly_dark", 
                margin=dict(l=10, r=10, t=30, b=20), dragmode="pan", 
                legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
            
            with st.expander("🔍 API Response"): st.json(result)
        else:
            st.error("Backend Error. Try again.")
