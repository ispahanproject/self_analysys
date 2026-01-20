import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio

# ダークモードグラフ設定
pio.templates.default = "plotly_dark"

# --- 設定: キーワード定義 ---

# 1. コンピテンシー (タグ) 判定用辞書
TAG_KEYWORDS = {
    "FA": ["Auto", "Automation", "FMS", "MCP", "AFDS", "Mode", "VNAV", "LNAV", "LOC", "APP"],
    "FM": ["Manual", "Hand", "Control", "Stick", "Rudder", "Brake", "Thrust", "Disconnect", "Raw", "Visual", "操作", "ハンド", "マニュアル", "舵", "足", "ブレーキ"],
    "AP": ["Proc", "Checklist", "SOP", "Limit", "Config", "Flap", "Gear", "手順", "規定", "チェックリスト", "リミット"],
    "SA": ["SA", "Monitor", "Weather", "WX", "Radar", "Cloud", "Wind", "Fog", "Ice", "Energy", "Speed", "Alt", "気象", "揺れ", "雲", "風", "視程", "モニター", "認識"],
    "DM": ["Deci", "Option", "Risk", "Plan", "Divert", "Go-around", "GA", "判断", "決断", "選択", "案", "リスク", "変更"],
    "WM": ["Time", "Task", "Rush", "Delay", "Busy", "Load", "時間", "タスク", "忙", "遅れ", "焦り"],
    "TB": ["Team", "CA", "CP", "Copilot", "Captain", "Leader", "Member", "Atmosphere", "チーム", "機長", "副操縦士", "客室", "雰囲気", "連携"],
    "CO": ["Comm", "Talk", "Listen", "ATC", "Call", "Briefing", "Radio", "PA", "Assert", "話", "聞", "交信", "ブリーフィング", "連絡", "伝"],
    "KK": ["Know", "System", "Reg", "Law", "Terrain", "Route", "知識", "システム", "法", "地形", "空港", "特性"],
    "AA": ["Attitude", "Safe", "Customer", "Comfort", "Rule", "Comp", "態度", "安全", "顧客", "快適", "遵", "丁寧"]
}

# 2. フライトフェーズ判定用辞書 (★今回追加)
PHASE_KEYWORDS = {
    "Pre-flight": ["Pre-flight", "Briefing", "Show up", "ブリーフィング", "準備", "天気確認", "整備", "シップ", "外部点検"],
    "Taxi": ["Taxi", "Ground", "Ramp", "Gate", "タキシング", "地上", "滑走路", "R/W", "ブロックアウト"],
    "Takeoff": ["Takeoff", "T/O", "Departure", "V1", "VR", "Rotate", "離陸", "滑走", "上がり"],
    "Climb": ["Climb", "FL", "Level off", "上昇", "レベルオフ", "SID"],
    "Cruise": ["Cruise", "Level", "Turbulence", "巡航", "揺れ", "ステップ", "気流"],
    "Descent": ["Descent", "Descend", "TOD", "STAR", "Arrival", "降下", "アライバル"],
    "Approach": ["Approach", "App", "ILS", "LOC", "G/S", "Vector", "Go-around", "GA", "進入", "アプローチ", "会合"],
    "Landing": ["Landing", "Land", "Touchdown", "Flare", "Rollout", "着陸", "接地", "フレア", "リバース", "クロスウィンド"],
    "Parking": ["Parking", "Spot", "Shutdown", "Engine off", "Block in", "スポット", "エンジンカット", "ブロックイン"],
    "Debriefing": ["Debriefing", "Review", "デブリーフィング", "振り返り", "解散"]
}
PHASE_LIST = list(PHASE_KEYWORDS.keys())

st.set_page_config(page_title="Pilot Log", page_icon="✈️", layout="wide")
st.title("👨‍✈️ Pilot Performance Tracker")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# データの読み込み
df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3], ttl=5)
if df.empty:
    df = pd.DataFrame(columns=["Date", "Phase", "Memo", "Tags"])
else:
    df["Date"] = df["Date"].astype(str)
    df["Tags"] = df["Tags"].astype(str)

# --- 入力エリア ---
st.sidebar.header("📝 New Entry")

# 1. メモ入力 (ここに入力された内容を見て、下のPhaseとTagsを書き換えます)
memo = st.sidebar.text_area("Flight Memo", height=150, placeholder="例: 強い横風着陸でマニュアル操作を行った。")

# --- 自動判別ロジック ---

# A. Phaseの自動判別
default_phase_index = 0 # デフォルトはPre-flight
if memo:
    # 辞書を上から順番にチェックして、最初にヒットしたフェーズを採用
    for i, (p_name, keywords) in enumerate(PHASE_KEYWORDS.items()):
        if any(k.lower() in memo.lower() for k in keywords):
            default_phase_index = i
            break

# B. Tagsの自動判別
auto_tags = []
if memo:
    for tag, keywords in TAG_KEYWORDS.items():
        if any(k.lower() in memo.lower() for k in keywords):
            auto_tags.append(tag)
auto_tags = list(set(auto_tags))

# --- 入力フォーム表示 ---

date = st.sidebar.date_input("Date", datetime.now())

# Phase選択肢 (index引数を使って、自動判別した位置を初期選択にする)
phase = st.sidebar.selectbox("Phase", PHASE_LIST, index=default_phase_index)

# Tags選択肢 (default引数を使って、自動判別したタグを初期選択にする)
selected_tags = st.sidebar.multiselect(
    "Performance Indicators", 
    options=list(TAG_KEYWORDS.keys()),
    default=auto_tags
)

# 保存ボタン
if st.sidebar.button("Save Entry", type="primary"):
    new_row = pd.DataFrame([{
        "Date": str(date),
        "Phase": phase,
        "Memo": memo,
        "Tags": ", ".join(selected_tags)
    }])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Sheet1", data=updated_df)
    st.sidebar.success("Saved!")
    st.rerun()

# --- ダッシュボード表示 ---
tab1, tab2 = st.tabs(["📊 Analytics", "🗂 Logbook"])

with tab1:
    if not df.empty:
        all_tags_list = []
        for tags_str in df["Tags"]:
            if tags_str and tags_str != "nan":
                all_tags_list.extend([t.strip() for t in tags_str.split(",")])
        
        if all_tags_list:
            tag_counts = pd.Series(all_tags_list).value_counts()
            
            # レーダーチャート
            categories = list(TAG_KEYWORDS.keys())
            values = [tag_counts.get(cat, 0) for cat in categories]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name='Performance',
                line_color='#00CC96'
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, showticklabels=False),
                    bgcolor='rgba(0,0,0,0)'
                ),
                margin=dict(l=40, r=40, t=40, b=40),
                paper_bgcolor='rgba(0,0,0,0)',
                font_color="white"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # インサイト
            st.markdown("### 💡 Latest Insights")
            col1, col2 = st.columns(2)
            with col1:
                top_tag = tag_counts.idxmax()
                st.metric("Most Frequent", f"{top_tag} ({tag_counts.max()})")
            with col2:
                recent_phase = df.iloc[-1]["Phase"]
                st.metric("Last Phase", recent_phase)

with tab2:
    search = st.text_input("🔍 Search Logs", "")
    if search:
        display_df = df[df["Memo"].str.contains(search, case=False, na=False)]
    else:
        display_df = df
        
    st.dataframe(
        display_df.sort_values(by="Date", ascending=False), 
        use_container_width=True,
        hide_index=True
    )
