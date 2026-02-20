import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import os
import numpy as np
from datetime import datetime
import pytz

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="A.D.E.I.S 終極機率戰情室 (v20.0)", layout="wide")

# --- 2. 歷史紀錄系統 (CSV 雲端保險箱) ---
HISTORY_FILE = "asset_history.csv"

def load_last_record():
    if not os.path.exists(HISTORY_FILE): return None
    try:
        df = pd.read_csv(HISTORY_FILE)
        return df.iloc[-1] if not df.empty else None
    except: return None

def save_record(data_dict):
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

# --- 3. 自動抓取引擎 ---
@st.cache_data(ttl=3600)
def get_market_data():
    data = {"ath": 32996.0, "pe_0050": None}
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty: data["ath"] = float(hist['High'].max())
        etf_50 = yf.Ticker("0050.TW")
        if 'trailingPE' in etf_50.info: data["pe_0050"] = etf_50.info['trailingPE']
    except: pass
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

# 移除 00948B，保留黃金四角
defaults = {
    'p_675': 185.0, 's_675': 11000, 'p_631': 466.7, 's_631': 331,
    'p_670': 157.95, 's_670': 616, 'p_662': 102.25, 's_662': 25840,
    'p_713': 52.10, 's_713': 66000, 'p_865': 47.51, 's_865': 10000
}
for k, v in defaults.items(): init_state(k, v)

# --- 5. 側邊欄輸入區 ---
with st.sidebar:
    st.header("📝 監控數據輸入")
    if st.button("📂 載入線上最新數據", type="secondary"):
        last_data = load_last_record()
        if last_data is not None:
            try:
                st.session_state['input_index'] = float(last_data['Current_Index'])
                st.session_state['input_ath'] = float(last_data['ATH'])
                st.session_state['manual_ath_check'] = True 
                if 'PE_Ratio' in last_data: st.session_state['input_pe'] = float(last_data['PE_Ratio'])
                for code in ['675', '631', '670', '662', '713', '865']:
                    if f'P_00{code}' in last_data:
                        st.session_state[f'p_{code}'] = float(last_data[f'P_00{code}'])
                        st.session_state[f's_{code}'] = int(last_data[f'S_00{code}'])
                st.toast("✅ 成功載入！", icon="📂")
                st.rerun()
            except Exception as e: st.error(f"載入失敗: {e}")
        else: st.warning("⚠️ 雲端目前無紀錄，請先上傳您的備份檔。")

    with st.expander("0. 市場位階 & 估值", expanded=True):
        col_ath1, col_ath2 = st.columns([2, 1])
        with col_ath1: st.metric("自動 ATH", f"{ath_auto:,.0f}")
        with col_ath2: use_manual_ath = st.checkbox("修正", key="manual_ath_check")
        final_ath = st.number_input("輸入 ATH", step=10.0, format="%.0f", key="input_ath") if use_manual_ath else ath_auto
        
        st.markdown("---")
        current_index = st.number_input("今日大盤點數", step=10.0, format="%.0f", key="input_index")
        mdd_pct = ((final_ath - current_index) / final_ath) * 100 if final_ath > 0 else 0.0
        st.info(f"📉 目前 MDD: {mdd_pct:.2f}%")
        
        st.markdown("---")
        if pe_0050_ref: st.caption(f"參考: 0050 PE {pe_0050_ref:.2f}")
        pe_val = st.number_input("輸入大盤 P/E (決定槓桿上限)", step=0.1, key="input_pe")

        safe_leverage_limit = 160
        if pe_val < 17.0: safe_leverage_limit = 320
        elif pe_val < 19.0: safe_leverage_limit = 280
        elif pe_val < 21.0: safe_leverage_limit = 240
        elif pe_val < 23.0: safe_leverage_limit = 200
        else: safe_leverage_limit = 160
        st.caption(f"🛡️ 安全槓桿上限: {safe_leverage_limit}%")

        st.markdown("---")
        base_exposure = st.number_input("基準曝險 % (Tier 1)", value=23.0, min_value=20.0, max_value=30.0, step=1.0)

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

    with st.expander("3. 防禦資產 (高息)", expanded=True):
        c1, c2 = st.columns(2)
        p_713 = c1.number_input("00713 價格", step=0.05, key="p_713")
        s_713 = c2.number_input("00713 股數", step=1000, key="s_713")

    with st.expander("4. 子彈庫 (無息短債)", expanded=True):
        c1, c2 = st.columns(2)
        p_865 = c1.number_input("00865B 價格", step=0.01, key="p_865")
        s_865 = c2.number_input("00865B 股數", step=1000, key="s_865")

    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)

# --- 6. 運算引擎 ---
v_675, v_631, v_670 = p_675 * s_675, p_631 * s_631, p_670 * s_670
v_662, v_713, v_865 = p_662 * s_662, p_713 * s_713, p_865 * s_865

val_attack = v_675 + v_631 + v_670
val_core, val_defense, val_ammo = v_662, v_713, v_865
total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

real_exposure = (val_attack * 2.0) + (val_core * 1.0) + (val_defense * 1.0) + (val_ammo * 1.0)
real_leverage_ratio = (real_exposure / net_assets) * 100 if net_assets > 0 else 0

beta_weighted_sum = ((v_675*1.6) + (v_631*1.6) + (v_670*2.0) + (v_713*0.6) + (v_662*1.0) + (v_865*0.0))
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0

tier_0, tier_1, tier_2 = base_exposure, base_exposure + 5.0, base_exposure + 5.0
tier_3, tier_4, tier_5 = base_exposure + 10.0, base_exposure + 15.0, base_exposure + 20.0

ladder_data = [
    {"MDD區間": "< 5%", "目標曝險": tier_0, "位階": "Tier 1 (基準)"},
    {"MDD區間": "5%~10%", "目標曝險": tier_1, "位階": "Tier 1.5 (警戒)"},
    {"MDD區間": "10%~20%", "目標曝險": tier_2, "位階": "Tier 2 (初跌)"},
    {"MDD區間": "20%~35%", "目標曝險": tier_3, "位階": "Tier 3 (主跌)"},
    {"MDD區間": "35%~45%", "目標曝險": tier_4, "位階": "Tier 4 (恐慌)"},
    {"MDD區間": "> 45%", "目標曝險": tier_5, "位階": "Tier 5 (毀滅)"},
]

if mdd_pct < 5.0: target_attack_ratio, current_tier_index = tier_0, 0
elif mdd_pct < 10.0: target_attack_ratio, current_tier_index = tier_1, 1
elif mdd_pct < 20.0: target_attack_ratio, current_tier_index = tier_2, 2
elif mdd_pct < 35.0: target_attack_ratio, current_tier_index = tier_3, 3
elif mdd_pct < 45.0: target_attack_ratio, current_tier_index = tier_4, 4
else: target_attack_ratio, current_tier_index = tier_5, 5

current_tier_name = ladder_data[current_tier_index]["位階"]
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0
# 優化：放寬 Gap 容忍度至 5% (適應大資金)
gap_tolerance = 5.0 
gap = current_attack_ratio - target_attack_ratio

max_allowed_exposure_kelly = net_assets * (safe_leverage_limit / 100.0)
exposure_gap = max_allowed_exposure_kelly - real_exposure
max_assets_broker = net_assets / (1 - 0.35)
max_loan_broker = max_assets_broker - net_assets
loan_headroom = max_loan_broker - loan_amount

if exposure_gap < 0:
    recommendation_action, recommendation_amount = "REDUCE", abs(exposure_gap)
else:
    recommendation_action, recommendation_amount = "BORROW", min(exposure_gap / 2, loan_headroom)

last_record = load_last_record()
diff_total = total_assets - last_record['Total_Assets'] if last_record is not None else 0
last_date_str = last_record['Date'] if last_record is not None else "無紀錄"

with st.sidebar:
    st.markdown("---")
    st.subheader("💾 雲端保險箱")
    uploaded_file = st.file_uploader("📤 1. 恢復記憶 (上傳歷史 CSV)", type=["csv"])
    if uploaded_file is not None:
        try:
            pd.read_csv(uploaded_file).to_csv(HISTORY_FILE, index=False)
            st.success("✅ 記憶已恢復！請點擊上方載入")
        except Exception as e: st.error(f"上傳失敗: {e}")

    if st.button("💾 2. 儲存今日最新狀態", type="primary"):
        now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
        save_data = {
            "Date": now_str, "Total_Assets": total_assets, "Net_Assets": net_assets,
            "MDD": mdd_pct, "Current_Index": current_index, "ATH": final_ath, "PE_Ratio": pe_val,
            "P_00675": p_675, "P_00631": p_631, "P_00670": p_670, "P_00662": p_662, "P_00713": p_713, "P_00865": p_865,
            "S_00675": s_675, "S_00631": s_631, "S_00670": s_670, "S_00662": s_662, "S_00713": s_713, "S_00865": s_865
        }
        save_record(save_data)
        st.success(f"已儲存！時間: {now_str}")
        st.rerun()
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "rb") as f: csv_bytes = f.read()
        st.download_button("📥 3. 下載最新備份", data=csv_bytes, file_name=f"ADEIS_Backup_{datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y%m%d')}.csv", mime="text/csv")

# --- 7. 主畫面 ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 戰情室 Dashboard", "📖 現金流與 SOP", "🚀 選擇權戰情室 (TXO)", "🔮 蒙地卡羅未來推演"])

with tab1:
    st.subheader("1. 動態戰略地圖")
    m1, m2, m3, m4 = st.columns([1, 1, 1, 2])
    m1.metric("📉 目前大盤 MDD", f"{mdd_pct:.2f}%", help=f"計算基準 ATH: {final_ath:,.0f}")
    m2.metric("⚡ 目前攻擊曝險", f"{current_attack_ratio:.2f}%", delta=f"{gap:+.2f}% (偏離)", delta_color="inverse" if abs(gap)>gap_tolerance else "off")
    m3.metric("🎯 當前目標曝險", f"{target_attack_ratio:.0f}%", help=f"位階: {current_tier_name}")
    
    df_ladder = pd.DataFrame(ladder_data)
    def highlight_current_row(row): return ['background-color: #ffcccc' if row['位階'] == current_tier_name else '' for _ in row]
    with m4:
        st.dataframe(df_ladder.style.apply(highlight_current_row, axis=1).format({"目標曝險": "{:.0f}%"}), hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("2. 投資組合核心數據與指令")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"${diff_total:,.0f}")
    col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}")
    col3.metric("⚙️ 實質槓桿率", f"{real_leverage_ratio:.1f}%", delta="⚠️ 超速" if real_leverage_ratio > safe_leverage_limit else "✅ 安全", delta_color="inverse" if real_leverage_ratio > safe_leverage_limit else "normal")
    col4.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color="inverse" if maintenance_ratio < 300 else "normal")
    col5.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color="inverse" if loan_ratio > 35 else "normal")

    st.markdown("**AI 戰略指令**")
    if maintenance_ratio < 250: st.error("⛔ **紅色警戒：維持率危險！禁止買進，優先賣出債券或核心資產還債。**")
    elif real_leverage_ratio > safe_leverage_limit: st.warning(f"⚠️ **槓桿超標 (上限 {safe_leverage_limit}%)：禁止加碼正二，請用現金流還款降壓。**")
    else:
        if gap > gap_tolerance: st.warning(f"🔴 **賣出訊號 (+{gap:.1f}%)：賣出約 ${val_attack - (total_assets * target_attack_ratio / 100):,.0f} 正二，轉入 00865B 子彈庫。**")
        elif gap < -gap_tolerance: st.success(f"🟢 **買進訊號 ({gap:.1f}%)：動用約 ${(total_assets * target_attack_ratio / 100) - val_attack:,.0f} 買進正二。**")
        else: st.success(f"✅ **系統待機：財務健康且無偏離 (容忍度 +/- {gap_tolerance}%)。**")

with tab2:
    st.title("📖 A.D.E.I.S 實戰教戰守則")
    st.markdown("""
    ### 🌊 現金流瀑布模型 (由上而下分配)
    1. **第一層 (生存線)**：預留足夠扣繳未來數月「質押利息」的現金。
    2. **第二層 (降壓防禦)**：若 U值 > 35% 或 P/E > 26.5，剩下的錢全數拿去「償還本金」。
    3. **第三層 (估值再投資)**：若護城河安全，看 P/E 燈號買進：
       * 🔴 P/E > 25 (貴) ➔ 買 **00865B** 或 **00713** (囤積子彈)。
       * 🟡 P/E 21~25 (普) ➔ 買 **00662** (擴張核心)。
       * 🟢 P/E < 21 (俗) ➔ 買 **00675L** (低檔重壓)。
    """)

with tab3:
    st.title("🚀 選擇權每週戰情室 (TXO Weekly)")
    delta_safety_dist = current_index * 0.025
    if pe_val >= 24.0:
        st.subheader("🎯 本週建議策略：🐻 Bear Call Spread (高空收租)")
        st.info("P/E 昂貴。預期大盤上檔受限，賣出上方買權收取時間價值。")
        c1, c2 = st.columns(2)
        c1.metric("1. 賣出 (Sell) 履約價", f"{round((current_index + delta_safety_dist) / 100) * 100}")
        c2.metric("2. 買進 (Buy) 履約價", f"{round((current_index + delta_safety_dist) / 100) * 100 + 500}")
    elif pe_val >= 21.0:
        st.subheader("🎯 本週建議策略：🐂 Bull Put Spread (低檔收租)")
        st.info("P/E 合理。趨勢穩健，賣出下方賣權收取權利金。")
        c1, c2 = st.columns(2)
        c1.metric("1. 賣出 (Sell) 履約價", f"{round((current_index - delta_safety_dist) / 100) * 100}")
        c2.metric("2. 買進 (Buy) 履約價", f"{round((current_index - delta_safety_dist) / 100) * 100 - 500}")
    else:
        st.subheader("🛑 本週建議：❌ 戰略停火")
        st.warning("目前估值偏低，應全力做多正二現貨，避免賣 Put 風險。")

# --- 8. 🔮 蒙地卡羅未來推演模組 ---
with tab4:
    st.title("🔮 蒙地卡羅未來資產推演 (Monte Carlo Simulation)")
    st.markdown("基於您 **今日真實的資產配置** 與 **借款金額**，模擬未來 10,000 種平行宇宙的財富軌跡。")
    
    with st.expander("⚙️ 調整總體經濟預期假設 (可微調)", expanded=False):
        st.markdown("系統已根據您的四角配置 (正二、納斯達克、高息、短債) 計算出加權預設值。您可以根據對未來 AI 發展的樂觀/悲觀程度微調：")
        w_atk, w_cor = val_attack/total_assets if total_assets>0 else 0, val_core/total_assets if total_assets>0 else 0
        w_def, w_amo = val_defense/total_assets if total_assets>0 else 0, val_ammo/total_assets if total_assets>0 else 0
        
        default_mu = (w_atk * 0.22) + (w_cor * 0.12) + (w_def * 0.08) + (w_amo * 0.04)
        default_vol = (w_atk * 0.40) + (w_cor * 0.20) + (w_def * 0.12) + (w_amo * 0.03)
        
        c_mu, c_vol = st.columns(2)
        port_mu = c_mu.slider("預期投資組合 年化報酬率 (CAGR)", min_value=0.0, max_value=0.40, value=float(default_mu), step=0.01, format="%.2f")
        port_vol = c_vol.slider("預期投資組合 年化波動率 (Volatility)", min_value=0.05, max_value=0.50, value=float(default_vol), step=0.01, format="%.2f")
    
    mc_years = st.slider("🕰️ 選擇推演時間軸 (Years)", min_value=1, max_value=20, value=5, step=1)
    
    if st.button("🚀 啟動 10,000 次平行宇宙推演", type="primary"):
        with st.spinner(f"正在運算未來 {mc_years} 年的 10,000 種可能性..."):
            np.random.seed(42) # 固定隨機種子讓每次顯示穩定，實戰可移除
            num_simulations = 10000
            steps = mc_years * 12 # 每月結算一次
            dt = 1 / 12
            
            # Geometric Brownian Motion (GBM) 矩陣運算
            Z = np.random.normal(0, 1, (steps, num_simulations))
            drift = (port_mu - 0.5 * port_vol**2) * dt
            diffusion = port_vol * np.sqrt(dt) * Z
            daily_returns = np.exp(drift + diffusion)
            
            # 計算總資產路徑
            price_paths = np.zeros_like(daily_returns)
            price_paths[0] = total_assets
            for t in range(1, steps):
                price_paths[t] = price_paths[t-1] * daily_returns[t]
                
            # 計算淨資產 (扣除固定借款)
            net_paths = price_paths - loan_amount
            
            # 斷頭判定 (任一月份 T值 < 130%)
            margin_call_threshold = loan_amount * 1.3
            ruin_paths = np.any(price_paths < margin_call_threshold, axis=0)
            ruin_prob = np.mean(ruin_paths) * 100
            
            # 提取期末淨資產 (排除破產的路徑)
            final_net_assets = net_paths[-1, ~ruin_paths]
            
            if len(final_net_assets) > 0:
                p05 = np.percentile(final_net_assets, 5)
                p50 = np.percentile(final_net_assets, 50)
                p95 = np.percentile(final_net_assets, 95)
            else:
                p05 = p50 = p95 = 0

            # --- 繪製機率雲圖 (抽樣 100 條線繪製避免當機) ---
            sample_paths = net_paths[:, np.random.choice(num_simulations, 100, replace=False)]
            time_axis = np.linspace(0, mc_years, steps)
            
            fig = go.Figure()
            for i in range(100):
                fig.add_trace(go.Scatter(x=time_axis, y=sample_paths[:, i], mode='lines', line=dict(color='rgba(135, 206, 250, 0.1)'), showlegend=False))
            
            # 加上中位數趨勢線
            median_path = np.median(net_paths, axis=1)
            fig.add_trace(go.Scatter(x=time_axis, y=median_path, mode='lines', line=dict(color='#FFD700', width=3), name='中位數預期'))
            # 加上投入成本線 (目前的淨資產)
            fig.add_trace(go.Scatter(x=[0, mc_years], y=[net_assets, net_assets], mode='lines', line=dict(color='#FF4B4B', width=2, dash='dash'), name='目前淨資產起點'))
            
            fig.update_layout(title=f"未來 {mc_years} 年淨資產推演 (抽樣 100 條路徑)", xaxis_title="年度", yaxis_title="淨資產 (台幣)", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            # --- 顯示終極報告 ---
            st.subheader("📊 家族傳承機率報告")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric(f"💀 斷頭/破產機率", f"{ruin_prob:.2f}%", help="未來任一月份維持率跌破 130% 的機率")
            r2.metric(f"⛈️ 最差 5% (悲觀)", f"${p05:,.0f}", help="運氣極差，遇到長期空頭的情況")
            r3.metric(f"⛅ 中位數 (標準)", f"${p50:,.0f}", help="最有可能發生的財富落點")
            r4.metric(f"☀️ 最佳 5% (樂觀)", f"${p95:,.0f}", help="AI 超級週期延續，運氣極佳的情況")
            
            if ruin_prob > 5.0:
                st.error("⚠️ **風險警告：** 您的斷頭機率高於 5%。建議在「戰情室 Dashboard」中調降 U值 (償還借款) 或增加 00713/00865B 的防禦配置，再重新推演。")
            else:
                st.success("✅ **系統評估：** 您的投資組合抗壓性極佳，幾乎免疫黑天鵝造成的斷頭風險，請安心享受時間複利。")
