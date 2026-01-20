import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio
import plotly.graph_objects as go
import json
import requests
import re

# --- 初期設定 ---
pio.templates.default = "plotly_dark"
st.set_page_config(page_title="AI Pilot Log Chat", page_icon="✈️", layout="wide")

# 定義
COMPETENCIES = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
PHASES = ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"]

st.title("👨‍✈️ AI Instructor Chat Log")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# データ読み込み（エラーハンドリング付き）
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

# --- セッション状態の初期化 ---
if "messages" not in st.session_state:
    # 初回のAIからの挨拶
    st.session_state.messages = [
        {"role": "assistant", "content": "お疲れ様です、キャプテン。本日のフライトはいかがでしたか？気になったことや反省点があれば教えてください。"}
    ]

# 保存用フォームの一時データ
if 'form_phase' not in st.session_state: st.session_state.form_phase = "Pre-flight"
if 'form_tags' not in st.session_state: st.session_state.form_tags = []
if 'form_airport' not in st.session_state: st.session_state.form_airport = ""
if 'form_memo' not in st.session_state: st.session_state.form_memo = ""
if 'form_feedback' not in st.session_state: st.session_state.form_feedback = ""

# --- レイアウト: 2カラム (左: チャット / 右: 保存フォーム & ダッシュボード) ---
# スマホだと縦に並びます
col_chat, col_tools = st.columns([2, 1])

# ==========================================
# 左カラム: チャットインターフェース
# ==========================================
with col_chat:
    # 1. 過去のメッセージを表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 2. ユーザー入力エリア
    if prompt := st.chat_input("フライトの振り返りを入力..."):
        # ユーザーのメッセージを表示・保存
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AIの応答生成
        api_key_raw = st.secrets.get("GEMINI_API_KEY", "")
        api_key = str(api_key_raw).replace('"', '').replace("'", "").strip()

        if not api_key:
            st.error("APIキーが設定されていません。")
        else:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown("Thinking...")

                # プロンプト: 会話とJSON抽出を両立させる
                system_prompt = f"""
                役割：あなたはベテランパイロット教官です。
                ユーザー（パイロット）との対話を通じて、フライトの振り返りをサポートします。
                
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
                
                ※ 会話の中にフライト情報が含まれていない場合は、JSONの中身は空文字などで埋めてください。

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
                        
                        # 区切り文字で分割
                        if "||JSON_START||" in raw_text:
                            parts = raw_text.split("||JSON_START||")
                            chat_response = parts[0].strip()
                            json_part = parts[1].strip().replace("```json", "").replace("```", "")
                            
                            # JSONパースとフォームへの反映
                            try:
                                extracted_data = json.loads(json_part)
                                st.session_state.form_phase = extracted_data.get("phase", st.session_state.form_phase)
                                st.session_state.form_tags = extracted_data.get("tags", st.session_state.form_tags)
                                st.session_state.form_airport = extracted_data.get("airport", st.session_state.form_airport)
                                # AIのアドバイスをフィードバック欄へ
                                if extracted_data.get("feedback"):
                                    st.session_state.form_feedback = extracted_data.get("feedback")
                                # メモ欄にはユーザーの直前の発言を入れる（または会話全体を入れるよう改造も可）
                                st.session_state.form_memo = prompt 
                                
                            except:
                                pass # JSON解釈失敗時は無視（会話だけ続ける）
                        else:
                            chat_response = raw_text
                        
                        # 画面表示と履歴保存
                        message_placeholder.markdown(chat_response)
                        st.session_state.messages.append({"role": "assistant", "content": chat_response})
                        
                        # フォームを更新するためにリラン（UX向上のため）
                        st.rerun()
                        
                    else:
                        message_placeholder.error(f"Error: {response.status_code}")
                except Exception as e:
                    message_placeholder.error(f"通信エラー: {e}")

# ==========================================
# 右カラム: ログ保存 & データ分析
# ==========================================
with col_tools:
    st.header("📝 Log Entry")
    st.info("チャットで話すと自動入力されます")
    
    with st.form("save_form"):
        date = st.date_input("Date", datetime.now())
        airport = st.text_input("Airport", value=st.session_state.form_airport)
        
        # フェーズ選択
        curr_phase = st.session_state.form_phase
        p_idx = PHASES.index(curr_phase) if curr_phase in PHASES else 0
        phase = st.selectbox("Phase", PHASES, index=p_idx)
        
        tags = st.multiselect("Tags", COMPETENCIES, default=st.session_state.form_tags)
        
        # メモ（チャットの内容を修正可能にする）
        memo = st.text_area("Memo", value=st.session_state.form_memo, height=100)
        
        # AIフィードバック（保存用）
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
            
            # 入力クリア
            st.session_state.form_memo = ""
            st.session_state.form_feedback = ""
            st.rerun()

    st.markdown("---")
    
    # 簡易ダッシュボード (タブで切り替え)
    tab_log, tab_stats = st.tabs(["🗂 Recent Logs", "📊 Stats"])
    
    with tab_log:
        search = st.text_input("🔍 Search", "")
        target_df = df[df["Memo"].str.contains(search, case=False, na=False)] if search else df
        st.dataframe(target_df.sort_values("Date", ascending=False).head(5), hide_index=True, use_container_width=True)

    with tab_stats:
        # タグチャート
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
