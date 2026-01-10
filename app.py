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

# --- KONFIGURASI ---
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

# --- 4. TAMPILAN STREAMLIT ---
st.set_page_config(page_title="RiceGuard AI Dashboard", layout="wide")

st.title("🌾 RiceGuard AI: Monitoring & Report")
st.markdown(f"**Topik:** `{TOPIC_SENSOR}` | **Limit:** `200 Data`")
st.markdown("---")

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
if st.session_state.logs:
    last = st.session_state.logs[-1]
    
    # Status & Metrics
    st.info(f"### 🤖 Prediksi AI: **{last['Status']}**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Suhu", f"{last['Suhu']} °C")
    m2.metric("Lembap", f"{last['Kelembapan']} %")
    m3.metric("LDR", int(last['LDR']))

    # Grafik
    df = pd.DataFrame(st.session_state.logs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Suhu'], name="Suhu", line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df['Waktu'], y=df['Kelembapan'], name="Lembap", yaxis="y2", line=dict(color='blue')))
    fig.update_layout(
        yaxis=dict(title=dict(text="Suhu (°C)", font=dict(color="red")), tickfont=dict(color="red")),
        yaxis2=dict(title=dict(text="Lembap (%)", font=dict(color="blue")), tickfont=dict(color="blue"), overlaying='y', side='right'),
        height=350, margin=dict(t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. TABEL & FITUR DOWNLOAD ---
    st.markdown("---")
    st.subheader("📋 Riwayat Data Terakhir")
    
    # Tombol Download CSV
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data (.csv)",
        data=csv_data,
        file_name=f"Log_Gudang_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime='text/csv',
    )
    
    st.dataframe(df[::-1], use_container_width=True)

else:
    st.warning("⌛ Menunggu data dari sensor...")

# Auto Refresh
time.sleep(1)
st.rerun()s
