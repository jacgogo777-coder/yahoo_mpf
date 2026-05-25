import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import mplfinance.original_flavor as mpf
import pandas as pd
import numpy as np
import matplotlib
import os
from matplotlib import font_manager

# ==========================================
# 0. 網頁基本配置與字型處理
# ==========================================
st.set_page_config(page_title="2026 股市 AI 紅盤實作專案", layout="wide")

# 處理中文字型 (解決雲端 Linux 亂碼問題)
font_path = "NotoSansTC-Regular.ttf"
if os.path.exists(font_path):
    font_manager.fontManager.addfont(font_path)
    prop = font_manager.FontProperties(fname=font_path)
    plt.rcParams['font.sans-serif'] = [prop.get_name()]
else:
    # 本機環境嘗試使用正黑體
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']

plt.rcParams['axes.unicode_minus'] = False

st.title("📊 2026 歡慶端午 Yahoo 股市分析專案")
st.markdown("本專案演示了從資料獲取、多維度技術指標計算到專業級多圖表排版的完整流程。")

# ==========================================
# 1. 側邊欄參數設定
# ==========================================
st.sidebar.header("⚙️ 參數設定")
stock_id = st.sidebar.text_input("股票代號", "2330.TW")
# 設定預設觀測日期 (根據 Source 3 邏輯)
default_start = datetime(2025, 11, 20)
default_end = datetime(2026, 5, 22)

target_start = st.sidebar.date_input("觀測起始日", default_start)
target_end = st.sidebar.date_input("觀測結束日", default_end)
warmup_days = st.sidebar.slider("指標預熱天數 (用於 EMA/MACD 準確度)", 30, 100, 60)

# ==========================================
# 2. 步驟一：資料獲取與「預熱」邏輯
# ==========================================
st.header("Step 1: 資料獲取與預熱處理")
with st.expander("📖 為什麼需要預熱資料？"):
    st.write("""
    EMA (指數移動平均) 與 MACD 指標具有延續性。如果直接從觀測日開始計算，初始值會產生嚴重的偏差。
    本程式自動向前抓取 60 天的資料進行「預熱」計算，確保在進入觀測日區間時，所有指標已趨於穩定準確。
    """)

@st.cache_data
def load_stock_data(symbol, start_dt, end_dt, warmup):
    # 向前推 warmup 天數
    fetch_start = start_dt - timedelta(days=warmup)
    df = yf.download(symbol, start=fetch_start, end=end_dt, auto_adjust=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

df_all = load_stock_data(stock_id, target_start, target_end, warmup_days)

if df_all.empty:
    st.error("找不到資料，請檢查代號或網路連線。")
    st.stop()

# ==========================================
# 3. 步驟二：多維度技術指標運算
# ==========================================
st.header("Step 2: 技術指標運算 (Indicator Math)")

def calculate_indicators(df):
    # SMA
    df['SMA_5'] = df['Close'].rolling(window=5).mean()
    df['SMA_10'] = df['Close'].rolling(window=10).mean()
    df['SMA_20'] = df['Close'].rolling(window=20).mean()

    # Bollinger Bands
    df['std_dev'] = df['Close'].rolling(window=20).std()
    df['upper_band'] = df['SMA_20'] + (df['std_dev'] * 2)
    df['lower_band'] = df['SMA_20'] - (df['std_dev'] * 2)

    # KDJ (EWM 快速法)
    n = 9
    low_min = df['Low'].rolling(window=n).min()
    high_max = df['High'].rolling(window=n).max()
    df['RSV'] = ((df['Close'] - low_min) / (high_max - low_min)) * 100
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()
    df['J'] = 3 * df['D'] - 2 * df['K']

    # OBV
    df['OBV'] = np.where(df['Close'] > df['Close'].shift(1), df['Volume'], -df['Volume']).cumsum()

    # MACD
    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = df['EMA12'] - df['EMA26']
    df['MACD'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD Histogram'] = df['DIF'] - df['MACD']

    # RSI (Yahoo 靈魂公式)
    def yahoo_rsi(series, period):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    df['RSI5'] = yahoo_rsi(df['Close'], 5)
    df['RSI10'] = yahoo_rsi(df['Close'], 10)

    # BIAS 乖離率
    df['BIAS10'] = ((df['Close'] - df['SMA_10']) / df['SMA_10']) * 100
    df['BIAS20'] = ((df['Close'] - df['SMA_20']) / df['SMA_20']) * 100
    df['B10-B20'] = df['BIAS10'] - df['BIAS20']
    
    return df

df_calculated = calculate_indicators(df_all)

# 切割資料回使用者選取的觀測時間
mask_start = pd.Timestamp(target_start)
df = df_calculated.loc[mask_start:].copy()
df.index = df.index.map(lambda x: x.strftime('%y-%m-%d'))

with st.expander("🔍 查看已計算的指標數據 (前五筆)"):
    st.dataframe(df.head())

# ==========================================
# 4. 步驟三：專業多圖層視覺化
# ==========================================
st.header("Step 3: 綜合技術指標儀表板")

# 繪圖設定
fig = plt.figure(figsize=(14, 16), layout='constrained')
# 定義 8 個子圖層
ax1 = fig.add_subplot(8,1,(1,3)) # 主圖
ax2 = fig.add_subplot(8,1,4)     # OBV
ax3 = fig.add_subplot(8,1,5)     # KDJ
ax4 = fig.add_subplot(8,1,6)     # MACD
ax5 = fig.add_subplot(8,1,7)     # RSI
ax6 = fig.add_subplot(8,1,8)     # BIAS

# --- Ax1: K線 + 均線 + 布林帶 ---
ax1.set_xticks(range(0,len(df.index),15))
ax1.set_xticklabels(df.index[::15])
mpf.candlestick2_ochl(ax1, df['Open'], df['Close'], df['High'], df['Low'], 
                       width=0.8, colorup='r', colordown='g', alpha=1)
ax1.plot(df['SMA_5'],label='5MA', color='cyan', lw=1)
ax1.plot(df['SMA_10'],label='10MA', color='purple', lw=1)
ax1.plot(df['SMA_20'],label='20MA', color='orange', lw=1)
ax1.plot(df['upper_band'], label='Upper', color='g', ls=':', lw=1)
ax1.plot(df['lower_band'], label='Lower', color='g', ls=':', lw=1)
ax1.legend(loc='upper left', fontsize='small')
ax1.set_title(f"{stock_id} 綜合技術分析", fontsize=16)

# --- Ax2: OBV 與 成交量 ---
ax2.set_xticks(range(0,len(df.index),15))
ax2.set_xticklabels([])
vol_colors = np.where(df['Close'] > df['Close'].shift(1), 'r', 'g')
ax2.plot(df['OBV'], color='purple', ls='--', label='OBV')
ax2_v = ax2.twinx()
ax2_v.bar(df.index, df['Volume'], color=vol_colors, alpha=0.3, width=0.8)
ax2.legend(loc='upper left', fontsize='small')

# --- Ax3: KDJ ---
ax3.plot(df['K'], label='K', color='cyan', lw=1)
ax3.plot(df['D'], label='D', color='purple', lw=1)
ax3.plot(df['J'], label='J', color='orange', ls='--')
ax3.set_xticks(range(0,len(df.index),15))
ax3.set_xticklabels(df.index[::15])
ax3.legend(loc='upper left', fontsize='small')

# --- Ax4: MACD ---
ax4.plot(df['DIF'], label='DIF', color='purple')
ax4.plot(df['MACD'], label='MACD', color='skyblue')
m_hist_colors = np.where(df['MACD Histogram'] >= 0, 'r', 'g')
ax4.bar(df.index, df['MACD Histogram'], color=m_hist_colors, alpha=0.6)
ax4.axhline(0, color='gray', ls='--', lw=1)
ax4.set_xticks(range(0,len(df.index),15))
ax4.set_xticklabels([])
ax4.legend(loc='upper left', fontsize='small')

# --- Ax5: RSI ---
ax5.plot(df['RSI5'], label='RSI5', color='cyan', lw=1)
ax5.plot(df['RSI10'], label='RSI10', color='purple', lw=1)
ax5.axhline(70, color='r', ls='--', lw=0.8, alpha=0.5)
ax5.axhline(30, color='g', ls='--', lw=0.8, alpha=0.5)
ax5.set_ylim(0, 100)
ax5.set_xticks(range(0,len(df.index),15))
ax5.set_xticklabels(df.index[::15])
ax5.legend(loc='upper left', fontsize='small')

# --- Ax6: BIAS (乖離率差距柱狀圖) ---
ax6.plot(df['BIAS10'], label='BIAS10', color='cyan', lw=1)
ax6.plot(df['BIAS20'], label='BIAS20', color='purple', lw=1)
bias_diff_colors = np.where(df['B10-B20'] >= 0, 'r', 'g')
ax6.bar(df.index, df['B10-B20'], color=bias_diff_colors, alpha=0.6)
ax6.axhline(0, color='gray', ls='--', lw=1)
ax6.set_xticks(range(0,len(df.index),15))
ax4.set_xticklabels([])
ax6.legend(loc='upper left', fontsize='small')

# 渲染到網頁
st.pyplot(fig)

st.divider()
st.info("💡 課程提示：觀察 MACD 柱狀圖與 RSI 超買超賣區，配合 BIAS 乖離率差距，可更全面判斷趨勢強弱。")
