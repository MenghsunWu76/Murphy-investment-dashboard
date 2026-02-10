import streamlit as st
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="全天候動態曝險戰情室", layout="wide")

# --- 標題區 ---
st.title("🛡️ 階梯式動態曝險系統 (Beta 1.0~1.2)")
st.caption("核心策略：MDD 階梯式加碼 + 閥值再平衡 (+/- 3%)")

# --- 側邊欄：輸入區 ---
with st.sidebar:
    st.header("📝 每日監控數據輸入")
    
    # 1. 市場數據 (用於自動決定目標比例)
    with st.expander("0. 市場位階 (計算 MDD)", expanded=True):
        st.caption("輸入大盤點數以決定目標曝險 %")
        current_index = st.number_input("今日大盤收盤點數", value=31346.0, step=10.0, format="%.1f")
        ath_index = st.number_input("歷史最高點數 (ATH)", value=32996.0, step=10.0, format="%.1f")
        
        # 計算 MDD
        if ath_index > 0:
            mdd_pct = ((ath_index - current_index) / ath_index) * 100
        else:
            mdd_pct = 0.0
        
        st.info(f"📉 目前 MDD: -{mdd_pct:.2f}%")

    # 2. 攻擊型資產
    with st.expander("1. 攻擊型資產 (正二)", expanded=True):
        st.caption("Beta: 台股 1.6 / 美股 2.0")
        col_a1, col_a2 = st.columns(2)
        p_675 = col_a1.number_input("00675L 價格", value=185.00, step=0.1)
        s_675 = col_a2.number_input("00675L 股數", value=11000, step=1000)
        
        col_b1, col_b2 = st.columns(2)
        p_631 = col_b1.number_input("00631L 價格", value=466.70, step=0.1)
        s_631 = col_b2.number_input("00631L 股數", value=331, step=100)
        
        col_c1, col_c2 = st.columns(2)
        p_670 = col_c1.number_input("00670L 價格", value=157.95, step=0.1)
        s_670 = col_c2.number_input("00670L 股數", value=616, step=100)

    # 3. 核心資產
    with st.expander("2. 核心資產 (美股)", expanded=True):
        st.caption("Beta: 1.0")
        col_d1, col_d2 = st.columns(2)
        p_662 = col_d1.number_input("00662 價格", value=102.25, step=0.1)
        s_662 = col_d2.number_input("00662 股數", value=25840, step=100)

    # 4. 防禦資產
    with st.expander("3. 防禦資產 (現金流)", expanded=True):
        st.caption("Beta: 0.6")
        col_e1, col_e2 = st.columns(2)
        p_713 = col_e1.number_input("00713 價格", value=52.10, step=0.05)
        s_713 = col_e2.number_input("00713 股數", value=66000, step=1000)

    # 5. 子彈庫
    with st.expander("4. 子彈庫 (債券)", expanded=True):
        st.caption("Beta: 0.0 / -0.1")
        col_f1, col_f2 = st.columns(2)
        p_865 = col_f1.number_input("00865B 價格", value=47.51, step=0.01)
        s_865 = col_f2.number_input("00865B 股數", value=10000, step=1000)
        
        col_g1, col_g2 = st.columns(2)
        p_948 = col_g1.number_input("00948B 價格", value=9.63, step=0.01)
        s_948 = col_g2.number_input("00948B 股數", value=50000, step=1000)

    # 6. 負債
    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)
    
    st.info("💡 數據輸入完畢後，右側儀表板會自動運算")

# --- 核心運算引擎 ---

# 1. 計算個別市值
v_675 = p_675 * s_675
v_631 = p_631 * s_631
v_670 = p_670 * s_670
v_662 = p_662 * s_662
v_713 = p_713 * s_713
v_865 = p_865 * s_865
v_948 = p_948 * s_948

# 2. 類別市值彙整
val_attack = v_675 + v_631 + v_670
val_core = v_662
val_defense = v_713
val_ammo = v_865 + v_948

# 3. 總資產與淨值
total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

# 4. Beta 貢獻值計算 (依據您提供的圖片定義)
# 00675L/631L: 1.60, 00670L: 2.00, 00662: 1.00, 00713: 0.60, 00865B: 0.00, 00948B: -0.10
beta_weighted_sum = (
    (v_675 * 1.60) +
    (v_631 * 1.60) +
    (v_670 * 2.00) +
    (v_662 * 1.00) +
    (v_713 * 0.60) +
    (v_865 * 0.00) +
    (v_948 * -0.10)
)
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0

# 5. 關鍵比率計算
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0

# 6. 決定「目標攻擊曝險 %」 (動態階梯邏輯)
# 邏輯來源：MDD < 10% -> 23% | 10-25% -> 28% | 25-40% -> 33% | >40% -> 40%~50%
if mdd_pct < 10.0:
    target_attack_ratio = 23.0
    tier_status = "🟢 高位震盪區 (基準 23%)"
elif mdd_pct < 25.0:
    target_attack_ratio = 28.0
    tier_status = "🟡 初跌段 (加碼至 28%)"
elif mdd_pct < 40.0:
    target_attack_ratio = 33.0
    tier_status = "🟠 主跌段 (加碼至 33%)"
else:
    target_attack_ratio = 40.0
    tier_status = "🔴 恐慌區 (加碼至 40%+)"

# 7. 閥值再平衡計算
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0 # 您設定的 +/- 3%

# --- 儀表板顯示區 ---

# === 第一排：核心財務指標 ===
col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 資產總市值 (I)", f"${total_assets:,.0f}", delta=f"淨值: ${net_assets:,.0f}")
col2.metric("📉 整體 Beta 值", f"{portfolio_beta:.2f}", delta="目標: 1.0 ~ 1.2", delta_color="off")

# 維持率警示顏色
t_color = "normal"
if maintenance_ratio < 250: t_color = "inverse"
col3.metric("🛡️ 整戶維持率 (T)", f"{maintenance_ratio:.0f}%", delta="安全線 > 250%", delta_color=t_color)

# 負債比警示顏色
l_color = "normal"
if loan_ratio > 35: l_color = "inverse"
col4.metric("💳 質押負債比 (U)", f"{loan_ratio:.1f}%", delta="安全線 < 35%", delta_color=l_color)

st.divider()

# === 第二排：閥值再平衡監控 (核心功能) ===
st.subheader("⚖️ 閥值再平衡監控 (Rebalancing Monitor)")

# 顯示目前的位階狀態
st.info(f"📍 目前市場位階：**{tier_status}** (MDD: -{mdd_pct:.2f}%)")

m1, m2, m3, m4 = st.columns(4)

m1.metric("⚡ 即時攻擊比例", f"{current_attack_ratio:.2f}%")
m2.metric("🎯 目標攻擊比例", f"{target_attack_ratio:.0f}%", help="依據 MDD 自動調整")

# 偏離度 (Gap)
gap_color = "off"
if abs(gap) > threshold: gap_color = "inverse" # 超過 3% 亮紅燈
m3.metric("📏 偏離度 (Gap)", f"{gap:+.2f}%", delta=f"容許範圍 +/- {threshold}%", delta_color=gap_color)

# 動作建議 (Action)
action_text = "HOLD (持有)"
action_color = "gray"
if gap > threshold:
    action_text = "SELL (賣出)"
    action_color = "red"
elif gap < -threshold:
    action_text = "BUY (買進)"
    action_color = "green"

m4.markdown(f"""
    <div style="text-align: center;">
        <p style="margin-bottom: 0px; color: gray;">系統指令</p>
        <h2 style="color: {action_color}; margin-top: 0px;">{action_text}</h2>
    </div>
""", unsafe_allow_html=True)

# 顯示具體的買賣建議金額
if gap > threshold:
    sell_amount = val_attack - (total_assets * target_attack_ratio / 100)
    st.warning(f"🔴 **觸發賣出訊號！** 攻擊比例過高。\n\n建議操作：賣出約 **${sell_amount:,.0f}** 的正二資產，轉入子彈庫。")
elif gap < -threshold:
    buy_amount = (total_assets * target_attack_ratio / 100) - val_attack
    st.success(f"🟢 **觸發買進訊號！** 攻擊比例過低。\n\n建議操作：動用子彈庫約 **${buy_amount:,.0f}**，買進正二資產。")
else:
    st.success("✅ **系統平衡中**。無需操作，讓複利奔跑。")

st.divider()

# === 第三排：資產分布視覺化 ===
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("資產配置分布")
    chart_data = pd.DataFrame({
        '類別': ['攻擊型 (正二)', '核心 (00662)', '防禦 (00713)', '子彈庫 (債券)'],
        '市值': [val_attack, val_core, val_defense, val_ammo]
    })
    st.bar_chart(chart_data, x='類別', y='市值', color="#FF4B4B")

with c2:
    st.subheader("📊 詳細數據表")
    detail_data = {
        '代號': ['00675L/631L', '00670L', '00662', '00713', '00865B', '00948B'],
        '市值': [v_675+v_631, v_670, v_662, v_713, v_865, v_948],
        'Beta': [1.60, 2.00, 1.00, 0.60, 0.00, -0.10]
    }
    st.dataframe(pd.DataFrame(detail_data).style.format({"市值": "${:,.0f}", "Beta": "{:.2f}"}))
