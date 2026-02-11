import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import os
from datetime import datetime
import pytz

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="全天候戰情室", layout="wide")

# --- 2. 歷史紀錄系統 (CSV) ---
HISTORY_FILE = "asset_history.csv"

def load_last_record():
    if not os.path.exists(HISTORY_FILE): return None
    try:
        df = pd.read_csv(HISTORY_FILE)
        return df.iloc[-1] if not df.empty else None
    except: return None

def save_record(total, net, mdd, date_str):
    new_data = {"Date": [date_str], "Total_Assets": [total], "Net_Assets": [net], "MDD": [mdd]}
    new_df = pd.DataFrame(new_data)
    if not os.path.exists(HISTORY_FILE): new_df.to_csv(HISTORY_FILE, index=False)
    else: new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

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

# --- 4. 側邊欄輸入區 ---
with st.sidebar:
    st.header("📝 監控數據輸入")
    
    # A. 市場數據 & ATH 修正
    with st.expander("0. 市場位階 (ATH 修正)", expanded=True):
        col_ath1, col_ath2 = st.columns([2, 1])
        with col_ath1: st.metric("自動抓取 ATH", f"{ath_auto:,.0f}")
        with col_ath2: use_manual_ath = st.checkbox("手動修正", value=False)
            
        final_ath = st.number_input("輸入正確 ATH", value=ath_auto, step=10.0, format="%.0f") if use_manual_ath else ath_auto
        st.markdown("---")
        current_index = st.number_input("今日大盤收盤點數", value=31346.0, step=10.0, format="%.0f")
        
        mdd_pct = ((final_ath - current_index) / final_ath) * 100 if final_ath > 0 else 0.0
        st.info(f"📉 目前 MDD: {mdd_pct:.2f}% (ATH: {final_ath:,.0f})")
        
        base_exposure = st.number_input("目前基準曝險 % (Tier 1)", value=23.0, min_value=20.0, max_value=30.0, step=1.0)
        ratchet_level = int(base_exposure - 20)
        level_sign = "+" if ratchet_level > 0 else ""
        st.caption(f"ℹ️ 目前位階: {level_sign}{ratchet_level}")

    # B. 資產數據輸入
    with st.expander("1. 攻擊型資產 (正二)", expanded=True):
        c1, c2 = st.columns(2)
        p_675 = c1.number_input("00675L 價格", value=185.0, step=0.1)
        s_675 = c2.number_input("00675L 股數", value=11000, step=1000)
        c3, c4 = st.columns(2)
        p_631 = c3.number_input("00631L 價格", value=466.7, step=0.1)
        s_631 = c4.number_input("00631L 股數", value=331, step=100)
        c5, c6 = st.columns(2)
        p_670 = c5.number_input("00670L 價格", value=157.95, step=0.1)
        s_670 = c6.number_input("00670L 股數", value=616, step=100)

    with st.expander("2. 核心資產 (美股)", expanded=True):
        c1, c2 = st.columns(2)
        p_662 = c1.number_input("00662 價格", value=102.25, step=0.1)
        s_662 = c2.number_input("00662 股數", value=25840, step=100)

    with st.expander("3. 防禦資產 (現金流)", expanded=True):
        c1, c2 = st.columns(2)
        p_713 = c1.number_input("00713 價格", value=52.10, step=0.05)
        s_713 = c2.number_input("00713 股數", value=66000, step=1000)

    with st.expander("4. 子彈庫 (國庫券/債券)", expanded=True):
        c1, c2 = st.columns(2)
        p_865 = c1.number_input("00865B 價格", value=47.51, step=0.01)
        s_865 = c2.number_input("00865B 股數", value=10000, step=1000)
        c3, c4 = st.columns(2)
        p_948 = c3.number_input("00948B 價格", value=9.63, step=0.01)
        s_948 = c4.number_input("00948B 股數", value=50000, step=1000)

    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)

# --- 5. 運算引擎 ---
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
v_948 = p_948 * s_948

val_attack = v_675 + v_631 + v_670
val_core = v_662
val_defense = v_713
val_ammo = v_865 + v_948
total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

beta_weighted_sum = ((v_675*1.6) + (v_631*1.6) + (v_670*2.0) + (v_713*0.6) + (v_662*1.0) + (v_865*0.0) + (v_948*-0.1))
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 6. 讀取與儲存歷史資料 ---
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
    if st.button("💾 儲存今日資產紀錄", type="primary"):
        now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
        save_record(total_assets, net_assets, mdd_pct, now_str)
        st.success(f"已儲存！時間: {now_str}")
        st.rerun()

    if last_record is not None:
        st.caption(f"上次存檔: {last_date_str}")

# --- 7. 主畫面 (分頁系統) ---

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
        st.caption(f"ℹ️ {level_str}位階動態曝險 (基準: {base_exposure:.0f}%)")
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
            '代號': ['00675L', '00631L', '00670L', '00662', '00713', '00865B', '00948B'],
            '類別': ['攻擊', '攻擊', '攻擊', '核心', '防禦', '子彈', '子彈'],
            'Beta': [1.60, 1.60, 2.00, 1.00, 0.60, 0.00, -0.10],
            '市值': [v_675, v_631, v_670, v_662, v_713, v_865, v_948]
        }
         st.dataframe(pd.DataFrame(detail_data).style.format({"市值": "${:,.0f}", "Beta": "{:.2f}"}))

# === 分頁 2: 操作指南 ===
with tab2:
    st.title("📖 全天候系統操作指南 (SOP)")
    
    st.subheader("⚙️ 每日操作流程 (Daily Routine)")
    st.markdown("""
    1.  **資料更新 (Data Check)**
        * 確認側邊欄的 `自動抓取 ATH` 數值是否合理。若有落差，勾選「手動修正」並輸入正確數值。
        * 確認 `今日大盤收盤點數` 為最新數據。
        * 更新各類資產的 **「股數」** 與最新的 **「質押借款總額」**。
    
    2.  **儀表板判讀 (Dashboard Check)**
        * 觀察 **「戰略地圖」**：確認目前位階 (Tier) 與 目標曝險 %。
        * 檢查 **「紅綠燈訊號」**：
            * 🟢 **綠燈 (買進)**：偏離度 < -3%，且維持率健康 (>300%)。
            * 🔴 **紅燈 (賣出)**：偏離度 > +3%，需執行再平衡，將獲利轉入子彈庫。
            * 🟠 **黃燈 (風險)**：維持率 < 300% 或 負債比 > 35%，禁止加碼，優先還款。
            * ✅ **待機**：偏離度在 +/- 3% 內，不做動作，讓複利奔跑。
    
    3.  **存檔記錄 (Archive)**
        * 確認無誤後，點擊側邊欄底部的 **「💾 儲存今日資產紀錄」**。
        * 系統會自動計算與上次的資產差異。
    """)
    
    st.divider()
    
    st.subheader("🔍 核心指標深度解讀 (Metric Deep Dive)")
    
    with st.expander("1. MDD (最大回檔) 與 戰略位階 (Tier)"):
        st.markdown("""
        * **定義**：目前大盤指數距離歷史最高點 (ATH) 的跌幅百分比。
        * **作用**：用來判斷市場的「恐慌程度」。
        * **策略邏輯**：
            * **< 5% (高位)**：保持基準曝險 (Base)，不追高。
            * **5~10% (警戒)**：小幅加碼 (+5%)。
            * **10~20% (初跌)**：進入價值區，依階梯加碼。
            * **> 20% (主跌段)**：市場恐慌，此時應由子彈庫提供銀彈，大幅加碼攻擊型資產。
        """)

    with st.expander("2. Gap (偏離度) 與 閥值再平衡"):
        st.markdown("""
        * **定義**：`目前攻擊曝險` - `目標攻擊曝險` 的差值。
        * **閥值 (Threshold)**：設定為 **3%**。
        * **作用**：過濾市場雜訊，避免頻繁交易。
        * **操作**：
            * 只有當 Gap 超過 **+3%** (漲太多) 或 低於 **-3%** (跌太深) 時，才需要動手。
            * 這是一種「被動擇時」策略，強迫自己「買低賣高」。
        """)

    with st.expander("3. T值 (整戶維持率) - 生存底線"):
        st.markdown("""
        * **公式**：`總資產市值 / 質押借款金額 * 100%`
        * **券商斷頭線**：通常為 **130%** (低於此數值會被強制賣股)。
        * **本系統安全線**：**300%**。
        * **警戒線**：**250%**。一旦低於此數值，系統會亮出「紅色警戒」，此時**禁止任何買進動作**，必須優先賣出資產或補錢來償還債務，確保生存。
        """)

    with st.expander("4. U值 (質押負債比) - 槓桿天花板"):
        st.markdown("""
        * **公式**：`質押借款金額 / 總資產市值 * 100%`
        * **作用**：控制總槓桿水準。
        * **限制**：系統建議不要超過 **35%**。
        * **解讀**：負債比過高代表槓桿開太大，雖然上漲時賺很快，但下跌時維持率會掉得非常快。控制在 35% 以下是長期持有的舒適區。
        """)

    with st.expander("5. Ratchet Rule (棘輪效應) - 動態基準"):
        st.markdown("""
        * **定義**：隨著資產規模成長或對市場信心增加，逐步調高「基準曝險 (Base Exposure)」。
        * **邏輯**：
            * 基準 20% -> 0 位階
            * 基準 21% -> +1 位階
            * ...
            * 基準 30% -> +10 位階
        * **效果**：這讓整套階梯系統可以「只進不退」，當您調高基準時，所有 MDD 區間的目標曝險都會同步墊高，讓資金利用率最大化。
        """)
