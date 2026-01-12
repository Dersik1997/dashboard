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

# --- 4. TAMPILAN & CSS KUSTOM (ALERT BULAT DI KANAN) ---
st.set_page_config(page_title="RiceGuard AI Dashboard", layout="wide")

st.markdown("""
    <style>
    /* Container Alert Bulat */
    .status-circle {
        position: fixed;
        top: 80px;
        right: 30px;
        width: 100px;
        height: 100px;
        border-radius: 50%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        color: white;
        font-weight: bold;
        text-align: center;
        font-size: 12px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
        animation: pulse-animation 2s infinite;
        border: 3px solid white;
    }

    /* Animasi Denyut agar lebih menarik */
    @keyframes pulse-animation {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }

    .circle-normal { background-color: #28a745; }
    .circle-warning { background-color: #ffc107; color: black; }
    .circle-danger { background-color: #dc3545; }

    /* Ukuran teks di dalam bulatan */
    .circle-label { font-size: 10px; margin-bottom: 2px; }
    .circle-status { font-size: 14px; text-transform: uppercase; }
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

if st.session_state.logs:
    last = st.session_state.logs[-1]
    current_status = last['Status']
    
    # Tentukan Warna Berdasarkan Status
    if current_status == "Normal":
        circle_class = "circle-normal"
        emoji = "✅"
    elif current_status == "Cahaya_Masuk":
        circle_class = "circle-warning"
        emoji = "⚠️"
    else:
        circle_class = "circle-danger"
        emoji = "🚨"

    # 1. POP-UP ALERT BULAT DI KANAN
    st.markdown(f"""
        <div class="status-circle {circle_class}">
            <div class="circle-label">{emoji} AI</div>
            <div class="circle-status">{current_status.split('_')[0]}</div>
            <div class="circle-label">{last['Waktu']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.title("🌾 RiceGuard AI: Monitoring")
    
    # 2. METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Temperatur", f"{last['Suhu']} °C")
    col2.metric("Kelembapan", f"{last['Kelembapan']} %")
    col3.metric("LDR", int(last['LDR']))

    # 3. GRAFIK
    df = pd.DataFrame(st.session_state.logs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Suhu'], name="Suhu", line=dict(color='red', width=3)))
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Kelembapan'], name="Lembap", yaxis="y2", line=dict(color='blue', width=3)))
    
    fig.update_layout(
        yaxis=dict(title=dict(text="Suhu (°C)", font=dict(color="red")), tickfont=dict(color="red")),
        yaxis2=dict(title=dict(text="Lembap (%)", font=dict(color="blue")), tickfont=dict(color="blue"), overlaying='y', side='right'),
        height=400, margin=dict(t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 4. DOWNLOAD & TABEL
    st.markdown("---")
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download Log CSV", data=csv_data, file_name=f"Log_RiceGuard.csv", mime='text/csv')
    st.dataframe(df[::-1], use_container_width=True)

else:
    st.title("🌾 RiceGuard AI: Monitoring")
    st.warning("⌛ Menunggu data sensor...")

# Auto Refresh
time.sleep(1)
st.rerun()
