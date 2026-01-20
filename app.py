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
st.set_page_config(page_title="AI Pilot Log Chat", page_icon="✈️", layout="wide")

# 定義
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

st.title("👨‍✈️ AI Instructor Chat Log")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4, 5], ttl=5)
except:
    try:
        df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4], ttl=5)
    except:
        df = pd.DataFrame()

required_columns = ["Date", "Phase", "Memo", "Tags", "AI_Feedback", "Airport"]
if df.empty:
    df = pd.DataFrame(columns=required_columns)
else:
    for col in required_columns:
        if col not in df.columns: df[col] = ""
    for col in df.columns: df[col] = df[col].astype(str)

# --- セッション状態 ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "お疲れ様です、キャプテン。本日のフライトはいかがでしたか？"}
    ]

if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_airport' not in st.session_state: st.session_state.form_airport = ""
if 'form_memo' not in st.session_state: st.session_state.form_memo = ""
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

# --- レイアウト ---
col_chat, col_tools = st.columns([2, 1])

# ==========================================
# 左カラム: チャット
# ==========================================
with col_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("フライトの振り返りを入力..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if not api_key:
            st.error("APIキーが設定されていません。")
        else:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown("Analyzing...")

                # --- プロンプト修正部分 ---
                system_prompt = f"""
                役割：あなたはベテランパイロット教官です。
                ユーザーとの対話を通じて、フライトの振り返りをサポートします。
                
                【重要】出力形式のルール:
                回答は必ず以下の2つのパートに分けて出力してください。
                区切り文字として `||JSON_START||` を使用してください。

                [Part 1: 会話パート]
                ユーザーへの返答、質問、またはアドバイスを自然な日本語で記述。
                
                `||JSON_START||`
                
                [Part 2: データ抽出パート]
                これまでの会話内容から、ログブックに記録すべき情報を抽出しJSONで出力。
                
                JSON項目:
                - phase: {PHASES} から1つ
                - tags: {COMPETENCIES} から複数可
                - airport: 空港コード (IATA 3レター)
                - feedback: ログに残すべき教官コメントの要約(1文)
                - memo_summary: ★重要★ 会話内容に含まれる「起こった事実」のみを抽出し、箇条書きで整理したテキスト。感情（怖かった、焦った等）は排除し、客観的事実のみを記すこと。改行コードを含めてよい。
                  (例: "- HND RWY34RへILS進入\n- 500ftで強い右横風を確認\n- 接地後の減速操作が遅れた")

                現在のユーザーの発言: {prompt}
                """

                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
                data = {"contents": [{"parts": [{"text": system_prompt}]}]}

                try:
                    response = requests.post(url, headers=headers, json=data, timeout=30)
                    if response.status_code == 200:
                        result_json = response.json()
                        raw_text = result_json['candidates'][0]['content']['parts'][0]['text']
                        
                        if "||JSON_START||" in raw_text:
                            parts = raw_text.split("||JSON_START||")
                            chat_response = parts[0].strip()
                            json_part = parts[1].strip().replace("```json", "").replace("```", "")
                            
                            try:
                                extracted_data = json.loads(json_part)
                                st.session_state.form_phase = extracted_data.get("phase", st.session_state.form_phase)
                                st.session_state.form_tags = extracted_data.get("tags", st.session_state.form_tags)
                                st.session_state.form_airport = extracted_data.get("airport", st.session_state.form_airport)
                                if extracted_data.get("feedback"):
                                    st.session_state.form_feedback = extracted_data.get("feedback")
                                
                                # ★ここを変更: AIが作った「事実の箇条書き(memo_summary)」をメモ欄に入れる
                                if extracted_data.get("memo_summary"):
                                    st.session_state.form_memo = extracted_data.get("memo_summary")
                                else:
                                    # 生成されなかった場合は念のため元の入力を入れる
                                    st.session_state.form_memo = prompt

                            except:
                                pass
                        else:
                            chat_response = raw_text
                        
                        message_placeholder.markdown(chat_response)
                        st.session_state.messages.append({"role": "assistant", "content": chat_response})
                        st.rerun()
                        
                    else:
                        message_placeholder.error(f"Error: {response.status_code}")
                except Exception as e:
                    message_placeholder.error(f"通信エラー: {e}")

# ==========================================
# 右カラム: 保存フォーム
# ==========================================
with col_tools:
    st.header("📝 Log Entry")
    st.caption("AIが事実のみを箇条書きで整理します")
    
    with st.form("save_form"):
        date = st.date_input("Date", datetime.now())
        airport = st.text_input("Airport", value=st.session_state.form_airport)
        
        curr_phase = st.session_state.form_phase
        p_idx = PHASES.index(curr_phase) if curr_phase in PHASES else 0
        phase = st.selectbox("Phase", PHASES, index=p_idx)
        
        tags = st.multiselect("Tags", COMPETENCIES, default=st.session_state.form_tags)
        
        # メモ（AIが整理した箇条書きが入る）
        memo = st.text_area("Memo (Facts Only)", value=st.session_state.form_memo, height=150)
        
        feedback = st.text_area("AI Feedback (Saved)", value=st.session_state.form_feedback, height=80)
        
        if st.form_submit_button("💾 Save to Sheet", type="primary"):
            new_row = pd.DataFrame([{
                "Date": str(date),
                "Phase": phase,
                "Memo": memo,
                "Tags": ", ".join(tags),
                "AI_Feedback": feedback,
                "Airport": airport
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("Saved!")
            st.session_state.form_memo = ""
            st.session_state.form_feedback = ""
            st.rerun()

    st.markdown("---")
    
    tab_log, tab_stats = st.tabs(["🗂 Recent Logs", "📊 Stats"])
    
    with tab_log:
        search = st.text_input("🔍 Search", "")
        target_df = df[df["Memo"].str.contains(search, case=False, na=False)] if search else df
        st.dataframe(target_df.sort_values("Date", ascending=False).head(5), hide_index=True, use_container_width=True)

    with tab_stats:
        all_tags = []
        for t in df["Tags"]:
            if t and t != "nan": all_tags.extend([x.strip() for x in t.split(",")])
        if all_tags:
            counts = pd.Series(all_tags).value_counts()
            fig = go.Figure(data=go.Scatterpolar(
                r=[counts.get(c, 0) for c in COMPETENCIES],
                theta=COMPETENCIES, fill='toself'
            ))
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
