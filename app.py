import streamlit as st
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="全天候動態曝險戰情室", layout="wide")

# --- 標題區 ---
st.title("🛡️ 階梯式動態曝險系統 (Beta 1.0~1.2)")
st.caption("目標：長期存活並獲取超額報酬 | 核心：MDD 階梯加碼 + 閥值再平衡")

# --- 側邊欄：最新數據輸入 ---
with st.sidebar:
    st.header("📝 今日收盤數據輸入")
    
    st.subheader("1. 攻擊型資產 (正二)")
    price_00675L = st.number_input("00675L 現價", value=180.0, step=0.5)
    shares_00675L = st.number_input("00675L 股數", value=11000, step=1000)
    
    st.subheader("2. 核心資產 (美股)")
    price_00662 = st.number_input("00662 現價", value=102.1, step=0.1)
    shares_00662 = st.number_input("00662 股數", value=25840, step=100)
    
    st.subheader("3. 防禦資產 (現金流)")
    price_00713 = st.number_input("00713 現價", value=51.95, step=0.05)
    shares_00713 = st.number_input("00713 股數", value=66000, step=1000)
    
    st.subheader("4. 子彈庫 (國庫券)")
    # 因為債券通常直接看總市值比較直觀，這裡讓您直接輸入總金額
    val_00865B = st.number_input("00865B 總市值 (元)", value=475700, step=10000)
    
    st.subheader("5. 負債監控")
    loan_amount = st.number_input("目前質押借款總額 (O)", value=2350000, step=10000)
    
    st.info("💡 輸入完畢後，右側儀表板會自動更新")

# --- 核心計算引擎 ---
# 計算各資產市值
val_00675L = price_00675L * shares_00675L
val_00662 = price_00662 * shares_00662
val_00713 = price_00713 * shares_00713

# 總資產與淨值
total_assets = val_00675L + val_00662 + val_00713 + val_00865B
net_assets = total_assets - loan_amount

# 計算權重 (Weight)
w_675 = val_00675L / total_assets
w_662 = val_00662 / total_assets
w_713 = val_00713 / total_assets
w_865 = val_00865B / total_assets

# 計算組合 Beta (根據您的設定)
# 00675L: 1.6, 00662: 1.0, 00713: 0.6, 00865B: 0.0
portfolio_beta = (w_675 * 1.6) + (w_662 * 1.0) + (w_713 * 0.6) + (w_865 * 0.0)

# 計算維持率與負債比
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100

# 攻擊佔比 (用於閥值再平衡)
attack_ratio = w_675 * 100

# --- 儀表板顯示區 ---

# 第一排：關鍵指標 (KPIs)
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    label="💰 資產總市值 (I)",
    value=f"${total_assets:,.0f}",
    delta=f"淨值: ${net_assets:,.0f}"
)

col2.metric(
    label="📉 整體 Beta 值",
    value=f"{portfolio_beta:.2f}",
    delta="目標: 1.0 ~ 1.2",
    delta_color="off"
)

# 設定維持率顏色邏輯
t_color = "normal"
if maintenance_ratio < 250: t_color = "inverse"

col3.metric(
    label="🛡️ 整戶維持率 (T)",
    value=f"{maintenance_ratio:.0f}%",
    delta=f"安全線 > 250%",
    delta_color=t_color
)

col4.metric(
    label="📊 攻擊資產佔比",
    value=f"{attack_ratio:.1f}%",
    delta="閥值: 26% (賣出)",
    delta_color="off"
)

st.divider()

# 第二排：圖表與操作指令
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("資產配置可視化")
    # 準備圖表資料
    chart_df = pd.DataFrame({
        '資產類別': ['攻擊 (正二)', '核心 (00662)', '防禦 (00713)', '子彈 (00865B)'],
        '金額': [val_00675L, val_00662, val_00713, val_00865B],
        'Beta貢獻': [w_675*1.6, w_662*1.0, w_713*0.6, 0]
    })
    
    # 顯示長條圖
    st.bar_chart(chart_df, x='資產類別', y='金額', color=["#FF4B4B"])
    
    # 顯示詳細數據表
    with st.expander("查看詳細數據表"):
        st.dataframe(chart_df.style.format({"金額": "${:,.0f}", "Beta貢獻": "{:.2f}"}))

with c2:
    st.subheader("🤖 系統操作指令 (Action)")
    
    # === 核心邏輯判斷區 ===
    
    # 1. 檢查安全閥 (維持率)
    if maintenance_ratio < 250:
        st.error(f"⚠️ **紅色警報 (防守)**\n\n維持率低於 250%！\n\n**指令：**\n1. 禁止任何加碼。\n2. 優先用現金流或賣出資產還款。")
    
    # 2. 檢查是否需要賣出 (閥值再平衡)
    elif attack_ratio > 26:
        st.warning(f"🔴 **賣出訊號 (閥值再平衡)**\n\n攻擊佔比已達 {attack_ratio:.1f}% (超過 26%)。\n\n**指令：**\n1. 賣出部分 00675L。\n2. 資金轉入 00865B 子彈庫。")
    
    # 3. 檢查是否需要加碼 (假設 MDD 邏輯需人工判斷大盤，這裡做簡單提示)
    else:
        st.success(f"🟢 **系統待機 (Hold)**\n\n目前各項指標健康。\n\n**指令：**\n持續持有，讓時間複利運作。\n\n*(若大盤 MDD > 10% 且維持率健康，可手動加碼正二)*")

    st.markdown("---")
    st.write(f"**質押負債比 (U):** {loan_ratio:.1f}%")
    if loan_ratio < 35:
        st.caption("✅ 負債比健康 (低於 35%)")
    else:
        st.caption("❌ 負債比過高，請注意！")
