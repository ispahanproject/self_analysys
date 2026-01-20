import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 設定 ---
COMPETENCIES = [
    "FA (Automation)", "FM (Manual Control)", "AP (Procedures)", 
    "SA (Sit. Awareness)", "DM (Decision Making)", "WM (Workload)", 
    "TB (Team Building)", "CO (Communication)", "KK (Knowledge)", "AA (Attitude)"
]

st.set_page_config(page_title="Pilot Log", page_icon="✈️")
st.title("👨‍✈️ Pilot Performance Tracker")

# --- Google Sheets 接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# データの読み込み (try-exceptを外して、エラーをそのまま表示させる)
df = conn.read(worksheet="Sheet1", usecols=[0, 1, 2, 3], ttl=5)

# 空データ対策
if df.empty:
    df = pd.DataFrame(columns=["Date", "Phase", "Memo", "Tags"])
else:
    # 日付型変換などを安全に行う
    df["Date"] = df["Date"].astype(str)
    df["Tags"] = df["Tags"].astype(str)

# --- 入力フォーム (サイドバー/スマホなら上部) ---
with st.expander("📝 New Flight Entry", expanded=True):
    with st.form("input_form"):
        date = st.date_input("Date", datetime.now())
        phase = st.selectbox("Phase", ["Pre-flight", "Taxi", "Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing", "Parking", "Debriefing"])
        memo = st.text_area("Flight Memo", placeholder="例: 強い横風。風下ラダーを意識して接地。")
        
        # 簡易タグ付け
        selected_tags = st.multiselect("Performance Indicators", 
                                       ["FA", "FM", "AP", "SA", "DM", "WM", "TB", "CO", "KK", "AA"])
        
        submitted = st.form_submit_button("Save Entry")

        if submitted:
            # 新しい行を作成
            new_row = pd.DataFrame([{
                "Date": str(date),
                "Phase": phase,
                "Memo": memo,
                "Tags": ", ".join(selected_tags)
            }])
            
            # 結合して更新
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("Log Saved! Please refresh to see analytics.")
            st.rerun() # 画面リロード

# --- ダッシュボード表示 ---
tab1, tab2 = st.tabs(["📊 Analytics", "🗂 Logbook"])

with tab1:
    if not df.empty:
        # タグの集計処理
        all_tags_list = []
        for tags_str in df["Tags"]:
            if tags_str and tags_str != "nan":
                all_tags_list.extend([t.strip() for t in tags_str.split(",")])
        
        if all_tags_list:
            tag_counts = pd.Series(all_tags_list).value_counts()
            
            # レーダーチャート
            radar_data = pd.DataFrame({
                "r": [tag_counts.get(comp.split()[0], 0) for comp in COMPETENCIES],
                "theta": [comp.split()[0] for comp in COMPETENCIES]
            })
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=radar_data['r'],
                theta=radar_data['theta'],
                fill='toself',
                name='Performance'
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True)),
                showlegend=False,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("データがまだありません。ログを入力してください。")
    else:
        st.info("データがありません。")

with tab2:
    st.dataframe(df.sort_values(by="Date", ascending=False), use_container_width=True)
