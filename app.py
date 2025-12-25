import streamlit as st
import pandas as pd
import os
import glob
import json
import time
from datetime import datetime, date, timedelta, timezone

# ==========================================
# ⚙️ 系統核心設定
# ==========================================

TW_TZ = timezone(timedelta(hours=8))
DB_FILE = "salary_database.csv"
CONFIG_FILE = "system_config_v2.json"

# 預設費率
DEFAULT_RATES = {
    "主教": {"基礎": 180, "進階": 195, "高級": 240, "速樁": 240},
    "實習主教": {"基礎": 140, "進階": 155, "高級": 190, "速樁": 190},
    "助教": {"基礎": 400, "進階": 400, "高級": 400, "進高合": 500, "速樁": 600},
    "實習助教": {"基礎": 200, "進階": 200, "高級": 200, "進高合": 300, "速樁": 300}
}
DEFAULT_EXTRAS = {"鞋子": 500, "護具": 100}

# 預設只有莊祥霖一人
DEFAULT_COACHES = [
    {"name": "莊祥霖", "role": "主教", "is_admin": True}
]

# ==========================================
# 🔧 工具函數
# ==========================================

def get_tw_time():
    return datetime.now(TW_TZ)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("coaches", DEFAULT_COACHES), config.get("rates", DEFAULT_RATES), config.get("extras", DEFAULT_EXTRAS)
        except:
            pass
    return DEFAULT_COACHES, DEFAULT_RATES, DEFAULT_EXTRAS

def save_config(coaches, rates, extras):
    config = {"coaches": coaches, "rates": rates, "extras": extras}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def update_coach_role(coach_name, new_role):
    coaches, rates, extras = load_config()
    updated = False
    for c in coaches:
        if c["name"] == coach_name and c["role"] != new_role:
            c["role"] = new_role
            updated = True
            break
    if updated:
        save_config(coaches, rates, extras)
        return True
    return False

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        # 補齊所有欄位
        if "跟課主教" not in df.columns: df["跟課主教"] = ""
        if "助教扣款" not in df.columns: df["助教扣款"] = 0
        if "護具" not in df.columns: df["護具"] = 0 
        if "建檔時間" in df.columns:
            df["建檔時間"] = df["建檔時間"].astype(str)
        return df
    return pd.DataFrame(columns=[
        "日期", "年份", "月份", "姓名", "職位", "班級", 
        "人數", "基本薪資", "跟課主教", "助教扣款",
        "鞋子", "護具", "裝備獎金", "總金額", "建檔時間"
    ])

def save_to_db(record):
    df = load_db()
    new_row = pd.DataFrame([record])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def delete_records(timestamp_list):
    df = load_db()
    if df.empty: return
    df_new = df[~df["建檔時間"].isin(timestamp_list)]
    df_new.to_csv(DB_FILE, index=False)

# ==========================================
# 🖥️ 主程式
# ==========================================

# 🔥 這裡遵照指示，版本號維持 3.0
st.set_page_config(page_title="薪資系統 3.0", page_icon="🛼", layout="wide")

COACHES_LIST, RATES, EXTRAS = load_config()

# --- 側邊欄 ---
with st.sidebar:
    st.header("👤 使用者登入")
    coach_map = {f"{c['name']} ({c['role']})": c for c in COACHES_LIST}
    
    idx = 0
    if 'last_selected_user' in st.session_state and st.session_state['last_selected_user'] in coach_map:
        idx = list(coach_map.keys()).index(st.session_state['last_selected_user'])

    selected_label = st.selectbox("請選擇您的名字", list(coach_map.keys()), index=idx)
    st.session_state['last_selected_user'] = selected_label
    
    current_user_data = coach_map[selected_label]
    current_name = current_user_data['name']
    current_role = current_user_data['role']
    is_admin = current_user_data.get('is_admin', False)

    st.divider()
    app_mode = "👨‍🏫 教練打卡區"
    if is_admin:
        st.success("識別為管理者")
        app_mode = st.radio("前往", ["👨‍🏫 教練打卡區", "📊 管理者後台"])
    else:
        st.info(f"預設職位：{current_role}")

# ==========================================
# 🟢 教練打卡區
# ==========================================
if app_mode == "👨‍🏫 教練打卡區":
    st.title(f"👋 你好，{current_name}")
    
    # 1. 數據卡
    df = load_db()
    today_date = get_tw_time().date()
    today_income = 0
    month_income = 0
    
    if not df.empty:
        df['日期'] = pd.to_datetime(df['日期']).dt.date
        my_df = df[df["姓名"] == current_name]
        today_income = my_df[my_df["日期"] == today_date]["總金額"].sum()
        month_income = my_df[
            (pd.to_datetime(my_df["日期"]).dt.year == today_date.year) & 
            (pd.to_datetime(my_df["日期"]).dt.month == today_date.month)
        ]["總金額"].sum()
        
    c1, c2 = st.columns(2)
    c1.metric("💰 今日薪資", f"${int(today_income):,}")
    c2.metric("📅 本月累積", f"${int(month_income):,}")
    
    st.divider()

    # 2. 打卡輸入區
    st.subheader("📝 新增紀錄")
    
    d1, d2 = st.columns(2)
    r_date = d1.date_input("日期", today_date)
    
    role_options = list(RATES.keys())
    default_role_index = role_options.index(current_role) if current_role in role_options else 0
    r_role = d2.selectbox("職位", role_options, index=default_role_index)
    
    class_dict = RATES.get(r_role, {})
    class_keys = list(class_dict.keys())
    class_keys.append("📝 其他 (自填)")
    
    d3, d4 = st.columns(2)
    r_class_select = d3.selectbox(
        "班級 / 項目", 
        class_keys, 
        format_func=lambda x: f"{x} (${class_dict[x]})" if x in class_dict else x
    )
    
    final_class_name = r_class_select
    calc_base = 0
    count_val = 0
    target_head_coach = "-" 
    
    if r_class_select == "📝 其他 (自填)":
        custom_note = d4.text_input("輸入事項說明", placeholder="例：帶隊比賽...")
        custom_price = d4.number_input("輸入金額", min_value=0)
        final_class_name = custom_note if custom_note else "其他 (未填說明)"
        calc_base = custom_price
        count_val = 1
        
        if "主教" not in r_role:
             all_coaches = [c["name"] for c in COACHES_LIST]
             target_head_coach = d4.selectbox("👀 跟課主教", ["-"] + all_coaches)
             
    else:
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
            all_coaches = [c["name"] for c in COACHES_LIST]
            # 排除自己
            coach_names_only = [c for c in all_coaches if c != current_name]
            target_head_coach = d4.selectbox("👀 跟課主教 (協助哪位主教?)", ["-"] + coach_names_only)
    
    st.write("🛍️ 裝備銷售")
    d5, d6 = st.columns(2)
    shoes = d5.number_input(f"鞋子 (${EXTRAS.get('鞋子', 0)})", min_value=0)
    gear = d6.number_input(f"護具 (${EXTRAS.get('護具', 0)})", min_value=0)
    
    st.markdown("---")
    if st.button("✅ 確認送出紀錄", type="primary", use_container_width=True):
        bonus = (shoes * EXTRAS.get("鞋子",0)) + (gear * EXTRAS.get("護具",0))
        total = calc_base + bonus
        
        rec = {
            "日期": str(r_date), "年份": r_date.year, "月份": r_date.month,
            "姓名": current_name, "職位": r_role, 
            "班級": final_class_name,
            "人數": count_val, 
            "基本薪資": calc_base, 
            "跟課主教": target_head_coach,
            "鞋子": shoes, "護具": gear,
            "裝備獎金": bonus, "總金額": total,
            "建檔時間": str(get_tw_time())
        }
        save_to_db(rec)
        
        # 自動扣款
        if target_head_coach != "-" and target_head_coach is not None:
            deduct_rec = {
                "日期": str(r_date), "年份": r_date.year, "月份": r_date.month,
                "姓名": target_head_coach,
                "職位": "系統自動扣款", 
                "班級": f"扣除助教費 ({current_name})", 
                "人數": 0, 
                "基本薪資": -calc_base, 
                "跟課主教": "-",
                "鞋子": 0, "護具": 0, "裝備獎金": 0, 
                "總金額": -calc_base, 
                "建檔時間": str(get_tw_time()) + "_deduct"
            }
            save_to_db(deduct_rec)
            st.toast(f"已自動從 {target_head_coach} 的薪資扣除 ${calc_base}")

        update_coach_role(current_name, r_role)
        st.success("紀錄已儲存！")
        time.sleep(1)
        st.rerun()

    # 3. 歷史
    st.markdown("---")
    with st.expander("📂 查看與管理我的近期紀錄 (近 60 天)", expanded=False):
        if not df.empty:
            sixty_days_ago = today_date - timedelta(days=60)
            my_recent = df[(df["姓名"] == current_name) & (df["日期"] >= sixty_days_ago)].sort_values("日期", ascending=False)
            
            if not my_recent.empty:
                st.write("### 🗑️ 刪除紀錄")
                my_recent["顯示名稱"] = my_recent.apply(
                    lambda x: f"【{x['日期']}】 {x['班級']} - ${x['總金額']}", axis=1
                )
                records_to_delete = st.multiselect(
                    "選擇要刪除的紀錄：",
                    options=my_recent["建檔時間"].tolist(),
                    format_func=lambda x: my_recent[my_recent["建檔時間"] == x]["顯示名稱"].values[0]
                )
                if records_to_delete:
                    if st.button("🗑️ 確認刪除", type="primary"):
                        delete_records(records_to_delete)
                        st.success("刪除成功！")
                        st.rerun()
                
                st.divider()
                st.write("### 📋 詳細列表")
                cols_to_hide = ["年份", "月份", "建檔時間", "顯示名稱"]
                st.dataframe(my_recent.drop(columns=cols_to_hide, errors='ignore'), use_container_width=True)
            else:
                st.info("無近期紀錄")
        else:
            st.info("尚無資料")

# ==========================================
# 📊 管理者後台
# ==========================================
elif app_mode == "📊 管理者後台":
    st.title("📊 管理者中心")
    tab1, tab2 = st.tabs(["💰 薪資報表與管理", "⚙️ 系統與人員設定"])
    
    with tab1:
        df = load_db()
        if df.empty:
            st.info("暫無資料")
        else:
            c_y, c_m, c_p = st.columns(3)
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
                
                col_d, col_del = st.columns([2, 1])
                with col_d:
                    st.download_button("📥 下載完整報表 (CSV)", m_df.to_csv(index=False).encode('utf-8-sig'), f"salary_{sy}_{sm}.csv")
                
                st.markdown("---")
                st.subheader("📋 詳細流水帳")
                
                with st.expander("🗑️ 開啟刪除模式", expanded=False):
                    m_df["顯示名稱"] = m_df.apply(
                        lambda x: f"{x['姓名']} | {x['日期']} | {x['班級']} | ${x['總金額']}", axis=1
                    )
                    admin_del_list = st.multiselect(
                        "選擇要刪除的紀錄：",
                        options=m_df["建檔時間"].tolist(),
                        format_func=lambda x: m_df[m_df["建檔時間"] == x]["顯示名稱"].values[0]
                    )
                    if admin_del_list:
                        if st.button("🚨 確認刪除"):
                            delete_records(admin_del_list)
                            st.rerun()

                cols_to_hide = ["年份", "月份", "建檔時間", "顯示名稱"]
                st.dataframe(m_df.drop(columns=cols_to_hide, errors='ignore'), use_container_width=True)

    with tab2:
        st.header("⚙️ 人員與費率管理")
        st.subheader("1. 教練名單")
        df_coaches = pd.DataFrame(COACHES_LIST)
        edited_coaches = st.data_editor(
            df_coaches,
            column_config={
                "name": "姓名",
                "role": st.column_config.SelectboxColumn("預設職位", options=list(RATES.keys()), required=True),
                "is_admin": st.column_config.CheckboxColumn("管理者權限")
            },
            num_rows="dynamic", use_container_width=True
        )
        st.subheader("2. 課程費率")
        flat_rates = [{"職位": r, "班級": c, "金額": p} for r, cls in RATES.items() for c, p in cls.items()]
        edited_rates = st.data_editor(pd.DataFrame(flat_rates), num_rows="dynamic", use_container_width=True)
        st.subheader("3. 裝備價格")
        edited_extras = st.data_editor(pd.DataFrame(list(EXTRAS.items()), columns=["項目", "金額"]), use_container_width=True)
        
        if st.button("💾 儲存設定", type="primary"):
            new_coaches = [c for c in edited_coaches.to_dict("records") if c["name"] and str(c["name"]).strip()]
            new_rates = {r: {} for r in ["主教", "實習主教", "助教", "實習助教"]}
            for _, row in edited_rates.iterrows():
                if row["職位"] in new_rates: new_rates[row["職位"]][row["班級"]] = row["金額"]
            new_extras = {row["項目"]: row["金額"] for _, row in edited_extras.iterrows()}
            save_config(new_coaches, new_rates, new_extras)
            st.success("設定已儲存！")
            st.rerun()