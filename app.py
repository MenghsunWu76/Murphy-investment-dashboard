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
st.set_page_config(page_title="A.D.E.I.S 波動率煞車戰情室 (v22.0)", layout="wide")

# --- 2. 歷史紀錄系統 ---
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

# --- 3. 自動抓取引擎 (新增波動率計算) ---
@st.cache_data(ttl=3600)
def get_market_data():
    data = {"ath": 32996.0, "pe_0050": None, "current_vol": 0.20} # 預設波動率20%
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty: 
            data["ath"] = float(hist['High'].max())
            # 計算近 60 交易日的年化波動率
            recent_hist = hist.tail(60)
            daily_returns = recent_hist['Close'].pct_change().dropna()
            data["current_vol"] = float(daily_returns.std() * np.sqrt(252))
            
        etf_50 = yf.Ticker("0050.TW")
        if 'trailingPE' in etf_50.info: data["pe_0050"] = etf_50.info['trailingPE']
    except: pass
    return data

with st.spinner('正在連線抓取市場數據與波動率...'):
    market_data = get_market_data()
    ath_auto = market_data["ath"]
    pe_0050_ref = market_data["pe_0050"]
    real_volatility = market_data["current_vol"]

# --- 4. 初始化 Session State ---
def init_state(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

init_state('manual_ath_check', False)
init_state('input_ath', ath_auto)
init_state('input_index', 31346.0)
init_state('input_pe', 26.5)

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
        else: st.warning("⚠️ 雲端無紀錄，請先上傳備份檔。")

    with st.expander("0. 市場位階與風險平價引擎", expanded=True):
        col_ath1, col_ath2 = st.columns([2, 1])
        with col_ath1: st.metric("自動 ATH", f"{ath_auto:,.0f}")
        with col_ath2: use_manual_ath = st.checkbox("修正", key="manual_ath_check")
        final_ath = st.number_input("輸入 ATH", step=10.0, format="%.0f", key="input_ath") if use_manual_ath else ath_auto
        
        current_index = st.number_input("今日大盤點數", step=10.0, format="%.0f", key="input_index")
        mdd_pct = ((final_ath - current_index) / final_ath) * 100 if final_ath > 0 else 0.0
        
        st.markdown("---")
        pe_val = st.number_input("輸入大盤 P/E", step=0.1, key="input_pe")
        
        # --- 核心優化：雙引擎限速器 ---
        # 1. 估值限速 (PE Limit)
        pe_limit = 160
        if pe_val < 17.0: pe_limit = 320
        elif pe_val < 19.0: pe_limit = 280
        elif pe_val < 21.0: pe_limit = 240
        elif pe_val < 23.0: pe_limit = 200
        
        # 2. 波動率限速 (動態凱利公式)
        market_mu = 0.1415 # 長期台股報酬率預設
        leverage_cost = 0.015 # 槓桿成本
        safe_vol = max(real_volatility, 0.15) # 避免低波動時算出無限大槓桿，設底線 15%
        kelly_limit = ((market_mu - leverage_cost) / (safe_vol ** 2)) * 100
        
        # 3. 最終安全上限：取兩者最嚴格者
        safe_leverage_limit = min(pe_limit, kelly_limit)
        
        st.info(f"📊 近 60 日真實波動率: {real_volatility*100:.1f}%")
        st.caption(f"📍 P/E 戰略上限: {pe_limit}%")
        st.caption(f"📍 凱利波動極限: {kelly_limit:.0f}%")
        if kelly_limit < pe_limit:
            st.warning(f"🚨 **波動率煞車啟動！最終安全上限: {safe_leverage_limit:.0f}%**")
        else:
            st.success(f"🛡️ **估值控管中。最終安全上限: {safe_leverage_limit:.0f}%**")

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

with st.sidebar:
    st.markdown("---")
    st.subheader("💾 雲端保險箱")
    if st.button("💾 儲存今日最新狀態", type="primary"):
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

# --- 7. 主畫面 ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 戰情室 Dashboard", "📖 煞車機制說明", "🚀 選擇權戰情室", "🔮 蒙地卡羅未來推演"])

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
    st.subheader("2. 💰 資金水位與額度試算 (Liquidity Check)")
    liq_c1, liq_c2, liq_c3 = st.columns(3)
    liq_c1.metric("🛡️ 最終安全限額", f"{safe_leverage_limit:.0f}%")
    liq_c1.progress(min(real_leverage_ratio / safe_leverage_limit if safe_leverage_limit>0 else 1.0, 1.0), text=f"目前使用率: {real_leverage_ratio:.1f}%")
    
    liq_c2.metric("🏦 券商限額 (U<35%)", f"$ {max_loan_broker:,.0f}")
    liq_c2.progress(min(loan_amount / max_loan_broker if max_loan_broker > 0 else 0, 1.0), text=f"目前借款: $ {loan_amount:,.0f}")
    
    if recommendation_action == "REDUCE":
        liq_c3.metric("⚠️ 建議減碼 (去槓桿)", f"- $ {recommendation_amount/2:,.0f}", "受波動率或估值限制", delta_color="inverse")
    else:
        liq_c3.metric("✅ 可動用額度 (加碼)", f"+ $ {recommendation_amount:,.0f}", "買入正二(2x)之最大金額", delta_color="normal")

    st.divider()
    st.subheader("3. 投資組合核心數據")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}")
    col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}")
    col3.metric("⚙️ 實質槓桿率", f"{real_leverage_ratio:.1f}%", delta="⚠️ 超速" if real_leverage_ratio > safe_leverage_limit else "✅ 安全", delta_color="inverse" if real_leverage_ratio > safe_leverage_limit else "normal")
    col4.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color="inverse" if maintenance_ratio < 300 else "normal")
    col5.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color="inverse" if loan_ratio > 35 else "normal")

    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        chart_data = pd.DataFrame({'資產類別': ['攻擊型', '核心', '防禦', '子彈庫'], '市值': [val_attack, val_core, val_defense, val_ammo]})
        fig = px.pie(chart_data, values='市值', names='資產類別', color='資產類別', color_discrete_map={'攻擊型': '#FF4B4B', '核心': '#FFD700', '防禦': '#2E8B57', '子彈庫': '#87CEFA'}, hole=0.45)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**AI 戰略指令**")
        risk_msgs = []
        if maintenance_ratio < 300: risk_msgs.append(f"⚠️ 維持率 ({maintenance_ratio:.0f}%) 低於 300%")
        if loan_ratio > 35: risk_msgs.append(f"⚠️ 負債比 ({loan_ratio:.1f}%) 高於 35%")
        if real_leverage_ratio > safe_leverage_limit: risk_msgs.append(f"⚠️ 槓桿超速 (限 {safe_leverage_limit:.0f}%)")

        if maintenance_ratio < 250: st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，賣股還債。")
        elif len(risk_msgs) > 0: st.warning(f"🟠 **風險提示**\n\n{chr(10).join(risk_msgs)}\n\n**指令：考慮減碼。**")
        else:
            if gap > gap_tolerance: st.warning(f"🔴 **賣出訊號** (+{gap:.1f}%)\n賣出：${val_attack - (total_assets * target_attack_ratio / 100):,.0f} 轉入子彈庫")
            elif gap < -gap_tolerance: st.success(f"🟢 **買進訊號** ({gap:.1f}%)\n動用：${(total_assets * target_attack_ratio / 100) - val_attack:,.0f} 買進正二")
            else: st.success(f"✅ **系統待機**\n財務健康且無偏離。")

with tab2:
    st.title("📖 V22 波動率煞車機制說明")
    st.markdown("""
    系統會自動抓取台股近 60 日波動率，並套用連續時間凱利公式：
    * $f^* = (市場報酬 - 槓桿成本) / 波動率^2$
    
    如果遇到股災，雖然 P/E 變便宜（允許開 320%），但若當下市場極度恐慌、波動率飆升，系統會強制將您的槓桿上限下修（例如降至 150%）。**寧可少賺反彈的第一段，也絕不在高波動中被震出場。**
    """)

# V21.1 既有的選擇權與蒙地卡羅模組維持不變 (省略顯示以節省版面，請直接沿用您既有的 Tab3, Tab4 程式碼)
with tab3:
    st.info("🚀 選擇權每週戰情室 (維持原設定)")
with tab4:
    st.info("🔮 蒙地卡羅未來推演 (維持 V21.1 設定)")
