import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import os
from datetime import datetime
import pytz

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="A.D.E.I.S 雲端戰情室 (v19.0)", layout="wide")

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
        st.link_button("🔗 查詢證交所官方 P/E", "https://www.twse.com.tw/zh/page/trading/exchange/BWIBBU_d.html")
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

# --- 7. [New] 雲端保險箱 (備份與還原) ---
with st.sidebar:
    st.markdown("---")
    st.subheader("💾 雲端保險箱 (資料備份區)")
    
    # 上傳功能：若雲端重啟遺失資料，用此按鈕恢復
    uploaded_file = st.file_uploader("📤 1. 恢復記憶 (上傳歷史 CSV)", type=["csv"], help="若點擊上方載入無反應，請先上傳您電腦裡的備份檔。")
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file)
            df_upload.to_csv(HISTORY_FILE, index=False)
            st.success("✅ 記憶已恢復！請點擊最上方「📂 載入線上最新數據」")
        except Exception as e:
            st.error(f"上傳失敗: {e}")

    # 儲存功能：存入雲端暫存檔
    if st.button("💾 2. 儲存今日最新狀態", type="primary"):
        now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
        save_data = {
            "Date": now_str, "Total_Assets": total_assets, "Net_Assets": net_assets,
            "MDD": mdd_pct, "Current_Index": current_index, "ATH": final_ath, "PE_Ratio": pe_val,
            "P_00675": p_675, "P_00631": p_631, "P_00670": p_670, "P_00662": p_662, "P_00713": p_713, "P_00865": p_865,
            "S_00675": s_675, "S_00631": s_631, "S_00670": s_670, "S_00662": s_662, "S_00713": s_713, "S_00865": s_865
        }
        save_record(save_data)
        st.success(f"已儲存至雲端！時間: {now_str}")
        st.rerun()
    
    # 下載功能：強迫把雲端資料載回本機保管
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "rb") as f:
            csv_bytes = f.read()
        st.download_button(
            label="📥 3. 下載最新備份 (存入本機)",
            data=csv_bytes,
            file_name=f"ADEIS_Backup_{datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="⚠️ 儲存後，務必點擊此按鈕將檔案下載到您的電腦妥善保管！"
        )
        st.caption(f"線上最後存檔: {last_date_str}")

# --- 8. 主畫面 ---
tab1, tab2, tab3 = st.tabs(["📊 戰情室 Dashboard", "📖 雲端版操作指南", "🚀 選擇權戰情室 (TXO)"])

with tab1:
    st.subheader("1. 動態戰略地圖")
    m1, m2, m3, m4 = st.columns([1, 1, 1, 2])
    m1.metric("📉 目前大盤 MDD", f"{mdd_pct:.2f}%", help=f"計算基準 ATH: {final_ath:,.0f}")
    m2.metric("⚡ 目前攻擊曝險", f"{current_attack_ratio:.2f}%", delta=f"{gap:+.2f}% (偏離)", delta_color="inverse" if abs(gap)>3.0 else "off")
    m3.metric("🎯 當前目標曝險", f"{target_attack_ratio:.0f}%", help=f"位階: {current_tier_name}")
    
    df_ladder = pd.DataFrame(ladder_data)
    def highlight_current_row(row): return ['background-color: #ffcccc' if row['位階'] == current_tier_name else '' for _ in row]
    with m4:
        st.caption(f"ℹ️ 策略引擎: MDD 階梯 (參考 P/E: {pe_val})")
        st.dataframe(df_ladder.style.apply(highlight_current_row, axis=1).format({"目標曝險": "{:.0f}%"}), hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("2. 💰 資金水位與額度試算 (Liquidity Check)")
    liq_c1, liq_c2, liq_c3 = st.columns(3)
    liq_c1.metric("🛡️ 戰略限額 (Kelly)", f"{safe_leverage_limit}%")
    liq_c1.progress(min(real_leverage_ratio / safe_leverage_limit, 1.0), text=f"目前使用率: {real_leverage_ratio:.1f}%")
    
    liq_c2.metric("🏦 券商限額 (U<35%)", f"$ {max_loan_broker:,.0f}")
    liq_c2.progress(min(loan_amount / max_loan_broker if max_loan_broker > 0 else 0, 1.0), text=f"目前借款: $ {loan_amount:,.0f}")
    
    if recommendation_action == "REDUCE":
        liq_c3.metric("⚠️ 建議減碼 (去槓桿)", f"- $ {recommendation_amount/2:,.0f}", "若賣正二(2x)所需金額", delta_color="inverse")
    else:
        liq_c3.metric("✅ 可動用額度 (加碼)", f"+ $ {recommendation_amount:,.0f}", "買入正二(2x)之最大金額", delta_color="normal")

    st.divider()
    st.subheader("3. 投資組合核心數據")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"${diff_total:,.0f}")
    col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}")
    col3.metric("⚙️ 實質槓桿率", f"{real_leverage_ratio:.1f}%", delta="⚠️ 超速" if real_leverage_ratio > safe_leverage_limit else "✅ 安全", delta_color="inverse" if real_leverage_ratio > safe_leverage_limit else "normal")
    col4.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 300%", delta_color="inverse" if maintenance_ratio < 300 else "normal")
    col5.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color="inverse" if loan_ratio > 35 else "normal")

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
        if real_leverage_ratio > safe_leverage_limit: risk_msgs.append(f"⚠️ 槓桿 ({real_leverage_ratio:.1f}%) 超標")

        if maintenance_ratio < 250: st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，賣股還債。")
        elif len(risk_msgs) > 0:
            st.warning(f"🟠 **風險提示**\n\n{chr(10).join(risk_msgs)}\n\n**指令：禁止加碼，考慮減碼。**")
        else:
            if gap > 3.0: st.warning(f"🔴 **賣出訊號** (+{gap:.1f}%)\n賣出：${val_attack - (total_assets * target_attack_ratio / 100):,.0f} 轉入子彈庫")
            elif gap < -3.0: st.success(f"🟢 **買進訊號** ({gap:.1f}%)\n動用：${(total_assets * target_attack_ratio / 100) - val_attack:,.0f} 買進正二")
            else: st.success(f"✅ **系統待機**\n財務健康且無偏離。\n目前偏離度: {gap:+.2f}%")

with tab2:
    st.title("📖 雲端版專屬操作指南 (SOP)")
    st.markdown("""
    ### ⚠️ 雲端備份鐵則 (極度重要)
    雲端伺服器 (如 Streamlit Cloud) 的暫存空間可能會因為長時間閒置而重啟清空。因此，**您的電腦才是最終的金庫**。
    
    ### 🔄 日常操作 4 步驟：
    1. **喚醒記憶 (若需要)**：打開網頁，若點擊「載入線上最新數據」發現沒資料，請點擊左側 **「📤 1. 恢復記憶」**，把您電腦裡的 `ADEIS_Backup.csv` 上傳進去。
    2. **更新與檢查**：輸入今天的 P/E、股價，檢查儀表板的燈號與額度。
    3. **存檔**：點擊 **「💾 2. 儲存今日最新狀態」**，讓系統計算並記下這筆歷史。
    4. **下載入庫 (必做)**：儲存完後，**立刻點擊「📥 3. 下載最新備份」**！將這個 `.csv` 檔案存入您的 Mac 或 iCloud 資料夾，作為最新的防護備份。
    """)

with tab3:
    st.title("🚀 選擇權每週戰情室 (TXO Weekly)")
    delta_safety_dist = current_index * 0.025
    txo_strategy, txo_title, txo_desc = "WAIT", "❌ 戰略停火", "目前估值偏低，應全力做多正二現貨，避免賣 Put 風險。"
    
    if pe_val >= 24.0:
        txo_strategy, txo_title, txo_desc = "BEAR_CALL", "🐻 Bear Call Spread (高空收租)", "P/E 昂貴。預期大盤上檔受限，賣出上方買權收取時間價值。"
        sell_strike, buy_strike = round((current_index + delta_safety_dist) / 100) * 100, round((current_index + delta_safety_dist) / 100) * 100 + 500
    elif pe_val >= 21.0:
        txo_strategy, txo_title, txo_desc = "BULL_PUT", "🐂 Bull Put Spread (低檔收租)", "P/E 合理。趨勢穩健，賣出下方賣權收取權利金。"
        sell_strike, buy_strike = round((current_index - delta_safety_dist) / 100) * 100, round((current_index - delta_safety_dist) / 100) * 100 - 500
    
    st.subheader("🔢 口數建議 (Position Sizing)")
    txo_contract_val = current_index * 50
    coverage_ratio = st.slider("設定資產覆蓋率 (Hedge Ratio)", 10, 60, 30, 10)
    suggested_lots = int((total_assets * (coverage_ratio / 100)) / txo_contract_val)
    
    col_lots1, col_lots2 = st.columns(2)
    col_lots1.metric("🛡️ 建議操作口數", f"{suggested_lots} 組")
    col_lots2.metric("💰 曝險總值", f"${suggested_lots * txo_contract_val:,.0f}")
    
    st.divider()
    if txo_strategy != "WAIT":
        st.subheader(f"🎯 本週建議策略：{txo_title}")
        st.info(txo_desc)
        c1, c2, c3 = st.columns(3)
        c1.metric("1. 賣出 (Sell)", f"{sell_strike}")
        c2.metric("2. 買進 (Buy)", f"{buy_strike}")
        c3.metric("預估 Delta", "~ 0.20")
    else:
        st.subheader(f"🛑 本週建議：{txo_title}")
        st.warning(txo_desc)
