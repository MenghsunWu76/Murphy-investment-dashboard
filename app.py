import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import os
from datetime import datetime
import pytz

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="全天候戰情室 (v18.0 資金水位旗艦版)", layout="wide")

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

# --- 3. 自動抓取引擎 (ATH & 0050 PE) ---
@st.cache_data(ttl=3600)
def get_market_data():
    data = {"ath": 32996.0, "pe_0050": None}
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty: 
            data["ath"] = float(hist['High'].max())
        
        etf_50 = yf.Ticker("0050.TW")
        if 'trailingPE' in etf_50.info:
            data["pe_0050"] = etf_50.info['trailingPE']
    except: 
        pass
    return data

with st.spinner('正在連線抓取市場數據...'):
    market_data = get_market_data()
    ath_auto = market_data["ath"]
    pe_0050_ref = market_data["pe_0050"]

# --- 4. 初始化 Session State ---
def init_state(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

init_state('manual_ath_check', False)
init_state('input_ath', ath_auto)
init_state('input_index', 31346.0)
init_state('input_pe', 26.5)

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
    
    # === 一鍵讀取 ===
    if st.button("📂 載入上次存檔數據", type="secondary"):
        last_data = load_last_record()
        if last_data is not None:
            try:
                st.session_state['input_index'] = float(last_data['Current_Index'])
                st.session_state['input_ath'] = float(last_data['ATH'])
                st.session_state['manual_ath_check'] = True 
                
                if 'PE_Ratio' in last_data:
                    st.session_state['input_pe'] = float(last_data['PE_Ratio'])

                for code in ['675', '631', '670', '662', '713', '865']:
                    st.session_state[f'p_{code}'] = float(last_data[f'P_00{code}'])
                    st.session_state[f's_{code}'] = int(last_data[f'S_00{code}'])
                
                st.toast("✅ 成功載入！", icon="📂")
                st.rerun()
            except Exception as e:
                st.error(f"載入失敗: {e}")
        else:
            st.warning("⚠️ 無紀錄")

    # A. 市場數據 (MDD 核心 + P/E 衛士)
    with st.expander("0. 市場位階 & 估值", expanded=True):
        col_ath1, col_ath2 = st.columns([2, 1])
        with col_ath1: st.metric("自動 ATH", f"{ath_auto:,.0f}")
        with col_ath2: use_manual_ath = st.checkbox("修正", key="manual_ath_check")
            
        if use_manual_ath:
            final_ath = st.number_input("輸入 ATH", step=10.0, format="%.0f", key="input_ath")
        else:
            final_ath = ath_auto
        
        st.markdown("---")
        current_index = st.number_input("今日大盤點數", step=10.0, format="%.0f", key="input_index")
        
        mdd_pct = ((final_ath - current_index) / final_ath) * 100 if final_ath > 0 else 0.0
        st.info(f"📉 目前 MDD: {mdd_pct:.2f}%")
        
        # P/E 輸入與參考
        st.markdown("---")
        if pe_0050_ref:
            st.caption(f"參考: 0050 PE {pe_0050_ref:.2f}")
        st.link_button("🔗 查詢證交所官方 P/E", "https://www.twse.com.tw/zh/page/trading/exchange/BWIBBU_d.html")
        
        pe_val = st.number_input("輸入大盤 P/E (決定槓桿上限)", step=0.1, key="input_pe")

        # 計算安全槓桿上限 (依據您的凱利公式圖表)
        safe_leverage_limit = 160
        if pe_val < 17.0: safe_leverage_limit = 320
        elif pe_val < 19.0: safe_leverage_limit = 280
        elif pe_val < 21.0: safe_leverage_limit = 240
        elif pe_val < 23.0: safe_leverage_limit = 200
        else: safe_leverage_limit = 160 # PE > 23 (包含 25, 26.5)

        st.caption(f"🛡️ 安全槓桿上限: {safe_leverage_limit}%")

        st.markdown("---")
        base_exposure = st.number_input("基準曝險 % (Tier 1)", value=23.0, min_value=20.0, max_value=30.0, step=1.0)
        
        ratchet_level = int(base_exposure - 20)
        level_sign = "+" if ratchet_level > 0 else ""
        st.caption(f"ℹ️ 棘輪位階: {level_sign}{ratchet_level}")

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
# 資產市值
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

# 實質槓桿率計算
real_exposure = (val_attack * 2.0) + (val_core * 1.0) + (val_defense * 1.0) + (val_ammo * 1.0)
real_leverage_ratio = (real_exposure / net_assets) * 100 if net_assets > 0 else 0

# 其他指標
beta_weighted_sum = ((v_675*1.6) + (v_631*1.6) + (v_670*2.0) + (v_713*0.6) + (v_662*1.0) + (v_865*0.0))
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0

# MDD 階梯
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
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 7. [New] 資金水位與額度試算引擎 ---
# A. P/E 限額計算 (Strategy Ceiling)
# 凱利允許的最大曝險 = 淨資產 * 安全槓桿率
max_allowed_exposure_kelly = net_assets * (safe_leverage_limit / 100.0)
exposure_gap = max_allowed_exposure_kelly - real_exposure # 正數=可加碼，負數=需減碼

# B. 券商限額計算 (Broker Ceiling - U值 35%)
# 35% 負債比上限反推最大貸款額 = 總資產 * 0.35 (近似)
# 更保守算法：維持淨資產不變下，最大資產 = NetAssets / (1-0.35)
max_assets_broker = net_assets / (1 - 0.35)
max_loan_broker = max_assets_broker - net_assets
loan_headroom = max_loan_broker - loan_amount

# C. 綜合建議
recommendation_action = "HOLD"
recommendation_amount = 0
action_color = "off"

# 判斷邏輯
if exposure_gap < 0:
    # 超速：需要減碼
    recommendation_action = "REDUCE"
    recommendation_amount = abs(exposure_gap) # 這是需要減少的"曝險值"
    # 如果是賣正二(2x)，只需賣一半金額; 如果還款(1x)，需還全額
    action_color = "inverse" # 紅燈
else:
    # 安全：計算可動用額度
    recommendation_action = "BORROW"
    # 可借金額 = Min(凱利剩餘曝險空間/2, 券商剩餘額度)
    # 假設借錢買正二(2x)，每一塊錢增加2塊曝險 -> 故除以2
    borrow_power_kelly = exposure_gap / 2 
    recommendation_amount = min(borrow_power_kelly, loan_headroom)
    action_color = "normal" # 綠燈

# --- 8. 讀取與儲存歷史資料 ---
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
            "PE_Ratio": pe_val,
            "P_00675": p_675, "P_00631": p_631, "P_00670": p_670,
            "P_00662": p_662, "P_00713": p_713, "P_00865": p_865,
            "S_00675": s_675, "S_00631": s_631, "S_00670": s_670,
            "S_00662": s_662, "S_00713": s_713, "S_00865": s_865
        }
        
        save_record(save_data)
        st.success(f"已儲存！時間: {now_str}")
        st.rerun()

    if last_record is not None:
        st.caption(f"上次存檔: {last_date_str}")

# --- 9. 主畫面 (分頁系統) ---

tab1, tab2, tab3 = st.tabs(["📊 戰情室 Dashboard", "📖 操作指南 & 指標解讀", "🚀 選擇權戰情室 (TXO)"])

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
        st.caption(f"ℹ️ 策略引擎: MDD 階梯 (參考 P/E: {pe_val})")
        st.dataframe(df_ladder.style.apply(highlight_current_row, axis=1).format({"目標曝險": "{:.0f}%"}), hide_index=True, use_container_width=True)

    st.divider()

    # [New] 資金水位與額度試算
    st.subheader("2. 💰 資金水位與額度試算 (Liquidity Check)")
    
    liq_c1, liq_c2, liq_c3 = st.columns(3)
    
    # Col 1: P/E 戰略限額
    liq_c1.metric("🛡️ 戰略限額 (Kelly)", f"{safe_leverage_limit}%", help="依據 P/E 決定的安全槓桿上限")
    liq_c1.progress(min(real_leverage_ratio / safe_leverage_limit, 1.0), text=f"目前使用率: {real_leverage_ratio:.1f}%")
    
    # Col 2: 券商硬限額 (U=35%)
    liq_c2.metric("🏦 券商限額 (U<35%)", f"$ {max_loan_broker:,.0f}", help="質押負債比 35% 對應的借款上限")
    usage_rate_broker = loan_amount / max_loan_broker if max_loan_broker > 0 else 0
    liq_c2.progress(min(usage_rate_broker, 1.0), text=f"目前借款: $ {loan_amount:,.0f}")
    
    # Col 3: 最終建議 (Actionable)
    if recommendation_action == "REDUCE":
        liq_c3.metric("⚠️ 建議減碼 (去槓桿)", f"- $ {recommendation_amount/2:,.0f}", "若賣正二(2x)所需金額", delta_color="inverse")
        st.toast("⚠️ 槓桿超速！請考慮減碼。", icon="🚨")
    else:
        liq_c3.metric("✅ 可動用額度 (加碼)", f"+ $ {recommendation_amount:,.0f}", "買入正二(2x)之最大金額", delta_color="normal")
    
    st.divider()

    st.subheader("3. 投資組合核心數據")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"${diff_total:,.0f}", help="vs 上次存檔")
    col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}")
    
    lev_delta_color = "normal"
    lev_msg = "✅ 安全"
    if real_leverage_ratio > safe_leverage_limit:
        lev_delta_color = "inverse"
        lev_msg = f"⚠️ 超速 (上限{safe_leverage_limit}%)"
    
    col3.metric("⚙️ 實質槓桿率", f"{real_leverage_ratio:.1f}%", delta=lev_msg, delta_color=lev_delta_color, help="公式: 總市場曝險(含正二) / 淨資產")

    t_color = "normal"
    if maintenance_ratio < 250: t_color = "inverse"
    elif maintenance_ratio < 300: t_color = "inverse"
    col4.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color=t_color)
    
    u_color = "inverse" if loan_ratio > 35 else "normal"
    col5.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color=u_color)

    st.divider()

    st.subheader("4. 資產配置與指令")
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
        if real_leverage_ratio > safe_leverage_limit: risk_msgs.append(f"⚠️ 槓桿 ({real_leverage_ratio:.1f}%) 超過 P/E 安全上限 ({safe_leverage_limit}%)")

        if maintenance_ratio < 250:
            st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，賣股還債。")
        elif len(risk_msgs) > 0:
            risk_text = "\n".join(risk_msgs)
            st.warning(f"🟠 **風險提示**\n\n{risk_text}\n\n**指令：**\n風險指標超標，禁止加碼，考慮減碼。")
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
    1.  **資料更新**
        * 點擊 **「📂 載入上次存檔數據」**。
        * 輸入 **「P/E」** 與 **「ATH」**。
        * 更新股數與質押金額。
    2.  **儀表板判讀**
        * **資金水位**：查看「可動用額度」。
        * **Gap**：+/- 3% 再平衡。
        * **實質槓桿率**：確認是否顯示「✅ 安全」。
    3.  **存檔**：點擊 **「💾 儲存」**。
    """)
    st.divider()
    
    st.subheader("📊 凱利動態槓桿比例表 (P/E 風控)")
    st.markdown("""
    | 本益比 (P/E) | 預估指數位置 | 建議安全槓桿率 | 策略動作 |
    | :--- | :--- | :--- | :--- |
    | **> 26.5** | 33,600+ | **160%** | **超限減碼**：處於防禦狀態，等待評價回落。 |
    | **25.0 ~ 26.5** | 31,700 | **160%** | **防禦區**：維持最低槓桿。 |
    | **23.0 ~ 25.0** | 29,160 | **200%** | **基準區**：回到 2 倍槓桿 (如 100% 現貨 + 100% 借貸/正二)。 |
    | **21.0 ~ 23.0** | 26,630 | **240%** | **加碼區**：估值進入中值，轉向積極。 |
    | **19.0 ~ 21.0** | 24,090 | **280%** | **重倉區**：評價進入甜蜜點，大幅擴張風險敞口。 |
    | **< 17.0** | 21,550 | **320%** | **滿積區**：執行策略上限，全速前進。 |
    """)

    st.divider()
    st.subheader("🔍 核心指標深度解讀")
    with st.expander("1. 實質槓桿率 (Leverage Ratio)"):
        st.write("公式：`總市場曝險(正二算2倍) / 淨資產`。這是您最真實的曝險倍數。")
    with st.expander("2. MDD (最大回檔)"): st.write("策略絕對核心。MDD 決定戰場位置 (位階)。")
    with st.expander("3. T值 & U值"): st.write("維持率 > 300%，負債比 < 35%。")

# === 分頁 3: 選擇權戰情室 ===
with tab3:
    st.title("🚀 選擇權每週戰情室 (TXO Weekly)")
    st.markdown("利用 **Delta 機率** 與 **P/E 位階**，打造穩健的現金流外掛。")
    
    delta_safety_dist = current_index * 0.025
    
    txo_strategy = "WAIT"
    txo_title = "❌ 戰略停火 (Ceasefire)"
    txo_desc = "目前估值偏低，應全力做多正二現貨，避免賣 Put 風險。"
    
    if pe_val >= 24.0:
        txo_strategy = "BEAR_CALL"
        txo_title = "🐻 Bear Call Spread (高空收租)"
        txo_desc = "P/E 昂貴 (>24)。預期大盤上檔受限，賣出上方買權收取時間價值，作為正二現貨的避險。"
        sell_strike = round((current_index + delta_safety_dist) / 100) * 100
        buy_strike = sell_strike + 500
        
    elif pe_val >= 21.0:
        txo_strategy = "BULL_PUT"
        txo_title = "🐂 Bull Put Spread (低檔收租)"
        txo_desc = "P/E 合理 (21~24)。趨勢穩健，賣出下方賣權收取權利金，增加現金流。"
        sell_strike = round((current_index - delta_safety_dist) / 100) * 100
        buy_strike = sell_strike - 500
    
    st.subheader("🔢 口數建議 (Position Sizing)")
    
    txo_contract_val = current_index * 50
    st.caption(f"ℹ️ 一口 TXO 合約價值: ${txo_contract_val:,.0f}")
    
    coverage_ratio = st.slider("設定資產覆蓋率 (Hedge Ratio)", min_value=10, max_value=60, value=30, step=10, help="建議 20%~30% 為舒適區")
    
    safe_exposure = total_assets * (coverage_ratio / 100)
    suggested_lots = int(safe_exposure / txo_contract_val)
    
    col_lots1, col_lots2 = st.columns(2)
    col_lots1.metric("🛡️ 建議操作口數", f"{suggested_lots} 組", help=f"基於 {coverage_ratio}% 資產覆蓋率")
    col_lots2.metric("💰 曝險總值", f"${suggested_lots * txo_contract_val:,.0f}")
    
    st.divider()
    
    if txo_strategy != "WAIT":
        st.subheader(f"🎯 本週建議策略：{txo_title}")
        st.info(txo_desc)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("1. 賣出 (Sell)", f"{sell_strike}", "收取權利金 (主)", delta_color="inverse")
        c2.metric("2. 買進 (Buy)", f"{buy_strike}", "保護 (價差 500點)", delta_color="normal")
        c3.metric("📊 預估 Delta", "~ 0.20", "約 2.5% 安全距離")
        
        st.caption(f"💡 邏輯：目前指數 {current_index:,.0f} +/- {delta_safety_dist:.0f} 點 (安全距離)")
        st.warning("**紀律提醒**：若大盤觸及「賣出履約價」，請無條件停損/平倉，嚴禁凹單。")
    
    else:
        st.subheader(f"🛑 本週建議：{txo_title}")
        st.warning(txo_desc)
        st.caption(f"目前 P/E: {pe_val} (低於 21.0)")

    st.divider()
    with st.expander("🔍 什麼是 Delta 0.2 安全距離？"):
        st.markdown("""
        * **原理**：Delta 0.2 代表該履約價只有 **20% 的機率** 會被穿價 (輸錢)。
        * **操作**：賣在这个位置，就像在郊區收房租，雖然租金不如市中心 (價平) 高，但非常安全。
        """)
