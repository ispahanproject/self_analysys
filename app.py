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
st.set_page_config(page_title="Cockpit Logbook", page_icon="✈️", layout="wide")

# --- 💎 UIデザイン (Glass Cockpit Style) ---
st.markdown("""
<style>
    /* フォント読み込み (Orbitron: 未来的 / Roboto Mono: 計器) */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto+Mono:wght@400;700&display=swap');

    /* 背景画像設定 (夜のコックピット/滑走路の雰囲気) */
    .stApp {
        background-image: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.8)), 
                          url("https://images.unsplash.com/photo-1483450388569-aa47dfd42ede?q=80&w=2574&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        font-family: 'Roboto Mono', monospace;
    }

    /* タイトルフォント */
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        color: #00d4ff !important;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.7); /* ネオン発光 */
        letter-spacing: 2px;
    }

    /* コンテナのグラスモーフィズム (磨りガラス効果) */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background: rgba(20, 30, 40, 0.6);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    /* 入力フォームのスタイル */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(0, 0, 0, 0.5) !important;
        color: #00ff41 !important;
        border: 1px solid #00ff41;
        border-radius: 4px;
        font-family: 'Roboto Mono', monospace;
    }
    
    /* ボタンのスタイル (Glowing Button) */
    .stButton button {
        background: linear-gradient(45deg, #0b3d0b, #1e5c1e);
        color: #00ff41;
        border: 1px solid #00ff41;
        border-radius: 6px;
        font-family: 'Orbitron', sans-serif;
        font-weight: bold;
        transition: 0.3s;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
    .stButton button:hover {
        background: #00ff41;
        color: black;
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.8); /* ホバー時に強く発光 */
    }

    /* チャットメッセージ */
    .stChatMessage {
        background-color: rgba(0, 0, 0, 0.6);
        border-left: 3px solid #00d4ff;
        border-radius: 0 10px 10px 0;
    }
    div[data-testid="stChatMessageContent"] {
        color: #e0e0e0;
    }

    /* Metrics (HUD数値) */
    div[data-testid="stMetricValue"] {
        color: #ff9900 !important; /* アンバー色 */
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px rgba(255, 153, 0, 0.6);
        font-size: 2.5rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #aaaaaa !important;
        font-size: 0.9rem !important;
    }

    /* タブ */
    button[data-baseweb="tab"] {
        color: #8b949e;
        font-family: 'Orbitron', sans-serif;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #00ff41 !important;
        border-bottom-color: #00ff41 !important;
        text-shadow: 0 0 8px rgba(0, 255, 65, 0.5);
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
    st.session_state.messages = [{"role": "assistant", "content": "お疲れ様！今日のフライトはどうだった？フライトログを更新しましょう。"}]
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
# ✈️ HUD (Head Up Display)
# ==========================================
st.markdown("## ✈️ COCKPIT LOGBOOK")

# グラスモーフィズムなHUDコンテナ
with st.container():
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("LOG ENTRIES", len(df))
    with m2: 
        last_apt = df.iloc[-1]["Airport"] if not df.empty else "---"
        st.metric("LAST LOCATION", last_apt)
    with m3:
        all_tags = []
        for t in df["Tags"]:
            if t and t != "nan": all_tags.extend([x.strip() for x in t.split(",")])
        top_tag = pd.Series(all_tags).mode()[0] if all_tags else "---"
        st.metric("PRIMARY FOCUS", top_tag)
    with m4:
        st.write("") # スペーサー
        if st.button("🔄 SYSTEM REBOOT"):
            reset_entry()
            st.rerun()

st.markdown("---")

# ==========================================
# Main Layout
# ==========================================
col_chat, col_data = st.columns([1.6, 1.4])

# --- 左: Communication Log ---
with col_chat:
    st.markdown("### 📡 COMMS CHANNEL")
    
    # チャットコンテナの高さを確保
    chat_container = st.container(height=650)
    
    with chat_container:
        for msg in st.session_state.messages:
            avatar = "👨‍✈️" if msg["role"] == "user" else "👩‍✈️"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # 入力欄
    if prompt := st.chat_input("TRANSMIT FLIGHT REPORT..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👨‍✈️"):
                st.markdown(prompt)

        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if api_key:
            with chat_container:
                with st.chat_message("assistant", avatar="👩‍✈️"):
                    placeholder = st.empty()
                    placeholder.markdown("`ESTABLISHING DATA LINK...`")
                    
                    current_memo = st.session_state.form_memo
                    
                    system_prompt = f"""
                    あなたは「頼れる女性の先輩パイロット」です。
                    ユーザーの発言に対して、まずは日本語で会話を行ってください。

                    【口調】
                    - 親しみやすく、包容力のある先輩口調（「〜だね」「〜かな？」）
                    - 雑談や食事の話にも気さくに反応すること。

                    その後に、区切り文字を入れてJSONデータを出力してください。

                    [現在のメモ状況]
                    {current_memo}

                    [ユーザーの新しい発言]
                    {prompt}

                    【★データクリーニング規則】
                    1. `memo_summary` は「公式な運航記録」である。
                    2. **ノイズ（食事、個人の感情、世間話）は絶対に記録しないこと。**
                    3. 既存のメモにノイズがあれば削除・浄化すること。
                    4. 記録対象は「運航事実、操作、気象、機体状態、安全上の懸念」のみ。

                    【出力フォーマット】
                    (Part 1: 会話 - 雑談OK)
                    
                    ||JSON_START||
                    
                    (Part 2: JSONデータ - 事実のみ)
                    {{
                        "phase": "{PHASES} から選択",
                        "tags": {COMPETENCIES} から選択(リスト),
                        "airport": "IATAコード",
                        "feedback": "教官コメント(1文)",
                        "memo_summary": "事実の箇条書き"
                    }}
                    """
                    
                    # 安定版モデルを使用
                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                    
                    headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
                    data = {"contents": [{"parts": [{"text": system_prompt}]}]}

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = requests.post(url, headers=headers, json=data, timeout=30)
                            if response.status_code == 200: break
                            elif response.status_code == 503:
                                placeholder.markdown(f"`SERVER BUSY. RETRYING ({attempt+1}/{max_retries})...`")
                                time.sleep(2)
                                continue
                            else: break
                        except Exception as e:
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
                            
                    except UnboundLocalError:
                         placeholder.error("Network Error.")

# --- 右: Data Panel ---
with col_data:
    st.markdown("### 💾 FLIGHT RECORDER")
    
    # タブもカスタマイズ
    tab_input, tab_archive = st.tabs(["⏺ ENTRY", "📂 DATABASE"])
    
    with tab_input:
        # グラスモーフィズムのフォーム
        with st.container():
            with st.form("save_form"):
                c1, c2 = st.columns(2)
                with c1: date = st.date_input("DATE", datetime.now())
                with c2: airport = st.text_input("AIRPORT (IATA)", value=st.session_state.form_airport)
                
                curr_p = st.session_state.form_phase
                p_idx = PHASES.index(curr_p) if curr_p in PHASES else 0
                phase = st.selectbox("PHASE", PHASES, index=p_idx)
                
                curr_t = st.session_state.form_tags
                if not isinstance(curr_t, list): curr_t = []
                valid_t = [t for t in curr_t if t in COMPETENCIES]
                tags = st.multiselect("COMPETENCY TAGS", COMPETENCIES, default=valid_t)
                
                st.caption("LOG DETAILS (AUTO-GENERATED)")
                memo = st.text_area("Memo", value=st.session_state.form_memo, height=180, label_visibility="collapsed")
                
                st.caption("INSTRUCTOR FEEDBACK")
                feedback = st.text_area("FB", value=st.session_state.form_feedback, height=80, label_visibility="collapsed")
                
                # 光る保存ボタン
                if st.form_submit_button("⏺ SAVE TO LOGBOOK", type="primary"):
                    new_row = pd.DataFrame([{
                        "Date": str(date), "Phase": phase, "Memo": memo, 
                        "Tags": ", ".join(tags), "AI_Feedback": feedback, "Airport": airport
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
                    st.toast("ENTRY SECURED", icon="✅")
                    reset_entry()
                    st.rerun()
        
        # レーダーチャート
        if all_tags:
            counts = pd.Series(all_tags).value_counts()
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
                    angularaxis=dict(tickfont=dict(color='#00ff41', size=11, family='Orbitron'))
                ),
                margin=dict(t=30, b=30, l=30, r=30), height=300
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab_archive:
        search_query = st.text_input("🔍 SEARCH DATABASE", placeholder="Keywords...")
        if not df.empty:
            display_df = df
            if search_query:
                display_df = df[df["Memo"].str.contains(search_query, case=False, na=False) | 
                                df["Tags"].str.contains(search_query, case=False, na=False)]
            
            # データフレームのスタイル調整は難しいので標準機能で表示
            st.dataframe(display_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True, height=500)
            
            st.markdown("### 📑 FLIGHT REPORTS")
            for index, row in display_df.sort_values("Date", ascending=False).head(5).iterrows():
                title = f"✈️ {row['Date']} | {row['Phase']} @ {row['Airport']}"
                with st.expander(title):
                    st.markdown(f"**TAGS:** `{row['Tags']}`")
                    st.info(f"**LOG:**\n{row['Memo']}")
                    if row['AI_Feedback']: st.success(f"**FEEDBACK:**\n{row['AI_Feedback']}")
        else:
            st.warning("NO FLIGHT DATA AVAILABLE")
