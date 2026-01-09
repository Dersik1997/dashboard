import streamlit as st
import pandas as pd
import json
import time
import queue
import paho.mqtt.client as mqtt
from datetime import datetime
import plotly.graph_objs as go

# 1. ANTRIAN DATA (Thread-Safe Bridge)
# Menggunakan cache agar queue tidak terhapus saat script rerun
@st.cache_resource
def get_queue():
    return queue.Queue()

data_queue = get_queue()

# --- KONFIGURASI ---
MQTT_BROKER = "broker.emqx.io"
TOPIC_SENSOR = "iot/sensor/data"

# 2. MQTT CALLBACK
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        # Print di terminal untuk memastikan data terus mengalir
        print(f"DEBUG: Data Masuk -> {payload}")
        data = json.loads(payload)
        
        # Masukkan ke Queue (Bukan ke st.session_state)
        data_queue.put(data)
    except Exception as e:
        print(f"Error on_message: {e}")

# 3. KONEKSI MQTT (Single Instance)
@st.cache_resource
def init_mqtt():
    # Gunakan VERSION1 untuk paho-mqtt 2.0+
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(TOPIC_SENSOR)
    client.loop_start()
    return client

# Jalankan MQTT di background
init_mqtt()

# --- 4. TAMPILAN STREAMLIT ---
st.set_page_config(page_title="RiceGuard AI", layout="wide")
st.title("🌾 RiceGuard AI Monitoring")

if "logs" not in st.session_state:
    st.session_state.logs = []

# PINDAHKAN DATA DARI QUEUE KE SESSION STATE
# Ini dilakukan di main thread Streamlit agar aman
while not data_queue.empty():
    raw_data = data_queue.get()
    new_row = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "temp": raw_data.get("temp", 0),
        "hum": raw_data.get("hum", 0),
        "ldr": raw_data.get("ldr", 0),
        "status": raw_data.get("status", "Unknown")
    }
    st.session_state.logs.append(new_row)
    if len(st.session_state.logs) > 50: # Simpan 50 data terakhir
        st.session_state.logs.pop(0)

# --- 5. RENDER UI ---
if st.session_state.logs:
    last = st.session_state.logs[-1]
    
    # Indikator Status
    st.subheader(f"Status Saat Ini: {last['status']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Temperatur", f"{last['temp']} °C")
    col2.metric("Kelembapan", f"{last['hum']} %")
    col3.metric("Cahaya", int(last['ldr']))

    # Grafik
    df = pd.DataFrame(st.session_state.logs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['ts'], y=df['temp'], name="Suhu", line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df['ts'], y=df['hum'], name="Lembap", yaxis="y2", line=dict(color='blue')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Tabel
    st.dataframe(df[::-1], use_container_width=True)
else:
    st.warning("⚠️ Data sudah masuk di terminal, menunggu sinkronisasi ke Dashboard...")
    st.info("Pastikan browser tidak dalam mode 'Sleep' atau 'Tab Inactive'.")

# --- 6. AUTO REFRESH ---
time.sleep(1)
st.rerun()