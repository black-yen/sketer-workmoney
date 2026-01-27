import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 系統設定 (原本的 JSON 設定改成寫在這裡，才不會消失)
# ==========================================

TW_TZ = timezone(timedelta(hours=8))
SHEET_NAME = "salary_database"

# 1. 費率設定
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 240},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500, "速樁": 600},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 300, "速樁": 300}
}

# 2. 額外加給
DEFAULT_EXTRAS = {"鞋子": 500, "護具": 100}

# 3. 教練名單 (要新增人名，請直接複製一行修改)
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True},
    {"name": "莊雁貽", "role": "主教", "is_admin": False},
    {"name": "黃奕硯", "role": "實習主教", "is_admin": False},
    {"name": "劉恩新", "role": "實習主教", "is_admin": False},
    {"name": "周承燁", "role": "實習主教", "is_admin": False},
    {"name": "蔡孟澔", "role": "實習主教", "is_admin": False},
    {"name": "藍奕翔", "role": "實習主教", "is_admin": False},
    {"name": "蔡宜蓁", "role": "助教", "is_admin": False},
    {"name": "劉恩加", "role": "助教", "is_admin": False},
]

# ==========================================
# 🔧 Google Cloud 連線工具 (核心心臟)
# ==========================================

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
    """確保雲端試算表有標題"""
    try:
        if not sheet.row_values(1):
            # 依照你原本的欄位順序
            header = ["日期", "年份", "月份", "姓名", "職位", "班級", "人數", "基本薪資", "跟課主教", "助教扣款", "鞋子", "護具", "裝備獎金", "總金額", "建檔時間"]
            sheet.append_row(header)
    except:
        pass

# ==========================================
# 🖥️ 主程式 (UI 介面完全復刻你的版本)
# ==========================================

st.set_page_config(page_title="薪資系統 3.0 (雲端版)", page_icon="🛼", layout="wide")

# --- 側邊欄 ---
with st.sidebar:
    st.header("👤 使用者登入")
    
    # 建立選單 (固定括號顯示)
    coach_names = [c["name"] for c in DEFAULT_COACHES]
    
    # 記憶上一次選擇的使用者
    idx = 0
    if 'last_selected_user' in st.session_state and st.session_state['last_selected_user'] in coach_names:
        idx = coach_names.index(st.session_state['last_selected_user'])
        
    selected_name = st.selectbox("請選擇您的名字", coach_names, index=idx)
    st.session_state['last_selected_user'] = selected_name
    
    # 抓取資料
    current_user_data = next((c for c in DEFAULT_COACHES if c["name"] == selected_name), None)
    
    # 顯示固定括號 (遵照你的要求)
    if current_user_data:
        st.success(f"目前身份：**{selected_name} ({current_user_data['role']})**")
        
    st.divider()
    
    # 權限切換
    app_mode = "👨‍🏫 教練打卡區"
    if current_user_data and current_user_data.get('is_admin', False):
        st.info("識別為管理者")
        app_mode = st.radio("前往", ["👨‍🏫 教練打卡區", "📊 管理者後台"])

# ==========================================
# 🟢 教練打卡區 (邏輯完全移植)
# ==========================================
if app_mode == "👨‍🏫 教練打卡區":
    st.title(f"👋 你好，{selected_name}")
    
    # 1. 數據卡 (改為從雲端讀取)
    today_income = 0
    month_income = 0
    
    sheet = connect_to_sheet()
    my_df = pd.DataFrame() # 預設為空
    
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty:
                df["日期"] = pd.to_datetime(df["日期"])
                today_date = get_tw_time().date()
                
                # 篩選我的資料
                my_df = df[df["姓名"] == selected_name].copy()
                
                # 計算今日
                today_rows = my_df[my_df["日期"].dt.date == today_date]
                today_income = today_rows["總金額"].sum()
                
                # 計算本月
                month_rows = my_df[(my_df["日期"].dt.year == today_date.year) & (my_df["日期"].dt.month == today_date.month)]
                month_income = month_rows["總金額"].sum()
        except:
            pass
            
    c1, c2 = st.columns(2)
    c1.metric("💰 今日薪資", f"${int(today_income):,}")
    c2.metric("📅 本月累積", f"${int(month_income):,}")
    
    st.divider()

    # 2. 打卡輸入區 (完全復刻你的 Columns 版型)
    st.subheader("📝 新增紀錄")
    
    d1, d2 = st.columns(2)
    r_date = d1.date_input("日期", get_tw_time())
    
    # 職位選擇 (預設選你的，但可改)
    role_options = list(DEFAULT_RATES.keys())
    default_role_index = 0
    if current_user_data and current_user_data["role"] in role_options:
        default_role_index = role_options.index(current_user_data["role"])
    
    r_role = d2.selectbox("職位", role_options, index=default_role_index)
    
    # 班級連動
    class_dict = DEFAULT_RATES.get(r_role, {})
    class_keys = list(class_dict.keys())
    class_keys.append("📝 其他 (自填)")
    
    d3, d4 = st.columns(2)
    r_class_select = d3.selectbox(
        "班級 / 項目", 
        class_keys, 
        format_func=lambda x: f"{x} (${class_dict[x]})" if x in class_dict else x
    )
    
    # 邏輯計算
    final_class_name = r_class_select
    calc_base = 0
    count_val = 0
    target_head_coach = "-" 
    
    # 處理「其他」
    if r_class_select == "📝 其他 (自填)":
        custom_note = d4.text_input("輸入事項說明", placeholder="例：帶隊比賽...")
        custom_price = d4.number_input("輸入金額", min_value=0)
        final_class_name = custom_note if custom_note else "其他 (未填說明)"
        calc_base = custom_price
        count_val = 1
        
        # 讓非主教也能選跟課主教
        if "主教" not in r_role:
             all_coaches = [c["name"] for c in DEFAULT_COACHES]
             target_head_coach = d4.selectbox("👀 跟課主教", ["-"] + all_coaches)
             
    else:
        # 處理標準班級
        unit_price = class_dict[r_class_select]
        
        if "主教" in r_role:
            count_val = d4.number_input("人數", min_value=0)
            calc_base = count_val * unit_price
            if count_val > 0:
                st.info(f"試算：${unit_price} x {count_val}人 = ${calc_base}")
        else:
            d4.info(f"固定薪資：${unit_price}")
            calc_base = unit_price
            count_val = 1
            
            st.markdown("---")
            all_coaches = [c["name"] for c in DEFAULT_COACHES]
            # 排除自己
            coach_names_only = [c for c in all_coaches if c != selected_name]
            target_head_coach = d4.selectbox("👀 跟課主教 (協助哪位主教?)", ["-"] + coach_names_only)
    
    st.write("🛍️ 裝備銷售")
    d5, d6 = st.columns(2)
    shoes = d5.number_input(f"鞋子 (${DEFAULT_EXTRAS.get('鞋子', 0)})", min_value=0)
    gear = d6.number_input(f"護具 (${DEFAULT_EXTRAS.get('護具', 0)})", min_value=0)
    
    st.markdown("---")
    
    # --- 送出按鈕 (寫入雲端) ---
    if st.button("✅ 確認送出紀錄", type="primary", use_container_width=True):
        if sheet:
            init_sheet_header(sheet)
            
            bonus = (shoes * DEFAULT_EXTRAS.get("鞋子",0)) + (gear * DEFAULT_EXTRAS.get("護具",0))
            total = calc_base + bonus
            timestamp = str(get_tw_time().strftime("%Y-%m-%d %H:%M:%S"))
            
            # 1. 寫入自己的紀錄
            # 欄位順序: ["日期", "年份", "月份", "姓名", "職位", "班級", "人數", "基本薪資", "跟課主教", "助教扣款", "鞋子", "護具", "裝備獎金", "總金額", "建檔時間"]
            row_data = [
                str(r_date), r_date.year, r_date.month,
                selected_name, r_role, final_class_name,
                count_val, calc_base, target_head_coach, 0, # 助教扣款為0
                shoes, gear, bonus, total, timestamp
            ]
            
            with st.spinner("寫入雲端中..."):
                sheet.append_row(row_data)
                
                # 2. 自動扣款功能 (如果有點跟課主教)
                if target_head_coach != "-" and target_head_coach is not None:
                    # 幫主教寫入一筆負數資料
                    deduct_row = [
                        str(r_date), r_date.year, r_date.month,
                        target_head_coach, "系統自動扣款", f"扣除助教費 ({selected_name})",
                        0, -calc_base, "-", 0, # 基本薪資是負的
                        0, 0, 0, -calc_base, timestamp + "_deduct"
                    ]
                    sheet.append_row(deduct_row)
                    st.toast(f"已自動從 {target_head_coach} 的薪資扣除 ${calc_base}")

            st.success("紀錄已儲存！")
            time.sleep(1)
            st.rerun()

    # 3. 歷史紀錄 (雲端版)
    st.markdown("---")
    with st.expander("📂 查看與管理我的近期紀錄 (近 60 天)", expanded=False):
        if not my_df.empty:
            # 製作顯示名稱給刪除選單用
            my_df = my_df.sort_values("日期", ascending=False)
            
            # --- 刪除功能 ---
            st.write("### 🗑️ 刪除紀錄")
            
            # 重新抓取原始資料來對應行號 (避免刪錯)
            raw_data = sheet.get_all_values()
            delete_options = []
            
            # 建立刪除選單
            for idx, row in enumerate(raw_data):
                if idx == 0: continue
                # 只能刪除自己的
                if row[3] == selected_name: 
                     # 顯示：日期 | 班級 | 金額
                     label = f"Row {idx+1} | {row[0]} | {row[5]} (${row[13]})"
                     delete_options.append((idx + 1, label))
            
            # 只顯示最近 20 筆供刪除
            delete_options.reverse()
            
            target_del = st.selectbox("選擇要刪除的紀錄：", delete_options, format_func=lambda x: x[1]) if delete_options else None
            
            if target_del:
                if st.button("🗑️ 確認刪除", type="primary"):
                    try:
                        sheet.delete_rows(target_del[0])
                        st.success("刪除成功！")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗：{e}")

            st.divider()
            st.write("### 📋 詳細列表")
            display_cols = ["日期", "班級", "總金額", "職位", "備註"] # 簡化顯示
            st.dataframe(my_df, use_container_width=True)
            
        else:
            st.info("尚無資料")

# ==========================================
# 📊 管理者後台 (UI 復刻)
# ==========================================
elif app_mode == "📊 管理者後台":
    st.title("📊 管理者中心")
    tab1, tab2 = st.tabs(["💰 薪資報表與管理", "⚙️ 系統與人員設定"])
    
    with tab1:
        sheet = connect_to_sheet()
        if sheet:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if df.empty:
                st.info("暫無資料")
            else:
                c_y, c_m, c_p = st.columns(3)
                df["年份"] = pd.to_numeric(df["年份"])
                df["月份"] = pd.to_numeric(df["月份"])
                
                years = sorted(df["年份"].unique(), reverse=True)
                sy = c_y.selectbox("年份", years)
                
                months = sorted(df[df["年份"] == sy]["月份"].unique())
                sm = c_m.selectbox("月份", months)
                
                target_coach = c_p.selectbox("篩選教練", ["全部顯示"] + list(df["姓名"].unique()))
                
                mask = (df["年份"] == sy) & (df["月份"] == sm)
                if target_coach != "全部顯示":
                    mask = mask & (df["姓名"] == target_coach)
                
                m_df = df[mask]
                st.divider()
                
                if m_df.empty:
                    st.warning("查無資料")
                else:
                    st.subheader(f"{sy}年 {sm}月 - 薪資表")
                    
                    # 統計表
                    summary = m_df.groupby("姓名").agg({
                        "總金額": "sum", "班級": "count", "人數": "sum", "鞋子": "sum", "護具": "sum"
                    }).reset_index().rename(columns={
                        "班級": "總堂數", 
                        "人數": "總學生數", 
                        "總金額": "應付薪資",
                        "鞋子": "賣出鞋子",
                        "護具": "賣出護具"
                    })
                    
                    st.dataframe(summary, use_container_width=True)
                    st.markdown("---")
                    
                    # 詳細流水帳
                    st.subheader("📋 詳細流水帳")
                    st.dataframe(m_df, use_container_width=True)

    with tab2:
        st.header("⚙️ 系統設定")
        st.warning("⚠️ 注意：雲端版請勿在此修改設定")
        st.info("""
        因為 Streamlit Cloud 會定時重置，直接在網頁上修改設定 (例如新增教練) 會導致隔天資料消失。
        
        **正確修改方式：**
        請去 GitHub 修改 `app.py` 最上方的 `DEFAULT_COACHES` 或 `DEFAULT_RATES` 區塊，
        修改完儲存 (Commit)，網頁就會永久更新了！
        """)
        
        # 顯示目前的設定給你看，方便你複製
        st.subheader("目前生效的名單 (唯讀)")
        st.json(DEFAULT_COACHES)
        st.subheader("目前生效的費率 (唯讀)")
        st.json(DEFAULT_RATES)






