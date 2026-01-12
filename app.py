import streamlit as st
import pandas as pd
import json
import time
import queue
import paho.mqtt.client as mqtt
from datetime import datetime
import plotly.graph_objs as go

# 1. ANTRIAN DATA
@st.cache_resource
def get_queue():
    return queue.Queue()

data_queue = get_queue()

# --- KONFIGURASI MQTT ---
MQTT_BROKER = "broker.emqx.io"
TOPIC_SENSOR = "iot/sensor/data"

# 2. MQTT CALLBACK
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        data_queue.put(data)
    except Exception as e:
        print(f"Error on_message: {e}")

# 3. KONEKSI MQTT
@st.cache_resource
def init_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(TOPIC_SENSOR)
    client.loop_start()
    return client

init_mqtt()

# --- 4. TAMPILAN & CSS KUSTOM ---
st.set_page_config(page_title="RiceGuard AI Dashboard", layout="wide")

# CSS untuk Sticky Header (Pop-up Alert yang ikut scroll)
st.markdown("""
    <style>
    .sticky-header {
        position: fixed;
        top: 50px;
        left: 0;
        width: 100%;
        z-index: 999;
        padding: 10px 20px;
        border-bottom: 2px solid #ddd;
        text-align: center;
        font-weight: bold;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
    }
    .status-normal { background-color: #d4edda; color: #155724; }
    .status-warning { background-color: #fff3cd; color: #856404; }
    .status-danger { background-color: #f8d7da; color: #721c24; }
    
    /* Memperbaiki jarak agar konten bawah tidak tertutup sticky header */
    .main-content { margin-top: 80px; }
    </style>
    """, unsafe_allow_html=True)

# Session State untuk Log Data
if "logs" not in st.session_state:
    st.session_state.logs = []

# PINDAHKAN DATA DARI QUEUE KE SESSION STATE
while not data_queue.empty():
    raw_data = data_queue.get()
    
    s_val = raw_data.get("suhu", 0)
    k_val = raw_data.get("kelembapan", 0)
    l_val = raw_data.get("ldr", 0)
    st_val = raw_data.get("status", "Unknown")
    
    # Logika Anti-Duplikat
    is_duplicate = False
    if st.session_state.logs:
        last_entry = st.session_state.logs[-1]
        if (last_entry["Suhu"] == s_val and last_entry["Kelembapan"] == k_val and last_entry["Status"] == st_val):
            is_duplicate = True

    if not is_duplicate:
        new_row = {
            "Tanggal": datetime.now().strftime("%Y-%m-%d"),
            "Waktu": datetime.now().strftime("%H:%M:%S"),
            "Suhu": s_val,
            "Kelembapan": k_val,
            "LDR": l_val,
            "Status": st_val
        }
        st.session_state.logs.append(new_row)
        if len(st.session_state.logs) > 200: 
            st.session_state.logs.pop(0)

# --- 5. RENDER UI ---

# Cek data terakhir untuk Alert
if st.session_state.logs:
    last = st.session_state.logs[-1]
    current_status = last['Status']
    
    # Tentukan class CSS berdasarkan status
    if current_status == "Normal":
        status_class = "status-normal"
        icon = "✅"
    elif current_status == "Cahaya_Masuk":
        status_class = "status-warning"
        icon = "⚠️"
    else:
        status_class = "status-danger"
        icon = "🚨"

    # 1. POP-UP ALERT (Sticky Header)
    st.markdown(f"""
        <div class="sticky-header {status_class}">
            {icon} STATUS AI SAAT INI: {current_status.upper()} | 
            🕒 Terakhir Update: {last['Waktu']} | 🌡️ {last['Suhu']}°C | 💧 {last['Kelembapan']}%
        </div>
        """, unsafe_allow_html=True)

    # Beri ruang kosong agar konten tidak tertutup sticky header
    st.markdown('<div class="main-content"></div>', unsafe_allow_html=True)

    st.title("🌾 RiceGuard AI: Monitoring & Report")
    
    # 2. METRICS UTAMA
    col1, col2, col3 = st.columns(3)
    col1.metric("Suhu", f"{last['Suhu']} °C")
    col2.metric("Kelembapan", f"{last['Kelembapan']} %")
    col3.metric("LDR", int(last['LDR']))

    # 3. GRAFIK REALTIME
    df = pd.DataFrame(st.session_state.logs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Suhu'], name="Suhu", line=dict(color='red', width=3)))
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Kelembapan'], name="Lembap", yaxis="y2", line=dict(color='blue', width=3)))
    
    fig.update_layout(
        title="Tren Sensor Real-time",
        xaxis=dict(title="Waktu"),
        yaxis=dict(title=dict(text="Suhu (°C)", font=dict(color="red")), tickfont=dict(color="red")),
        yaxis2=dict(title=dict(text="Lembap (%)", font=dict(color="blue")), tickfont=dict(color="blue"), overlaying='y', side='right'),
        height=400, margin=dict(t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 4. TABEL & DOWNLOAD
    st.markdown("---")
    st.subheader("📋 Riwayat 200 Data Terakhir")
    
    c1, c2 = st.columns([1, 4])
    csv_data = df.to_csv(index=False).encode('utf-8')
    c1.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name=f"Log_Gudang_{datetime.now().strftime('%H%M%S')}.csv",
        mime='text/csv',
    )
    
    st.dataframe(df[::-1], use_container_width=True)

else:
    st.title("🌾 RiceGuard AI: Monitoring & Report")
    st.warning("⌛ Menunggu data pertama dari sensor ESP32...")

# 6. AUTO REFRESH (1 Detik agar terasa realtime)
time.sleep(1)
st.rerun()
