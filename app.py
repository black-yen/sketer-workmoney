import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime, timedelta, timezone

# ===============================
# ⚙️ 系統核心設定 (要改名單或價錢改這裡)
# ===============================

# 設定台灣時區
TW_TZ = timezone(timedelta(hours=8))

# 你的 Google Sheet 檔名 (必須跟雲端硬碟的一模一樣)
SHEET_NAME = "salary_database"

# 1. 薪資費率設定
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 250},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 250},
}

# 2. 額外加給設定
DEFAULT_EXTRAS = {"鞋子": 500, "護具": 100}

# 3. 教練名單 (若要新增教練，請複製一行修改名字)
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True},
    {"name": "測試教練", "role": "助教", "is_admin": False},
]

# ===============================
# 🔧 Google Sheets 連線工具
# ===============================

def get_tw_time():
    """取得台灣目前的日期時間"""
    return datetime.now(TW_TZ)

def connect_to_sheet():
    """連線到 Google Sheets"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # 從 Streamlit Secrets 讀取金鑰
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 開啟試算表
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"連線失敗！請檢查 Secrets 設定或試算表名稱。錯誤訊息: {e}")
        return None

def init_sheet_header(sheet):
    """初始化試算表標題 (如果第一次用的話)"""
    try:
        # 檢查第一列有沒有標題，沒有的話加上去
        if not sheet.row_values(1):
            header = ["日期", "教練姓名", "職位", "項目", "金額", "備註", "記錄時間"]
            sheet.append_row(header)
    except:
        pass

# ===============================
# 📱 介面與邏輯
# ===============================

st.set_page_config(page_title="薪資系統 (雲端版)", page_icon="💰")
st.title("💰 溜冰教學薪資系統 v3.4 (雲端版)")

# --- 側邊欄：選擇使用者 ---
st.sidebar.header("👤 使用者登入")
coach_names = [c["name"] for c in DEFAULT_COACHES]
selected_coach_name = st.sidebar.selectbox("請選擇你的名字", coach_names)

# 找到目前登入者的資料
current_user = next((c for c in DEFAULT_COACHES if c["name"] == selected_coach_name), None)

if current_user:
    st.sidebar.success(f"嗨，{selected_coach_name} ({current_user['role']})")
    
    # 顯示目前費率 (唯讀)
    with st.sidebar.expander("查看我的薪資費率"):
        my_rates = DEFAULT_RATES.get(current_user["role"], {})
        st.write(my_rates)

# --- 建立頁籤 ---
tab1, tab2 = st.tabs(["📝 新增紀錄", "📊 詳細流水帳"])

# --- TAB 1: 新增紀錄 ---
with tab1:
    st.subheader("新增一筆薪資")
    
    # 1. 選擇日期
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.date_input("日期", get_tw_time())
    
    # 2. 選擇項目 (根據職位顯示不同選項)
    my_rates = DEFAULT_RATES.get(current_user["role"], {})
    item_options = list(my_rates.keys()) + list(DEFAULT_EXTRAS.keys()) + ["其他"]
    
    selected_item = st.selectbox("項目", item_options)
    
    # 3. 自動計算金額
    default_amount = 0
    if selected_item in my_rates:
        default_amount = my_rates[selected_item]
    elif selected_item in DEFAULT_EXTRAS:
        default_amount = DEFAULT_EXTRAS[selected_item]
        
    amount_input = st.number_input("金額", value=default_amount, step=10)
    note_input = st.text_input("備註 (選填)")
    
    # 4. 送出按鈕
    if st.button("確認送出紀錄", type="primary"):
        sheet = connect_to_sheet()
        if sheet:
            init_sheet_header(sheet)  # 確保有標題
            
            # 準備資料
            record = [
                str(date_input),
                current_user["name"],
                current_user["role"],
                selected_item,
                amount_input,
                note_input,
                str(get_tw_time().strftime("%Y-%m-%d %H:%M:%S"))
            ]
            
            # 寫入 Google Sheet
            with st.spinner("正在寫入雲端..."):
                sheet.append_row(record)
            
            st.success(f"✅ 成功儲存！金額：{amount_input}")
            # 稍微延遲後重新整理頁面，讓資料馬上顯示
            import time
            time.sleep(1)
            st.rerun()

# --- TAB 2: 查看與刪除 ---
with tab2:
    st.subheader("詳細流水帳")
    
    sheet = connect_to_sheet()
    if sheet:
        # 讀取所有資料
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            # 轉換日期格式以便排序
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.sort_values(by="日期", ascending=False) # 新的日期在上面
            
            # --- 篩選器 ---
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                # 年份篩選
                years = sorted(df["日期"].dt.year.unique(), reverse=True)
                sel_year = st.selectbox("年份", years)
            with col_f2:
                # 月份篩選
                months = sorted(df[df["日期"].dt.year == sel_year]["日期"].dt.month.unique())
                sel_month = st.selectbox("月份", months, index=len(months)-1 if months else 0)
            with col_f3:
                # 教練篩選 (如果是管理員可以看到全部，不然只能看自己)
                if current_user["is_admin"]:
                    coach_filter = st.selectbox("篩選教練", ["全部顯示"] + coach_names)
                else:
                    coach_filter = current_user["name"]
                    st.write(f"篩選教練: {coach_filter}")

            # 執行篩選
            mask = (df["日期"].dt.year == sel_year) & (df["日期"].dt.month == sel_month)
            if coach_filter != "全部顯示":
                mask = mask & (df["教練姓名"] == coach_filter)
            
            filtered_df = df[mask]
            
            # 顯示統計
            total_money = filtered_df["金額"].sum()
            st.metric("本月總薪資", f"${total_money:,}")
            
            # 顯示表格
            st.dataframe(filtered_df, use_container_width=True)
            
            # --- 刪除功能 ---
            st.divider()
            with st.expander("🗑️ 開啟刪除模式"):
                st.warning("注意：刪除後無法復原！")
                
                # 製作選單：顯示 日期 | 姓名 | 金額 (方便辨識)
                # 這裡要保留原始的 index 以便回推 Google Sheet 的行數
                # Google Sheet 第一列是標題，所以資料從第 2 列開始
                # gspread 的行數是從 1 開始算
                
                # 為了準確刪除，我們重新抓一次原始資料不排序，並加上行號
                raw_data = sheet.get_all_values() # 這是 list of lists
                # raw_data[0] 是標題, raw_data[1] 是第一筆資料(行號2)
                
                delete_options = []
                for idx, row in enumerate(raw_data):
                    if idx == 0: continue # 跳過標題
                    # 格式: 行號2 | 2025-12-25 | 莊祥霖 | $180
                    label = f"Row {idx+1} | {row[0]} | {row[1]} | ${row[4]} | {row[3]}"
                    
                    # 只能刪除這個月份且是這個人的 (避免誤刪)
                    try:
                        row_date = datetime.strptime(row[0], "%Y-%m-%d")
                        if row_date.year == sel_year and row_date.month == sel_month:
                             if coach_filter == "全部顯示" or row[1] == coach_filter:
                                delete_options.append((idx + 1, label))
                    except:
                        pass # 日期格式錯誤就不顯示
                
                # 下拉選單
                if delete_options:
                    target_row = st.selectbox("選擇要刪除的紀錄：", delete_options, format_func=lambda x: x[1])
                    
                    if st.button("🚨 確認刪除"):
                        row_index_to_delete = target_row[0]
                        try:
                            # ==========================================
                            # 🔥 這裡就是關鍵修復：用 delete_rows (加s)
                            # ==========================================
                            sheet.delete_rows(row_index_to_delete)
                            st.success("已刪除！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗：{e}")
                else:
                    st.info("目前條件下沒有可刪除的紀錄")
                
        else:
            st.info("目前還沒有任何資料，快去新增第一筆吧！")
