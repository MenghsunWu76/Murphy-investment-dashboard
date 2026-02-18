import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import os
from datetime import datetime
import pytz

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="全天候戰情室 (v10.0 雙引擎版)", layout="wide")

# --- 2. 歷史紀錄系統 (CSV) ---
HISTORY_FILE = "asset_history.csv"

def load_last_record():
    if not os.path.exists(HISTORY_FILE): return None
    try:
        df = pd.read_csv(HISTORY_FILE)
        return df.iloc[-1] if not df.empty else None
    except: return None

def save_record(data_dict):
    """儲存完整紀錄到 CSV"""
    new_df = pd.DataFrame([data_dict])
    if not os.path.exists(HISTORY_FILE):
        new_df.to_csv(HISTORY_FILE, index=False)
    else:
        try:
            existing_df = pd.read_csv(HISTORY_FILE)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_csv(HISTORY_FILE, index=False)
        except:
            new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

# --- 3. 自動抓取 ATH 引擎 ---
@st.cache_data(ttl=3600)
def get_ath_data():
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty: return float(hist['High'].max())
    except: pass
    return 32996.0

with st.spinner('正在連線計算歷史高點 (ATH)...'):
    ath_auto = get_ath_data()

# --- 4. 初始化 Session State ---
def init_state(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

init_state('manual_ath_check', False)
init_state('input_ath', ath_auto)
init_state('input_index', 31346.0)
init_state('input_pe', 22.0) # [New] P/E 預設值

# 資產預設值
defaults = {
    'p_675': 185.0, 's_675': 11000,
    'p_631': 466.7, 's_631': 331,
    'p_670': 157.95, 's_670': 616,
    'p_662': 102.25, 's_662': 25840,
    'p_713': 52.10, 's_713': 66000,
    'p_865': 47.51, 's_865': 10000
}
for k, v in defaults.items():
    init_state(k, v)

# --- 5. 側邊欄輸入區 ---
with st.sidebar:
    st.header("📝 監控數據輸入")
    
    # === 一鍵讀取功能 ===
    if st.button("📂 載入上次存檔數據", type="secondary", help="點擊後將自動填入上次儲存的股價、股數、P/E與大盤點數"):
        last_data = load_last_record()
        if last_data is not None:
            try:
                st.session_state['input_index'] = float(last_data['Current_Index'])
                st.session_state['input_ath'] = float(last_data['ATH'])
                st.session_state['manual_ath_check'] = True 
                
                # [New] 載入 P/E
                if 'PE_Ratio' in last_data:
                    st.session_state['input_pe'] = float(last_data['PE_Ratio'])

                for code in ['675', '631', '670', '662', '713', '865']:
                    st.session_state[f'p_{code}'] = float(last_data[f'P_00{code}'])
                    st.session_state[f's_{code}'] = int(last_data[f'S_00{code}'])
                
                st.toast("✅ 成功載入上次數據！", icon="📂")
                st.rerun()
            except Exception as e:
                st.error(f"載入失敗 (可能是舊存檔格式不符): {e}")
        else:
            st.warning("⚠️ 找不到存檔紀錄")

    # A. 市場數據 & ATH 修正
    with st.expander("0. 市場位階 (ATH 修正)", expanded=True):
        col_ath1, col_ath2 = st.columns([2, 1])
        with col_ath1: st.metric("自動抓取 ATH", f"{ath_auto:,.0f}")
        with col_ath2: use_manual_ath = st.checkbox("手動修正", key="manual_ath_check")
            
        if use_manual_ath:
            final_ath = st.number_input("輸入正確 ATH", step=10.0, format="%.0f", key="input_ath")
        else:
            final_ath = ath_auto
        
        st.markdown("---")
        current_index = st.number_input("今日大盤收盤點數", step=10.0, format="%.0f", key="input_index")
        
        mdd_pct = ((final_ath - current_index) / final_ath) * 100 if final_ath > 0 else 0.0
        st.info(f"📉 目前 MDD: {mdd_pct:.2f}% (ATH: {final_ath:,.0f})")
        
        # [New] P/E 估值修正建議
        st.caption("---")
        st.caption("💎 估值輔助 (Dual Engine)")
        pe_val = st.number_input("目前大盤本益比 (P/E)", step=0.1, key="input_pe", help="建議參考證交所或財經網站數據")
        
        pe_msg = ""
        pe_color = "off"
        if pe_val > 24.0:
            pe_msg = "⚠️ 昂貴 (建議基準降至 20%)"
            pe_color = "inverse"
        elif pe_val < 18.0:
            pe_msg = "💎 便宜 (建議基準升至 30%)"
            pe_color = "normal"
        else:
            pe_msg = "✅ 合理 (維持標準配置)"
            pe_color = "off"
            
        st.caption(f"訊號: {pe_msg}")

        base_exposure = st.number_input("目前基準曝險 % (Tier 1)", value=23.0, min_value=20.0, max_value=30.0, step=1.0)
        ratchet_level = int(base_exposure - 20)
        level_sign = "+" if ratchet_level > 0 else ""
        st.caption(f"ℹ️ 目前位階: {level_sign}{ratchet_level}")

    # B. 資產數據輸入
    with st.expander("1. 攻擊型資產 (正二)", expanded=True):
        c1, c2 = st.columns(2)
        p_675 = c1.number_input("00675L 價格", step=0.1, key="p_675")
        s_675 = c2.number_input("00675L 股數", step=1000, key="s_675")
        c3, c4 = st.columns(2)
        p_631 = c3.number_input("00631L 價格", step=0.1, key="p_631")
        s_631 = c4.number_input("00631L 股數", step=100, key="s_631")
        c5, c6 = st.columns(2)
        p_670 = c5.number_input("00670L 價格", step=0.1, key="p_670")
        s_670 = c6.number_input("00670L 股數", step=100, key="s_670")

    with st.expander("2. 核心資產 (美股)", expanded=True):
        c1, c2 = st.columns(2)
        p_662 = c1.number_input("00662 價格", step=0.1, key="p_662")
        s_662 = c2.number_input("00662 股數", step=100, key="s_662")

    with st.expander("3. 防禦資產 (現金流)", expanded=True):
        c1, c2 = st.columns(2)
        p_713 = c1.number_input("00713 價格", step=0.05, key="p_713")
        s_713 = c2.number_input("00713 股數", step=1000, key="s_713")

    with st.expander("4. 子彈庫 (國庫券/債券)", expanded=True):
        c1, c2 = st.columns(2)
        p_865 = c1.number_input("00865B 價格", step=0.01, key="p_865")
        s_865 = c2.number_input("00865B 股數", step=1000, key="s_865")

    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)

# --- 6. 運算引擎 ---
tier_0 = base_exposure
tier_1 = base_exposure + 5.0
tier_2 = base_exposure + 5.0
tier_3 = base_exposure + 10.0
tier_4 = base_exposure + 15.0
tier_5 = base_exposure + 20.0

ladder_data = [
    {"MDD區間": "< 5% (高位)", "目標曝險": tier_0, "位階": "Tier 1 (基準)"},
    {"MDD區間": "5% ~ 10%", "目標曝險": tier_1, "位階": "Tier 1.5 (警戒)"},
    {"MDD區間": "10% ~ 20%", "目標曝險": tier_2, "位階": "Tier 2 (初跌)"},
    {"MDD區間": "20% ~ 35%", "目標曝險": tier_3, "位階": "Tier 3 (主跌)"},
    {"MDD區間": "35% ~ 45%", "目標曝險": tier_4, "位階": "Tier 4 (恐慌)"},
    {"MDD區間": "> 45%", "目標曝險": tier_5, "位階": "Tier 5 (毀滅)"},
]

target_attack_ratio = tier_0
current_tier_index = 0

if mdd_pct < 5.0: target_attack_ratio, current_tier_index = tier_0, 0
elif mdd_pct < 10.0: target_attack_ratio, current_tier_index = tier_1, 1
elif mdd_pct < 20.0: target_attack_ratio, current_tier_index = tier_2, 2
elif mdd_pct < 35.0: target_attack_ratio, current_tier_index = tier_3, 3
elif mdd_pct < 45.0: target_attack_ratio, current_tier_index = tier_4, 4
else: target_attack_ratio, current_tier_index = tier_5, 5

current_tier_name = ladder_data[current_tier_index]["位階"]

v_675 = p_675 * s_675
v_631 = p_631 * s_631
v_670 = p_670 * s_670
v_662 = p_662 * s_662
v_713 = p_713 * s_713
v_865 = p_865 * s_865

val_attack = v_675 + v_631 + v_670
val_core = v_662
val_defense = v_713
val_ammo = v_865
total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

beta_weighted_sum = ((v_675*1.6) + (v_631*1.6) + (v_670*2.0) + (v_713*0.6) + (v_662*1.0) + (v_865*0.0))
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 7. 讀取與儲存歷史資料 ---
last_record = load_last_record()
diff_total = 0
if last_record is not None:
    diff_total = total_assets - last_record['Total_Assets']
    last_date_str = last_record['Date']
else:
    last_date_str = "無紀錄"

with st.sidebar:
    st.markdown("---")
    st.subheader("💾 紀錄管理")
    if st.button("💾 儲存今日資產紀錄 (含明細)", type="primary"):
        now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
        
        save_data = {
            "Date": now_str,
            "Total_Assets": total_assets,
            "Net_Assets": net_assets,
            "MDD": mdd_pct,
            "Current_Index": current_index,
            "ATH": final_ath,
            "PE_Ratio": pe_val, # [New] 儲存 P/E
            # 股價 (P)
            "P_00675": p_675, "P_00631": p_631, "P_00670": p_670,
            "P_00662": p_662, "P_00713": p_713, "P_00865": p_865,
            # 股數 (S)
            "S_00675": s_675, "S_00631": s_631, "S_00670": s_670,
            "S_00662": s_662, "S_00713": s_713, "S_00865": s_865
        }
        
        save_record(save_data)
        st.success(f"已儲存！時間: {now_str}")
        st.rerun()

    if last_record is not None:
        st.caption(f"上次存檔: {last_date_str}")

# --- 8. 主畫面 (分頁系統) ---

tab1, tab2 = st.tabs(["📊 戰情室 Dashboard", "📖 操作指南 & 指標解讀"])

# === 分頁 1: 戰情室 ===
with tab1:
    st.subheader("1. 動態戰略地圖")
    m1, m2, m3, m4 = st.columns([1, 1, 1, 2])
    m1.metric("📉 目前大盤 MDD", f"{mdd_pct:.2f}%", help=f"計算基準 ATH: {final_ath:,.0f}")
    
    gap_color = "off"
    if abs(gap) > threshold: gap_color = "inverse"
    m2.metric("⚡ 目前攻擊曝險", f"{current_attack_ratio:.2f}%", delta=f"{gap:+.2f}% (偏離)", delta_color=gap_color)
    m3.metric("🎯 當前目標曝險", f"{target_attack_ratio:.0f}%", help=f"位階: {current_tier_name}")
    
    df_ladder = pd.DataFrame(ladder_data)
    def highlight_current_row(row):
        color = '#ffcccc' if row['位階'] == current_tier_name else ''
        return [f'background-color: {color}' for _ in row]
    
    with m4:
        level_str = f"+{ratchet_level}" if ratchet_level > 0 else f"{ratchet_level}"
        st.caption(f"ℹ️ {level_str}位階動態曝險 (P/E: {pe_val})") # 顯示 P/E
        st.dataframe(df_ladder.style.apply(highlight_current_row, axis=1).format({"目標曝險": "{:.0f}%"}), hide_index=True, use_container_width=True)

    st.divider()

    st.subheader("2. 投資組合核心數據")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"${diff_total:,.0f} (vs 上次)", help=f"上次紀錄時間: {last_date_str}")
    col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}", delta="目標: 1.05 ~ 1.20", delta_color="off")
    
    t_color = "normal"
    if maintenance_ratio < 250: t_color = "inverse"
    elif maintenance_ratio < 300: t_color = "inverse"
    col3.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color=t_color)
    
    u_color = "inverse" if loan_ratio > 35 else "normal"
    col4.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color=u_color)

    st.divider()

    st.subheader("3. 資產配置與指令")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**資產配置佔比**")
        chart_data = pd.DataFrame({
            '資產類別': ['攻擊型 (正二)', '核心 (00662)', '防禦 (00713)', '子彈庫 (債券)'],
            '市值': [val_attack, val_core, val_defense, val_ammo]
        })
        colors = {'攻擊型 (正二)': '#FF4B4B', '核心 (00662)': '#FFD700', '防禦 (00713)': '#2E8B57', '子彈庫 (債券)': '#87CEFA'}
        fig = px.pie(chart_data, values='市值', names='資產類別', color='資產類別', color_discrete_map=colors, hole=0.45)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**AI 戰略指令**")
        is_safe_t = maintenance_ratio >= 300
        is_safe_u = loan_ratio <= 35
        risk_msgs = []
        if not is_safe_t: risk_msgs.append(f"⚠️ 維持率 ({maintenance_ratio:.0f}%) 低於 300%")
        if not is_safe_u: risk_msgs.append(f"⚠️ 負債比 ({loan_ratio:.1f}%) 高於 35%")

        if maintenance_ratio < 250:
            st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，賣股還債。")
        elif len(risk_msgs) > 0:
            risk_text = "\n".join(risk_msgs)
            st.warning(f"🟠 **風險提示**\n\n{risk_text}\n\n**指令：**\n財務結構待加強，禁止大幅加碼。")
            if gap > threshold:
                 sell_amt = val_attack - (total_assets * target_attack_ratio / 100)
                 st.info(f"💡 **減壓機會**：賣出 ${sell_amt:,.0f} 正二還債！")
        else:
            if gap > threshold:
                sell_amt = val_attack - (total_assets * target_attack_ratio / 100)
                st.warning(f"🔴 **賣出訊號**\n\n攻擊佔比過高 (+{gap:.1f}%)。\n\n**賣出：** ${sell_amt:,.0f} \n**轉入：** 子彈庫")
            elif gap < -threshold:
                buy_amt = (total_assets * target_attack_ratio / 100) - val_attack
                st.success(f"🟢 **買進訊號**\n\n攻擊佔比過低 ({gap:.1f}%)。\n\n**動用：** ${buy_amt:,.0f} \n**買進：** 正二資產")
            else:
                st.success(f"✅ **系統待機**\n\n財務健康且無偏離。\n持續持有。")
                st.caption(f"目前偏離度: {gap:+.2f}% (容許範圍 +/- 3%)")
                
    st.markdown("---")
    with st.expander("📊 查看詳細資產清單"):
         detail_data = {
            '代號': ['00675L', '00631L', '00670L', '00662', '00713', '00865B'],
            '類別': ['攻擊', '攻擊', '攻擊', '核心', '防禦', '子彈'],
            'Beta': [1.60, 1.60, 2.00, 1.00, 0.60, 0.00],
            '市值': [v_675, v_631, v_670, v_662, v_713, v_865]
        }
         st.dataframe(pd.DataFrame(detail_data).style.format({"市值": "${:,.0f}", "Beta": "{:.2f}"}))

# === 分頁 2: 操作指南 ===
with tab2:
    st.title("📖 全天候系統操作指南 (SOP)")
    st.subheader("⚙️ 每日操作流程")
    st.markdown("""
    1.  **資料更新 (Data Check)**
        * 點擊 **「📂 載入上次存檔數據」**，快速還原。
        * 輸入 **「目前大盤本益比 (P/E)」**，參考下方建議調整 **「基準曝險」**。
        * 確認 `自動抓取 ATH` 與 `今日大盤` 數值。
        * 更新各類資產的 **「股數」** 與最新的 **「質押借款總額」**。
    2.  **儀表板判讀 (Dashboard Check)**
        * 觀察 **「戰略地圖」** 與 **「紅綠燈訊號」**。
    3.  **存檔記錄 (Archive)**
        * 點擊 **「💾 儲存今日資產紀錄」**。
    """)
    st.divider()
    st.subheader("🔍 核心指標深度解讀")
    with st.expander("1. MDD (最大回檔)"): st.write("目前大盤指數距離歷史最高點 (ATH) 的跌幅。")
    with st.expander("2. Gap (偏離度)"): st.write("目前攻擊曝險 - 目標攻擊曝險。")
    with st.expander("3. T值 (維持率)"): st.write("總資產 / 負債。低於 250% 為紅燈。")
    with st.expander("4. U值 (質押負債比)"): st.write("監控整體槓桿。安全上限 35%。")
    
    # [New] 新增 P/E 解讀
    with st.expander("5. P/E (本益比) - 價值修正引擎"):
        st.markdown("""
        * **作用**：結合基本面評價，修正純技術面的盲點。
        * **判斷標準**：
            * **P/E > 24.0 (昂貴)**：市場過熱，潛在報酬降低 -> **建議降低基準至 20%**。
            * **P/E < 18.0 (便宜)**：價值浮現，安全邊際高 -> **建議提高基準至 30%**。
            * **18.0 ~ 24.0 (合理)**：正常波動 -> **維持既有策略**。
        """)
