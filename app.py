import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="全天候戰情室 (v7.0 基準升級)", layout="wide")
st.title("🛡️ 全天候動態曝險系統 (v7.0)")
st.caption("核心：自動 ATH + 動態基準 (Ratchet Rule) + 閥值再平衡")

# --- 2. 自動抓取 ATH 引擎 ---
@st.cache_data(ttl=3600) # 設定 1 小時快取，因為 ATH 不會頻繁變動
def get_ath_data():
    try:
        # 抓取大盤指數 (^TWII) 過去 5 年的數據
        hist = yf.Ticker("^TWII").history(period="5y")
        if not hist.empty:
            ath_price = float(hist['High'].max())
            return ath_price
    except Exception as e:
        pass
    return 32996.0 # 若抓取失敗的預設值

# 執行抓取
with st.spinner('正在連線計算歷史高點 (ATH)...'):
    ath_auto = get_ath_data()

# --- 3. 側邊欄輸入區 ---
with st.sidebar:
    st.header("📝 每日監控數據輸入")
    
    # A. 市場數據 & 基準設定
    with st.expander("0. 市場位階與基準 (Auto)", expanded=True):
        # 1. 自動顯示 ATH
        st.metric("👑 歷史最高點 (ATH)", f"{ath_auto:,.0f}", help="自動抓取過去 5 年最高點")
        
        # 2. 手動輸入今日點數
        current_index = st.number_input("今日大盤收盤點數", value=31346.0, step=10.0, format="%.0f")
        
        # 3. 計算 MDD
        if ath_auto > 0:
            mdd_pct = ((ath_auto - current_index) / ath_auto) * 100
        else:
            mdd_pct = 0.0
            
        st.info(f"📉 目前 MDD: -{mdd_pct:.2f}%")
        
        st.markdown("---")
        
        # 4. 動態基準設定 (Ratchet Rule)
        st.caption("📈 動態基準設定 (上限 30%)")
        base_exposure = st.number_input(
            "目前基準曝險 % (Tier 1)", 
            value=23.0, 
            min_value=20.0, 
            max_value=30.0, 
            step=1.0,
            help="規則：每當歷史回測達 5%，基準調高 1%。目前已調高至 23%。"
        )

    # B. 資產數據輸入
    with st.expander("1. 攻擊型資產 (正二)", expanded=True):
        st.caption("Beta: 台股 1.6 / 美股 2.0")
        col_a1, col_a2 = st.columns(2)
        p_675 = col_a1.number_input("00675L 價格", value=185.0, step=0.1)
        s_675 = col_a2.number_input("00675L 股數", value=11000, step=1000)
        
        col_b1, col_b2 = st.columns(2)
        p_631 = col_b1.number_input("00631L 價格", value=466.7, step=0.1)
        s_631 = col_b2.number_input("00631L 股數", value=331, step=100)
        
        col_c1, col_c2 = st.columns(2)
        p_670 = col_c1.number_input("00670L 價格", value=157.95, step=0.1)
        s_670 = col_c2.number_input("00670L 股數", value=616, step=100)

    with st.expander("2. 核心資產 (美股)", expanded=True):
        st.caption("Beta: 1.0")
        col_d1, col_d2 = st.columns(2)
        p_662 = col_d1.number_input("00662 價格", value=102.25, step=0.1)
        s_662 = col_d2.number_input("00662 股數", value=25840, step=100)

    with st.expander("3. 防禦資產 (現金流)", expanded=True):
        st.caption("Beta: 0.6")
        col_e1, col_e2 = st.columns(2)
        p_713 = col_e1.number_input("00713 價格", value=52.10, step=0.05)
        s_713 = col_e2.number_input("00713 股數", value=66000, step=1000)

    with st.expander("4. 子彈庫 (國庫券/債券)", expanded=True):
        st.caption("Beta: 0.0 / -0.1")
        col_f1, col_f2 = st.columns(2)
        p_865 = col_f1.number_input("00865B 價格", value=47.51, step=0.01)
        s_865 = col_f2.number_input("00865B 股數", value=10000, step=1000)
        
        col_g1, col_g2 = st.columns(2)
        p_948 = col_g1.number_input("00948B 價格", value=9.63, step=0.01)
        s_948 = col_g2.number_input("00948B 股數", value=50000, step=1000)

    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)

# --- 3. 邏輯運算引擎 ---

# A. 定義階梯策略表 (動態更新)
# 這裡將 Tier 1 的目標改為變數 base_exposure
ladder_data = [
    {"MDD區間": "< 5% (高位)", "目標曝險": base_exposure, "位階": "Tier 1 (基準)"},
    {"MDD區間": "5% ~ 10%", "目標曝險": max(28.0, base_exposure), "位階": "Tier 1-2 (警戒)"}, # 若基準升高，此層也會被墊高
    {"MDD區間": "10% ~ 25%", "目標曝險": 28, "位階": "Tier 2 (初跌)"},
    {"MDD區間": "25% ~ 40%", "目標曝險": 33, "位階": "Tier 3 (主跌)"},
    {"MDD區間": "40% ~ 50%", "目標曝險": 40, "位階": "Tier 4 (恐慌)"},
    {"MDD區間": "> 50%", "目標曝險": 50, "位階": "Tier 5 (毀滅)"},
]

# B. 判定目前位階與目標
target_attack_ratio = base_exposure # 預設為基準
current_tier_index = 0

if mdd_pct < 5.0:
    target_attack_ratio = base_exposure
    current_tier_index = 0
elif mdd_pct < 10.0:
    # 這裡邏輯：如果 MDD 在 5-10%，通常目標是 28%，但如果您的基準已經調高到 29%，那就要取 max
    target_attack_ratio = max(28.0, base_exposure) 
    current_tier_index = 1
elif mdd_pct < 25.0:
    target_attack_ratio = 28.0
    current_tier_index = 2
elif mdd_pct < 40.0:
    target_attack_ratio = 33.0
    current_tier_index = 3
elif mdd_pct < 50.0:
    target_attack_ratio = 40.0
    current_tier_index = 4
else:
    target_attack_ratio = 50.0
    current_tier_index = 5

current_tier_name = ladder_data[current_tier_index]["位階"]

# C. 計算資產數據
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

# D. 計算 Beta
beta_weighted_sum = (
    (v_675 * 1.60) + (v_631 * 1.60) + (v_670 * 2.00) +
    (v_713 * 0.60) + (v_662 * 1.00) +
    (v_865 * 0.00) + (v_948 * -0.10)
)
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0

# E. 關鍵比率
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0

# F. 再平衡計算
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 4. 儀表板顯示區 ---

# === 標題 ===
st.title("🛡️ 全天候動態曝險戰情室 (v7.0)")
st.caption("核心：自動 ATH + 動態基準 (Ratchet Rule) + 閥值再平衡")

# === 區塊一：戰略位階地圖 ===
st.header("1. 動態戰略地圖")

m1, m2, m3 = st.columns([1, 1, 2])
m1.metric("📉 目前大盤 MDD", f"-{mdd_pct:.2f}%", help="距離自動抓取的 ATH 跌幅")
m2.metric("🎯 當前目標曝險", f"{target_attack_ratio:.0f}%", help=f"位階: {current_tier_name}")

# 高亮目前的階梯表
df_ladder = pd.DataFrame(ladder_data)
def highlight_current_row(row):
    color = '#ffcccc' if row['位階'] == current_tier_name else ''
    return [f'background-color: {color}' for _ in row]

with m3:
    st.dataframe(
        df_ladder.style.apply(highlight_current_row, axis=1),
        hide_index=True,
        use_container_width=True
    )

st.divider()

# === 區塊二：投資組合核心數據 ===
st.header("2. 投資組合核心數據")

col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"淨值: ${net_assets:,.0f}")
col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}", delta="目標: 1.05 ~ 1.20", delta_color="off")

# 維持率顏色邏輯
t_val = f"{maintenance_ratio:.0f}%"
t_delta = "安全線 > 300%"
t_color = "normal"

if maintenance_ratio < 250:
    t_color = "inverse" # 紅色
    t_delta = "⛔ 已破 250% (斷頭警戒)"
elif maintenance_ratio < 300:
    t_color = "inverse" # 紅色
    t_delta = "⚠️ 未達 300% 安全值"

col3.metric("🛡️ 整戶維持率 (T)", t_val, delta=t_delta, delta_color=t_color)

# 負債比顏色邏輯
u_color = "inverse" if loan_ratio > 35 else "normal"
col4.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color=u_color)

st.divider()

# === 區塊三：閥值再平衡與甜甜圈圖 ===
st.header("3. 資產配置與指令")
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("資產配置佔比 (甜甜圈圖)")
    
    chart_data = pd.DataFrame({
        '資產類別': ['攻擊型 (正二)', '核心 (00662)', '防禦 (00713)', '子彈庫 (債券)'],
        '市值': [val_attack, val_core, val_defense, val_ammo]
    })
    
    colors = {
        '攻擊型 (正二)': '#FF4B4B', 
        '核心 (00662)': '#FFD700', 
        '防禦 (00713)': '#2E8B57', 
        '子彈庫 (債券)': '#87CEFA'
    }
    
    fig = px.pie(
        chart_data, 
        values='市值', 
        names='資產類別',
        color='資產類別',
        color_discrete_map=colors,
        hole=0.45,
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
    
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🤖 AI 戰略指令")
    
    # 風控
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
