import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime, timedelta, timezone
import time

# ===============================
# ⚙️ 系統核心設定
# ===============================

TW_TZ = timezone(timedelta(hours=8))
SHEET_NAME = "salary_database"

# 費率表 (配合截圖的邏輯)
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 250},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 250},
}

# 裝備單價
PRICE_SHOES = 500
PRICE_GEAR = 100

# 教練名單
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True},
    {"name": "測試教練", "role": "助教", "is_admin": False},
]

# ===============================
# 🔧 Google Sheets 連線工具
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
# 📱 介面設計 (復刻版)
# ===============================

st.set_page_config(page_title="薪資系統", page_icon="💰", layout="wide")

# --- 側邊欄 ---
st.sidebar.header("👤 使用者登入")
coach_names = [c["name"] for c in DEFAULT_COACHES]
selected_coach_name = st.sidebar.selectbox("請選擇您的名字", coach_names)
current_user = next((c for c in DEFAULT_COACHES if c["name"] == selected_coach_name), None)

st.sidebar.write("---")
st.sidebar.write("前往")

# 這裡就是你要的「圓點切換」導覽列
page = st.sidebar.radio("", ["🔴 教練打卡區", "🔵 管理者後台"], label_visibility="collapsed")

# ===============================
# 🔴 頁面 1: 教練打卡區 (復刻你的截圖)
# ===============================
if page == "🔴 教練打卡區":
    
    # 1. 頂部歡迎語與薪資概況
    if current_user:
        st.title(f"👋 你好，{current_user['name']}")
        
        # 撈取資料計算今日與本月薪資
        sheet = connect_to_sheet()
        today_salary = 0
        month_salary = 0
        
        if sheet:
            try:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
                if not df.empty:
                    df["日期"] = pd.to_datetime(df["日期"])
                    now = get_tw_time()
                    
                    # 篩選我的資料
                    my_df = df[df["教練姓名"] == current_user["name"]]
                    
                    # 今日
                    today_df = my_df[my_df["日期"].dt.date == now.date()]
                    today_salary = today_df["金額"].sum()
                    
                    # 本月
                    month_df = my_df[(my_df["日期"].dt.year == now.year) & (my_df["日期"].dt.month == now.month)]
                    month_salary = month_df["金額"].sum()
            except:
                pass

        # 顯示大數字儀表板
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("🔥 今日薪資", f"${today_salary:,}")
        col_m2.metric("💰 本月累積", f"${month_salary:,}")
        
        st.markdown("---")

        # 2. 新增紀錄區塊 (完全依照截圖排版)
        st.subheader("📝 新增紀錄")
        
        # 第一排：日期 | 職位
        c1, c2 = st.columns(2)
        with c1:
            date_input = st.date_input("日期", get_tw_time())
        with c2:
            st.selectbox("職位", [current_user["role"]], disabled=True) # 鎖定顯示

        # 第二排：班級項目 | 人數
        c3, c4 = st.columns(2)
        with c3:
            # 製作帶有金額的選項，例如 "基礎 ($180)"
            my_rates = DEFAULT_RATES.get(current_user["role"], {})
            rate_options = [f"{k} (${v})" for k, v in my_rates.items()]
            selected_rate_str = st.selectbox("班級 / 項目", rate_options)
        with c4:
            count_class = st.number_input("人數 / 堂數", min_value=0, value=0, step=1)

        # 3. 裝備銷售區塊
        st.subheader("🛍️ 裝備銷售")
        c5, c6 = st.columns(2)
        with c5:
            count_shoes = st.number_input(f"鞋子 (${PRICE_SHOES})", min_value=0, value=0)
        with c6:
            count_gear = st.number_input(f"護具 (${PRICE_GEAR})", min_value=0, value=0)

        st.write("") # 空行
        
        # 4. 紅色大按鈕
        if st.button("✅ 確認送出紀錄", type="primary", use_container_width=True):
            if count_class == 0 and count_shoes == 0 and count_gear == 0:
                st.warning("⚠️ 請至少輸入一項數值")
            else:
                sheet = connect_to_sheet()
                if sheet:
                    init_sheet_header(sheet)
                    timestamp = str(get_tw_time().strftime("%Y-%m-%d %H:%M:%S"))
                    records_to_add = []
                    
                    # 解析班級選擇 (把 "基礎 ($180)" 拆解回 "基礎" 和 180)
                    selected_item_name = selected_rate_str.split(" (")[0]
                    selected_item_price = my_rates[selected_item_name]
                    
                    # 1. 處理班級薪資
                    if count_class > 0:
                        total_class = selected_item_price * count_class
                        note = f"共 {count_class} 人/堂"
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], selected_item_name, total_class, note, timestamp])
                        
                    # 2. 處理鞋子
                    if count_shoes > 0:
                        total_shoes = PRICE_SHOES * count_shoes
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], "販售-鞋子", total_shoes, f"賣出 {count_shoes} 雙", timestamp])

                    # 3. 處理護具
                    if count_gear > 0:
                        total_gear = PRICE_GEAR * count_gear
                        records_to_add.append([str(date_input), current_user["name"], current_user["role"], "販售-護具", total_gear, f"賣出 {count_gear} 組", timestamp])

                    # 批次寫入雲端
                    with st.spinner("正在寫入雲端..."):
                        for row in records_to_add:
                            sheet.append_row(row)
                    
                    st.success("✅ 紀錄已送出！")
                    time.sleep(1)
                    st.rerun()

        # 5. 底部展開區 (查看我的近期紀錄)
        st.write("")
        with st.expander("📂 查看與管理我的近期紀錄 (近 60 天)"):
            if 'my_df' in locals() and not my_df.empty:
                # 簡單顯示表格
                display_cols = ["日期", "項目", "金額", "備註"]
                st.dataframe(my_df.sort_values("日期", ascending=False).head(60)[display_cols], use_container_width=True)
            else:
                st.info("尚無資料")

# ===============================
# 🔵 頁面 2: 管理者後台 (獨立出來)
# ===============================
elif page == "🔵 管理者後台":
    st.title("📊 管理者後台")
    
    # 權限檢查
    if not current_user["is_admin"]:
        st.error("⛔ 抱歉，您沒有管理員權限。")
    else:
        sheet = connect_to_sheet()
        if sheet:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if not df.empty:
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.sort_values(by="日期", ascending=False)
                
                # 篩選器
                col1, col2, col3 = st.columns(3)
                with col1:
                    years = sorted(df["日期"].dt.year.unique(), reverse=True)
                    sel_year = st.selectbox("年份", years)
                with col2:
                    months = sorted(df[df["日期"].dt.year == sel_year]["日期"].dt.month.unique())
                    sel_month = st.selectbox("月份", months, index=len(months)-1 if months else 0)
                with col3:
                    coach_filter = st.selectbox("篩選教練", ["全部顯示"] + coach_names)

                mask = (df["日期"].dt.year == sel_year) & (df["日期"].dt.month == sel_month)
                if coach_filter != "全部顯示":
                    mask = mask & (df["教練姓名"] == coach_filter)
                
                filtered_df = df[mask]
                
                st.metric("本月總支出", f"${filtered_df['金額'].sum():,}")
                st.dataframe(filtered_df, use_container_width=True)
                
                # 刪除功能
                st.write("---")
                st.subheader("🗑️ 刪除紀錄")
                
                raw_data = sheet.get_all_values()
                delete_options = []
                for idx, row in enumerate(raw_data):
                    if idx == 0: continue
                    try:
                        r_date = datetime.strptime(row[0], "%Y-%m-%d")
                        if r_date.year == sel_year and r_date.month == sel_month:
                             if coach_filter == "全部顯示" or row[1] == coach_filter:
                                label = f"Row {idx+1} | {row[0]} | {row[1]} | {row[3]} (${row[4]})"
                                delete_options.append((idx + 1, label))
                    except:
                        pass
                
                if delete_options:
                    target = st.selectbox("選擇要刪除的項目", delete_options, format_func=lambda x: x[1])
                    if st.button("🚨 確認刪除資料"):
                        try:
                            sheet.delete_rows(target[0])
                            st.success("刪除成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗：{e}")
                else:
                    st.info("無可刪除資料")
