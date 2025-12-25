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

# 薪資費率
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 250},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 250},
}

DEFAULT_EXTRAS = {"鞋子": 500, "護具": 100}

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
# 📱 介面開始 (單頁式版型)
# ===============================

st.set_page_config(page_title="薪資系統", page_icon="💰", layout="wide") # 加回 wide 模式
st.title("💰 溜冰教學薪資系統 (雲端版)")

# --- 側邊欄：登入 ---
st.sidebar.header("👤 使用者登入")
coach_names = [c["name"] for c in DEFAULT_COACHES]
selected_coach_name = st.sidebar.selectbox("請選擇你的名字", coach_names)
current_user = next((c for c in DEFAULT_COACHES if c["name"] == selected_coach_name), None)

if current_user:
    st.sidebar.success(f"嗨，{selected_coach_name} ({current_user['role']})")

# ===============================
# 📝 上半部：新增紀錄區域
# ===============================
st.subheader("📝 新增薪資紀錄")

# 排版：左邊選日期，右邊選項目
c1, c2 = st.columns(2)
with c1:
    date_input = st.date_input("日期", get_tw_time())
with c2:
    my_rates = DEFAULT_RATES.get(current_user["role"], {})
    item_options = list(my_rates.keys()) + list(DEFAULT_EXTRAS.keys()) + ["其他"]
    selected_item = st.selectbox("項目", item_options)

# 排版：左邊金額，右邊備註
c3, c4 = st.columns(2)
with c3:
    default_amount = 0
    if selected_item in my_rates:
        default_amount = my_rates[selected_item]
    elif selected_item in DEFAULT_EXTRAS:
        default_amount = DEFAULT_EXTRAS[selected_item]
    amount_input = st.number_input("金額", value=default_amount, step=10)
with c4:
    note_input = st.text_input("備註 (選填)")

# 送出按鈕 (設為全寬)
if st.button("確認送出紀錄", type="primary", use_container_width=True):
    sheet = connect_to_sheet()
    if sheet:
        init_sheet_header(sheet)
        record = [
            str(date_input),
            current_user["name"],
            current_user["role"],
            selected_item,
            amount_input,
            note_input,
            str(get_tw_time().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        with st.spinner("寫入中..."):
            sheet.append_row(record)
        st.success(f"✅ 已儲存！ ${amount_input}")
        time.sleep(1)
        st.rerun()

st.markdown("---") # 分隔線

# ===============================
# 📊 下半部：詳細流水帳區域
# ===============================
st.subheader("📊 詳細流水帳")

sheet = connect_to_sheet()
if sheet:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values(by="日期", ascending=False)

        # 篩選工具列
        f1, f2, f3 = st.columns(3)
        with f1:
            years = sorted(df["日期"].dt.year.unique(), reverse=True)
            sel_year = st.selectbox("年份", years)
        with f2:
            months = sorted(df[df["日期"].dt.year == sel_year]["日期"].dt.month.unique())
            sel_month = st.selectbox("月份", months, index=len(months)-1 if months else 0)
        with f3:
            if current_user["is_admin"]:
                coach_filter = st.selectbox("篩選教練", ["全部顯示"] + coach_names)
            else:
                coach_filter = current_user["name"]
                st.write(f"篩選教練: {coach_filter}")

        # 資料過濾邏輯
        mask = (df["日期"].dt.year == sel_year) & (df["日期"].dt.month == sel_month)
        if coach_filter != "全部顯示":
            mask = mask & (df["教練姓名"] == coach_filter)
        
        filtered_df = df[mask]

        # 顯示總金額大字
        st.metric("本月總金額", f"${filtered_df['金額'].sum():,}")
        
        # 顯示表格
        st.dataframe(filtered_df, use_container_width=True)

        # 刪除區塊
        with st.expander("🗑️ 刪除紀錄 (小心使用)"):
            raw_data = sheet.get_all_values()
            delete_options = []
            for idx, row in enumerate(raw_data):
                if idx == 0: continue
                try:
                    r_date = datetime.strptime(row[0], "%Y-%m-%d")
                    if r_date.year == sel_year and r_date.month == sel_month:
                         if coach_filter == "全部顯示" or row[1] == coach_filter:
                            # 顯示格式：行號 | 日期 | 名字 | 金額
                            label = f"Row {idx+1} | {row[0]} | {row[1]} | ${row[4]}"
                            delete_options.append((idx + 1, label))
                except:
                    pass
            
            if delete_options:
                target = st.selectbox("選擇要刪除哪一筆", delete_options, format_func=lambda x: x[1])
                if st.button("🚨 確認刪除"):
                    try:
                        sheet.delete_rows(target[0]) # 已經修復的指令
                        st.success("刪除成功")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"錯誤：{e}")
            else:
                st.info("本月無可刪除資料")
    else:
        st.info("目前沒有資料")
