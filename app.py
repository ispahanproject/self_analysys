import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio
import plotly.graph_objects as go
import json
import requests

# --- 初期設定 ---
pio.templates.default = "plotly_dark"
st.set_page_config(page_title="Pilot AI Log", page_icon="✈️", layout="wide")

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

# --- サイドバー: AI解析付き入力フォーム ---
st.sidebar.header("📝 New Entry with AI")

if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="例: クロスウィンド着陸。接地寸前に風下ラダーを入れたらスムーズだった。")

if st.sidebar.button("✨ Analyze with AI", type="primary"):
    # 【最重要修正】APIキーのゴミ取り（引用符や改行を強制削除）
    raw_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = str(raw_key).replace('"', '').replace("'", "").strip()
    
    if not api_key:
        st.sidebar.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    elif input_memo:
        with st.sidebar.status("Co-pilot is analyzing..."):
            prompt_text = f"""
            あなたはベテランパイロットのインストラクターです。
            以下のフライトメモを分析し、必ずJSON形式のみで出力してください。Markdownの装飾は不要です。
            
            [メモ]
            {input_memo}
            
            [出力要件]
            1. "phase": メモの内容に最も合致するフライトフェーズ ({', '.join(PHASES)}) から1つ選ぶ。
            2. "tags": 関連するコンピテンシー ({', '.join(COMPETENCIES)}) をリストで選ぶ (最大3つ)。
            3. "feedback": インストラクターとしての短いフィードバック(1文)。
            
            Example: {{"phase": "Landing", "tags": ["FM", "SA"], "feedback": "適切な修正操作です。"}}
            """
            
            # APIリクエスト設定 (URLパラメータではなくヘッダーを使用)
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key  # ここでクリーンなキーを渡す
            }
            data = {
                "contents": [{"parts": [{"text": prompt_text}]}]
            }
            
            try:
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    result_json = response.json()
                    text = result_json['candidates'][0]['content']['parts'][0]['text']
                    # JSONクリーニング
                    text = text.replace("```json", "").replace("```", "").strip()
                    result = json.loads(text)
                    
                    st.session_state.form_phase = result.get("phase", "Pre-flight")
                    st.session_state.form_tags = result.get("tags", [])
                    st.session_state.form_feedback = result.get("feedback", "")
                    st.rerun()
                else:
                    st.sidebar.error(f"Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                st.sidebar.error(f"通信エラー: {e}")
    else:
        st.sidebar.warning("メモを入力してください")

# 3. 確認・修正・保存フォーム
with st.sidebar.form("save_form"):
    date = st.date_input("Date", datetime.now())
    
    current_phase_idx = 0
    if st.session_state.form_phase in PHASES:
        current_phase_idx = PHASES.index(st.session_state.form_phase)
        
    phase = st.selectbox("Phase", PHASES, index=current_phase_idx)
    tags = st.multiselect("Performance Indicators", COMPETENCIES, default=st.session_state.form_tags)
    feedback = st.text_area("AI / Instructor Comment", value=st.session_state.form_feedback, height=80)
    
    submitted = st.form_submit_button("Save to Logbook")
    
    if submitted:
        new_row = pd.DataFrame([{
            "Date": str(date),
            "Phase": phase,
            "Memo": input_memo,
            "Tags": ", ".join(tags),
            "AI_Feedback": feedback
        }])
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        st.success("Log Saved!")
        st.session_state.form_phase = "Pre-flight"
        st.session_state.form_tags = []
        st.session_state.form_feedback = ""
        st.rerun()

# --- ダッシュボード表示 ---
tab1, tab2 = st.tabs(["📊 Analytics", "🗂 Logbook"])

with tab1:
    if not df.empty:
        all_tags = []
        for t_str in df["Tags"]:
            if t_str != "nan" and t_str:
                all_tags.extend([t.strip() for t in t_str.split(",")])
        
        if all_tags:
            tag_counts = pd.Series(all_tags).value_counts()
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=[tag_counts.get(c, 0) for c in COMPETENCIES],
                theta=COMPETENCIES,
                fill='toself',
                name='My Stats'
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True)),
                margin=dict(t=20, b=20, l=40, r=40)
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    search = st.text_input("🔍 Search Logs", "")
    target_df = df[df["Memo"].str.contains(search, case=False, na=False)] if search else df
    
    for index, row in target_df.sort_values(by="Date", ascending=False).iterrows():
        fb_text = row.get('AI_Feedback', '')
        if fb_text == 'nan': fb_text = ''
        
        with st.expander(f"{row['Date']} - {row['Phase']} ({row['Tags']})"):
            st.markdown(f"**Memo:**\n{row['Memo']}")
            if fb_text:
                st.info(f"**🤖 AI Feedback:**\n{fb_text}")
