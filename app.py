import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime, timedelta, timezone
import time

# ===============================
# ⚙️ 系統核心設定 (除非你要改價錢，不然不用動這裡)
# ===============================

TW_TZ = timezone(timedelta(hours=8))
SHEET_NAME = "salary_database"

# 費率設定
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 250},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 250},
}

# 裝備價格
PRICE_SHOES = 500
PRICE_GEAR = 100

# 教練名單
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True},
    {"name": "測試教練", "role": "助教", "is_admin": False},
]

# ===============================
# 🔧 Google Sheets 連線工具 (不動)
# ===============================

def get_tw_time():
    return datetime.now(TW_TZ)

def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"連線失敗：{e}")
        return None

def init_sheet_header(sheet):
    try:
        if not sheet.row_values(1):
            header = ["日期", "教練姓名", "職位", "項目", "金額", "備註", "記錄時間"]
            sheet.append_row(header)
    except:
        pass

# ===============================
# 📱 介面設計 (嚴格遵守截圖版型)
# ===============================

st.set_page_config(page_title="薪資系統", page_icon="💰", layout="wide")

# --- 側邊欄 ---
st.sidebar.header("👤 使用者登入")
coach_names = [c["name"] for c in DEFAULT_COACHES]
selected_coach_name = st.sidebar.selectbox("請選擇您的名字", coach_names)
current_user = next((c for c in DEFAULT_COACHES if c["name"] == selected_coach_name), None)

st.sidebar.write("---")
st.sidebar.write("前往")

# 導覽列 (Radio Buttons)
page = st.sidebar.radio("", ["🔴 教練打卡區", "🔵 管理者後台"], label_visibility="collapsed")

# ===============================
# 🔴 頁面 1: 教練打卡區 (你的截圖介面 + 刪除功能回歸)
# ===============================
if page == "🔴 教練打卡區":
    
    # 1. 歡迎與統計
    if current_user:
        st.title(f"👋 你好，{current_user['name']}")
        
        sheet = connect_to_sheet()
        today_salary = 0
        month_salary = 0
        my_df = pd.DataFrame() # 先宣告空的
        
        if sheet:
            try:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
                if not df.empty:
                    df["日期"] = pd.to_datetime(df["日期"])
                    now = get_tw_time()
                    
                    # 篩選我的資料
                    my_df = df[df["教練姓名"] == current_user["name"]].copy()
                    
                    # 統計金額
                    today_df = my_df[my_df["日期"].dt.date == now.date()]
                    today_salary = today_df["金額"].sum()
                    
                    month_df = my_df[(my_df["日期"].dt.year == now.year) & (my_df["日期"].dt.month == now.month)]
                    month_salary = month_df["金額"].sum()
            except:
                pass

        col_m1, col_m2 = st.columns(2)
        col_m1.metric("🔥 今日薪資", f"${today_salary:,}")
        col_m2.metric("💰 本月累積", f"${month_salary:,}")
        
        st.markdown("---")

        # 2. 新增紀錄 (依照截圖排版)
        st.subheader("📝 新增紀錄")
        
        c1, c2 = st.columns(2)
        with c1:
            date_input = st.date_input("日期", get_tw_time())
        with c2:
            st.selectbox("職位", [current_user["role"]], disabled=True)

        c3, c4 = st.columns(2)
        with c3:
            my_rates = DEFAULT_RATES.get(current_user["role"], {})
            rate_options = [f"{k} (${v})" for k, v in my_rates.items()]
            selected_rate_str = st.selectbox("班級 / 項目", rate_options)
        with c4:
            count_class = st.number_input("人數 / 堂數", min_value=0, value=0, step=1)

        st.subheader("🛍️ 裝備銷售")
        c5, c6 = st.columns(2)
        with c5:
            count_shoes = st.number_input(f"鞋子 (${PRICE_SHOES})", min_value=0, value=0)
        with c6:
            count_gear = st.number_input(f"護具 (${PRICE_GEAR})", min_value=0, value=0)

        st.write("")
        
        # 送出按鈕
        if st.button("✅ 確認送出紀錄", type="primary", use_container_width=True):
            if count_class == 0 and count_shoes == 0 and count_gear == 0:
                st.warning("⚠️ 請至少輸入一項數值")
            else:
                sheet = connect_to_sheet()
                if sheet:
                    init_sheet_header(sheet)
                    timestamp = str(get_tw_time().strftime("%Y-%m-%d %H:%M:%S"))
                    records_to_add = []
                    
                    selected_item_name = selected_rate_str.split(" (")[0]
                    selected_item_price = my_rates[selected_item_name]
                    
                    if count_class > 0:
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], selected_item_name, selected_item_price * count_class, f"共 {count_class} 人/堂", timestamp])
                        
                    if count_shoes > 0:
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], "販售-鞋子", PRICE_SHOES * count_shoes, f"賣出 {count_shoes} 雙", timestamp])

                    if count_gear > 0:
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], "販售-護具", PRICE_GEAR * count_gear, f"賣出 {count_gear} 組", timestamp])

                    with st.spinner("寫入雲端中..."):
                        for row in records_to_add:
                            sheet.append_row(row)
                    
                    st.success("✅ 紀錄已送出！")
                    time.sleep(1)
                    st.rerun()

        # 3. 近期紀錄與刪除 (這裡把消失的功能加回來了！)
        st.write("")
        with st.expander("📂 查看與管理我的近期紀錄 (含刪除功能)", expanded=True):
            if not my_df.empty:
                # 顯示表格
                my_df_sorted = my_df.sort_values("日期", ascending=False).head(20)
                st.dataframe(my_df_sorted[["日期", "項目", "金額", "備註"]], use_container_width=True)
                
                # --- 刪除功能 (加回來了) ---
                st.divider()
                st.write("🗑️ **刪除我的紀錄**")
                
                # 重新抓取原始資料來對應行號 (避免刪錯)
                raw_data = sheet.get_all_values()
                delete_options = []
                for idx, row in enumerate(raw_data):
                    if idx == 0: continue
                    # 只顯示「我」的資料
                    if row[1] == current_user["name"]:
                         label = f"Row {idx+1} | {row[0]} | {row[3]} (${row[4]})"
                         delete_options.append((idx + 1, label))
                
                # 為了方便，只顯示最近 10 筆可刪除的
                delete_options.reverse()
                
                if delete_options:
                    col_del1, col_del2 = st.columns([3, 1])
                    with col_del1:
                        target = st.selectbox("選擇要刪除的項目", delete_options[:20], format_func=lambda x: x[1])
                    with col_del2:
                        st.write("") 
                        st.write("")
                        if st.button("🚨 刪除"):
                            try:
                                sheet.delete_rows(target[0])
                                st.success("已刪除！")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"刪除失敗：{e}")
                else:
                    st.info("無資料可刪除")
            else:
                st.info("目前尚無資料")

# ===============================
# 🔵 頁面 2: 管理者後台 (保留完整功能)
# ===============================
elif page == "🔵 管理者後台":
    st.title("📊 管理者後台")
    if not current_user["is_admin"]:
        st.error("⛔ 權限不足")
    else:
        sheet = connect_to_sheet()
        if sheet:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty:
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.sort_values(by="日期", ascending=False)
                
                # 簡單篩選
                coach_filter = st.selectbox("篩選教練", ["全部顯示"] + coach_names)
                if coach_filter != "全部顯示":
                    df = df[df["教練姓名"] == coach_filter]
                
                st.metric("總支出", f"${df['金額'].sum():,}")
                st.dataframe(df, use_container_width=True)
