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

input_memo = st.sidebar.text_area("Flight Memo", height=120, placeholder="例: クロスウィンド着陸。接地寸前に風下ラダーを入れたらスムーズだった。")

if st.sidebar.button("✨ Analyze with AI", type="primary"):
    # APIキーの徹底クリーニング
    raw_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = str(raw_key).replace('"', '').replace("'", "").strip()
    
    if not api_key:
        st.sidebar.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    elif input_memo:
        with st.sidebar.status("Running Auto-Diagnostics..."):
            
            # 試行するモデルの候補リスト（新しい順）
            MODELS_TO_TRY = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro",
                "gemini-pro"
            ]
            
            success = False
            last_error = ""
            
            prompt_text = f"""
            あなたはベテランパイロットのインストラクターです。
            以下のフライトメモを分析し、必ずJSON形式のみで出力してください。Markdown不要。
            
            [メモ] {input_memo}
            
            [出力]
            {{"phase": "Landing", "tags": ["FM", "SA"], "feedback": "コメント"}}
            
            選択肢: Phase={PHASES}, Tags={COMPETENCIES}
            """
            
            headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
            data = {"contents": [{"parts": [{"text": prompt_text}]}]}

            # --- 総当たりループ開始 ---
            for model_name in MODELS_TO_TRY:
                st.write(f"Testing model: `{model_name}` ...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=10)
                    
                    if response.status_code == 200:
                        # 成功！
                        result_json = response.json()
                        text = result_json['candidates'][0]['content']['parts'][0]['text']
                        text = text.replace("```json", "").replace("```", "").strip()
                        result = json.loads(text)
                        
                        st.session_state.form_phase = result.get("phase", "Pre-flight")
                        st.session_state.form_tags = result.get("tags", [])
                        st.session_state.form_feedback = result.get("feedback", "")
                        success = True
                        break # ループを抜ける
                    else:
                        # 404などのエラーなら次へ
                        error_json = response.json()
                        last_error = error_json.get('error', {}).get('message', response.text)
                        
                except Exception as e:
                    last_error = str(e)
                    continue

            # --- 結果判定 ---
            if success:
                st.rerun()
            else:
                # 全滅した場合、サーバーに「使えるモデル一覧」を問い合わせて表示する
                st.error("❌ 全てのモデルで接続に失敗しました。")
                st.error(f"最後のエラー: {last_error}")
                
                st.warning("🔍 サーバー上の利用可能なモデル一覧を取得します...")
                try:
                    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                    list_resp = requests.get(list_url)
                    if list_resp.status_code == 200:
                        models_data = list_resp.json()
                        available_names = [m['name'] for m in models_data.get('models', [])]
                        st.code(json.dumps(available_names, indent=2))
                        st.info("上記リストに含まれるモデル名しか使用できません。APIキーの種類（Vertex AIなど）によってはリストが空の場合があります。")
                    else:
                        st.error(f"モデル一覧の取得も失敗しました: {list_resp.text}")
                except Exception as e:
                    st.error(f"診断エラー: {e}")

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
    feedback = st.text_area("AI / Instructor Comment", value=st.session_state.form_feedback, height=80)
    
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

# --- ログ表示 ---
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
            fig.update_layout(polar=dict(radialaxis=dict(visible=True)), margin=dict(t=20, b=20, l=40, r=40))
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
