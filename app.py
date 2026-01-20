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

# --- ★リセット用関数 (記憶をクリアして初期状態に戻す) ---
def reset_entry():
    st.session_state.messages = [
        {"role": "assistant", "content": "お疲れ様です、キャプテン。次のフライトについて話しましょう。"}
    ]
    st.session_state.form_phase = "Pre-flight"
    st.session_state.form_tags = []
    st.session_state.form_airport = ""
    st.session_state.form_memo = ""
    st.session_state.form_feedback = ""

# --- セッション状態初期化 ---
if "messages" not in st.session_state:
    # 初回起動時だけここを通る（以降はreset_entryで管理）
    reset_entry()

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
    # 過去ログ表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 入力欄
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
                message_placeholder.markdown("Updating Log...")

                current_memo_content = st.session_state.form_memo

                # プロンプト（追記ロジック）
                system_prompt = f"""
                役割：あなたはベテランパイロット教官です。
                ユーザーとの対話を通じて、フライトログの作成をサポートします。

                【タスク】
                「現在のメモ」と「新しい発言」を統合し、最新のログ情報を作成してください。

                [現在のメモの状態]
                {current_memo_content}

                [ユーザーの新しい発言]
                {prompt}

                【重要：出力形式のルール】
                回答は必ず以下の2つのパートに分けて出力してください。
                区切り文字として `||JSON_START||` を使用してください。

                [Part 1: 会話パート]
                ユーザーへの返答、追加の質問、またはアドバイスを自然な日本語で記述。

                `||JSON_START||`

                [Part 2: データ更新パート (JSON)]
                以下の項目を含むJSONを出力。
                
                - phase: {PHASES} から最も適切なもの
                - tags: {COMPETENCIES} から関連するものを**累積**して選択
                - airport: 空港コード (IATA 3レター)
                - feedback: 教官コメントの要約(1文)
                - memo_summary: ★最重要★
                  「現在のメモ」の内容を保持しつつ、「新しい発言」から得られた事実を**追記・統合**した箇条書きテキスト。
                  過去の事実を勝手に消さないこと。時系列順に整理すること。

                Markdown装飾なしの純粋なJSONとして出力してください。
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
                                
                                if extracted_data.get("memo_summary"):
                                    st.session_state.form_memo = extracted_data.get("memo_summary")

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
# 右カラム: 保存フォーム & ツール
# ==========================================
with col_tools:
    st.header("📝 Log Entry")
    
    # ★ここに手動リセットボタンを追加
    if st.button("🔄 Start New Entry (Reset)", help="保存せずに会話と入力をリセットします"):
        reset_entry()
        st.rerun()
        
    st.markdown("---")

    with st.form("save_form"):
        date = st.date_input("Date", datetime.now())
        airport = st.text_input("Airport", value=st.session_state.form_airport)
        
        curr_phase = st.session_state.form_phase
        p_idx = PHASES.index(curr_phase) if curr_phase in PHASES else 0
        phase = st.selectbox("Phase", PHASES, index=p_idx)
        
        tags = st.multiselect("Tags", COMPETENCIES, default=st.session_state.form_tags)
        
        memo = st.text_area("Memo (Facts Only)", value=st.session_state.form_memo, height=200)
        
        feedback = st.text_area("AI Feedback", value=st.session_state.form_feedback, height=80)
        
        # 保存ボタン
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
            
            # ★保存成功時に自動リセット
            reset_entry()
            st.rerun()

    st.markdown("---")
    
    # ログ・分析タブ
    tab_log, tab_stats = st.tabs(["🗂 Logs", "📊 Stats"])
    
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
