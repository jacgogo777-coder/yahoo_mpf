import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import mplfinance.original_flavor as mpf
import pandas as pd
import numpy as np
import os
import hmac
from matplotlib import font_manager

st.set_page_config(
    page_title="2026 股市 AI 紅綠燈多空指標分析系統",
    page_icon="📈",
    layout="wide"
)

# 安全讀取 st.secrets 設定
def get_secret(key, default_val=None):
    """安全取得 Streamlit Secrets，若不存在則回傳預設值。"""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default_val

def password_required():
    """只有輸入 Streamlit Secrets 中的密碼後，才允許顯示主頁。"""
    if st.session_state.get("authenticated", False):
        return True

    expected_password = str(get_secret("APP_PASSWORD", ""))

    if not expected_password:
        st.error("⚠️ 尚未設定登入密碼！請在 Streamlit Cloud 平台的 Secrets（或本地 `.streamlit/secrets.toml`）中加入 `APP_PASSWORD`。")
        st.code('APP_PASSWORD = "你的自訂密碼"', language="toml")
        return False

    st.title("🔐 2026 股市 AI 紅盤實作專案")
    st.caption("請輸入系統密碼以進入分析主頁。")

    with st.form("login_form", clear_on_submit=True):
        entered_password = st.text_input(
            "密碼",
            type="password",
            placeholder="請輸入存取密碼",
        )
        submitted = st.form_submit_button("登入", use_container_width=True)

    if submitted:
        if hmac.compare_digest(entered_password, expected_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤，請重新輸入。")

    return False


if not password_required():
    st.stop()

# 側邊欄登出按鈕
if st.sidebar.button("🔒 登出系統", use_container_width=True):
    st.session_state["authenticated"] = False
    st.rerun()

# 處理中文字型 (解決雲端 Linux 與本機亂碼問題)
font_path = "NotoSansTC-Regular.ttf"
if os.path.exists(font_path):
    font_manager.fontManager.addfont(font_path)
    prop = font_manager.FontProperties(fname=font_path)
    plt.rcParams['font.sans-serif'] = [prop.get_name()]
else:
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'DejaVu Sans', 'sans-serif']

plt.rcParams['axes.unicode_minus'] = False

st.title("📊 股市 AI 紅綠燈多空指標分析系統")
st.markdown("""
本系統結合專業技術指標運算與**多空紅綠燈診斷模型**：
- 🔴 **紅燈 (看多 / +1 分)**：偏多訊號、黃金交叉、均線支撐或超賣底部反彈。
- 🟢 **綠燈 (看空 / -1 分)**：偏空訊號、死亡交叉、均線反壓或超買過熱修正。
- 🟡 **黃燈 (中立 / 0 分)**：盤整無明確方向或處於中性區間。
""")

st.sidebar.header("⚙️ 參數設定")

# 讀取 Secrets 預設值或預設備援值
secret_default_stock = str(get_secret("DEFAULT_STOCK", "2330.TW"))
secret_warmup = int(get_secret("WARMUP_DAYS", 60))

stock_id = st.sidebar.text_input("股票代號", value=secret_default_stock)

# 預設觀測日期區間
default_start = datetime(2025, 11, 19).date()
default_end = datetime(2026, 5, 22).date()

target_start = st.sidebar.date_input("觀測起始日", default_start)
target_end = st.sidebar.date_input("觀測結束日", default_end)
warmup_days = st.sidebar.slider("指標預熱天數 (用於 EMA/RSI 準確度)", 30, 100, secret_warmup)

# 側邊欄狀態診斷 (字型與 Secrets)
with st.sidebar.expander("🔐 Secrets 與系統狀態"):
    if os.path.exists(font_path):
        st.success("✅ 已載入 NotoSansTC 中文字型")
    else:
        st.warning("⚠️ 使用系統預設中文字型")

    try:
        if hasattr(st, "secrets") and len(st.secrets.keys()) > 0:
            st.success(f"✅ 已讀取 Secrets 設定項：{', '.join(st.secrets.keys())}")
        else:
            st.info("ℹ️ 目前使用預設參數（未偵測到 secrets.toml）")
    except Exception:
        st.info("ℹ️ 目前使用預設參數（未偵測到 secrets.toml）")

st.header("Step 1: 資料獲取與預熱處理")
with st.expander("📖 為什麼需要預熱資料？"):
    st.write("""
    - **預熱機制 (Warm-up)**：EMA、MACD 與 RSI 都是具備「延續性」的指標。如果直接從觀測日開始計算，初始值會產生嚴重的偏差。
    - 本程式自動向前抓取（預設 60 天）的資料進行「預熱」計算，確保在進入使用者選定的觀測區間時，所有指標已趨於穩定準確。
    - **避免格式錯誤**：強制將日期轉為 `YYYY-MM-DD` 格式再向 Yahoo Finance 請求，確保網頁一開啟就能正確載入資料。
    """)

@st.cache_data(show_spinner=False)
def load_stock_data(symbol, start_dt, end_dt, warmup):
    fetch_start = start_dt - timedelta(days=warmup)
    start_str = fetch_start.strftime('%Y-%m-%d')
    end_str = end_dt.strftime('%Y-%m-%d')
    
    df = yf.download(symbol, start=start_str, end=end_str, auto_adjust=False, progress=False)
    
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

with st.spinner('正在獲取股票歷史行情數據...'):
    df_all = load_stock_data(stock_id, target_start, target_end, warmup_days)

if df_all.empty:
    st.error("❌ 找不到該標的行情資料，請檢查股票代號（台股如 2330.TW，美股如 AAPL）或網路連線。")
    st.stop()

st.header("Step 2: 6 大技術指標運算 (Technical Math)")

with st.spinner('計算技術指標中 (SMA, BBands, KDJ, OBV, MACD, RSI, BIAS)...'):
    df_calc = df_all.copy()
    
    # 1. SMA 均線與布林通道 (BBands)
    df_calc['SMA_5'] = df_calc['Close'].rolling(window=5).mean()
    df_calc['SMA_10'] = df_calc['Close'].rolling(window=10).mean()
    df_calc['SMA_20'] = df_calc['Close'].rolling(window=20).mean()
    df_calc['std_dev'] = df_calc['Close'].rolling(window=20).std()
    df_calc['upper_band'] = df_calc['SMA_20'] + (df_calc['std_dev'] * 2)
    df_calc['lower_band'] = df_calc['SMA_20'] - (df_calc['std_dev'] * 2)

    # 2. KDJ 指標 (9日 RSV + EWM 平滑)
    n = 9
    low_min = df_calc['Low'].rolling(window=n).min()
    high_max = df_calc['High'].rolling(window=n).max()
    df_calc['RSV'] = ((df_calc['Close'] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
    df_calc['RSV'] = df_calc['RSV'].fillna(50)
    df_calc['K'] = df_calc['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df_calc['D'] = df_calc['K'].ewm(alpha=1/3, adjust=False).mean()
    df_calc['J'] = 3 * df_calc['K'] - 2 * df_calc['D']

    # 3. OBV 能量潮
    price_diff = df_calc['Close'].diff().fillna(0)
    obv_direction = np.where(price_diff > 0, 1, np.where(price_diff < 0, -1, 0))
    df_calc['OBV'] = (obv_direction * df_calc['Volume']).cumsum()
    df_calc['OBV_EMA'] = df_calc['OBV'].ewm(span=5, adjust=False).mean()

    # 4. MACD 指標 (12, 26, 9)
    df_calc['EMA12'] = df_calc['Close'].ewm(span=12, adjust=False).mean()
    df_calc['EMA26'] = df_calc['Close'].ewm(span=26, adjust=False).mean()
    df_calc['DIF'] = df_calc['EMA12'] - df_calc['EMA26']
    df_calc['MACD'] = df_calc['DIF'].ewm(span=9, adjust=False).mean()
    df_calc['MACD_Hist'] = df_calc['DIF'] - df_calc['MACD']

    # 5. RSI 相對強弱指標 (Yahoo 靈魂平滑公式)
    def calculate_yahoo_rsi(series, period):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    df_calc['RSI5'] = calculate_yahoo_rsi(df_calc['Close'], 5).fillna(50)
    df_calc['RSI10'] = calculate_yahoo_rsi(df_calc['Close'], 10).fillna(50)

    # 6. BIAS 乖離率
    df_calc['BIAS10'] = ((df_calc['Close'] - df_calc['SMA_10']) / df_calc['SMA_10']) * 100
    df_calc['BIAS20'] = ((df_calc['Close'] - df_calc['SMA_20']) / df_calc['SMA_20']) * 100
    df_calc['B10-B20'] = df_calc['BIAS10'] - df_calc['BIAS20']

# 建立逐日紅綠燈診斷模型 (+1 偏多紅燈, -1 偏空綠燈, 0 中立黃燈)
# 1. 均線/布林帶燈號
sma_bull = (df_calc['Close'] > df_calc['SMA_20']) & (df_calc['SMA_5'] >= df_calc['SMA_10'])
sma_bear = (df_calc['Close'] < df_calc['SMA_20']) & (df_calc['SMA_5'] <= df_calc['SMA_10'])
df_calc['Score_SMA'] = np.where(sma_bull, 1, np.where(sma_bear, -1, 0))

# 2. KDJ 燈號
kdj_bull = (df_calc['K'] > df_calc['D']) & (df_calc['K'] < 80)
kdj_bear = (df_calc['K'] < df_calc['D']) & (df_calc['K'] > 20)
df_calc['Score_KDJ'] = np.where(kdj_bull, 1, np.where(kdj_bear, -1, 0))

# 3. OBV 能量潮燈號
obv_bull = df_calc['OBV'] >= df_calc['OBV_EMA']
df_calc['Score_OBV'] = np.where(obv_bull, 1, -1)

# 4. MACD 燈號
macd_bull = df_calc['MACD_Hist'] > 0
macd_bear = df_calc['MACD_Hist'] < 0
df_calc['Score_MACD'] = np.where(macd_bull, 1, np.where(macd_bear, -1, 0))

# 5. RSI 燈號 (多方區間與超買超賣反轉)
rsi_bull = ((df_calc['RSI5'] > 50) & (df_calc['RSI5'] >= df_calc['RSI10'])) | (df_calc['RSI5'] < 25)
rsi_bear = ((df_calc['RSI5'] < 50) & (df_calc['RSI5'] < df_calc['RSI10'])) | (df_calc['RSI5'] > 80)
df_calc['Score_RSI'] = np.where(rsi_bull, 1, np.where(rsi_bear, -1, 0))

# 6. BIAS 乖離率燈號
bias_bull = df_calc['B10-B20'] >= 0
df_calc['Score_BIAS'] = np.where(bias_bull, 1, -1)

# 統計每日 6 大指標多空總分 (範圍：-6 ~ +6)
df_calc['Total_Score'] = (
    df_calc['Score_SMA'] + 
    df_calc['Score_KDJ'] + 
    df_calc['Score_OBV'] + 
    df_calc['Score_MACD'] + 
    df_calc['Score_RSI'] + 
    df_calc['Score_BIAS']
)

# 過濾掉預熱期間資料，保留使用者指定的觀測區間
df_calc.index = pd.to_datetime(df_calc.index)
mask_start = pd.Timestamp(target_start)
df = df_calc.loc[mask_start:].copy()

if df.empty:
    st.warning("⚠️ 觀測區間內無交易資料，請調整起始日期或標的代號。")
    st.stop()

# 格式化顯示用索引字串
df_chart = df.copy()
df_chart.index = df_chart.index.map(lambda x: x.strftime('%y-%m-%d'))

st.header("🚦 指標紅綠燈多空診斷報告 (最新交易日)")

latest_row = df.iloc[-1]
latest_date_str = df.index[-1].strftime('%Y-%m-%d')
close_val = float(latest_row['Close'])
prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else close_val
price_change = close_val - prev_close
price_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0

total_score = int(latest_row['Total_Score'])

# 統計各指標紅黃綠燈數量
score_items = [
    ("均線與布林帶 (SMA & BBands)", int(latest_row['Score_SMA']), f"收盤價 {close_val:.2f} | 20MA: {latest_row['SMA_20']:.2f}"),
    ("KDJ 指標", int(latest_row['Score_KDJ']), f"K: {latest_row['K']:.1f} | D: {latest_row['D']:.1f} | J: {latest_row['J']:.1f}"),
    ("OBV 能量潮", int(latest_row['Score_OBV']), f"OBV: {latest_row['OBV']:.0f} | 5日EMA: {latest_row['OBV_EMA']:.0f}"),
    ("MACD 指標", int(latest_row['Score_MACD']), f"DIF: {latest_row['DIF']:.2f} | MACD: {latest_row['MACD']:.2f} | 柱狀: {latest_row['MACD_Hist']:.2f}"),
    ("RSI 相對強弱", int(latest_row['Score_RSI']), f"RSI5: {latest_row['RSI5']:.1f} | RSI10: {latest_row['RSI10']:.1f}"),
    ("BIAS 乖離率", int(latest_row['Score_BIAS']), f"BIAS10: {latest_row['BIAS10']:.2f}% | BIAS20: {latest_row['BIAS20']:.2f}%")
]

red_count = sum(1 for _, s, _ in score_items if s > 0)
green_count = sum(1 for _, s, _ in score_items if s < 0)
yellow_count = sum(1 for _, s, _ in score_items if s == 0)

# 多空診斷評級
if total_score >= 4:
    sentiment_tag = "🚀 強烈看多 (Strong Bullish)"
    summary_desc = "多數指標呈現多頭排列與上漲動能，短中期趨勢偏多發展。"
elif 1 <= total_score <= 3:
    sentiment_tag = "📈 偏多震盪 (Moderate Bullish)"
    summary_desc = "多方稍佔優勢，但部分指標出現鈍化或整理，宜順勢操作並留意回檔支撐。"
elif total_score == 0:
    sentiment_tag = "⚖️ 盤整中立 (Neutral Range)"
    summary_desc = "多空力道膠著平衡，建議等待明確的方向性突破或帶量關鍵訊號。"
elif -3 <= total_score <= -1:
    sentiment_tag = "📉 偏空修正 (Moderate Bearish)"
    summary_desc = "空方動能佔優，短期均線或指標轉弱，需防範進一步回測支撐風險。"
else:
    sentiment_tag = "⚠️ 強烈看空 (Strong Bearish)"
    summary_desc = "多項技術指標全數破位翻空，下行風險較高，建議保守觀望或嚴設停損。"

# 頂部 KPI 卡片顯示
c1, c2, c3, c4 = st.columns(4)
c1.metric("最新收盤價", f"{close_val:.2f}", f"{price_change:+.2f} ({price_pct:+.2f}%)")
c2.metric("燈號統計 (紅 / 綠 / 黃)", f"🔴 {red_count} | 🟢 {green_count} | 🟡 {yellow_count}")
c3.metric("多空綜合總分 (滿分 ±6)", f"{total_score:+d} 分")
c4.metric("AI 綜合診斷結論", sentiment_tag)

# 顯示總結狀態框
st.info(f"📅 **診斷基準日：{latest_date_str}** ｜ **綜合研判**：{summary_desc}")

st.subheader("📋 6 大指標多空詳細燈號一覽")
table_data = []
for name, score, detail in score_items:
    if score > 0:
        light = "🔴 紅燈 (+1 看多)"
    elif score < 0:
        light = "🟢 綠燈 (-1 看空)"
    else:
        light = "🟡 黃燈 (0 中立)"
    table_data.append({
        "指標項目": name,
        "診斷燈號 (紅正/綠負)": light,
        "評分貢獻": f"{score:+d}",
        "即時指標數值 / 狀態": detail
    })

st.table(pd.DataFrame(table_data))

st.header("Step 3: 綜合技術指標儀表板 (6大指標視覺化)")
with st.expander("📖 查看圖表排版設計說明"):
    st.markdown("""
    本圖表使用 Matplotlib 的 `add_subplot(8, 1, ...)` 將畫布切分為 8 個單位高度：
    - **區塊 1-3 (主圖)**：顯示 K 線、5/10/20 日均線與布林通道。
    - **區塊 4 (OBV & Volume)**：結合能量潮曲線與成交量柱狀圖 (雙 Y 軸)。
    - **區塊 5 (KDJ)**：K、D、J 三線交叉觀察。
    - **區塊 6 (MACD)**：DIF、MACD 指標及其紅綠柱狀圖。
    - **區塊 7 (RSI)**：觀察 RSI5 與 RSI10 是否觸及超買 (70) 或超賣 (30) 虛線區間。
    - **區塊 8 (BIAS)**：10日與 20日乖離率，及兩者差距的柱狀圖 (輔助判斷極端行情)。
    """)

# 建立圖表畫布 (高度 16 容納 6 個圖表)
fig = plt.figure(figsize=(14, 16), layout='constrained')

ax1 = fig.add_subplot(8, 1, (1, 3)) # 主圖 (佔 3 單位)
ax2 = fig.add_subplot(8, 1, 4)      # OBV (佔 1 單位)
ax3 = fig.add_subplot(8, 1, 5)      # KDJ (佔 1 單位)
ax4 = fig.add_subplot(8, 1, 6)      # MACD (佔 1 單位)
ax5 = fig.add_subplot(8, 1, 7)      # RSI (佔 1 單位)
ax6 = fig.add_subplot(8, 1, 8)      # BIAS (佔 1 單位)

x_ticks_pos = range(0, len(df_chart.index), max(1, len(df_chart.index) // 10))
x_ticks_labels = [df_chart.index[i] for i in x_ticks_pos]

# --- Ax1: K線 + 均線 + 布林帶 ---
ax1.set_xticks(x_ticks_pos)
ax1.set_xticklabels(x_ticks_labels)
mpf.candlestick2_ochl(ax1, df_chart['Open'], df_chart['Close'], df_chart['High'], df_chart['Low'], 
                       width=0.8, colorup='r', colordown='g', alpha=1)
ax1.plot(df_chart['SMA_5'].values, label='5日均線', color='cyan', lw=1)
ax1.plot(df_chart['SMA_10'].values, label='10日均線', color='purple', lw=1)
ax1.plot(df_chart['SMA_20'].values, label='20日均線', color='orange', lw=1)
ax1.plot(df_chart['upper_band'].values, label='布林上軌', color='g', ls=':', lw=1)
ax1.plot(df_chart['lower_band'].values, label='布林下軌', color='g', ls=':', lw=1)
ax1.legend(loc='upper left', fontsize='small')
ax1.set_title(f"【{stock_id}】綜合技術分析與多空評分", fontsize=16)

# --- Ax2: OBV 與 成交量 ---
ax2.set_xticks(x_ticks_pos)
ax2.set_xticklabels([])
vol_colors = np.where(df_chart['Close'] >= df_chart['Close'].shift(1).fillna(0), 'r', 'g')
ax2.plot(df_chart['OBV'].values, color='purple', ls='--', label='OBV')
ax2.plot(df_chart['OBV_EMA'].values, color='orange', lw=1, label='OBV 5EMA')
ax2_v = ax2.twinx()
ax2_v.bar(range(len(df_chart)), df_chart['Volume'], color=vol_colors, alpha=0.6, width=0.8)
ax2.set_title("OBV 能量潮與成交量")
ax2.legend(loc='upper left', fontsize='small')

# --- Ax3: KDJ ---
ax3.plot(df_chart['K'].values, label='K線', color='cyan', lw=1)
ax3.plot(df_chart['D'].values, label='D線', color='purple', lw=1)
ax3.plot(df_chart['J'].values, label='J線', color='orange', ls='--')
ax3.axhline(80, color='r', ls=':', alpha=0.5)
ax3.axhline(20, color='g', ls=':', alpha=0.5)
ax3.set_xticks(x_ticks_pos)
ax3.set_xticklabels([])
ax3.set_title("KDJ 指標")
ax3.legend(loc='upper left', fontsize='small')

# --- Ax4: MACD ---
ax4.plot(df_chart['DIF'].values, label='DIF', color='purple')
ax4.plot(df_chart['MACD'].values, label='MACD', color='skyblue')
macd_hist_colors = np.where(df_chart['MACD_Hist'] >= 0, 'r', 'g')
ax4.bar(range(len(df_chart)), df_chart['MACD_Hist'], color=macd_hist_colors, alpha=0.6)
ax4.axhline(0, color='gray', ls='--', lw=1)
ax4.set_xticks(x_ticks_pos)
ax4.set_xticklabels([])
ax4.set_title("MACD 指標")
ax4.legend(loc='upper left', fontsize='small')

# --- Ax5: RSI ---
ax5.plot(df_chart['RSI5'].values, label='RSI5', color='cyan', lw=1)
ax5.plot(df_chart['RSI10'].values, label='RSI10', color='purple', lw=1)
ax5.axhline(70, color='r', ls='--', lw=0.8, alpha=0.5)
ax5.axhline(30, color='g', ls='--', lw=0.8, alpha=0.5)
ax5.set_ylim(0, 100)
ax5.set_xticks(x_ticks_pos)
ax5.set_xticklabels([])
ax5.set_title("RSI 相對強弱指標")
ax5.legend(loc='upper left', fontsize='small')

# --- Ax6: BIAS ---
ax6.plot(df_chart['BIAS10'].values, label='BIAS10', color='cyan', lw=1)
ax6.plot(df_chart['BIAS20'].values, label='BIAS20', color='purple', lw=1)
bias_colors = np.where(df_chart['B10-B20'] >= 0, 'r', 'g')
ax6.bar(range(len(df_chart)), df_chart['B10-B20'], color=bias_colors, alpha=0.6)
ax6.axhline(0, color='gray', ls='--', lw=1)
ax6.set_xticks(x_ticks_pos)
ax6.set_xticklabels(x_ticks_labels, rotation=30)
ax6.set_title("BIAS 乖離率 (柱狀為 B10-B20 差值)")
ax6.legend(loc='upper left', fontsize='small')

st.pyplot(fig)

st.header("Step 4: 歷史多空總分走勢回測")
st.markdown("觀察觀測區間內**每日多空總分 (-6 ~ +6)** 的動態轉折變化：")

score_fig, score_ax = plt.subplots(figsize=(14, 4), layout='constrained')
score_colors = np.where(df_chart['Total_Score'] > 0, '#ef4444', np.where(df_chart['Total_Score'] < 0, '#22c55e', '#eab308'))

score_ax.bar(range(len(df_chart)), df_chart['Total_Score'], color=score_colors, alpha=0.75, label='多空總分 (紅正/綠負)')
score_ax.plot(df_chart['Total_Score'].rolling(3, min_periods=1).mean().values, color='navy', lw=1.5, ls='-', label='3日平滑趨勢')
score_ax.axhline(0, color='gray', ls='--', lw=1)
score_ax.set_ylim(-6.5, 6.5)
score_ax.set_xticks(x_ticks_pos)
score_ax.set_xticklabels(x_ticks_labels, rotation=30)
score_ax.set_title("觀測區間歷史多空總分走勢 (-6 ~ +6)", fontsize=13)
score_ax.legend(loc='upper left', fontsize='small')
score_ax.grid(axis='y', linestyle=':', alpha=0.4)

st.pyplot(score_fig)

st.divider()
st.caption("⚠️ 免責聲明：本系統所有指標運算與紅綠燈多空總分僅供程式實作與學術研究參考，不構成任何形式之投資邀約或買賣建議。")