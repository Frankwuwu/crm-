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
        /* Use Streamlit's default background to ensure text contrast compatibility */
        
        /* Metric Cards - Glassmorphism */
        div[data-testid="metric-container"] {
            background-color: rgba(28, 131, 225, 0.1);
            border: 1px solid rgba(28, 131, 225, 0.1);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }
        div[data-testid="metric-container"]:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            border-color: rgba(28, 131, 225, 0.3);
        }
        
        /* Headers - Gradient Text */
        h1, h2, h3 {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 700 !important;
        }
        
        h1 {
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            /* Fallback for browsers that don't support clip */
            color: #FF6B6B; 
        }

        /* Tabs - Pills Design */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            border-radius: 20px;
            padding: 0 20px;
            border: 1px solid transparent;
            transition: all 0.2s;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(150, 150, 150, 0.1);
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #FF6B6B;
            color: white !important;
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
    
    # 1. Basic Type Conversion
    if '訂單時間' in df.columns:
        df['訂單時間'] = pd.to_datetime(df['訂單時間'], errors='coerce')
        df['消費日期'] = df['訂單時間'].dt.date
        df['年份'] = df['訂單時間'].dt.year
        df['月份'] = df['訂單時間'].dt.month
        df['月份名稱'] = df['訂單時間'].dt.strftime('%Y-%m')

    if '總價' in df.columns:
        df['總價'] = pd.to_numeric(df['總價'], errors='coerce').fillna(0) # Standardize price
    
    # 2. Advanced Fields Generation (The "Cleaning" Request)
    
    # (A) MemberID: Name + Phone
    if '會員' in df.columns and '手機' in df.columns:
        df['會員ID'] = df['會員'].astype(str) + "_" + df['手機'].astype(str)
    elif '會員' in df.columns:
        df['會員ID'] = df['會員']
    else:
        df['會員ID'] = 'Unknown'

    # (B) Visit Sort Order
    df = df.sort_values(['會員ID', '訂單時間'])
    df['第幾次來'] = df.groupby('會員ID').cumcount() + 1
    
    # (C) Annual Frequency
    annual_freq = df.groupby(['會員ID', '年份']).size().reset_index(name='年度總次數')
    df = df.merge(annual_freq, on=['會員ID', '年份'], how='left')

    # (D) Parsing Item & Scheme from '品項'
    # Logic: Extracting "Buy X Get Y" or "Single"
    def parse_item_scheme(item_name):
        item_name = str(item_name)
        scheme = "一般單次"
        main_item = item_name
        
        # Keywords for schemes
        schemes = ["買3送1", "買5送1", "買10送2", "體驗", "贈送", "包堂"]
        for s in schemes:
            if s in item_name:
                scheme = s
                # Try to remove scheme from name to get Main Item
                main_item = item_name.replace(s, "").replace("買", "").strip()
                break
        
        return pd.Series([main_item, scheme])

    if '品項' in df.columns:
        df[['主項目', '銷售方案']] = df['品項'].apply(parse_item_scheme)
    else:
        df['主項目'] = 'Unknown'
        df['銷售方案'] = 'Unknown'

    # (E) Real Cash Correction
    # Logic: If Payment is 'Coupon'/'Voucher', Cash is 0? 
    # Or rely on '定價/實收' column if parsed. 
    # For now, simplistic logic: if '券' in payment method, Real Cash = 0, else Total Price
    def calc_real_cash(row):
        pay_method = str(row.get('支付方式', ''))
        total = row.get('總價', 0)
        
        if '商品券' in pay_method or '贈送' in pay_method:
            return 0
        return total

    df['現金實收(修正)'] = df.apply(calc_real_cash, axis=1)
    df['實收金額'] = df['總價'] # Reuse total price as base revenue

    # (F) Customer Status (Active/Lost) & Last Visit
    latest_visit = df.groupby('會員ID')['訂單時間'].max().reset_index()
    latest_visit.columns = ['會員ID', '最後到店']
    df = df.merge(latest_visit, on='會員ID', how='left')
    
    today = pd.Timestamp.now()
    df['未到店天數'] = (today - df['最後到店']).dt.days
    
    def get_status(days):
        if days > 120: return "🔴 已流失 (>120天)"
        elif days > 60: return "🟡 沉睡中 (60-120天)"
        else: return "🟢 活躍中"
        
    df['客群狀態'] = df['未到店天數'].apply(get_status)

    # (G) Category Mapping (Simple Heuristic for now)
    # Mapping '分類' to '大分類' based on user image examples
    def map_category(cat):
        cat = str(cat)
        if "臉部" in cat or "皮膚" in cat or "儲值" in cat: return "01. 臉部皮膚管理"
        if "除毛" in cat: return "02. 專業除毛專科"
        if "美齒" in cat: return "04. 淨白美齒SPA"
        return "99. 其他"

    if '分類' in df.columns:
        df['大分類'] = df['分類'].apply(map_category)
    else:
        df['大分類'] = '99. 其他'

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
        except Exception:
            # Fallback if specific quantiles fail
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
        
        # --- Cleaned Data Preview ---
        with st.expander("📋 查看資料清洗結果 (Data Cleaning Preview)", expanded=False):
            st.caption("系統已自動將原始資料清洗為分析專用格式：")
            
            # Select columns to show based on user request
            show_cols = [
                '會員ID', '消費日期', '品項', '主項目', '銷售方案', 
                '第幾次來', '年度總次數', 
                '實收金額', '現金實收(修正)', 
                '客群狀態', '未到店天數', '大分類'
            ]
            # Filter cols that actually exist
            show_cols = [c for c in show_cols if c in df.columns]
            
            st.dataframe(df[show_cols].head(100), use_container_width=True)
            
            # Download Button
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下載清洗後的完整資料 (CSV)",
                csv,
                "cleaned_crm_data.csv",
                "text/csv",
                key='download-csv'
            )

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
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("年度總營收", f"${total_rev:,.0f}", delta="累積")
    col2.metric("總訂單數", f"{total_orders:,}", delta="筆")
    col3.metric("活躍會員數", f"{total_members:,}", delta="人")
    col4.metric("平均客單價 (AOV)", f"${avg_order_value:,.0f}", delta="元/單")
    
    st.markdown("---")

    # --- Tabs ---
    tabs = st.tabs([
        "📈 營運概覽", 
        "👥 會員深度分析", 
        "🔄 留存與回購", 
        "🛍️ 產品矩陣",
        "🎁 促銷成效"
    ])
    
    # 1. Overview
    with tabs[0]:
        st.subheader("📊 營運趨勢監控")
        st.plotly_chart(plot_revenue_trend(df_filtered), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            monthly_rev = df_filtered.groupby('月份')['總價'].sum().reset_index()
            fig_mon = px.bar(monthly_rev, x='月份', y='總價', title='月度營收表現', color='總價', color_continuous_scale='Bluyl')
            st.plotly_chart(fig_mon, use_container_width=True)
        with c2:
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
            retention_matrix, cohort_size = calculate_cohort(df)
            
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

    # 4. Products (BCG)
    with tabs[3]:
        st.subheader("🛍️ 產品波士頓矩陣")
        st.caption("協助您識別明星商品與潛力股")
        
        if '品項' in df_filtered.columns:
            prod_stats = df_filtered.groupby('品項').agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            prod_stats.columns = ['品項', '銷量', '營收']
            
            # --- Cleaning & Controls ---
            c1, c2 = st.columns(2)
            with c1:
                min_orders = st.slider("過濾低銷量雜訊 (最少訂單數)", 1, 50, 3, help="排除訂單數過少的商品，讓圖表更清晰")
            with c2:
                label_mode = st.radio("標籤顯示模式", ["重點顯示 (Top 20)", "全部顯示", "不顯示"], horizontal=True)

            # Filter noise
            prod_stats_clean = prod_stats[prod_stats['銷量'] >= min_orders].copy()
            
            # Calculate medians based on CLEAN data
            sales_med = prod_stats_clean['銷量'].median()
            rev_med = prod_stats_clean['營收'].median()
            
            # Classification
            def classify(row):
                if row['銷量'] >= sales_med and row['營收'] >= rev_med:
                    return '⭐ 明星'
                elif row['銷量'] >= sales_med:
                    return '🐔 金牛'
                elif row['營收'] >= rev_med:
                    return '💎 潛力'
                else:
                    return '🐕 瘦狗'
            
            prod_stats_clean['Type'] = prod_stats_clean.apply(classify, axis=1)
            
            # Truncate names for display
            prod_stats_clean['ShortName'] = prod_stats_clean['品項'].apply(lambda x: x[:10] + '...' if len(str(x)) > 10 else str(x))
            
            # Determine which labels to show
            if label_mode == "全部顯示":
                prod_stats_clean['Label'] = prod_stats_clean['ShortName']
            elif label_mode == "重點顯示 (Top 20)":
                # Prioritize high revenue items
                top_items = prod_stats_clean.nlargest(20, '營收')['品項'].tolist()
                prod_stats_clean['Label'] = prod_stats_clean.apply(lambda x: x['ShortName'] if x['品項'] in top_items else "", axis=1)
            else:
                prod_stats_clean['Label'] = ""

            # Plot
            fig_bcg = px.scatter(
                prod_stats_clean, 
                x='銷量', 
                y='營收', 
                color='Type', 
                hover_data=['品項', '銷量', '營收'], 
                text='Label',
                title=f'產品分布圖 (共 {len(prod_stats_clean)} 項商品)',
                color_discrete_map={'⭐ 明星': '#00b894', '🐔 金牛': '#0984e3', '💎 潛力': '#fdcb6e', '🐕 瘦狗': '#b2bec3'}
            )
            
            fig_bcg.update_traces(textposition='top center', marker=dict(size=10, opacity=0.8, line=dict(width=1, color='White')))
            fig_bcg.add_hline(y=rev_med, line_dash="dash", line_color="gray", annotation_text="營收中位數")
            fig_bcg.add_vline(x=sales_med, line_dash="dash", line_color="gray", annotation_text="銷量中位數")
            
            fig_bcg.update_layout(height=600)
            st.plotly_chart(fig_bcg, use_container_width=True)
            
            # Data Table
            with st.expander("查看詳細數據表"):
                st.dataframe(prod_stats_clean.sort_values('營收', ascending=False), use_container_width=True)
                
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
        <p style='font-size: 1.2em; opacity: 0.7;'>請從左側欄位上傳您的交易資料 (CSV/Excel) 以開始分析</p>
        <div style='background-color: rgba(60, 150, 255, 0.1); padding: 20px; border-radius: 10px; display: inline-block; text-align: left; border: 1px solid rgba(60, 150, 255, 0.2);'>
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
