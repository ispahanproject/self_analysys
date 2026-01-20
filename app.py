import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio
import google.generativeai as genai
import json

# --- 初期設定 ---
pio.templates.default = "plotly_dark"
st.set_page_config(page_title="Pilot AI Log", page_icon="✈️", layout="wide")

# --- Gemini API設定 ---
model = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 最新ライブラリではこれが標準です
        model = genai.GenerativeModel('gemini-1.5-flash')
    else:
        st.error("Secretsに 'GEMINI_API_KEY' がありません。")
except Exception as e:
    st.error(f"API Error: {e}")

# コンピテンシー定義
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

st.title("👨‍✈️ AI Pilot Performance Tracker")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)
try:
    df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4], ttl=5)
except:
    try:
        df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3], ttl=5)
    except:
        df = pd.DataFrame()

if df.empty:
    df = pd.DataFrame(columns=["Date", "Phase", "Memo", "Tags", "AI_Feedback"])
else:
    if "AI_Feedback" not in df.columns: df["AI_Feedback"] = ""
    for col in df.columns: df[col] = df[col].astype(str)

# --- 入力フォーム ---
st.sidebar.header("📝 New Entry with AI")

if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="メモを入力...")

if st.sidebar.button("✨ Analyze with AI", type="primary"):
    if model and input_memo:
        with st.sidebar.status("Co-pilot is analyzing..."):
            prompt = f"""
            以下を分析しJSONで出力せよ:
            メモ: {input_memo}
            1. "phase": {PHASES} から1つ
            2. "tags": {COMPETENCIES} から最大3つ
            3. "feedback": 日本語で1文のフィードバック
            Example: {{"phase": "Landing", "tags": ["FM"], "feedback": "コメント"}}
            """
            try:
                response = model.generate_content(prompt)
                text = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                st.session_state.form_phase = result.get("phase", "Pre-flight")
                st.session_state.form_tags = result.get("tags", [])
                st.session_state.form_feedback = result.get("feedback", "")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

with st.sidebar.form("save"):
    date = st.date_input("Date", datetime.now())
    idx = PHASES.index(st.session_state.form_phase) if st.session_state.form_phase in PHASES else 0
    phase = st.selectbox("Phase", PHASES, index=idx)
    tags = st.multiselect("Tags", COMPETENCIES, default=st.session_state.form_tags)
    fb = st.text_area("Feedback", value=st.session_state.form_feedback)
    
    if st.form_submit_button("Save"):
        new_row = pd.DataFrame([{"Date": str(date), "Phase": phase, "Memo": input_memo, "Tags": ", ".join(tags), "AI_Feedback": fb}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
        st.success("Saved!")

# --- ログ表示 ---
st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)
