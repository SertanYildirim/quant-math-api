import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import random
import datetime

# --- AYARLAR ---
API_URL = "http://127.0.0.1:8000/analyze"
st.set_page_config(page_title="QuantMath Terminal", layout="wide", page_icon="📈")

# --- BAŞLIK ---
st.title("📈 QuantMath: Algorithmic Trading Dashboard")
st.markdown("API tabanlı teknik analiz ve sinyal üretim motoru.")

# --- YAN MENÜ (INPUT) ---
st.sidebar.header("⚙️ Simülasyon Ayarları")
symbol = st.sidebar.text_input("Sembol", "BTC/USD")
num_candles = st.sidebar.slider("Mum Sayısı (Data Points)", 50, 500, 200)


# --- FONKSİYON: Sahte Veri Üretici ---
def generate_dummy_data(count):
    data = []
    price = 45000.0
    base_time = datetime.datetime.now() - datetime.timedelta(minutes=count * 15)

    for i in range(count):
        change = random.uniform(-50, 55)
        price += change

        candle = {
            "timestamp": (base_time + datetime.timedelta(minutes=i * 15)).strftime("%Y-%m-%d %H:%M:%S"),
            "open": price,
            "high": price + random.uniform(5, 50),
            "low": price - random.uniform(5, 50),
            "close": price + random.uniform(-10, 10),
            "volume": random.randint(100, 1000)
        }
        data.append(candle)
    return data


# --- BUTON VE MANTIK ---
if st.sidebar.button("🚀 Piyasayı Analiz Et", type="primary"):

    with st.spinner("API'ye bağlanılıyor ve analiz yapılıyor..."):
        try:
            # 1. Veri Üret
            dummy_data = generate_dummy_data(num_candles)

            # 2. API'ye Gönder
            payload = {
                "symbol": symbol,
                "interval": "15m",
                "data": dummy_data
            }
            response = requests.post(API_URL, json=payload)

            if response.status_code == 200:
                result = response.json()

                # --- SONUÇLARI GÖSTER ---

                # 1. Metrikler (KPI)
                col1, col2, col3, col4 = st.columns(4)

                # Sinyal Rengi
                signal = result['signal']
                signal_color = "normal"
                if "BUY" in signal: signal_color = "off"  # Streamlit'te yeşil trick
                if "SELL" in signal: signal_color = "inverse"

                col1.metric("Sembol", result['symbol'])
                col2.metric("Son Fiyat", f"${result['last_price']:.2f}")
                col3.metric("RSI (14)", result['indicators']['RSI'])
                col4.metric("ALGORİTMA KARARI", signal, delta=signal if "BUY" in signal else f"-{signal}")

                # 2. Grafik Çizimi (Plotly)
                st.subheader("📊 Fiyat Grafiği ve SMA Trendi")

                # DataFrame oluştur (Grafik için)
                df_chart = pd.DataFrame(dummy_data)

                fig = go.Figure()

                # Mum Grafiği
                fig.add_trace(go.Candlestick(
                    x=df_chart['timestamp'],
                    open=df_chart['open'], high=df_chart['high'],
                    low=df_chart['low'], close=df_chart['close'],
                    name='Fiyat'
                ))

                # SMA çizgilerini manuel hesaplayıp çizdirelim (Görsel şov için)
                # Not: Gerçek SMA API'den geliyor ama grafikte göstermek için burada basitçe çiziyoruz
                df_chart['SMA50'] = df_chart['close'].rolling(50).mean()
                fig.add_trace(
                    go.Scatter(x=df_chart['timestamp'], y=df_chart['SMA50'], line=dict(color='orange', width=1),
                               name='SMA 50'))

                fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                # 3. Ham JSON Verisi
                with st.expander("🔍 API'den Gelen Ham JSON Yanıtı"):
                    st.json(result)

            else:
                st.error(f"API Hatası: {response.status_code}")
                st.text(response.text)

        except Exception as e:
            st.error(f"Bağlantı Hatası: {e}")
            st.info("İpucu: 'uvicorn main:app --reload' komutuyla API'nin çalıştığından emin misin?")

else:
    st.info("Analizi başlatmak için sol menüdeki butona basın.")