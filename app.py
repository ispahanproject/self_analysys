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

# --- サイドバー ---
st.sidebar.header("📝 New Entry with AI")

if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="例: クロスウィンド着陸。分析をお願い。")

if st.sidebar.button("✨ Analyze with AI", type="primary"):
    raw_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = str(raw_key).replace('"', '').replace("'", "").strip()
    
    if not api_key:
        st.sidebar.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    elif input_memo:
        with st.sidebar.status("Instructor is checking..."):
            
            # --- ここにあなたのペルソナ設定を適用 ---
            prompt_text = f"""
            役割とペルソナ：
            あなたは、長年の経験を持つ『ベテランエアラインパイロット教官兼データアナリスト』です。航空業界の専門知識とデータ分析スキルを駆使し、ユーザーのフライト記録を整理・分析して、安全性の向上と技術の磨き込みをサポートします。

            振る舞いとルール（システム適合版）：
            以下のフライトメモを読み、JSON形式で出力してください。

            1. **データの入力・分類・タグ付け**:
               - メモから最適な `phase` ({', '.join(PHASES)}) を1つ特定する。
               - 関連するパフォーマンス指標 `tags` ({', '.join(COMPETENCIES)}) を選ぶ。

            2. **出力の制御（モード分岐）**:
               - **通常時（メモ入力のみ）**: ユーザーが事実を記録しているだけの場合は、分析やアドバイスを行わないこと。その場合、`feedback` 欄には「登録完了」とだけ記すこと。
               - **分析モード**: ユーザーから「分析して」「傾向は？」「どうすればいい？」等の指示がある、または明らかなミスや危険な兆候が含まれる場合のみ、現役教官の視点からプロフェッショナルで客観的なフィードバックを `feedback` 欄に記入すること。

            [メモ]
            {input_memo}
            
            [出力JSONフォーマット]
            {{
                "phase": "Landing",
                "tags": ["FM", "SA"],
                "feedback": "（モードに応じて「登録完了」または「教官からのアドバイス」を記述）"
            }}
            必ずJSON形式のみを出力し、Markdown装飾は含めないでください。
            """
            
            # Gemini 2.5 Flash を使用
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            
            headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key
            }
            data = {
                "contents": [{"parts": [{"text": prompt_text}]}]
            }
            
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                if response.status_code == 200:
                    result_json = response.json()
                    try:
                        text = result_json['candidates'][0]['content']['parts'][0]['text']
                        text = text.replace("```json", "").replace("```", "").strip()
                        result = json.loads(text)
                        
                        st.session_state.form_phase = result.get("phase", "Pre-flight")
                        st.session_state.form_tags = result.get("tags", [])
                        st.session_state.form_feedback = result.get("feedback", "")
                        st.rerun()
                    except:
                        st.sidebar.error("AIからの応答解析に失敗しました。")
                else:
                    st.sidebar.error(f"Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                st.sidebar.error(f"通信エラー: {e}")
    else:
        st.sidebar.warning("メモを入力してください")

# 3. 保存フォーム
with st.sidebar.form("save_form"):
    date = st.date_input("Date", datetime.now())
    
    current_phase_idx = 0
    if st.session_state.form_phase in PHASES:
        current_phase_idx = PHASES.index(st.session_state.form_phase)
        
    phase = st.selectbox("Phase", PHASES, index=current_phase_idx)
    tags = st.multiselect("Performance Indicators", COMPETENCIES, default=st.session_state.form_tags)
    feedback = st.text_area("Instructor Feedback", value=st.session_state.form_feedback, height=100)
    
    if st.form_submit_button("Save to Logbook"):
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
                st.info(f"**👨‍✈️ Instructor:**\n{fb_text}")
