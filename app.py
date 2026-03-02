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
st.set_page_config(page_title="A.D.E.I.S 全能自駕戰情室 (v25.0)", layout="wide")

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

# --- 3. 自動抓取引擎 (包含即時波動率) ---
@st.cache_data(ttl=3600)
def get_market_data():
    data = {"ath": 32996.0, "pe_0050": None, "current_vol": 0.20}
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty: 
            data["ath"] = float(hist['High'].max())
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
init_state('mortgage_loan', 0.0)
init_state('personal_loan', 0.0)

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
                if 'Mortgage' in last_data: st.session_state['mortgage_loan'] = float(last_data['Mortgage'])
                if 'Personal_Loan' in last_data: st.session_state['personal_loan'] = float(last_data['Personal_Loan'])
                for code in ['675', '631', '670', '662', '713', '865']:
                    if f'P_00{code}' in last_data:
                        st.session_state[f'p_{code}'] = float(last_data[f'P_00{code}'])
                        st.session_state[f's_{code}'] = int(last_data[f'S_00{code}'])
                st.toast("✅ 成功載入！", icon="📂")
                st.rerun()
            except Exception as e: st.error(f"載入失敗: {e}")
        else: st.warning("⚠️ 雲端目前無紀錄，請先上傳您的備份檔。")

    with st.expander("0. 市場位階 & 雙引擎煞車系統", expanded=True):
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
        pe_val = st.number_input("輸入大盤 P/E (決定估值上限)", step=0.1, key="input_pe")

        # 1. 估值限速 (PE Limit)
        pe_limit = 160
        if pe_val < 17.0: pe_limit = 320
        elif pe_val < 19.0: pe_limit = 280
        elif pe_val < 21.0: pe_limit = 240
        elif pe_val < 23.0: pe_limit = 200
        
        # 2. 波動率限速 (動態凱利公式)
        market_mu = 0.1415 
        leverage_cost = 0.015 
        safe_vol = max(real_volatility, 0.15) 
        kelly_limit = ((market_mu - leverage_cost) / (safe_vol ** 2)) * 100
        
        # 3. 最終安全上限
        safe_leverage_limit = min(pe_limit, kelly_limit)

        st.caption(f"📍 P/E 戰略上限: {pe_limit}%")
        st.caption(f"📍 凱利波動極限: {kelly_limit:.0f}% (VIX: {real_volatility*100:.1f}%)")
        if kelly_limit < pe_limit:
            st.warning(f"🚨 **波動率煞車啟動！最終上限: {safe_leverage_limit:.0f}%**")
        else:
            st.success(f"🛡️ **估值控管中。最終上限: {safe_leverage_limit:.0f}%**")

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

    st.subheader("5. 負債監控 (券商與場外)")
    loan_amount = st.number_input("🏦 目前質押借款總額", value=2350000, step=10000)
    mortgage_loan = st.number_input("🏠 房屋增貸未還餘額", key="mortgage_loan", step=10000)
    personal_loan = st.number_input("💳 信貸未還餘額", key="personal_loan", step=10000)

# --- 6. 運算引擎 ---
v_675, v_631, v_670 = p_675 * s_675, p_631 * s_631, p_670 * s_670
v_662, v_713, v_865 = p_662 * s_662, p_713 * s_713, p_865 * s_865

val_attack = v_675 + v_631 + v_670
val_core, val_defense, val_ammo = v_662, v_713, v_865

# 券商層級資產 (用於維持率與槓桿計算)
total_assets = val_attack + val_core + val_defense + val_ammo
portfolio_net_assets = total_assets - loan_amount

# 家族層級真實淨資產 (扣除所有場外負債)
true_net_assets = portfolio_net_assets - mortgage_loan - personal_loan

real_exposure = (val_attack * 2.0) + (val_core * 1.0) + (val_defense * 1.0) + (val_ammo * 1.0)
real_leverage_ratio = (real_exposure / portfolio_net_assets) * 100 if portfolio_net_assets > 0 else 0

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

# --- V23.2 核心：AI 動態擴容再平衡閥值 (Auto-Scaling Gap Tolerance) ---
if true_net_assets < 10000000:
    gap_tolerance = 3.0  # 累積期：高靈敏度，緊咬市場波動
else:
    gap_tolerance = 5.0  # 守成期：低摩擦成本，忽略小震盪

gap = current_attack_ratio - target_attack_ratio

max_allowed_exposure_kelly = portfolio_net_assets * (safe_leverage_limit / 100.0)
exposure_gap = max_allowed_exposure_kelly - real_exposure
max_assets_broker = portfolio_net_assets / (1 - 0.35)
max_loan_broker = max_assets_broker - portfolio_net_assets
loan_headroom = max_loan_broker - loan_amount

if exposure_gap < 0:
    recommendation_action, recommendation_amount = "REDUCE", abs(exposure_gap)
else:
    recommendation_action, recommendation_amount = "BORROW", min(exposure_gap / 2, loan_headroom)

last_record = load_last_record()
diff_total = true_net_assets - (last_record['True_Net_Assets'] if last_record is not None and 'True_Net_Assets' in last_record else portfolio_net_assets)
last_date_str = last_record['Date'] if last_record is not None else "無紀錄"

with st.sidebar:
        st.markdown("---")
        st.subheader("💾 雲端保險箱")
        uploaded_file = st.file_uploader("📤 1. 恢復記憶 (上傳歷史 CSV)", type=["csv"])
        
        # 👑 新增保險栓：必須按下確認按鈕，才執行覆寫，避免 rerun 時無限洗掉新存檔
        if uploaded_file is not None:
            if st.button("📥 確認匯入此備份檔"):
                try:
                    pd.read_csv(uploaded_file).to_csv(HISTORY_FILE, index=False)
                    st.success("✅ 記憶已恢復！請點擊最上方『載入線上最新數據』")
                except Exception as e: 
                    st.error(f"上傳失敗: {e}")

    if st.button("💾 2. 儲存今日最新狀態", type="primary"):
        now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
        save_data = {
            "Date": now_str, "Total_Assets": total_assets, "Portfolio_Net_Assets": portfolio_net_assets, "True_Net_Assets": true_net_assets,
            "MDD": mdd_pct, "Current_Index": current_index, "ATH": final_ath, "PE_Ratio": pe_val,
            "Mortgage": mortgage_loan, "Personal_Loan": personal_loan,
            "P_00675": p_675, "P_00631": p_631, "P_00670": p_670, "P_00662": p_662, "P_00713": p_713, "P_00865": p_865,
            "S_00675": s_675, "S_00631": s_631, "S_00670": s_670, "S_00662": s_662, "S_00713": s_713, "S_00865": s_865
        }
        save_record(save_data)
        st.success(f"已儲存！時間: {now_str}")
        st.rerun()
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "rb") as f: csv_bytes = f.read()
        st.download_button("📥 3. 下載最新備份", data=csv_bytes, file_name=f"ADEIS_Backup_{datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y%m%d')}.csv", mime="text/csv")

# --- 7. 主畫面 (新增 Tab5 系統校準模組) ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 戰情室 Dashboard", "📖 現金流與 SOP", "🚀 選擇權戰情室 (v25)", "🔮 蒙地卡羅未來推演", "⚖️ 系統校準與診斷"
])

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
    
    st.subheader("2. 💰 券商資金水位試算 (Liquidity Check)")
    liq_c1, liq_c2, liq_c3 = st.columns(3)
    liq_c1.metric("🛡️ 最終安全限額", f"{safe_leverage_limit:.0f}%", help="由估值與真實波動率兩者中最嚴格者決定")
    liq_c1.progress(min(real_leverage_ratio / safe_leverage_limit if safe_leverage_limit>0 else 1.0, 1.0), text=f"目前使用率: {real_leverage_ratio:.1f}%")
    
    liq_c2.metric("🏦 券商限額 (U<35%)", f"$ {max_loan_broker:,.0f}")
    liq_c2.progress(min(loan_amount / max_loan_broker if max_loan_broker > 0 else 0, 1.0), text=f"目前借款: $ {loan_amount:,.0f}")
    
    if recommendation_action == "REDUCE":
        liq_c3.metric("⚠️ 建議減碼 (去槓桿)", f"- $ {recommendation_amount/2:,.0f}", "受波動率或估值限制", delta_color="inverse")
    else:
        liq_c3.metric("✅ 可動用額度 (加碼)", f"+ $ {recommendation_amount:,.0f}", "買入正二(2x)之最大金額", delta_color="normal")

    st.divider()
    
    # 完美展開百萬/千萬級數字的寬度設定
    st.subheader("3. 投資組合核心數據")
    col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 0.8, 1.0, 1.0, 1.0])
    
    col1.metric("💰 總市值", f"${total_assets:,.0f}", help="您的股票與債券總值")
    col2.metric("💎 真實淨資產", f"${true_net_assets:,.0f}", delta=f"{diff_total:+,.0f}", help="總市值 - 質押借款 - 房貸增貸 - 信貸")
    col3.metric("📉 Beta", f"{portfolio_beta:.2f}")
    col4.metric("⚙️ 槓桿率", f"{real_leverage_ratio:.1f}%", delta="⚠️ 超速" if real_leverage_ratio > safe_leverage_limit else "✅ 安全", delta_color="inverse" if real_leverage_ratio > safe_leverage_limit else "normal")
    col5.metric("🛡️ 維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color="inverse" if maintenance_ratio < 300 else "normal")
    col6.metric("💳 負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color="inverse" if loan_ratio > 35 else "normal")

    st.divider()
    
    st.subheader("4. 資產配置與指令")
    c1, c2 = st.columns([2, 1])
    with c1:
        chart_data = pd.DataFrame({'資產類別': ['攻擊型', '核心', '防禦', '子彈庫'], '市值': [val_attack, val_core, val_defense, val_ammo]})
        fig = px.pie(chart_data, values='市值', names='資產類別', color='資產類別', color_discrete_map={'攻擊型': '#FF4B4B', '核心': '#FFD700', '防禦': '#2E8B57', '子彈庫': '#87CEFA'}, hole=0.45)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**AI 戰略指令**")
        risk_msgs = []
        if maintenance_ratio < 300: risk_msgs.append(f"⚠️ 維持率 ({maintenance_ratio:.0f}%) 低於 300%")
        if loan_ratio > 35: risk_msgs.append(f"⚠️ 負債比 ({loan_ratio:.1f}%) 高於 35%")
        if real_leverage_ratio > safe_leverage_limit: risk_msgs.append(f"⚠️ 槓桿超速 (限 {safe_leverage_limit:.0f}%)")

        if maintenance_ratio < 250: st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，賣股還債。")
        elif len(risk_msgs) > 0:
            st.warning(f"🟠 **風險提示**\n\n{chr(10).join(risk_msgs)}\n\n**指令：禁止加碼，考慮減碼。**")
        else:
            if gap > gap_tolerance: st.warning(f"🔴 **賣出訊號** (+{gap:.1f}%)\n賣出：${val_attack - (total_assets * target_attack_ratio / 100):,.0f} 轉入子彈庫")
            elif gap < -gap_tolerance: st.success(f"🟢 **買進訊號** ({gap:.1f}%)\n動用：${(total_assets * target_attack_ratio / 100) - val_attack:,.0f} 買進正二")
            else: st.success(f"✅ **系統待機**\n財務健康且無偏離。\n動態容忍度: +/- {gap_tolerance}%")

with tab2:
    st.title("📖 A.D.E.I.S 實戰教戰守則 (無息子彈庫版)")
    st.markdown("""
    ### 🌊 現金流瀑布模型 (由上而下分配)
    *(註：00865B 為純資金池不配息，現金流主要來自 00713 股息與 TXO 收租)*
    
    1. **第一層 (生存線)**：預留足夠扣繳未來數月「質押利息」的現金，達成零成本槓桿。
    2. **第二層 (降壓防禦)**：若 U值 > 35% 或 P/E > 26.5，剩下的錢全數拿去「償還本金」。
    3. **第三層 (估值再投資)**：若護城河安全，看 P/E 燈號買進：
       * 🔴 P/E > 25 (貴) ➔ 買 **00865B** 或 **00713** (囤積子彈庫)。
       * 🟡 P/E 21~25 (普) ➔ 買 **00662** (擴張美股核心)。
       * 🟢 P/E < 21 (俗) ➔ 買 **00675L** (低檔火力全開)。
       
    ### 🚨 V22 波動率煞車機制說明
    系統會自動抓取台股近 60 日真實波動率，並套用連續時間凱利公式：$f^* = (市場報酬 - 槓桿成本) / 波動率^2$。
    如果遇到股災，雖然 P/E 變便宜，但若當下市場極度恐慌、波動率飆升，系統會強制將您的槓桿上限下修。**寧可少賺反彈第一段，也絕不在高波動中被震出場。**
    
    ### ⚖️ V23.2 動態擴容閥值 (Auto-Scaling)
    系統會依據您的「真實淨資產」自動切換容忍度：
    * **< 1,000萬**：容忍度 **3%** (積極累積，靈活追蹤波段)。
    * **> 1,000萬**：容忍度 **5%** (沉穩守成，減少法人級量體的摩擦手續費)。
    """)

# ==========================================
# 🚀 這裡就是完美修復、對接您專屬變數的 V25 Tab 3
# ==========================================
with tab3:
    st.header("🚀 選擇權每週戰情室 (TXO Weekly 動態對沖)")

    # 1. 定義動態安全距離 (Volatility 防護網)
    # 使用真正的變數：pe_val (大盤P/E)
    base_distance = 500
    if pe_val > 25.0:
        base_distance = 700
        st.warning("⚠️ 系統偵測：目前 P/E 處於高估值區，已自動將選擇權安全防護網拉寬至 700 點以上。")
    elif pe_val < 20.0:
        base_distance = 600

    # 2. 核心戰略判定引擎 (現貨 Delta 偏離度對沖)
    # 使用真正的變數：gap (偏離度), current_index (大盤點數)
    if gap >= 1.5:
        # 戰略 A：正偏離準備觸發賣出 -> 啟動 Synthetic Covered Call
        strategy_name = "Bear Call Spread (高空收租 / 預先鎖利)"
        strategy_icon = "🐻"
        strategy_desc = f"【狀態】現貨正偏離達 +{gap:.2f}%。現貨部位已超載上漲動能。\n\n【動作】在現貨觸發賣出閥值前，提前在上方賣出買權收租。大盤狂噴則現貨補貼期權；大盤回檔則權利金無風險落袋。"
        
        sell_strike = int(current_index + base_distance)
        sell_strike = round(sell_strike / 100) * 100 # 四捨五入到百位數
        buy_strike = sell_strike + 500 # 嚴格鎖定 500 點保證金風險

    elif -1.0 <= gap < 1.5:
        # 戰略 B：中性泥沼盤 -> 啟動 Iron Condor
        strategy_name = "Iron Condor (鐵鷹策略 / 泥沼盤雙收)"
        strategy_icon = "🦅"
        strategy_desc = f"【狀態】現貨偏離度為 {gap:.2f}% (中性健康區間)。大盤目前缺乏單邊極端動能。\n\n【動作】啟動鐵鷹策略，在上下安全距離外同時建立部位，雙向收取 Theta 時間價值。這是死魚盤的最佳提款機。"
        
        # 鐵鷹 Call 邊
        sell_call = int(current_index + base_distance + 100)
        sell_call = round(sell_call / 100) * 100
        buy_call = sell_call + 500
        
        # 鐵鷹 Put 邊
        sell_put = int(current_index - base_distance - 100)
        sell_put = round(sell_put / 100) * 100
        buy_put = sell_put - 500

    else:
        # 戰略 C：負偏離 -> 啟動 Bull Put Spread
        strategy_name = "Bull Put Spread (低檔防守收租)"
        strategy_icon = "🐂"
        strategy_desc = f"【狀態】現貨負偏離達 {gap:.2f}%。大盤近期回檔，估值壓力減輕。\n\n【動作】在下方賣出賣權。若大盤撐住，賺取權利金；若大盤續跌，等同於順勢增加多頭曝險，完美配合現貨逢低加碼邏輯。"
        
        sell_strike = int(current_index - base_distance)
        sell_strike = round(sell_strike / 100) * 100
        buy_strike = sell_strike - 500

    # 3. 渲染戰略面板
    st.markdown(f"### 🎯 本週建議策略：{strategy_icon} {strategy_name}")
    st.info(strategy_desc)

    # 4. 履約價顯示卡片
    if "Iron Condor" in strategy_name:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📉 上方防守 (Bear Call)")
            st.metric("賣出 (Sell) Call 履約價", f"{sell_call}")
            st.metric("買進 (Buy) Call 履約價", f"{buy_call}")
        with col2:
            st.markdown("#### 📈 下方防守 (Bull Put)")
            st.metric("賣出 (Sell) Put 履約價", f"{sell_put}")
            st.metric("買進 (Buy) Put 履約價", f"{buy_put}")
        st.error("🔒 系統鐵律：鐵鷹策略需動用雙邊保證金，請確認 00865B 子彈庫餘額充足，絕對不可動用 00713 質押額度！")
    else:
        col1, col2 = st.columns(2)
        with col1:
            target_sell_type = "Call" if "Bear" in strategy_name else "Put"
            st.metric(f"賣出 (Sell) {target_sell_type} 履約價", f"{sell_strike}")
        with col2:
            target_buy_type = "Call" if "Bear" in strategy_name else "Put"
            st.metric(f"買進 (Buy) {target_buy_type} 履約價", f"{buy_strike}")
        st.error(f"🔒 系統鐵律：必須同時買進 {buy_strike} 進行價差鎖定，嚴禁裸賣！")

    st.markdown("---")
    st.markdown("💡 **量化副手提醒**：以上為系統靜態基準點。極端跳空日或重大數據發布前，請將最新 CSV 傳送給 AI 副手，進行當日『勝率評估』與『最佳建倉時機 (Theta/Vega 決策)』。")


with tab4:
    st.title("🔮 蒙地卡羅未來資產推演 (AI-Optimized Gravity Model)")
    st.markdown("基於您 **今日真實的資產配置** 與 **所有場外負債**，結合 AI 超級週期的總經環境，模擬未來 10,000 種平行宇宙的真實財富軌跡。")
    
    with st.expander("⚙️ 總體經濟動態最佳化 (Dynamic Macro Optimization)", expanded=True):
        w_atk, w_cor = val_attack/total_assets if total_assets>0 else 0, val_core/total_assets if total_assets>0 else 0
        w_def, w_amo = val_defense/total_assets if total_assets>0 else 0, val_ammo/total_assets if total_assets>0 else 0
        
        pe_baseline = 22.0  
        safe_pe_val = max(min(pe_val, 30.0), 15.0) 
        
        mu_multiplier = pe_baseline / safe_pe_val
        vol_multiplier = 1.0 + (mdd_pct / 100.0) + (max(safe_pe_val - 24.0, 0) / 40.0)

        adj_atk_mu = 0.24 * mu_multiplier
        adj_cor_mu = 0.14 * ((mu_multiplier + 1.0) / 2)
        
        default_mu = (w_atk * adj_atk_mu) + (w_cor * adj_cor_mu) + (w_def * 0.08) + (w_amo * 0.04)
        default_vol = ((w_atk * 0.40) + (w_cor * 0.22) + (w_def * 0.12) + (w_amo * 0.03)) * vol_multiplier
        
        st.markdown(f"🧠 **AI 引擎自動判定**：大盤目前 P/E 為 `{pe_val}` (基準為 22.0)。系統已為您客觀計算出：")
        st.markdown(f"- 預期報酬率乘數：`{mu_multiplier:.2f}` 倍 (不過度悲觀，保留 AI 動能)")
        st.markdown(f"- 波動率風險乘數：`{vol_multiplier:.2f}` 倍")
        
        st.divider()
        c_mu, c_vol = st.columns(2)
        port_mu = c_mu.slider("最佳化投資組合 年化報酬率 (CAGR)", min_value=0.0, max_value=0.40, value=float(default_mu), step=0.01, format="%.2f")
        port_vol = c_vol.slider("最佳化投資組合 年化波動率 (Volatility)", min_value=0.05, max_value=0.50, value=float(default_vol), step=0.01, format="%.2f")
    
    mc_years = st.slider("🕰️ 選擇推演時間軸 (Years)", min_value=1, max_value=20, value=5, step=1)
    
    if st.button("🚀 啟動 10,000 次真實淨資產推演", type="primary"):
        with st.spinner(f"正在運算未來 {mc_years} 年的 10,000 種可能性..."):
            np.random.seed(42) 
            num_simulations = 10000
            steps = mc_years * 12 # 每月結算
            dt = 1 / 12
            
            Z = np.random.normal(0, 1, (steps, num_simulations))
            drift = (port_mu - 0.5 * port_vol**2) * dt
            diffusion = port_vol * np.sqrt(dt) * Z
            daily_returns = np.exp(drift + diffusion)
            
            price_paths = np.zeros_like(daily_returns)
            price_paths[0] = total_assets
            for t in range(1, steps):
                price_paths[t] = price_paths[t-1] * daily_returns[t]
                
            true_net_paths = price_paths - loan_amount - mortgage_loan - personal_loan
            
            margin_call_threshold = loan_amount * 1.3
            ruin_paths = np.any(price_paths < margin_call_threshold, axis=0)
            ruin_prob = np.mean(ruin_paths) * 100
            
            final_true_net_assets = true_net_paths[-1, ~ruin_paths]
            
            if len(final_true_net_assets) > 0:
                p05 = np.percentile(final_true_net_assets, 5)
                p50 = np.percentile(final_true_net_assets, 50)
                p95 = np.percentile(final_true_net_assets, 95)
            else:
                p05 = p50 = p95 = 0

            sample_paths = true_net_paths[:, np.random.choice(num_simulations, 100, replace=False)]
            time_axis = np.linspace(0, mc_years, steps)
            
            fig = go.Figure()
            for i in range(100):
                fig.add_trace(go.Scatter(x=time_axis, y=sample_paths[:, i], mode='lines', line=dict(color='rgba(135, 206, 250, 0.1)'), showlegend=False))
            
            median_path = np.median(true_net_paths, axis=1)
            fig.add_trace(go.Scatter(x=time_axis, y=median_path, mode='lines', line=dict(color='#FFD700', width=3), name='中位數預期'))
            fig.add_trace(go.Scatter(x=[0, mc_years], y=[true_net_assets, true_net_assets], mode='lines', line=dict(color='#FF4B4B', width=2, dash='dash'), name='目前真實淨資產起點'))
            
            fig.update_layout(title=f"未來 {mc_years} 年【真實淨資產】推演 (抽樣 100 條路徑)", xaxis_title="年度", yaxis_title="真實淨資產 (台幣)", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("📊 家族傳承真實財富報告")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric(f"💀 質押斷頭機率", f"{ruin_prob:.2f}%", help="未來任一月份券商維持率跌破 130% 的機率")
            r2.metric(f"⛈️ 最差 5% 真實財富", f"${p05:,.0f}", help="運氣極差情況下扣除所有負債後的剩餘淨值")
            r3.metric(f"⛅ 中位數 真實財富", f"${p50:,.0f}", help="最有可能發生的真實財富落點")
            r4.metric(f"☀️ 最佳 5% 真實財富", f"${p95:,.0f}", help="AI 超級週期延續情況下的真實財富")
            
            if ruin_prob > 5.0:
                st.error("⚠️ **風險警告：** 您的斷頭機率高於 5%。建議調降質押借款，或增加防禦配置，再重新推演。")
            else:
                st.success("✅ **系統評估：** 您的投資組合抗壓性極佳，請安心享受時間複利。")

# --- 9. 🆕 Tab 5：系統年度校準與診斷 (Calibration Room) ---
with tab5:
    st.title("⚖️ 系統校準與診斷 (Calibration Room)")
    st.markdown("自動比對雲端保險箱內的歷史軌跡，進行系統自我診斷與參數微調建議。建議每季檢視一次。")

    if os.path.exists(HISTORY_FILE):
        df_hist = pd.read_csv(HISTORY_FILE)
        if len(df_hist) >= 2:
            # 確保 'True_Net_Assets' 存在 (相容舊版 CSV)
            if 'True_Net_Assets' not in df_hist.columns:
                df_hist['True_Net_Assets'] = df_hist['Net_Assets'] if 'Net_Assets' in df_hist.columns else df_hist['Total_Assets']
                
            df_hist['Date'] = pd.to_datetime(df_hist['Date'])
            df_hist = df_hist.sort_values('Date')

            # 繪製歷史軌跡圖
            fig_hist = px.line(df_hist, x='Date', y='True_Net_Assets', title="💎 真實淨資產歷史軌跡 (依據存檔紀錄)", markers=True)
            fig_hist.update_layout(template="plotly_dark", yaxis_title="真實淨資產")
            st.plotly_chart(fig_hist, use_container_width=True)

            # 運算績效指標
            start_date = df_hist['Date'].iloc[0]
            end_date = df_hist['Date'].iloc[-1]
            days_passed = (end_date - start_date).days
            start_assets = df_hist['True_Net_Assets'].iloc[0]
            end_assets = df_hist['True_Net_Assets'].iloc[-1]

            if days_passed > 0 and start_assets > 0:
                annualized_return = ((end_assets / start_assets) ** (365 / days_passed)) - 1
            else:
                annualized_return = 0

            st.subheader("🕵️‍♂️ 系統歷史績效診斷")
            c1, c2, c3 = st.columns(3)
            c1.metric("歷史追蹤期間", f"{days_passed} 天")
            c2.metric("期間淨資產變化", f"${end_assets - start_assets:+,.0f}")
            c3.metric("換算年化報酬率 (CAGR)", f"{annualized_return*100:.2f}%")

            st.divider()

            st.markdown("### 🛠️ 動態參數校準建議")
            
            # 診斷 1: 實際報酬率檢驗
            st.markdown("#### 1. 成長動能檢測")
            if days_passed < 90:
                st.info("ℹ️ **樣本數不足**：追蹤時間未滿一季 (90天)，目前的年化報酬率可能因短期波動失真，請繼續累積存檔紀錄。")
            else:
                if annualized_return < 0.05:
                    st.warning("⚠️ **動能遲緩警告**：過去年化報酬低於 5%。請檢查 00675L 是否因長期盤整產生嚴重『波動耗損』，或檢視您的摩擦成本是否過高。若確認目前為系統性熊市，請保持紀律等待復甦。")
                elif annualized_return > 0.25:
                    st.success("🔥 **超額報酬提示**：資產增長極速 (CAGR > 25%)！系統運作完美。請特別注意是否因獲利而導致『槓桿過度擴張』，並確保有確實將多餘資金鎖入 00865B 與 00713。")
                else:
                    st.info("✅ **健康巡航**：資產增長符合預期區間，請繼續保持動態擴容與波動率煞車的良好紀律。")

            # 診斷 2: 槓桿成本(質押利率)校準
            st.markdown("#### 2. 資金成本校準 ($r$)")
            st.markdown("請輸入您**目前實際**的券商質押利率。系統將評估是否會吃掉正二的逆價差紅利：")
            actual_rate = st.number_input("輸入目前實際質押年利率 (%)", value=2.5, step=0.1)
            if actual_rate > 3.0:
                st.error(f"🚨 **資金成本過高**：目前利率 {actual_rate}% 偏高。這將侵蝕您的投資組合期望值，建議尋求轉貸降息，或考慮放緩借款擴張速度。")
            else:
                st.success(f"✅ **資金成本健康**：利率 {actual_rate}% 非常優異。享有正二低成本槓桿優勢，請安心維持目前的戰略極限。")

        else:
            st.warning("⚠️ 歷史資料不足：需要至少 2 筆儲存紀錄，才能啟動趨勢診斷與校準。請在左側側邊欄點擊「儲存今日最新狀態」來累積紀錄。")
    else:
        st.warning("⚠️ 找不到歷史備份檔 (`asset_history.csv`)。系統目前無記憶，請先在左側進行第一次儲存。")
