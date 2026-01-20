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

# Gemini API設定
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーが設定されていません。Secretsに GEMINI_API_KEY を追加してください。")

# コンピテンシー定義 (AIへの指示用)
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4], ttl=5) # 列数を増やしてAIコメントも保存可能に

# データ初期化
if df.empty:
    df = pd.DataFrame(columns=["Date", "Phase", "Memo", "Tags", "AI_Feedback"])
else:
    # 既存データにAI_Feedback列がない場合の対応
    if "AI_Feedback" not in df.columns:
        df["AI_Feedback"] = ""
    df["Date"] = df["Date"].astype(str)
    df["Tags"] = df["Tags"].astype(str)
    df["AI_Feedback"] = df["AI_Feedback"].astype(str)

st.title("👨‍✈️ AI Pilot Performance Tracker")

# --- サイドバー: AI解析付き入力フォーム ---
st.sidebar.header("📝 New Entry with AI")

# セッション状態の管理（AIの結果をフォームに反映させるため）
if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

# 1. メモ入力
input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="例: クロスウィンド着陸。接地寸前に風下ラダーを入れたらスムーズだった。")

# 2. AI解析ボタン
if st.sidebar.button("✨ Analyze with AI", type="primary"):
    if input_memo:
        with st.sidebar.status("Co-pilot is analyzing..."):
            # プロンプト作成
            prompt = f"""
            あなたはベテランパイロットのインストラクターです。
            以下のフライトメモを分析し、JSON形式で出力してください。
            
            [メモ]
            {input_memo}
            
            [出力要件]
            1. "phase": メモの内容に最も合致するフライトフェーズ ({', '.join(PHASES)}) から1つ選ぶ。
            2. "tags": 関連するコンピテンシー ({', '.join(COMPETENCIES)}) をリストで選ぶ (最大3つ)。
            3. "feedback": インストラクターとしての短いフィードバック(1文)。
            
            出力はJSONのみ。
            Example: {{"phase": "Landing", "tags": ["FM", "SA"], "feedback": "適切な修正操作です。"}}
            """
            
            try:
                response = model.generate_content(prompt)
                # JSON部分を抽出（ ```json ... ``` を除去）
                text = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                
                # 結果をセッションに保存
                st.session_state.form_phase = result.get("phase", "Pre-flight")
                st.session_state.form_tags = result.get("tags", [])
                st.session_state.form_feedback = result.get("feedback", "")
                st.rerun() # 画面更新してフォームに反映
                
            except Exception as e:
                st.sidebar.error(f"Analysis Failed: {e}")
    else:
        st.sidebar.warning("メモを入力してください")

# 3. 確認・修正・保存フォーム
with st.sidebar.form("save_form"):
    date = st.date_input("Date", datetime.now())
    
    # AIが提案した値がデフォルトに入る
    phase = st.selectbox("Phase", PHASES, index=PHASES.index(st.session_state.form_phase) if st.session_state.form_phase in PHASES else 0)
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
        # フォームリセット
        st.session_state.form_phase = "Pre-flight"
        st.session_state.form_tags = []
        st.session_state.form_feedback = ""
        st.rerun()

# --- ダッシュボード表示 ---
tab1, tab2 = st.tabs(["📊 Analytics", "🗂 Logbook"])

with tab1:
    if not df.empty:
        # タグ集計
        all_tags = []
        for t_str in df["Tags"]:
            if t_str != "nan" and t_str:
                all_tags.extend([t.strip() for t in t_str.split(",")])
        
        if all_tags:
            tag_counts = pd.Series(all_tags).value_counts()
            
            # レーダーチャート
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
    # 検索機能
    search = st.text_input("🔍 Search Logs", "")
    target_df = df[df["Memo"].str.contains(search, case=False, na=False)] if search else df
    
    # カード形式で表示
    for index, row in target_df.sort_values(by="Date", ascending=False).iterrows():
        with st.expander(f"{row['Date']} - {row['Phase']} ({row['Tags']})"):
            st.markdown(f"**Memo:**\n{row['Memo']}")
            st.info(f"**🤖 AI Feedback:**\n{row['AI_Feedback']}")
