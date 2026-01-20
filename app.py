import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio
import plotly.graph_objects as go
import json
import requests
import time

# --- ページ設定 ---
st.set_page_config(page_title="Flight Logbook", page_icon="✈️", layout="wide")

# --- デザイン(CSS) ---
# スマートでクリーンな「航空手帳」スタイル
st.markdown("""
<style>
    /* 全体のスタイル */
    .stApp {
        background-color: #f8f9fa; /* 薄いグレー背景 */
        color: #2c3e50;
        font-family: 'Helvetica Neue', 'Arial', sans-serif;
    }

    /* ヘッダー */
    h1, h2, h3 {
        color: #1a252f !important;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    
    /* コンテナ（カード）のスタイル */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background-color: #ffffff;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        padding: 20px;
        border: 1px solid #e9ecef;
    }

    /* 入力フォーム */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border: 1px solid #ced4da;
        border-radius: 6px;
    }

    /* ボタン */
    .stButton button {
        background-color: #0056b3; /* ネイビーブルー */
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: 0.2s;
    }
    .stButton button:hover {
        background-color: #004494;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    /* チャットメッセージ */
    .stChatMessage {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }

    /* メトリクス（数値） */
    div[data-testid="stMetricValue"] {
        color: #0056b3 !important;
        font-weight: 700;
    }
    
    /* タグ（バッジ）のスタイル（HTML表示用） */
    .tag-badge {
        display: inline-block;
        background-color: #e7f1ff;
        color: #0056b3;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        margin-right: 5px;
        margin-bottom: 5px;
        font-weight: 600;
    }
    .phase-badge {
        display: inline-block;
        background-color: #e9ecef;
        color: #495057;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        border: 1px solid #ced4da;
    }
</style>
""", unsafe_allow_html=True)

# --- 定義 ---
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

# --- データ接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)
try:
    df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4, 5], ttl=5)
except:
    try: df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3, 4], ttl=5)
    except: df = pd.DataFrame()

required_columns = ["Date", "Phase", "Memo", "Tags", "AI_Feedback", "Airport"]
if df.empty:
    df = pd.DataFrame(columns=required_columns)
else:
    for col in required_columns:
        if col not in df.columns: df[col] = ""
    for col in df.columns: df[col] = df[col].astype(str)

# --- 関数 ---
def reset_entry():
    st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です。フライトの振り返りを行いましょう。"}]
    st.session_state.form_phase = "Pre-flight"
    st.session_state.form_tags = []
    st.session_state.form_airport = ""
    st.session_state.form_memo = ""
    st.session_state.form_feedback = ""

if "messages" not in st.session_state: reset_entry()
if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_airport' not in st.session_state: st.session_state.form_airport = ""
if 'form_memo' not in st.session_state: st.session_state.form_memo = ""
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

# ==========================================
# Header / Dashboard
# ==========================================
c1, c2 = st.columns([3, 1])
with c1:
    st.title("✈️ Flight Logbook")
with c2:
    if st.button("New Entry (Reset)"):
        reset_entry()
        st.rerun()

# 簡易ダッシュボード（シンプル表示）
with st.container():
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Total Logs", len(df))
    with m2: 
        last_apt = df.iloc[-1]["Airport"] if not df.empty else "-"
        st.metric("Last Airport", last_apt)
    with m3:
        all_tags = []
        for t in df["Tags"]:
            if t and t != "nan": all_tags.extend([x.strip() for x in t.split(",")])
        top_tag = pd.Series(all_tags).mode()[0] if all_tags else "-"
        st.metric("Main Topic", top_tag)
    with m4:
        st.metric("Today", datetime.now().strftime("%m/%d"))

st.markdown("---")

# ==========================================
# Main Layout
# ==========================================
col_chat, col_data = st.columns([1.6, 1.4])

# --- 左: Chat Interface ---
with col_chat:
    st.subheader("💬 Chat & Analysis")
    
    chat_container = st.container(height=600)
    with chat_container:
        for msg in st.session_state.messages:
            # アイコンもシンプルに
            avatar = "👤" if msg["role"] == "user" else "✈️"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    if prompt := st.chat_input("フライトの振り返りを入力..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if api_key:
            with chat_container:
                with st.chat_message("assistant", avatar="✈️"):
                    placeholder = st.empty()
                    placeholder.markdown("`Thinking...`")
                    
                    current_memo = st.session_state.form_memo
                    
                    # --- プロンプト: 親しみやすい先輩だが、パイロット演出は控えめに ---
                    system_prompt = f"""
                    あなたは信頼できる先輩パイロット（女性）です。
                    ユーザーの発言に対し、親しみやすく、かつプロフェッショナルな視点で会話してください。
                    過剰な演技は不要ですが、頼りになる口調（「〜だね」「〜かな？」）で接してください。

                    その後、JSONデータを出力してください。

                    [Current Memo]
                    {current_memo}

                    [User Input]
                    {prompt}

                    【ルール】
                    1. 雑談（食事など）は会話のみで反応し、データ記録（JSON）からは削除すること。
                    2. JSONの `memo_summary` は事実のみを箇条書きにする。

                    【Format】
                    (Conversation part)
                    ||JSON_START||
                    (JSON part)
                    {{
                        "phase": "{PHASES} から1つ",
                        "tags": {COMPETENCIES} (List),
                        "airport": "IATA Code",
                        "feedback": "One sentence feedback",
                        "memo_summary": "Facts only"
                    }}
                    """
                    
                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                    headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
                    data = {"contents": [{"parts": [{"text": system_prompt}]}]}

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = requests.post(url, headers=headers, json=data, timeout=30)
                            if response.status_code == 200: break
                            elif response.status_code == 503:
                                time.sleep(2)
                                continue
                            else: break
                        except:
                            time.sleep(1)
                            continue
                    
                    try:
                        if response.status_code == 200:
                            result_json = response.json()
                            raw = result_json['candidates'][0]['content']['parts'][0]['text']
                            
                            if "||JSON_START||" in raw:
                                parts = raw.split("||JSON_START||")
                                chat_res = parts[0].strip()
                                json_part = parts[1].strip().replace("```json","").replace("```","")
                                
                                try:
                                    d = json.loads(json_part)
                                    st.session_state.form_phase = d.get("phase", st.session_state.form_phase)
                                    new_tags = d.get("tags", [])
                                    if not isinstance(new_tags, list): new_tags = []
                                    st.session_state.form_tags = new_tags
                                    st.session_state.form_airport = d.get("airport", st.session_state.form_airport)
                                    if d.get("feedback"): st.session_state.form_feedback = d.get("feedback")
                                    if d.get("memo_summary"): st.session_state.form_memo = d.get("memo_summary")
                                except: pass
                            else:
                                chat_res = raw
                            
                            placeholder.markdown(chat_res)
                            st.session_state.messages.append({"role": "assistant", "content": chat_res})
                            st.rerun()
                        else:
                            placeholder.error(f"Error: {response.status_code}")
                    except:
                         placeholder.error("Network Error.")

# --- 右: Data & Archive ---
with col_data:
    tab_entry, tab_list, tab_stats = st.tabs(["📝 Entry", "🗂 Archive", "📊 Stats"])
    
    # -----------------------
    # 1. 入力フォーム
    # -----------------------
    with tab_entry:
        with st.container():
            st.caption("AI Auto-Fill Form")
            with st.form("save_form"):
                c1, c2 = st.columns(2)
                with c1: date = st.date_input("Date", datetime.now())
                with c2: airport = st.text_input("Airport", value=st.session_state.form_airport)
                
                curr_p = st.session_state.form_phase
                p_idx = PHASES.index(curr_p) if curr_p in PHASES else 0
                phase = st.selectbox("Phase", PHASES, index=p_idx)
                
                curr_t = st.session_state.form_tags
                if not isinstance(curr_t, list): curr_t = []
                valid_t = [t for t in curr_t if t in COMPETENCIES]
                tags = st.multiselect("Competencies", COMPETENCIES, default=valid_t)
                
                st.markdown("**Facts**")
                memo = st.text_area("Memo", value=st.session_state.form_memo, height=150, label_visibility="collapsed")
                st.markdown("**Feedback**")
                feedback = st.text_area("FB", value=st.session_state.form_feedback, height=80, label_visibility="collapsed")
                
                if st.form_submit_button("Save Entry", type="primary", use_container_width=True):
                    new_row = pd.DataFrame([{
                        "Date": str(date), "Phase": phase, "Memo": memo, 
                        "Tags": ", ".join(tags), "AI_Feedback": feedback, "Airport": airport
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
                    st.toast("Saved successfully!", icon="✅")
                    reset_entry()
                    st.rerun()

    # -----------------------
    # 2. アーカイブ（カード表示）
    # -----------------------
    with tab_list:
        st.subheader("Log Archive")
        search_query = st.text_input("🔍 Search logs...", placeholder="Keyword")
        
        if not df.empty:
            display_df = df
            if search_query:
                display_df = df[df["Memo"].str.contains(search_query, case=False, na=False) | 
                                df["Tags"].str.contains(search_query, case=False, na=False)]
            
            # --- ★ここが新機能: カード型リスト表示 ---
            for index, row in display_df.sort_values("Date", ascending=False).iterrows():
                with st.container():
                    # ヘッダー行: 日付 | 空港 | フェーズ
                    cols = st.columns([1.5, 3])
                    with cols[0]:
                        st.markdown(f"**{row['Date']}**")
                        st.caption(f"{row['Airport']} / {row['Phase']}")
                    
                    with cols[1]:
                        # タグをバッジ表示
                        tags_html = ""
                        tags_str = str(row['Tags'])
                        if tags_str and tags_str != "nan":
                            for t in tags_str.split(","):
                                tags_html += f"<span class='tag-badge'>{t.strip()}</span>"
                        st.markdown(tags_html, unsafe_allow_html=True)

                    # 詳細（アコーディオン）
                    with st.expander("Show Details"):
                        st.markdown(f"**📝 Memo:**\n{row['Memo']}")
                        if row['AI_Feedback'] and row['AI_Feedback'] != "nan":
                            st.info(f"**💡 Feedback:**\n{row['AI_Feedback']}")
                st.write("") # スペース
        else:
            st.info("No logs found.")

    # -----------------------
    # 3. 統計 (Stats)
    # -----------------------
    with tab_stats:
        if all_tags:
            st.subheader("Competency Balance")
            counts = pd.Series(all_tags).value_counts()
            fig = go.Figure(data=go.Scatterpolar(
                r=[counts.get(c, 0) for c in COMPETENCIES], theta=COMPETENCIES,
                fill='toself', 
                line=dict(color='#0056b3'),
                fillcolor='rgba(0, 86, 179, 0.2)'
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20, l=30, r=30), height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("データが不足しています")
