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
    st.caption(f"**Target Backend:** `{BASE_URL}`")

st.markdown("---")


# --- HELPER: WAKE UP SERVER ---
def wake_up_server():
    try:
        requests.get(BASE_URL, timeout=1)
    except:
        pass


# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Market Data Settings")

    # 1. Asset Selection
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

    # 2. Data Period
    period = st.selectbox(
        "Data Period (Lookback)",
        ["1d (1 Day)", "5d (5 Days)", "1mo (1 Month)", "3mo (3 Months)", "1y (1 Year)", "ytd (Year to Date)"],
        index=2
    )

    period_code = period.split(" ")[0]

    # 3. Dynamic Intervals
    if period_code == "1d":
        valid_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]
        default_ix = 3  # 15m
    elif period_code == "5d":
        valid_intervals = ["5m", "15m", "30m", "60m", "90m", "1h", "1d"]
        default_ix = 3  # 60m
    elif period_code == "1mo":
        valid_intervals = ["15m", "30m", "60m", "90m", "1h", "1d"]
        default_ix = 5  # 1d
    elif period_code == "3mo":
        valid_intervals = ["1h", "1d", "1wk"]
        default_ix = 1  # 1d
    else:
        valid_intervals = ["1d", "1wk", "1mo"]
        default_ix = 0  # 1d

    interval = st.selectbox("Timeframe (Interval)", valid_intervals, index=default_ix)

    st.markdown("---")

    if st.button("🚀 Analyze Market", type="primary"):
        st.session_state['run_analysis'] = True

# --- MAIN PROCESS ---
if st.session_state.get('run_analysis', False):

    wake_up_server()

    with st.spinner(f"Fetching real-time data for {symbol}..."):
        try:
            # 1. FETCH DATA (Yahoo Finance)
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period_code, interval=interval)
            except Exception as yf_error:
                st.error(f"Yahoo Finance API Error: {yf_error}")
                st.warning("Too many requests. Please wait a minute and try again.")
                st.stop()

            if df.empty:
                st.error(f"No data found for '{symbol}'. Check if the ticker symbol is correct.")
                st.info("Tip: For crypto, ensure you add '-USD' (e.g., BTC-USD).")
                st.stop()

            # --- KRİTİK DÜZELTME ---
            # Backend SMA 200 hesaplıyor, bu yüzden en az 200 mum ŞART.
            # Eğer 200'den azsa, API'ye hiç gitmeden burada durduruyoruz.
            if len(df) < 200:
                st.warning(
                    f"⚠️ Insufficient data ({len(df)} candles). Strategy requires at least 200 data points for SMA calculation.")
                st.info(
                    "👉 Please increase 'Data Period' (e.g., switch from 1d to 5d) or decrease 'Timeframe' (e.g., switch from 1h to 15m).")
                st.stop()  # <--- BU KOMUT API HATASINI ENGELLER

            # Data Prep
            df = df.reset_index()

            # Detect Date Column
            date_col = None
            for col in df.columns:
                if "Date" in col or "Datetime" in col:
                    date_col = col
                    break

            if not date_col:
                st.error("Date column could not be detected. Data format issue.")
                st.stop()

            df['timestamp_str'] = df[date_col].astype(str)

            # Prepare Payload
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
            try:
                api_response = requests.post(API_URL, json=payload, timeout=50)

                # Sadece 200 OK dönerse işle, yoksa hatayı göster
                if api_response.status_code == 200:
                    result = api_response.json()

                    # --- DISPLAY RESULTS ---
                    sig = result['signal']

                    color_map = {
                        "STRONG_BUY": "green", "BUY": "#90EE90",
                        "NEUTRAL": "gray",
                        "SELL": "#F08080", "STRONG_SELL": "red"
                    }
                    color = color_map.get(sig, "gray")

                    # Metric Cards
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Asset", result['symbol'], f"{period_code} / {interval}")
                    c2.metric("Last Price", f"${result['last_price']:.2f}")

                    rsi_val = result.get('indicators', {}).get('RSI', 0)
                    c3.metric("RSI (14)", rsi_val)

                    c4.markdown(f"""
                        <div style="text-align: center; border: 2px solid {color}; padding: 5px; border-radius: 10px; background-color: rgba(0,0,0,0.2);">
                            <h3 style="color:{color}; margin:0; font-size: 1.2rem;">{sig}</h3>
                            <small style="color: #ccc;">AI Signal</small>
                        </div>
                    """, unsafe_allow_html=True)

                    st.markdown("---")

                    # CHARTING (Plotly)
                    st.subheader(f"📊 {symbol} Technical Analysis Chart")

                    # Calculate Local Indicators for Visualization
                    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
                    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.05,
                                        row_heights=[0.7, 0.3])

                    # Candles
                    fig.add_trace(go.Candlestick(
                        x=df[date_col], open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'], name='Price'
                    ), row=1, col=1)

                    # EMAs
                    fig.add_trace(
                        go.Scatter(x=df[date_col], y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'),
                        row=1, col=1)
                    fig.add_trace(
                        go.Scatter(x=df[date_col], y=df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'),
                        row=1, col=1)

                    # Volume
                    fig.add_trace(go.Bar(
                        x=df[date_col], y=df['Volume'], marker_color='rgba(100, 100, 250, 0.5)', name='Volume'
                    ), row=2, col=1)

                    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)

                    with st.expander("🔍 View Raw API Response"):
                        st.json(result)

                else:
                    # 400/500 hataları için kullanıcı dostu mesaj
                    st.error(f"Backend Error ({api_response.status_code}):")
                    try:
                        err_json = api_response.json()
                        st.code(err_json.get('detail', api_response.text))
                    except:
                        st.text(api_response.text)

            except requests.exceptions.ConnectionError:
                st.error(f"❌ Connection Error! Could not reach `{API_URL}`")
                st.info("If using Render Free Tier, the server might be sleeping. Wait 30s and try again.")
            except requests.exceptions.Timeout:
                st.error("❌ Timeout Error: Server took too long to wake up. Please try again.")
            except Exception as e:
                st.error(f"API Request Error: {e}")

        except Exception as e:
            st.error(f"System Error: {e}")

else:
    st.info("👈 Select a symbol from the left menu and click 'Analyze Market' to start.")
