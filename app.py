import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

st.set_page_config(page_title="美業 CRM 數據分析系統", layout="wide", page_icon="💅")

# 自訂 CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("💅 美業 CRM 數據分析系統")

# 資料需求說明
st.caption("📋 最少需要欄位：訂單號碼、訂單時間、會員、品項、總價")

# 側邊欄：多檔案上傳
st.sidebar.header("📁 資料上傳")
uploaded_files = st.sidebar.file_uploader(
    "上傳交易資料 (可選擇 10-20 個檔案)", 
    type=['xlsx', 'csv', 'parquet'],
    accept_multiple_files=True
)

if uploaded_files:
    # 合併所有上傳的檔案
    all_dfs = []
    
    with st.spinner('正在讀取並合併檔案...'):
        for uploaded_file in uploaded_files:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_temp = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.parquet'):
                    df_temp = pd.read_parquet(uploaded_file)
                else:
                    df_temp = pd.read_excel(uploaded_file)
                
                all_dfs.append(df_temp)
                st.sidebar.success(f"✅ {uploaded_file.name} ({len(df_temp):,} 筆)")
            except Exception as e:
                st.sidebar.error(f"❌ {uploaded_file.name} 讀取失敗")
    
    # 合併所有資料
    df = pd.concat(all_dfs, ignore_index=True)
    
    st.success(f"✅ 成功合併 {len(uploaded_files)} 個檔案，共 {len(df):,} 筆交易資料")
    
    # 資料預處理
    df['訂單時間'] = pd.to_datetime(df['訂單時間'], errors='coerce')
    df['年份'] = df['訂單時間'].dt.year
    df['月份'] = df['訂單時間'].dt.month
    
    # 計算每個會員的年度總次數
    member_annual_freq = df.groupby(['會員', '年份'])['訂單號碼'].nunique().reset_index()
    member_annual_freq.columns = ['會員', '年份', '年度總次數']
    df = df.merge(member_annual_freq, on=['會員', '年份'], how='left')
    
    # 選擇分析年度
    years = sorted(df['年份'].dropna().unique())
    selected_year = st.sidebar.selectbox("選擇分析年度", years, index=len(years)-1)
    
    # 建立頁籤
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 會員深度分析", 
        "🔍 會員黏著度",
        "💰 產品矩陣",
        "🎯 客群健康度",
        "📈 促銷方案"
    ])
    
    # ========== Tab 1: 會員深度分析 ==========
    with tab1:
        st.header(f"{selected_year} 年會員深度分析")
        
        df_year = df[df['年份'] == selected_year].copy()
        
        # 計算會員統計
        member_stats = df_year.groupby('會員').agg({
            '訂單號碼': 'nunique',
            '總價': 'sum'
        }).reset_index()
        member_stats.columns = ['會員', '年度總次數', '年度總消費']
        
        # 按年度總次數分組
        freq_dist = member_stats.groupby('年度總次數').agg({
            '會員': 'count',
            '年度總消費': 'sum'
        }).reset_index()
        freq_dist.columns = ['年度總次數', '人數', '總營收']
        
        # 合併 >10 次
        freq_dist_display = freq_dist[freq_dist['年度總次數'] <= 10].copy()
        if len(freq_dist[freq_dist['年度總次數'] > 10]) > 0:
            over_10 = pd.DataFrame({
                '年度總次數': ['>10'],
                '人數': [freq_dist[freq_dist['年度總次數'] > 10]['人數'].sum()],
                '總營收': [freq_dist[freq_dist['年度總次數'] > 10]['總營收'].sum()]
            })
            freq_dist_display = pd.concat([freq_dist_display, over_10], ignore_index=True)
        
        # 圖表：雙軸柱狀圖
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=freq_dist_display['年度總次數'].astype(str),
            y=freq_dist_display['人數'],
            name='人數',
            marker_color='lightblue',
            yaxis='y',
            text=freq_dist_display['人數'],
            textposition='outside'
        ))
        fig1.add_trace(go.Bar(
            x=freq_dist_display['年度總次數'].astype(str),
            y=freq_dist_display['總營收'],
            name='總營收',
            marker_color='#FF6B6B',
            yaxis='y2',
            opacity=0.7
        ))
        fig1.update_layout(
            title="會員分佈：人數 vs 營收貢獻",
            xaxis_title="年度總次數",
            yaxis=dict(title='人數', side='left'),
            yaxis2=dict(title='總營收 ($)', overlaying='y', side='right'),
            height=500,
            barmode='overlay'
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # 洞察
        if len(freq_dist_display) > 0:
            one_timer = freq_dist_display[freq_dist_display['年度總次數'].astype(str) == '1'].iloc[0]
            one_timer_pct = (one_timer['人數'] / freq_dist_display['人數'].sum() * 100)
            
            col1, col2 = st.columns(2)
            with col1:
                st.warning(f"""
                **⚠️ 一次性過客**
                - 只來 1 次：**{one_timer['人數']:,} 人** ({one_timer_pct:.1f}%)
                - 💡 建議：設計「首購後第二次優惠」
                """)
            with col2:
                vip_revenue = freq_dist_display[freq_dist_display['年度總次數'].astype(str).isin(['>10', '10', '9', '8'])]['總營收'].sum()
                vip_pct = (vip_revenue / freq_dist_display['總營收'].sum() * 100)
                st.success(f"""
                **✅ VIP 貢獻**
                - 高頻客戶貢獻：**{vip_pct:.1f}%** 營收
                - 💡 建議：VIP 專屬儲值方案
                """)
    
    # ========== Tab 2: 會員黏著度 ==========
    with tab2:
        st.header("會員黏著度分佈")
        
        freq_table = df_year.groupby('年度總次數')['會員'].nunique().reset_index()
        freq_table.columns = ['年度總次數', '人數']
        freq_table['佔比 (%)'] = (freq_table['人數'] / freq_table['人數'].sum() * 100).round(2)
        
        st.dataframe(freq_table, use_container_width=True, hide_index=True)
        
        # 圓餅圖
        freq_table_grouped = freq_table.copy()
        freq_table_grouped.loc[freq_table_grouped['年度總次數'] > 5, '年度總次數'] = '>5'
        freq_table_grouped = freq_table_grouped.groupby('年度總次數').sum().reset_index()
        
        fig_pie = px.pie(
            freq_table_grouped,
            values='人數',
            names='年度總次數',
            title='會員黏著度分佈',
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # ========== Tab 3: 產品矩陣 ==========
    with tab3:
        st.header("產品波士頓矩陣（BCG Matrix）")
        
        if '品項' in df.columns:
            product_matrix = df_year.groupby('品項').agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            product_matrix.columns = ['品項', '訂單數', '總營收']
            product_matrix = product_matrix[product_matrix['訂單數'] >= 3]
            
            median_orders = product_matrix['訂單數'].median()
            median_revenue = product_matrix['總營收'].median()
            
            def classify_product(row):
                if row['訂單數'] >= median_orders and row['總營收'] >= median_revenue:
                    return '⭐ 明星商品'
                elif row['訂單數'] >= median_orders:
                    return '🐔 帶路雞'
                elif row['總營收'] >= median_revenue:
                    return '💎 潛力股'
                else:
                    return '❌ 拖油瓶'
            
            product_matrix['分類'] = product_matrix.apply(classify_product, axis=1)
            
            fig_bcg = px.scatter(
                product_matrix,
                x='訂單數',
                y='總營收',
                color='分類',
                hover_data=['品項'],
                title='產品矩陣：人氣 vs 營收',
                color_discrete_map={
                    '⭐ 明星商品': '#2ECC71',
                    '🐔 帶路雞': '#3498DB',
                    '💎 潛力股': '#F39C12',
                    '❌ 拖油瓶': '#95A5A6'
                }
            )
            st.plotly_chart(fig_bcg, use_container_width=True)
            
            # 顯示各象限產品
            col1, col2 = st.columns(2)
            with col1:
                st.success("**⭐ 明星商品**")
                stars = product_matrix[product_matrix['分類'] == '⭐ 明星商品'].head(5)
                st.dataframe(stars[['品項', '訂單數', '總營收']], hide_index=True)
            
            with col2:
                st.info("**🐔 帶路雞**")
                chicken = product_matrix[product_matrix['分類'] == '🐔 帶路雞'].head(5)
                st.dataframe(chicken[['品項', '訂單數', '總營收']], hide_index=True)
        else:
            st.warning("⚠️ 資料中缺少「品項」欄位，無法進行產品矩陣分析")
    
    # ========== Tab 4: 客群健康度 ==========
    with tab4:
        st.header("客群健康度診斷")
        
        if '分類' in df.columns:
            # 計算客群狀態（如果沒有則自動生成）
            if '客群狀態' not in df.columns:
                latest_purchase = df.groupby('會員')['訂單時間'].max().reset_index()
                today = pd.Timestamp.now()
                
                def calc_status(last_date):
                    if pd.isna(last_date):
                        return '🔴 已流失'
                    days = (today - last_date).days
                    if days <= 90:
                        return '🟢 活躍中'
                    elif days <= 180:
                        return '🟡 需喚醒'
                    else:
                        return '🔴 已流失'
                
                latest_purchase['客群狀態'] = latest_purchase['訂單時間'].apply(calc_status)
                df = df.merge(latest_purchase[['會員', '客群狀態']], on='會員', how='left')
            
            health_matrix = df_year.groupby(['分類', '客群狀態'])['會員'].nunique().reset_index()
            health_pivot = health_matrix.pivot_table(
                index='分類',
                columns='客群狀態',
                values='會員',
                fill_value=0
            )
            
            st.dataframe(health_pivot, use_container_width=True)
            
            # 堆疊柱狀圖
            fig_health = go.Figure()
            colors = {'🟢 活躍中': '#2ECC71', '🟡 需喚醒': '#F39C12', '🔴 已流失': '#E74C3C'}
            
            for status in health_pivot.columns:
                fig_health.add_trace(go.Bar(
                    name=status,
                    x=health_pivot.index,
                    y=health_pivot[status],
                    marker_color=colors.get(status, 'gray')
                ))
            
            fig_health.update_layout(
                title="各分類客群健康度",
                barmode='stack',
                height=500
            )
            st.plotly_chart(fig_health, use_container_width=True)
        else:
            st.warning("⚠️ 資料中缺少「分類」欄位")
    
    # ========== Tab 5: 促銷方案 ==========
    with tab5:
        st.header("促銷方案成效分析")
        
        if '消費方式' in df.columns:
            promo_summary = df_year.groupby('消費方式').agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            promo_summary.columns = ['消費方式', '訂單數', '總營收']
            promo_summary = promo_summary.sort_values('總營收', ascending=False)
            
            st.dataframe(promo_summary, use_container_width=True, hide_index=True)
            
            fig_promo = px.bar(
                promo_summary.head(10),
                x='消費方式',
                y='總營收',
                title='各消費方式營收排名',
                text='總營收'
            )
            st.plotly_chart(fig_promo, use_container_width=True)
        else:
            st.warning("⚠️ 資料中缺少「消費方式」欄位")

else:
    st.info("👈 請從左側上傳交易資料檔案（可一次選擇多個檔案）")
    st.markdown("""
    ### 📊 系統功能
    
    #### 會員深度分析
    - 人數分佈 vs 營收貢獻
    - 自動識別一次性過客與 VIP
    
    #### 會員黏著度
    - 一年來幾次分佈表
    - 黏著度圓餅圖
    
    #### 產品矩陣
    - BCG 四象限分析
    - 明星商品 vs 帶路雞 vs 潛力股 vs 拖油瓶
    
    #### 客群健康度
    - 各分類流失率診斷
    - 活躍/需喚醒/已流失分佈
    
    #### 促銷方案
    - 消費方式成效排名
    - 營收貢獻分析
    """)
