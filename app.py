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

# 定義
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

st.title("👨‍✈️ AI Pilot Performance Tracker")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 列が増えたので usecols を 0~5 に拡張
try:
    df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4, 5], ttl=5)
except:
    try:
        # 古いシート構造対策（5列しかない場合）
        df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4], ttl=5)
    except:
        df = pd.DataFrame()

# データフレームの列整理
required_columns = ["Date", "Phase", "Memo", "Tags", "AI_Feedback", "Airport"]
if df.empty:
    df = pd.DataFrame(columns=required_columns)
else:
    # 足りない列があれば追加
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    # 文字列型に変換
    for col in df.columns:
        df[col] = df[col].astype(str)

# --- サイドバー ---
st.sidebar.header("📝 New Entry with AI")

# セッション管理 (Airportを追加)
if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""
if 'form_airport' not in st.session_state: st.session_state.form_airport = ""

input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="例: 羽田RWY34Rへのアプローチ中、横風が強かった。")

if st.sidebar.button("✨ Analyze with AI", type="primary"):
    raw_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = str(raw_key).replace('"', '').replace("'", "").strip()
    
    if not api_key:
        st.sidebar.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    elif input_memo:
        with st.sidebar.status("Instructor is analyzing..."):
            
            # --- プロンプト (Airport抽出指示を追加) ---
            prompt_text = f"""
            役割：ベテランパイロット教官兼データアナリスト
            
            タスク：以下のフライトメモを分析し、JSONデータを作成してください。
            
            [分析ルール]
            1. **Phase**: メモに最も合うフェーズを {PHASES} から1つ選択。
            2. **Tags**: 関連するコンピテンシーを {COMPETENCIES} から選択。
            3. **Airport**: メモから空港名やコード（羽田, HND, RJTTなど）を特定し、**IATA 3レターコード (例: HND)** に変換して出力。特定できない場合は空文字 "" とする。
            4. **Feedback**: 
               - 通常の記録なら「登録完了」。
               - 「分析して」「アドバイス」等の要求や、明白な危険兆候がある場合は、教官としてのアドバイスを記述。

            [メモ]
            {input_memo}
            
            [出力JSON例]
            {{
                "phase": "Landing",
                "tags": ["FM", "SA"],
                "airport": "HND", 
                "feedback": "登録完了"
            }}
            Markdown装飾なしのJSONのみを出力してください。
            """
            
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
            data = {"contents": [{"parts": [{"text": prompt_text}]}]}
            
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
                        st.session_state.form_airport = result.get("airport", "") # 空港を反映
                        st.session_state.form_feedback = result.get("feedback", "")
                        st.rerun()
                    except:
                        st.sidebar.error("AI応答の解析失敗")
                else:
                    st.sidebar.error(f"Error {response.status_code}")
            except Exception as e:
                st.sidebar.error(f"通信エラー: {e}")

# 3. 保存フォーム
with st.sidebar.form("save_form"):
    date = st.date_input("Date", datetime.now())
    
    # AIが特定した空港を表示（手修正可能）
    airport = st.text_input("Airport (IATA)", value=st.session_state.form_airport, placeholder="例: HND")
    
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
            "AI_Feedback": feedback,
            "Airport": airport  # 保存データに追加
        }])
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        st.success("Log Saved!")
        # フォームリセット
        st.session_state.form_phase = "Pre-flight"
        st.session_state.form_tags = []
        st.session_state.form_feedback = ""
        st.session_state.form_airport = ""
        st.rerun()

# --- ダッシュボード表示 ---
tab1, tab2 = st.tabs(["📊 Analytics", "🗂 Logbook"])

with tab1:
    if not df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # タグ分析（レーダーチャート）
            all_tags = []
            for t_str in df["Tags"]:
                if t_str and t_str != "nan":
                    all_tags.extend([t.strip() for t in t_str.split(",")])
            
            if all_tags:
                tag_counts = pd.Series(all_tags).value_counts()
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=[tag_counts.get(c, 0) for c in COMPETENCIES],
                    theta=COMPETENCIES,
                    fill='toself', name='Stats'
                ))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), margin=dict(t=20, b=20, l=20, r=20))
                st.markdown("### Competency Stats")
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            # 空港別分析（棒グラフ）
            st.markdown("### Frequent Airports")
            if "Airport" in df.columns:
                # 空白やnanを除去してカウント
                airport_counts = df["Airport"].replace("", pd.NA).dropna().value_counts().head(5)
                if not airport_counts.empty:
                    st.bar_chart(airport_counts)
                else:
                    st.info("データがありません")

with tab2:
    search = st.text_input("🔍 Search Logs", "")
    target_df = df[df["Memo"].str.contains(search, case=False, na=False)] if search else df
    
    # 最新順に並び替え
    for index, row in target_df.sort_values(by="Date", ascending=False).iterrows():
        fb_text = row.get('AI_Feedback', '')
        apt_text = row.get('Airport', '')
        
        # タイトルに空港名も含める
        header_text = f"{row['Date']} - {row['Phase']} ({row['Tags']})"
        if apt_text and apt_text != "nan":
            header_text += f" @ {apt_text}"
            
        with st.expander(header_text):
            st.markdown(f"**Memo:**\n{row['Memo']}")
            if fb_text and fb_text != "nan":
                st.info(f"**👨‍✈️ Instructor:**\n{fb_text}")
