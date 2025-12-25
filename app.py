import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime, timedelta, timezone
import time

# ===============================
# ⚙️ 設定區：以後要改名單或價錢，來這裡改就好！
# ===============================

# 1. 薪水價錢表
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 250},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 250},
}

# 2. 裝備單價
PRICE_SHOES = 500
PRICE_GEAR = 100

# 3. 教練名單
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True},
    {"name": "黃奕硯", "role": "實習主教", "is_admin": False},
]

# ===============================
# 🔧 核心工具 (不動)
# ===============================

TW_TZ = timezone(timedelta(hours=8))
SHEET_NAME = "salary_database"

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
# 📱 介面程式
# ===============================

st.set_page_config(page_title="薪資系統", page_icon="💰", layout="wide")

# --- 側邊欄 ---
st.sidebar.header("👤 使用者登入")
coach_names = [c["name"] for c in DEFAULT_COACHES]
selected_coach_name = st.sidebar.selectbox("請選擇您的名字", coach_names)

# 抓取基本資料
current_user = next((c for c in DEFAULT_COACHES if c["name"] == selected_coach_name), None)

# 左上角固定顯示設定檔裡的職位
if current_user:
    st.sidebar.success(f"目前身份：\n**{selected_coach_name} ({current_user['role']})**")

st.sidebar.write("---")
page = st.sidebar.radio("前往", ["🔴 教練打卡區", "🔵 管理者後台"], label_visibility="collapsed")

# ===============================
# 🔴 頁面 1: 教練打卡區
# ===============================
if page == "🔴 教練打卡區":
    
    if current_user:
        st.title(f"👋 你好，{selected_coach_name}")
        
        # --- 統計儀表板 ---
        today_salary = 0
        month_salary = 0
        my_df = pd.DataFrame()
        
        sheet = connect_to_sheet()
        if sheet:
            try:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
                if not df.empty:
                    df["日期"] = pd.to_datetime(df["日期"])
                    now = get_tw_time()
                    my_df = df[df["教練姓名"] == selected_coach_name].copy()
                    
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

        # --- 新增紀錄區 ---
        st.subheader("📝 新增紀錄")
        
        c1, c2 = st.columns(2)
        with c1:
            date_input = st.date_input("日期", get_tw_time())
        with c2:
            # 這裡依然可以讓你選職位 (方便代班)，但預設會選你原本的
            all_roles = list(DEFAULT_RATES.keys())
            try:
                default_idx = all_roles.index(current_user["role"])
            except:
                default_idx = 0
            selected_role_input = st.selectbox("職位 (可修改)", all_roles, index=default_idx)

        c3, c4 = st.columns(2)
        with c3:
            # 根據上面選的職位，跳出對應價格
            current_rates = DEFAULT_RATES.get(selected_role_input, {})
            rate_options = [f"{k} (${v})" for k, v in current_rates.items()]
            
            if rate_options:
                selected_rate_str = st.selectbox("班級 / 項目", rate_options)
            else:
                selected_rate_str = st.selectbox("班級 / 項目", ["無計費項目"])
                
        with c4:
            count_class = st.number_input("人數 / 堂數", min_value=0, value=0, step=1)

        # 裝備區
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
                    
                    # 1. 處理班級
                    if count_class > 0 and rate_options:
                        try:
                            item_name = selected_rate_str.split(" ($")[0]
                            item_price = int(selected_rate_str.split(" ($")[1].replace(")", ""))
                            total_class = item_price * count_class
                            note = f"共 {count_class} 人/堂"
                            
                            records_to_add.append([str(date_input), selected_coach_name, selected_role_input, item_name, total_class, note, timestamp])
                        except:
                            st.error("價格解析錯誤")
                        
                    # 2. 處理鞋子
                    if count_shoes > 0:
                        records_to_add.append([str(date_input), selected_coach_name, selected_role_input, "販售-鞋子", PRICE_SHOES * count_shoes, f"賣出 {count_shoes} 雙", timestamp])

                    # 3. 處理護具
                    if count_gear > 0:
                        records_to_add.append([str(date_input), selected_coach_name, selected_role_input, "販售-護具", PRICE_GEAR * count_gear, f"賣出 {count_gear} 組", timestamp])

                    if records_to_add:
                        with st.spinner("寫入中..."):
                            for row in records_to_add:
                                sheet.append_row(row)
                        st.success("✅ 紀錄已送出！")
                        time.sleep(1)
                        st.rerun()

        # --- 查看區 ---
        st.write("")
        with st.expander("📂 查看與管理我的近期紀錄 (含刪除功能)", expanded=True):
            if not my_df.empty:
                st.dataframe(my_df.sort_values("日期", ascending=False).head(20)[["日期", "職位", "項目", "金額", "備註"]], use_container_width=True)
                
                st.divider()
                st.write("🗑️ **刪除我的紀錄**")
                
                raw_data = sheet.get_all_values()
                delete_options = []
                for idx, row in enumerate(raw_data):
                    if idx == 0: continue
                    if row[1] == selected_coach_name:
                         label = f"Row {idx+1} | {row[0]} | {row[3]} (${row[4]})"
                         delete_options.append((idx + 1, label))
                
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
# 🔵 頁面 2: 管理者後台
# ===============================
elif page == "🔵 管理者後台":
    st.title("📊 管理者後台")
    
    if not current_user["is_admin"]:
        st.error("⛔ 抱歉，您沒有管理員權限。")
    else:
        st.info("💡 提示：若要新增教練或修改薪資費率，請直接在 GitHub 修改 `app.py` 程式碼頂端的設定區。")
        
        sheet = connect_to_sheet()
        if sheet:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if not df.empty:
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.sort_values(by="日期", ascending=False)
                
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

