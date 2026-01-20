import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.io as pio

# ダークモードグラフ設定
pio.templates.default = "plotly_dark"

# --- 設定: キーワード定義 (PIマニュアルに基づく簡易辞書) ---
# ここにある言葉がメモに含まれると、自動でタグが付きます
KEYWORD_MAPPING = {
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

COMPETENCIES = [f"{k} ({v[0]})" for k, v in KEYWORD_MAPPING.items()] # 表示用ラベル作成

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

# --- 入力ロジック (自動タグ付け機能) ---
st.sidebar.header("📝 New Entry")

# 入力をリアルタイムで反応させるため、formを使わずに直接書く
date = st.sidebar.date_input("Date", datetime.now())
phase = st.sidebar.selectbox("Phase", ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"])
memo = st.sidebar.text_area("Flight Memo", height=150, placeholder="ここにメモを書くと、キーワードに反応して自動でタグが提案されます。\n例: '強い横風でマニュアル操作'")

# ★ここが自動タグ付けの心臓部★
auto_tags = []
if memo:
    for tag, keywords in KEYWORD_MAPPING.items():
        for k in keywords:
            if k.lower() in memo.lower():
                auto_tags.append(tag)
                break

# 重複削除
auto_tags = list(set(auto_tags))

# タグ選択 (自動検出されたものをデフォルトにする)
selected_tags = st.sidebar.multiselect(
    "Performance Indicators (Auto-detected)", 
    options=["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"],
    default=auto_tags # <--- ここで自動入力！
)

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
            categories = ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"]
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
            
            # インサイト表示
            top_tag = tag_counts.idxmax()
            st.info(f"💡 最も意識されているコンピテンシー: **{top_tag}** ({tag_counts.max()}回)")

with tab2:
    # 検索機能
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
