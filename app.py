import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio
import plotly.graph_objects as go
import json
import requests

# --- ページ設定 ---
st.set_page_config(page_title="Cockpit Logbook", page_icon="✈️", layout="wide")

# --- デザイン(CSS) ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; font-family: 'Roboto Mono', monospace; }
    h1, h2, h3 { color: #e0e0e0 !important; font-family: 'Helvetica Neue', sans-serif; letter-spacing: 1px; }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #1c2026; color: #00ff41; border: 1px solid #30363d; border-radius: 4px;
    }
    .stButton button {
        background-color: #238636; color: white; border: 1px solid rgba(27,31,35,0.15); font-weight: 600;
    }
    .stButton button:hover { background-color: #2ea043; }
    .stChatMessage { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    div[data-testid="stMetricValue"] { color: #00d4ff; font-family: 'Roboto Mono', monospace; }
    
    /* タブのスタイル調整 */
    button[data-baseweb="tab"] { background-color: transparent; color: #8b949e; font-weight: bold; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #00ff41 !important; border-bottom-color: #00ff41 !important; }
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
    # ここで最初のメッセージを設定
    st.session_state.messages = [{"role": "assistant", "content": "SYSTEM READY. フライトの振り返りを開始します。状況を教えてください。"}]
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
# ✈️ HUD
# ==========================================
st.markdown("### ✈️ FLIGHT DATA ANALYZER")
m1, m2, m3, m4 = st.columns(4)
with m1: st.metric("TOTAL ENTRIES", len(df))
with m2: 
    last_apt = df.iloc[-1]["Airport"] if not df.empty else "N/A"
    st.metric("LAST AIRPORT", last_apt)
with m3:
    all_tags = []
    for t in df["Tags"]:
        if t and t != "nan": all_tags.extend([x.strip() for x in t.split(",")])
    top_tag = pd.Series(all_tags).mode()[0] if all_tags else "N/A"
    st.metric("TOP ISSUE", top_tag)
with m4:
    if st.button("🔄 SYSTEM RESET"):
        reset_entry()
        st.rerun()
st.markdown("---")

# ==========================================
# Main Layout
# ==========================================
col_chat, col_data = st.columns([1.6, 1.4])

# --- 左: Communication Log ---
with col_chat:
    st.subheader("📡 COMMS LOG")
    chat_container = st.container(height=600)
    
    # 履歴の表示
    with chat_container:
        for msg in st.session_state.messages:
            avatar = "👨‍✈️" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # 入力処理
    if prompt := st.chat_input("Input Flight Report..."):
        # 1. ユーザーのメッセージを表示・保存
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👨‍✈️"):
                st.markdown(prompt)

        # 2. APIキーの確認
        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if not api_key:
            st.error("⚠️ API KEY NOT FOUND. Check Secrets.")
        else:
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    placeholder = st.empty()
                    placeholder.markdown("`PROCESSING...`")
                    
                    current_memo = st.session_state.form_memo
                    
                    # --- プロンプト (会話を優先するように修正) ---
                    system_prompt = f"""
                    あなたはベテランパイロット教官です。
                    ユーザーの発言に対して、まずは**日本語で会話（質問、共感、アドバイス）**を行ってください。
                    その後に、区切り文字を入れてJSONデータを出力してください。

                    [現在のメモ状況]
                    {current_memo}

                    [ユーザーの新しい発言]
                    {prompt}

                    【出力フォーマット】
                    (Part 1: 会話)
                    ここには教官としての返答を書いてください。
                    
                    ||JSON_START||
                    
                    (Part 2: JSONデータ)
                    {{
                        "phase": "{PHASES} から選択",
                        "tags": {COMPETENCIES} から選択(リスト),
                        "airport": "IATAコード",
                        "feedback": "教官コメント(1文)",
                        "memo_summary": "事実の箇条書き(追記・統合)"
                    }}
                    """
                    
                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                    headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
                    data = {"contents": [{"parts": [{"text": system_prompt}]}]}

                    try:
                        response = requests.post(url, headers=headers, json=data, timeout=30)
                        if response.status_code == 200:
                            result_json = response.json()
                            raw = result_json['candidates'][0]['content']['parts'][0]['text']
                            
                            chat_res = ""
                            
                            # 分割処理
                            if "||JSON_START||" in raw:
                                parts = raw.split("||JSON_START||")
                                chat_res = parts[0].strip()
                                json_part = parts[1].strip().replace("```json","").replace("```","")
                                
                                # JSON解析
                                try:
                                    d = json.loads(json_part)
                                    st.session_state.form_phase = d.get("phase", st.session_state.form_phase)
                                    
                                    new_tags = d.get("tags", [])
                                    if not isinstance(new_tags, list): new_tags = []
                                    st.session_state.form_tags = new_tags
                                    
                                    st.session_state.form_airport = d.get("airport", st.session_state.form_airport)
                                    if d.get("feedback"): st.session_state.form_feedback = d.get("feedback")
                                    if d.get("memo_summary"): st.session_state.form_memo = d.get("memo_summary")
                                except:
                                    pass # JSON失敗しても会話は表示する
                            else:
                                # 区切り文字がない場合は全文を会話として扱う
                                chat_res = raw
                            
                            # AIの返答を表示・保存
                            placeholder.markdown(chat_res)
                            st.session_state.messages.append({"role": "assistant", "content": chat_res})
                            
                            # フォーム更新のためにリラン
                            st.rerun()
                            
                        else:
                            placeholder.error(f"API Error: {response.status_code}")
                            
                    except Exception as e:
                        placeholder.error(f"Connection Error: {e}")

# --- 右: Data Panel (Tabbed) ---
with col_data:
    tab_input, tab_archive = st.tabs(["⏺ RECORDER", "📂 ARCHIVE"])
    
    # ----------------------------------
    # タブ1: 入力フォーム
    # ----------------------------------
    with tab_input:
        st.caption("FLIGHT DATA ENTRY")
        with st.container(border=True):
            with st.form("save_form"):
                c1, c2 = st.columns(2)
                with c1: date = st.date_input("DATE", datetime.now())
                with c2: airport = st.text_input("ARPT", value=st.session_state.form_airport)
                
                curr_p = st.session_state.form_phase
                p_idx = PHASES.index(curr_p) if curr_p in PHASES else 0
                phase = st.selectbox("PHASE", PHASES, index=p_idx)
                
                curr_t = st.session_state.form_tags
                if not isinstance(curr_t, list): curr_t = []
                valid_t = [t for t in curr_t if t in COMPETENCIES]
                tags = st.multiselect("TAGS", COMPETENCIES, default=valid_t)
                
                st.markdown("**FACTS**")
                memo = st.text_area("Memo", value=st.session_state.form_memo, height=150, label_visibility="collapsed")
                st.markdown("**NOTES**")
                feedback = st.text_area("FB", value=st.session_state.form_feedback, height=80, label_visibility="collapsed")
                
                if st.form_submit_button("⏺ RECORD ENTRY", type="primary"):
                    new_row = pd.DataFrame([{
                        "Date": str(date), "Phase": phase, "Memo": memo, 
                        "Tags": ", ".join(tags), "AI_Feedback": feedback, "Airport": airport
                    }])
                    conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
                    st.toast("DATA SAVED", icon="💾")
                    reset_entry()
                    st.rerun()
        
        if all_tags:
            counts = pd.Series(all_tags).value_counts()
            fig = go.Figure(data=go.Scatterpolar(
                r=[counts.get(c, 0) for c in COMPETENCIES], theta=COMPETENCIES,
                fill='toself', line_color='#00ff41', fillcolor='rgba(0, 255, 65, 0.2)'
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                polar=dict(radialaxis=dict(visible=True, showticklabels=False, linecolor='#30363d')),
                margin=dict(t=20, b=20, l=30, r=30), height=250
            )
            st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------
    # タブ2: データベース
    # ----------------------------------
    with tab_archive:
        st.caption("MISSION LOGS DATABASE")
        search_query = st.text_input("🔍 FILTER LOGS", placeholder="Search keywords...")
        if not df.empty:
            display_df = df
            if search_query:
                display_df = df[df["Memo"].str.contains(search_query, case=False, na=False) | 
                                df["Tags"].str.contains(search_query, case=False, na=False)]
            st.dataframe(display_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True, height=400)
            st.markdown("---")
            st.markdown("### 📑 DETAILED REPORT")
            for index, row in display_df.sort_values("Date", ascending=False).head(5).iterrows():
                title = f"{row['Date']} | {row['Phase']} @ {row['Airport']}"
                with st.expander(title):
                    st.markdown(f"**TAGS:** `{row['Tags']}`")
                    st.info(f"**MEMO:**\n{row['Memo']}")
                    if row['AI_Feedback']: st.success(f"**INSTRUCTOR:**\n{row['AI_Feedback']}")
        else:
            st.info("NO DATA FOUND.")
