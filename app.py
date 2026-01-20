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
st.set_page_config(page_title="J.A.R.V.I.S. Flight Log", page_icon="🤖", layout="wide")

# --- デザイン(CSS) - IRON MAN HUD STYLE ---
st.markdown("""
<style>
    /* SFフォントのインポート */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto+Mono:wght@400;700&display=swap');

    /* 全体の背景とフォント設定 */
    .stApp {
        /* 深い宇宙のようなダークブルーグラデーション */
        background: radial-gradient(ellipse at center, #1b2735 0%, #090a0f 100%);
        color: #e0f7fa; /* 薄い水色テキスト */
        font-family: 'Roboto Mono', monospace; /* データ表示用等幅フォント */
    }

    /* ヘッダー（発光するSFフォント） */
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        color: #00d4ff !important; /* エレクトリック・ブルー */
        text-transform: uppercase;
        letter-spacing: 2px;
        text-shadow: 0 0 10px #00d4ff, 0 0 20px #00d4ff; /* 強い発光 */
    }
    
    /* コンテナ（ホログラフィックパネル） */
    /* Streamlitのコンテナ構造を特定してスタイル適用 */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background: rgba(10, 25, 40, 0.75); /* 半透明のダークブルー */
        box-shadow: 0 8px 32px 0 rgba(0, 212, 255, 0.1);
        backdrop-filter: blur( 10px ); /* すりガラス効果 */
        -webkit-backdrop-filter: blur( 10px );
        border-radius: 12px;
        border: 1px solid rgba(0, 212, 255, 0.2); /* 薄い発光ボーダー */
        border-left: 3px solid #00d4ff; /* 左側に強いアクセントライン */
    }

    /* 入力フォーム（データターミナル風） */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(0, 10, 20, 0.8) !important;
        color: #00d4ff !important;
        border: 1px solid #00d4ff;
        border-radius: 4px;
        font-family: 'Roboto Mono', monospace;
        box-shadow: inset 0 0 5px rgba(0, 212, 255, 0.2);
    }

    /* ボタン（アーク・リアクター風） */
    .stButton button {
        background: linear-gradient(135deg, #00d4ff 0%, #005bea 100%);
        border: none;
        border-radius: 4px;
        color: white;
        font-family: 'Orbitron', sans-serif;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.5);
        transition: 0.3s;
    }
    .stButton button:hover {
         box-shadow: 0 0 30px rgba(0, 212, 255, 1); /* ホバー時に強く発光 */
         transform: scale(1.02);
    }

    /* チャットメッセージ */
    .stChatMessage {
        background-color: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 10px;
    }
    /* AIのアバター背景 */
    .stChatMessage .stAvatar {
        background-color: #00d4ff;
        box-shadow: 0 0 10px #00d4ff;
    }

    /* メトリクス（HUDデータ表示 - ゴールドアクセント） */
    div[data-testid="stMetricValue"] {
        color: #ff9900 !important; /* アイアンマンのゴールド/オレンジ */
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px rgba(255, 153, 0, 0.8);
        font-size: 2.2rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #00d4ff !important;
        letter-spacing: 1px;
        font-size: 0.9rem !important;
    }
    
    /* タグ（エネルギーセル風） */
    .tag-badge {
        display: inline-block;
        background-color: rgba(0, 212, 255, 0.1);
        border: 1px solid #00d4ff;
        color: #00d4ff;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        margin-right: 5px;
        margin-bottom: 5px;
        font-family: 'Orbitron', sans-serif;
        box-shadow: 0 0 5px rgba(0, 212, 255, 0.5);
        text-shadow: 0 0 5px rgba(0, 212, 255, 0.8);
    }
    
    /* タブ */
    button[data-baseweb="tab"] {
        color: #5f7d95;
        font-family: 'Orbitron', sans-serif;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #00d4ff !important;
        border-bottom-color: #00d4ff !important;
        text-shadow: 0 0 10px #00d4ff;
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
    st.session_state.messages = [{"role": "assistant", "content": "SYSTEM ONLINE. J.A.R.V.I.S. at your service. Flight report initiated."}]
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
# Header / HUD Dashboard
# ==========================================
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🤖 J.A.R.V.I.S. FLIGHT HUD")
with c2:
    if st.button("🔄 REBOOT SYSTEM"):
        reset_entry()
        st.rerun()

# HUD Metrics Container
with st.container():
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("TOTAL MISSIONS", len(df))
    with m2: 
        last_apt = df.iloc[-1]["Airport"] if not df.empty else "N/A"
        st.metric("LAST LOCATION", last_apt)
    with m3:
        all_tags = []
        for t in df["Tags"]:
            if t and t != "nan": all_tags.extend([x.strip() for x in t.split(",")])
        top_tag = pd.Series(all_tags).mode()[0] if all_tags else "N/A"
        st.metric("PRIMARY FOCUS", top_tag)
    with m4:
        st.metric("SYSTEM STATUS", "ACTIVE")

st.markdown("---")

# ==========================================
# Main Layout
# ==========================================
col_chat, col_data = st.columns([1.6, 1.4])

# --- 左: Chat Interface ---
with col_chat:
    st.subheader("📡 TACTICAL COMMS")
    
    chat_container = st.container(height=600)
    with chat_container:
        for msg in st.session_state.messages:
            # アイコンを変更
            avatar = "👨‍✈️" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    if prompt := st.chat_input("TRANSMIT DATA..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👨‍✈️"):
                st.markdown(prompt)

        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if api_key:
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    placeholder = st.empty()
                    placeholder.markdown("`ANALYZING INPUT...`")
                    
                    current_memo = st.session_state.form_memo
                    
                    # --- プロンプト: J.A.R.V.I.S.風 ---
                    system_prompt = f"""
                    あなたはトニー・スタークのAIアシスタント「J.A.R.V.I.S.（ジャービス）」です。
                    ユーザー（パイロット）の発言に対し、知的で冷静かつ丁寧な口調で応答してください。
                    （例：「承知いたしました、サー」「データを確認します」「賢明な判断です」）

                    その後、フライトデータをJSON形式で抽出してください。

                    [Current Data Snippet]
                    {current_memo}

                    [User Transmission]
                    {prompt}

                    【プロトコル】
                    1. 雑談は会話でのみ応答し、データログからは排除せよ。
                    2. `memo_summary` は事実のみの簡潔な箇条書きとせよ。

                    【Format】
                    (J.A.R.V.I.S. Response)
                    ||JSON_START||
                    (Data Object)
                    {{
                        "phase": "{PHASES} から1つ",
                        "tags": {COMPETENCIES} (List),
                        "airport": "IATA Code",
                        "feedback": "J.A.R.V.I.S. comment (1 sentence)",
                        "memo_summary": "Facts only bullet points"
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
                                placeholder.markdown(f"`SERVER BUSY. REROUTING ({attempt+1}/{max_retries})...`")
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
                            placeholder.error(f"API Error: {response.status_code}")
                    except:
                         placeholder.error("CONNECTION LOST.")

# --- 右: Data & Archive ---
with col_data:
    tab_entry, tab_list, tab_stats = st.tabs(["⏺ DATA ENTRY", "📂 LOG ARCHIVE", "📊 ANALYTICS"])
    
    # -----------------------
    # 1. 入力フォーム (ホログラムパネル)
    # -----------------------
    with tab_entry:
        with st.container():
            st.caption("AUTO-GENERATED FLIGHT DATA")
            with st.form("save_form"):
                c1, c2 = st.columns(2)
                with c1: date = st.date_input("DATE", datetime.now())
                with c2: airport = st.text_input("LOCATION (IATA)", value=st.session_state.form_airport)
                
                curr_p = st.session_state.form_phase
                p_idx = PHASES.index(curr_p) if curr_p in PHASES else 0
                phase = st.selectbox("MISSION PHASE", PHASES, index=p_idx)
                
                curr_t = st.session_state.form_tags
                if not isinstance(curr_t, list): curr_t = []
                valid_t = [t for t in curr_t if t in COMPETENCIES]
                tags = st.multiselect("COMPETENCY MARKERS", COMPETENCIES, default=valid_t)
                
                st.markdown("**FACTUAL DATA**")
                memo = st.text_area("Memo", value=st.session_state.form_memo, height=150, label_visibility="collapsed")
                st.markdown("**AI FEEDBACK**")
                feedback = st.text_area("FB", value=st.session_state.form_feedback, height=80, label_visibility="collapsed")
                
                # アークリアクターボタン
                if st.form_submit_button("⏺ SECURE DATA", type="primary", use_container_width=True):
                    new_row = pd.DataFrame([{
                        "Date": str(date), "Phase": phase, "Memo": memo, 
                        "Tags": ", ".join(tags), "AI_Feedback": feedback, "Airport": airport
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
                    st.toast("DATA ENCRYPTED & STORED", icon="✅")
                    reset_entry()
                    st.rerun()

    # -----------------------
    # 2. アーカイブ（データリスト）
    # -----------------------
    with tab_list:
        st.subheader("MISSION DATABASE")
        search_query = st.text_input("🔍 SCAN LOGS...", placeholder="Keywords")
        
        if not df.empty:
            display_df = df
            if search_query:
                display_df = df[df["Memo"].str.contains(search_query, case=False, na=False) | 
                                df["Tags"].str.contains(search_query, case=False, na=False)]
            
            for index, row in display_df.sort_values("Date", ascending=False).iterrows():
                with st.container():
                    cols = st.columns([1.5, 3])
                    with cols[0]:
                        st.markdown(f"**{row['Date']}**")
                        st.caption(f"LOC: {row['Airport']} | PHS: {row['Phase']}")
                    
                    with cols[1]:
                        # 発光するタグ
                        tags_html = ""
                        tags_str = str(row['Tags'])
                        if tags_str and tags_str != "nan":
                            for t in tags_str.split(","):
                                tags_html += f"<span class='tag-badge'>{t.strip()}</span>"
                        st.markdown(tags_html, unsafe_allow_html=True)

                    with st.expander("ACCESS DETAILS"):
                        st.markdown(f"**📝 LOG DATA:**\n{row['Memo']}")
                        if row['AI_Feedback'] and row['AI_Feedback'] != "nan":
                            st.info(f"**🤖 J.A.R.V.I.S. NOTE:**\n{row['AI_Feedback']}")
                st.write("")
        else:
            st.info("NO MISSION DATA FOUND.")

    # -----------------------
    # 3. 統計 (ホログラムチャート)
    # -----------------------
    with tab_stats:
        if all_tags:
            st.subheader("PERFORMANCE ANALYTICS")
            counts = pd.Series(all_tags).value_counts()
            # ネオングリーンのレーダーチャート
            fig = go.Figure(data=go.Scatterpolar(
                r=[counts.get(c, 0) for c in COMPETENCIES], theta=COMPETENCIES,
                fill='toself', 
                line=dict(color='#00ff41', width=3), # ネオングリーン
                fillcolor='rgba(0, 255, 65, 0.2)'
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                polar=dict(
                    bgcolor="rgba(0,0,0,0.3)",
                    radialaxis=dict(visible=True, showticklabels=False, linecolor='#30363d', gridcolor='#30363d'),
                    angularaxis=dict(tickfont=dict(color='#00ff41', size=10, family='Orbitron'))
                ),
                margin=dict(t=30, b=30, l=30, r=30), height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("INSUFFICIENT DATA FOR ANALYSIS.")
