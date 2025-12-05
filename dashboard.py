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

# --- GÜVENLİ AYAR YÖNETİMİ (SECRETS) ---
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
    status_msg = "Cloud Connection" if "127.0.0.1" not in BASE_URL else "Local Connection"
    st.caption(f"**Status:** 🟢 {status_msg}")

st.markdown("---")

# --- 🔑 GÜVENLİK VE TARAYICI AYARLARI ---
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "x-api-key": API_KEY 
}

# --- HELPER: WAKE UP SERVER ---
def wake_up_server():
    try:
        # Hata yakalama burada da önemli, header'da karakter sorunu varsa burası da patlayabilir
        requests.get(BASE_URL, headers=BROWSER_HEADERS, timeout=3)
    except (UnicodeEncodeError, Exception):
        pass 

# --- HELPER: SMART FETCH DATA ---
def fetch_data(url, payload):
    
    wake_up_server()
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                status_box = st.info("⏳ Analiz yapılıyor... (Backend bağlantısı kuruluyor)")
            else:
                status_box.warning(f"⚠️ Sunucu yanıt vermedi, tekrar deneniyor ({attempt+1}/{max_retries})...")

            # Şifreli Header'ı gönderiyoruz
            response = requests.post(url, json=payload, headers=BROWSER_HEADERS, timeout=60)
            
            # Yetki Hatası Kontrolü
            if response.status_code == 403:
                status_box.error("⛔ ERİŞİM REDDEDİLDİ: API Anahtarı hatalı veya eksik.")
                st.stop()

            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                raise Exception("Sunucu HTML döndü (Nginx/Bot Koruması).")

            response.raise_for_status()
            status_box.empty()
            return response.json()
        
        # ÖZEL HATA YAKALAMA: Türkçe Karakter Sorunu
        except UnicodeEncodeError:
            status_box.error("❌ KRİTİK HATA: API Anahtarınız geçersiz karakter içeriyor.")
            st.error("HTTP başlıklarında Türkçe karakter (ı, ğ, ş, ü, ö, ç) kullanılamaz.")
            st.info(f"Şu anki anahtarınız: '{API_KEY}' -> Lütfen bunu İngilizce karakterlerle (i, g, s...) değiştirin.")
            st.stop()
            
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, Exception) as e:
            time.sleep(2)
            
            if attempt == max_retries - 1:
                status_box.error(f"❌ Hata: Backend erişilemedi.")
                st.error(f"Detay: {str(e)}")
                return None
            
    return None

# --- SIDEBAR: SETTINGS ---
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
        symbol = st.text_input("Enter Symbol (Yahoo Ticker)", value="BTC-USD")

    st.markdown("---")
    
    period = st.selectbox(
        "Data Period (Lookback)", 
        ["1d (1 Day)", "5d (5 Days)", "1mo (1 Month)", "3mo (3 Months)", "1y (1 Year)", "ytd (Year to Date)"], 
        index=2
    )
    
    period_code = period.split(" ")[0]
    
    if period_code == "1d":
        valid_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]
        default_ix = 3 
    elif period_code == "5d":
        valid_intervals = ["5m", "15m", "30m", "60m", "90m", "1h", "1d"]
        default_ix = 3 
    elif period_code == "1mo":
        valid_intervals = ["15m", "30m", "60m", "90m", "1h", "1d"]
        default_ix = 5 
    elif period_code == "3mo":
        valid_intervals = ["1h", "1d", "1wk"]
        default_ix = 1 
    else: 
        valid_intervals = ["1d", "1wk", "1mo"]
        default_ix = 0 

    interval = st.selectbox("Timeframe (Interval)", valid_intervals, index=default_ix)
    
    st.markdown("---")
    
    if st.button("🚀 Analyze Market", type="primary"):
        st.session_state['run_analysis'] = True

# --- MAIN PROCESS ---
if st.session_state.get('run_analysis', False):
    
    with st.spinner(f"Fetching real-time data for {symbol}..."):
        try:
            # 1. FETCH DATA
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period_code, interval=interval)
            except Exception as yf_error:
                st.error(f"Yahoo Finance API Error: {yf_error}")
                st.stop()
            
            if df.empty:
                st.error(f"No data found for '{symbol}'.")
                st.stop()
            
            if len(df) < 50:
                st.warning(f"Insufficient data ({len(df)} candles). Results might be inaccurate.")
            
            df = df.reset_index()
            
            date_col = None
            for col in df.columns:
                if "Date" in col or "Datetime" in col:
                    date_col = col
                    break
            
            if not date_col:
                st.error("Date column could not be detected.")
                st.stop()

            df['timestamp_str'] = df[date_col].astype(str)
            
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
            
            payload = {
                "symbol": symbol,
                "interval": interval,
                "data": candles
            }
            
            # 2. SEND TO API
            result = fetch_data(API_URL, payload)
            
            if result:
                sig = result['signal']
                color_map = {"STRONG_BUY": "green", "BUY": "#90EE90", "NEUTRAL": "gray", "SELL": "#F08080", "STRONG_SELL": "red"}
                color = color_map.get(sig, "gray")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Asset", result['symbol'], f"{period_code} / {interval}")
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
                st.subheader(f"📊 {symbol} Technical Analysis Chart")
                
                df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df[date_col], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df[date_col], y=df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
                fig.add_trace(go.Bar(x=df[date_col], y=df['Volume'], marker_color='rgba(100, 100, 250, 0.5)', name='Volume'), row=2, col=1)

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"))
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("🔍 View Raw API Response"):
                    st.json(result)

        except Exception as e:
            st.error(f"System Error: {e}")

else:
    st.info("👈 Select a symbol from the left menu and click 'Analyze Market' to start.")
