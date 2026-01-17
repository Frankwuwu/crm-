import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Set page config
st.set_page_config(
    page_title="Pro Beauty CRM | 專業美業數據分析",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# ==========================================
# 🎨 UI/UX Theme & Custom CSS
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* Main Container Background */
        .stApp {
            background-color: #f8f9fa;
        }
        
        /* Metric Cards */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.1);
        }
        
        /* Headers */
        h1, h2, h3 {
            color: #2c3e50;
            font-family: 'Helvetica Neue', sans-serif;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: #ffffff;
            border-radius: 8px 8px 0 0;
            border: 1px solid #e0e0e0;
            border-bottom: none;
            padding: 0 20px;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #6c5ce7;
            color: white;
        }
        
        /* Sidebar */
        .css-1d391kg {
            padding-top: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🔄 Data Processing Functions
# ==========================================
@st.cache_data
def load_data(uploaded_files):
    if not uploaded_files:
        return None
    
    all_dfs = []
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_temp = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith('.parquet'):
                df_temp = pd.read_parquet(uploaded_file)
            else:
                df_temp = pd.read_excel(uploaded_file)
            all_dfs.append(df_temp)
        except Exception as e:
            st.error(f"Error loading {uploaded_file.name}: {str(e)}")
            
    if not all_dfs:
        return None
        
    return pd.concat(all_dfs, ignore_index=True)

@st.cache_data
def preprocess_data(df):
    df = df.copy()
    
    # Ensure datetime
    if '訂單時間' in df.columns:
        df['訂單時間'] = pd.to_datetime(df['訂單時間'], errors='coerce')
        df['年份'] = df['訂單時間'].dt.year
        df['月份'] = df['訂單時間'].dt.month
        df['月份名稱'] = df['訂單時間'].dt.strftime('%Y-%m')
        df['日期'] = df['訂單時間'].dt.date
    
    # Ensure numeric
    if '總價' in df.columns:
        df['總價'] = pd.to_numeric(df['總價'], errors='coerce').fillna(0)
        
    return df

@st.cache_data
def calculate_rfm(df, end_date=None):
    if end_date is None:
        end_date = df['訂單時間'].max() + timedelta(days=1)
        
    # Recency, Frequency, Monetary
    rfm = df.groupby('會員').agg({
        '訂單時間': lambda x: (end_date - x.max()).days,
        '訂單號碼': 'nunique',
        '總價': 'sum'
    }).reset_index()
    
    rfm.columns = ['會員', 'Recency', 'Frequency', 'Monetary']
    
    # Simple Scoring (1-5 scale)
    if len(rfm) > 1:
        try:
            rfm['R_Score'] = pd.qcut(rfm['Recency'], 5, labels=[5, 4, 3, 2, 1])
            rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
            rfm['M_Score'] = pd.qcut(rfm['Monetary'], 5, labels=[1, 2, 3, 4, 5])
            rfm['RFM_Segment'] = rfm['R_Score'].astype(str) + rfm['F_Score'].astype(str) + rfm['M_Score'].astype(str)
            rfm['RFM_Score'] = rfm[['R_Score', 'F_Score', 'M_Score']].sum(axis=1)
        except Exception as e:
            st.warning("Data insufficient for quintile scoring, using simplified logic.")
            rfm['R_Score'] = 3
            rfm['F_Score'] = 3
            rfm['M_Score'] = 3
            rfm['RFM_Segment'] = '333'
            
    return rfm

@st.cache_data
def calculate_cohort(df):
    df_cohort = df.copy()
    df_cohort['OrderPeriod'] = df_cohort['訂單時間'].dt.to_period('M')
    df_cohort['CohortGroup'] = df_cohort.groupby('會員')['訂單時間'].transform('min').dt.to_period('M')
    
    cohort_data = df_cohort.groupby(['CohortGroup', 'OrderPeriod']).agg(n_customers=('會員', 'nunique')).reset_index()
    cohort_data['PeriodNumber'] = (cohort_data.OrderPeriod - cohort_data.CohortGroup).apply(lambda x: x.n)
    
    cohort_pivot = cohort_data.pivot(index='CohortGroup', columns='PeriodNumber', values='n_customers')
    cohort_size = cohort_pivot.iloc[:, 0]
    retention_matrix = cohort_pivot.divide(cohort_size, axis=0)
    
    return retention_matrix, cohort_size

# ==========================================
# 📊 Plotting Functions
# ==========================================
def plot_revenue_trend(df):
    daily_rev = df.groupby('日期')['總價'].sum().reset_index()
    daily_rev['MA7'] = daily_rev['總價'].rolling(7).mean()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily_rev['日期'], y=daily_rev['總價'], mode='lines', name='日營收', line=dict(color='#a8a0ff', width=1)))
    fig.add_trace(go.Scatter(x=daily_rev['日期'], y=daily_rev['MA7'], mode='lines', name='7日均線', line=dict(color='#6c5ce7', width=3)))
    
    fig.update_layout(
        title='營收趨勢分析',
        xaxis_title='日期',
        yaxis_title='營收 ($)',
        hovermode="x unified",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

def plot_rfm_scatter(rfm_df):
    fig = px.scatter(
        rfm_df, 
        x='Recency', 
        y='Frequency', 
        size='Monetary',
        color='R_Score',
        hover_data=['會員', 'Monetary'],
        title='RFM 客戶分群圖 (氣泡大小=總消費)',
        color_discrete_sequence=px.colors.sequential.Viridis
    )
    fig.update_layout(height=500)
    return fig

# ==========================================
# 🚀 Main Application
# ==========================================
def main():
    inject_custom_css()
    
    st.title("💎 Pro Beauty CRM Analytics")
    st.caption("透過數據驅動決策，提升美業經營績效")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("📂 資料中心")
        uploaded_files = st.file_uploader("上傳交易資料 (CSV/Excel/Parquet)", accept_multiple_files=True)
        
        st.markdown("---")
        st.markdown("### 💡 系統說明")
        st.info("支援多檔案合併，系統會自動清理並計算進階指標。")

    if not uploaded_files:
        _show_landing_page()
        return

    # --- Data Loading ---
    with st.spinner("正在處理數據大腦..."):
        raw_df = load_data(uploaded_files)
        df = preprocess_data(raw_df)
        
        # Global Filters
        years = sorted(df['年份'].unique().tolist(), reverse=True)
        
        st.sidebar.header("🔍 篩選條件")
        selected_year = st.sidebar.selectbox("選擇年份", years, index=0)
        
        df_filtered = df[df['年份'] == selected_year]
        
    # --- KPIs ---
    total_rev = df_filtered['總價'].sum()
    total_orders = df_filtered['訂單號碼'].nunique()
    total_members = df_filtered['會員'].nunique()
    avg_order_value = total_rev / total_orders if total_orders else 0
    
    # Comparison (Fake YoY for demo if only 1 year, else real calc could be added)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("年度總營收", f"${total_rev:,.0f}", delta="累積")
    col2.metric("總訂單數", f"{total_orders:,}", delta="筆")
    col3.metric("活躍會員數", f"{total_members:,}", delta="人")
    col4.metric("平均客單價 (AOV)", f"${avg_order_value:,.0f}", delta="元/單")
    
    st.markdown("---")

    # --- Tabs ---
    tabs = st.tabs([
        "📈 營運概覽 (Overview)", 
        "👥 會員深度分析 (RFM)", 
        "🔄 留存與回購 (Retention)", 
        "🛍️ 產品矩陣 (Products)",
        "🎁 促銷成效 (Promotions)"
    ])
    
    # 1. Overview
    with tabs[0]:
        st.subheader("📊 營運趨勢監控")
        st.plotly_chart(plot_revenue_trend(df_filtered), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            # Monthly Revenue
            monthly_rev = df_filtered.groupby('月份')['總價'].sum().reset_index()
            fig_mon = px.bar(monthly_rev, x='月份', y='總價', title='月度營收表現', color='總價', color_continuous_scale='Bluyl')
            st.plotly_chart(fig_mon, use_container_width=True)
        with c2:
            # Hourly/Daily patterns (if time available) or Pay methods
            if '消費方式' in df_filtered.columns:
                pay_mix = df_filtered.groupby('消費方式')['總價'].sum().reset_index()
                fig_pay = px.pie(pay_mix, values='總價', names='消費方式', title='支付方式佔比', hole=0.4)
                st.plotly_chart(fig_pay, use_container_width=True)

    # 2. Member Analysis (RFM)
    with tabs[1]:
        st.subheader("👥 會員價值模型 (RFM Analysis)")
        rfm_df = calculate_rfm(df_filtered)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(plot_rfm_scatter(rfm_df), use_container_width=True)
        with c2:
            st.info("""
            **RFM 指標說明**
            - **Recency (R)**: 最近一次消費距離天數 (越小越好)
            - **Frequency (F)**: 消費頻率 (越大越好)
            - **Monetary (M)**: 消費金額 (越大越好)
            """)
            
            # Show Top VIPs
            st.markdown("#### 🏆 Top 10 超級 VIP")
            st.dataframe(
                rfm_df.sort_values('Monetary', ascending=False).head(10)[['會員', 'Recency', 'Frequency', 'Monetary']],
                hide_index=True,
                use_container_width=True
            )

    # 3. Retention (Cohort)
    with tabs[2]:
        st.subheader("🔄 留存率世代分析 (Cohort Analysis)")
        st.caption("觀察不同月份加入的會員，隨著時間推移的留存情況")
        
        try:
            retention_matrix, cohort_size = calculate_cohort(df) # Use full data for cohort to see long term
            
            # Heatmap
            fig_cohort = go.Figure(data=go.Heatmap(
                z=retention_matrix.values,
                x=retention_matrix.columns,
                y=[str(x) for x in retention_matrix.index],
                colorscale='Blues',
                text=[[f"{val:.0%}" if not np.isnan(val) else "" for val in row] for row in retention_matrix.values],
                texttemplate="%{text}",
                showscale=True
            ))
            
            fig_cohort.update_layout(
                title='會員留存率熱力圖',
                xaxis_title='第 N 個月後',
                yaxis_title='首次購買月份',
                height=600
            )
            st.plotly_chart(fig_cohort, use_container_width=True)
            
        except Exception as e:
            st.warning("資料量不足或格式問題，無法產生留存分析圖表")
            st.error(str(e))

    # 4. Products (BCG)
    with tabs[3]:
        st.subheader("🛍️ 產品波士頓矩陣")
        
        if '品項' in df_filtered.columns:
            prod_stats = df_filtered.groupby('品項').agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            prod_stats.columns = ['品項', '銷量', '營收']
            
            # Median thresholds
            sales_med = prod_stats['銷量'].median()
            rev_med = prod_stats['營收'].median()
            
            prod_stats['Type'] = prod_stats.apply(
                lambda x: '⭐ 明星' if (x['銷量']>=sales_med and x['營收']>=rev_med) else
                          ('🐔 金牛/帶路' if x['銷量']>=sales_med else
                           ('💎 問題/潛力' if x['營收']>=rev_med else '🐕 瘦狗')), axis=1
            )
            
            fig_bcg = px.scatter(
                prod_stats, x='銷量', y='營收', color='Type', 
                hover_data=['品項'], text='品項',
                color_discrete_map={'⭐ 明星': '#00b894', '🐔 金牛/帶路': '#0984e3', '💎 問題/潛力': '#fdcb6e', '🐕 瘦狗': '#b2bec3'}
            )
            fig_bcg.update_traces(textposition='top center')
            fig_bcg.add_hline(y=rev_med, line_dash="dash", annotation_text="營收中位數")
            fig_bcg.add_vline(x=sales_med, line_dash="dash", annotation_text="銷量中位數")
            
            st.plotly_chart(fig_bcg, use_container_width=True)
        else:
            st.error("缺少「品項」欄位")

    # 5. Promotions
    with tabs[4]:
        st.subheader("🎁 促銷方案成效")
        if '消費方式' in df_filtered.columns:
            promo = df_filtered.groupby('消費方式')['總價'].sum().reset_index().sort_values('總價', ascending=True)
            fig_promo = px.bar(promo, y='消費方式', x='總價', orientation='h', title='促銷/支付方式營收貢獻')
            st.plotly_chart(fig_promo, use_container_width=True)

def _show_landing_page():
    st.markdown("""
    <div style='text-align: center; padding: 50px;'>
        <h1>👋 歡迎使用 Pro Beauty CRM</h1>
        <p style='font-size: 1.2em; color: #666;'>請從左側欄位上傳您的交易資料 (CSV/Excel) 以開始分析</p>
        <div style='background-color: #e3f2fd; padding: 20px; border-radius: 10px; display: inline-block; text-align: left;'>
            <strong>📋 資料格式需求：</strong><br>
            您的檔案應包含以下欄位：<br>
            - <code>訂單號碼</code> (Order ID)<br>
            - <code>訂單時間</code> (Date)<br>
            - <code>會員</code> (Member ID/Name)<br>
            - <code>品項</code> (Product Name)<br>
            - <code>總價</code> (Total Price)
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
