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

# ========== 側邊欄：多檔案上傳 ==========
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
                st.sidebar.error(f"❌ {uploaded_file.name} 讀取失敗：{str(e)}")
    
    # 合併所有資料
    df = pd.concat(all_dfs, ignore_index=True)
    
    st.success(f"✅ 成功合併 {len(uploaded_files)} 個檔案，共 {len(df):,} 筆交易資料")
    
    # 資料預處理
    df['訂單時間'] = pd.to_datetime(df['訂單時間'], errors='coerce')
    df['年份'] = df['訂單時間'].dt.year
    df['月份'] = df['訂單時間'].dt.month
    
    # 計算每個會員的年度總次數（用於後續分析）
    member_annual_freq = df.groupby(['會員', '年份'])['訂單號碼'].nunique().reset_index()
    member_annual_freq.columns = ['會員', '年份', '年度總次數']
    df = df.merge(member_annual_freq, on=['會員', '年份'], how='left')
    
    # 選擇分析年度
    years = sorted(df['年份'].dropna().unique())
    selected_year = st.sidebar.selectbox("選擇分析年度", years, index=len(years)-1)
    
    # 建立頁籤
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 會員深度分析（三大核心圖）", 
        "🔍 會員黏著度分析",
        "💰 產品矩陣分析",
        "🎯 客群健康度雷達",
        "📈 促銷方案成效"
    ])
    
    # ========== Tab 1: 會員深度分析（三大核心圖）==========
    with tab1:
        st.header("會員深度分析：拒絕平均值，看清真相")
        
        # 篩選當年度資料
        df_year = df[df['年份'] == selected_year].copy()
        
        # === 圖表一：會員分佈圖（拒絕平均值）===
        st.subheader("📊 圖表一：會員分佈圖（誰是過客？誰是鐵粉？）")
        st.info("💡 拒絕平均值！看清楚只來 1 次的過客 vs 買 10 次的鐵粉")
        
        # 計算每個會員的年度總次數和總消費
        member_stats = df_year.groupby('會員').agg({
            '訂單號碼': 'nunique',
            '總價': 'sum'
        }).reset_index()
        member_stats.columns = ['會員', '年度總次數', '年度總消費']
        
        # 按年度總次數分組統計
        freq_dist = member_stats.groupby('年度總次數').agg({
            '會員': 'count',
            '年度總消費': 'sum'
        }).reset_index()
        freq_dist.columns = ['年度總次數', '人數', '總營收']
        
        # 只顯示次數 <= 10，>10 的合併
        freq_dist_display = freq_dist[freq_dist['年度總次數'] <= 10].copy()
        if len(freq_dist[freq_dist['年度總次數'] > 10]) > 0:
            over_10 = pd.DataFrame({
                '年度總次數': ['>10'],
                '人數': [freq_dist[freq_dist['年度總次數'] > 10]['人數'].sum()],
                '總營收': [freq_dist[freq_dist['年度總次數'] > 10]['總營收'].sum()]
            })
            freq_dist_display = pd.concat([freq_dist_display, over_10], ignore_index=True)
        
        # 雙軸柱狀圖
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
            title=f"{selected_year} 年會員分佈：人數 vs 營收貢獻",
            xaxis_title="年度總次數",
            yaxis=dict(title='人數', side='left'),
            yaxis2=dict(title='總營收 ($)', overlaying='y', side='right'),
            hovermode='x unified',
            height=500,
            barmode='overlay'
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # 洞察
        one_timer = freq_dist_display[freq_dist_display['年度總次數'].astype(str) == '1'].iloc[0]
        one_timer_pct = (one_timer['人數'] / freq_dist_display['人數'].sum() * 100)
        one_timer_revenue_pct = (one_timer['總營收'] / freq_dist_display['總營收'].sum() * 100)
        
        col1, col2 = st.columns(2)
        with col1:
            st.warning(f"""
            **⚠️ 一次性過客虛胖陷阱**
            - 只來 1 次的客人：**{one_timer['人數']:,} 人** ({one_timer_pct:.1f}%)
            - 但只貢獻：**{one_timer_revenue_pct:.1f}%** 的營收
            - 💡 **行動方案**：設計「首購後 7 天內第二次優惠」
            """)
        with col2:
            vip_revenue = freq_dist_display[freq_dist_display['年度總次數'].astype(str).isin(['>10', '10', '9', '8'])]['總營收'].sum()
            vip_pct = (vip_revenue / freq_dist_display['總營收'].sum() * 100)
            st.success(f"""
            **✅ 80/20 法則驗證**
            - 高頻客戶（8次以上）貢獻：**{vip_pct:.1f}%** 營收
            - 💡 **行動方案**：VIP 專屬儲值方案，鎖定忠誠客戶
            """)
        
        st.markdown("---")
        
        # === 圖表二：留存斷崖圖（Magic Number）===
        st.subheader("📉 圖表二：留存斷崖圖（找出魔法數字）")
        st.info("💡 看看從第幾次開始，客人就不會走了？")
        
        # 這裡需要「第幾次來」的欄位，如果沒有則用訂單時間排序模擬
        if '第幾次來' in df.columns:
            visit_order_col = '第幾次來'
        else:
            # 為每個會員的訂單按時間排序，生成「第幾次來」
            df_sorted = df.sort_values(['會員', '訂單時間'])
            df_sorted['第幾次來'] = df_sorted.groupby('會員').cumcount() + 1
            df = df_sorted.copy()
            visit_order_col = '第幾次來'
        
        # 計算每個「第幾次來」的會員數
        visit_funnel = df[df['年份'] == selected_year].groupby(visit_order_col)['會員'].nunique().reset_index()
        visit_funnel.columns = ['第幾次來', '會員數']
        visit_funnel = visit_funnel[visit_funnel['第幾次來'] <= 10]  # 只看前 10 次
        
        # 計算留存率
        visit_funnel['留存率'] = (visit_funnel['會員數'] / visit_funnel.iloc[0]['會員數'] * 100).round(1)
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=visit_funnel['第幾次來'],
            y=visit_funnel['會員數'],
            name='會員數',
            marker_color='#4ECDC4',
            text=visit_funnel['會員數'],
            textposition='outside'
        ))
        fig2.add_trace(go.Scatter(
            x=visit_funnel['第幾次來'],
            y=visit_funnel['留存率'],
            name='留存率 (%)',
            mode='lines+markers',
            marker_color='red',
            yaxis='y2',
            line=dict(width=3)
        ))
        fig2.update_layout(
            title="留存斷崖圖：看清楚客人在第幾次流失",
            xaxis_title="第幾次來",
            yaxis=dict(title='會員數', side='left'),
            yaxis2=dict(title='留存率 (%)', overlaying='y', side='right'),
            height=500
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        # 找出 Magic Number（留存率下降幅度變小的點）
        if len(visit_funnel) > 2:
            visit_funnel['留存率降幅'] = visit_funnel['留存率'].diff().abs()
            magic_idx = visit_funnel[visit_funnel['第幾次來'] >= 3]['留存率降幅'].idxmin()
            magic_number = visit_funnel.loc[magic_idx, '第幾次來']
            
            st.success(f"""
            🎯 **找到魔法數字：第 {magic_number} 次**
            
            從數據看，客人來到第 {magic_number} 次後，流失率開始趨緩，代表他們進入「習慣養成期」。
            
            💡 **2026 核心 KPI：讓客人買到第 {magic_number} 次**
            """)
        
        st.markdown("---")
        
        # === 圖表三：帶路雞 vs 毒藥（首購商品歸因）===
        st.subheader("🐔 圖表三：帶路雞 vs 毒藥（第一次買什麼最重要！）")
        st.info("💡 找出哪個產品能讓客人變鐵粉，哪個產品會讓客人做一次就跑")
        
        # 取得每個會員的首購商品
        first_purchase = df.sort_values('訂單時間').groupby('會員').first().reset_index()
        
        # 計算終身交易次數
        lifetime_freq = df.groupby('會員')['訂單號碼'].nunique().reset_index()
        lifetime_freq.columns = ['會員', '終身交易次數']
        
        # 合併
        first_purchase_analysis = first_purchase[['會員', '品項']].merge(lifetime_freq, on='會員')
        
        # 如果有「客群狀態」欄位，加入分析
        if '客群狀態' in df.columns:
            member_status = df.groupby('會員')['客群狀態'].last().reset_index()
            first_purchase_analysis = first_purchase_analysis.merge(member_status, on='會員', how='left')
            
            # 按首購品項分組統計
            product_attribution = first_purchase_analysis.groupby(['品項', '客群狀態']).size().reset_index(name='人數')
            
            # 計算每個品項的總人數和活躍比例
            product_total = first_purchase_analysis.groupby('品項').size().reset_index(name='總人數')
            product_total = product_total[product_total['總人數'] >= 5]  # 至少 5 人
            
            # 透視表：品項 vs 客群狀態
            pivot_status = product_attribution.pivot_table(
                index='品項', 
                columns='客群狀態', 
                values='人數', 
                fill_value=0
            ).reset_index()
            
            # 合併總人數
            pivot_status = pivot_status.merge(product_total, on='品項')
            
            # 計算活躍比例
            if '🟢 活躍中' in pivot_status.columns:
                pivot_status['活躍比例'] = (pivot_status['🟢 活躍中'] / pivot_status['總人數'] * 100).round(1)
                pivot_status = pivot_status.sort_values('活躍比例', ascending=False)
                
                # 堆疊柱狀圖
                fig3 = go.Figure()
                
                status_colors = {
                    '🟢 活躍中': '#2ECC71',
                    '🟡 需喚醒': '#F39C12',
                    '🔴 已流失': '#E74C3C'
                }
                
                for status in ['🟢 活躍中', '🟡 需喚醒', '🔴 已流失']:
                    if status in pivot_status.columns:
                        fig3.add_trace(go.Bar(
                            name=status,
                            x=pivot_status['品項'].head(15),
                            y=pivot_status[status].head(15),
                            marker_color=status_colors.get(status, 'gray'),
                            text=pivot_status[status].head(15),
                            textposition='inside'
                        ))
                
                fig3.update_layout(
                    title="首購商品歸因：帶路雞 🐔 vs 毒藥 ☠️（只看第一次購買）",
                    xaxis_title="首購品項",
                    yaxis_title="人數",
                    barmode='stack',
                    height=500,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig3, use_container_width=True)
                
                # 標示帶路雞和毒藥
                col1, col2 = st.columns(2)
                
                with col1:
                    top_products = pivot_status.head(3)
                    st.success(f"""
                    **🐔 帶路雞商品 TOP 3**
                    
                    1. **{top_products.iloc[0]['品項']}**：活躍率 {top_products.iloc[0]['活躍比例']}%
                    2. **{top_products.iloc[1]['品項']}**：活躍率 {top_products.iloc[1]['活躍比例']}%
                    3. **{top_products.iloc[2]['品項']}**：活躍率 {top_products.iloc[2]['活躍比例']}%
                    
                    💡 **策略**：明年廣告預算重押這些項目！
                    """)
                
                with col2:
                    worst_products = pivot_status.tail(3).sort_values('活躍比例')
                    st.error(f"""
                    **☠️ 毒藥商品 TOP 3**
                    
                    1. **{worst_products.iloc[0]['品項']}**：活躍率僅 {worst_products.iloc[0]['活躍比例']}%
                    2. **{worst_products.iloc[1]['品項']}**：活躍率僅 {worst_products.iloc[1]['活躍比例']}%
                    3. **{worst_products.iloc[2]['品項']}**：活躍率僅 {worst_products.iloc[2]['活躍比例']}%
                    
                    ⚠️ **策略**：停止對新客推廣，檢討品質或砍掉！
                    """)
        else:
            st.warning("⚠️ 資料中缺少「客群狀態」欄位，無法進行完整歸因分析")
    
    # ========== Tab 2: 會員黏著度分析 ==========
    with tab2:
        st.header("📊 會員黏著度分佈（一年來幾次？）")
        st.info("💡 這是你的「會員金字塔」，看清楚誰是主力客群")
        
        # 計算年度總次數分佈
        freq_table = df_year.groupby('年度總次數')['會員'].nunique().reset_index()
        freq_table.columns = ['年度總次數', '人數']
        freq_table = freq_table.sort_values('年度總次數')
        
        # 計算百分比
        freq_table['佔比 (%)'] = (freq_table['人數'] / freq_table['人數'].sum() * 100).round(2)
        
        # 顯示表格
        st.dataframe(
            freq_table.style.format({'佔比 (%)': '{:.2f}%'}),
            use_container_width=True,
            hide_index=True
        )
        
        # 圓餅圖
        col1, col2 = st.columns(2)
        
        with col1:
            # 合併 >5 次的客戶
            freq_table_grouped = freq_table.copy()
            freq_table_grouped.loc[freq_table_grouped['年度總次數'] > 5, '年度總次數'] = '>5'
            freq_table_grouped = freq_table_grouped.groupby('年度總次數').sum().reset_index()
            
            fig_pie = px.pie(
                freq_table_grouped,
                values='人數',
                names='年度總次數',
                title='會員黏著度分佈',
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # 累積曲線
            freq_table['累積人數'] = freq_table['人數'].cumsum()
            freq_table['累積佔比'] = (freq_table['累積人數'] / freq_table['人數'].sum() * 100).round(1)
            
            fig_cumulative = px.line(
                freq_table,
                x='年度總次數',
                y='累積佔比',
                title='累積分佈曲線',
                markers=True
            )
            fig_cumulative.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80%")
            st.plotly_chart(fig_cumulative, use_container_width=True)
        
        # 洞察
        one_time_pct = freq_table[freq_table['年度總次數'] == 1]['佔比 (%)'].values[0] if 1 in freq_table['年度總次數'].values else 0
        loyal_pct = freq_table[freq_table['年度總次數'] >= 3]['佔比 (%)'].sum()
        
        st.success(f"""
        **📊 會員金字塔洞察**
        
        - 只來 1 次的過客：**{one_time_pct:.1f}%**（目標：讓他們變成「來 2 次」）
        - 來 3 次以上的主力客群：**{loyal_pct:.1f}%**（目標：用儲值方案鎖住他們）
        
        💡 **行動方案**：針對「來 2 次」的客人，發送「第 3 次半價」優惠，推過魔法數字門檻
        """)
    
    # ========== Tab 3: 產品波士頓矩陣 ==========
    with tab3:
        st.header("💰 產品波士頓矩陣（BCG Matrix）")
        st.info("💡 找出誰是「帶路雞（引流款）」、誰是「搖錢樹（利潤款）」")
        
        # 按品項統計
        product_matrix = df_year.groupby('品項').agg({
            '訂單號碼': 'nunique',
            '總價': 'sum'
        }).reset_index()
        product_matrix.columns = ['品項', '訂單數', '總營收']
        product_matrix['平均客單價'] = (product_matrix['總營收'] / product_matrix['訂單數']).round(0)
        
        # 篩選訂單數 >= 5
        product_matrix = product_matrix[product_matrix['訂單數'] >= 5]
        
        # 計算中位數作為象限分界
        median_orders = product_matrix['訂單數'].median()
        median_revenue = product_matrix['總營收'].median()
        
        # 分類
        def classify_product(row):
            if row['訂單數'] >= median_orders and row['總營收'] >= median_revenue:
                return '⭐ 明星商品'
            elif row['訂單數'] >= median_orders and row['總營收'] < median_revenue:
                return '🐔 帶路雞'
            elif row['訂單數'] < median_orders and row['總營收'] >= median_revenue:
                return '💎 潛力股'
            else:
                return '❌ 拖油瓶'
        
        product_matrix['分類'] = product_matrix.apply(classify_product, axis=1)
        
        # 氣泡圖
        fig_bcg = px.scatter(
            product_matrix,
            x='訂單數',
            y='總營收',
            size='平均客單價',
            color='分類',
            hover_data=['品項', '平均客單價'],
            title='產品波士頓矩陣：象限分析',
            color_discrete_map={
                '⭐ 明星商品': '#2ECC71',
                '🐔 帶路雞': '#3498DB',
                '💎 潛力股': '#F39C12',
                '❌ 拖油瓶': '#95A5A6'
            },
            size_max=60
        )
        fig_bcg.add_vline(x=median_orders, line_dash="dash", line_color="gray", annotation_text="人氣中位數")
        fig_bcg.add_hline(y=median_revenue, line_dash="dash", line_color="gray", annotation_text="營收中位數")
        fig_bcg.update_layout(height=600)
        st.plotly_chart(fig_bcg, use_container_width=True)
        
        # 四象限表格
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("**⭐ 明星商品（高人氣、高營收）**")
            stars = product_matrix[product_matrix['分類'] == '⭐ 明星商品'].sort_values('總營收', ascending=False)
            st.dataframe(stars[['品項', '訂單數', '總營收', '平均客單價']], hide_index=True)
            st.caption("💡 策略：主力推廣，千萬不能斷貨，廣告預算砸這裡")
            
            st.info("**🐔 帶路雞（高人氣、低營收）**")
            chicken = product_matrix[product_matrix['分類'] == '🐔 帶路雞'].sort_values('訂單數', ascending=False)
            st.dataframe(chicken[['品項', '訂單數', '總營收', '平均客單價']], hide_index=True)
            st.caption("💡 策略：用來吸客，設計升單話術（順便推美白、保養）")
        
        with col2:
            st.warning("**💎 潛力股（低人氣、高營收）**")
            potential = product_matrix[product_matrix['分類'] == '💎 潛力股'].sort_values('總營收', ascending=False)
            st.dataframe(potential[['品項', '訂單數', '總營收', '平均客單價']], hide_index=True)
            st.caption("💡 策略：多賣一個抵十個腋下，加強員工教育訓練")
            
            st.error("**❌ 拖油瓶（低人氣、低營收）**")
            losers = product_matrix[product_matrix['分類'] == '❌ 拖油瓶'].sort_values('總營收')
            st.dataframe(losers[['品項', '訂單數', '總營收', '平均客單價']], hide_index=True)
            st.caption("⚠️ 策略：砍掉！不要佔用價目表版面")
    
    # ========== Tab 4: 客群健康度雷達 ==========
    with tab4:
        st.header("🎯 客群健康度雷達（RFM Analysis）")
        st.info("💡 盤點你的「資產」還有多少是活的")
        
        if '客群狀態' in df.columns and '分類' in df.columns:
            # 透視表：分類 vs 客群狀態
            health_matrix = df_year.groupby(['分類', '客群狀態'])['會員'].nunique().reset_index()
            health_pivot = health_matrix.pivot_table(
                index='分類',
                columns='客群狀態',
                values='會員',
                fill_value=0
            )
            
            # 計算百分比
            health_pivot_pct = health_pivot.div(health_pivot.sum(axis=1), axis=0) * 100
            
            # 顯示表格
            st.subheader("📊 各分類客群健康度表")
            st.dataframe(
                health_pivot.style.background_gradient(cmap='RdYlGn', axis=1),
                use_container_width=True
            )
            
            # 堆疊柱狀圖
            fig_health = go.Figure()
            
            status_colors = {
                '🟢 活躍中': '#2ECC71',
                '🟡 需喚醒': '#F39C12',
                '🔴 已流失': '#E74C3C'
            }
            
            for status in health_pivot.columns:
                fig_health.add_trace(go.Bar(
                    name=status,
                    x=health_pivot.index,
                    y=health_pivot[status],
                    marker_color=status_colors.get(status, 'gray'),
                    text=health_pivot[status],
                    textposition='inside'
                ))
            
            fig_health.update_layout(
                title="客群健康度診斷（各分類）",
                xaxis_title="分類",
                yaxis_title="會員數",
                barmode='stack',
                height=500
            )
            st.plotly_chart(fig_health, use_container_width=True)
            
            # 警示分析
            st.subheader("⚠️ 健康度警示")
            
            for category in health_pivot.index:
                total = health_pivot.loc[category].sum()
                if '🔴 已流失' in health_pivot.columns:
                    lost_pct = (health_pivot.loc[category, '🔴 已流失'] / total * 100)
                    if lost_pct > 50:
                        st.error(f"""
                        **{category}** 的流失率達 **{lost_pct:.1f}%**！
                        
                        可能原因：
                        - 美容師技術或服務有問題
                        - 客人做一次就不來了
                        - 缺乏喚醒機制
                        
                        💡 **行動代號**：針對「🟡 需喚醒」的客人，發送專屬優惠簡訊
                        """)
        else:
            st.warning("⚠️ 資料中缺少「客群狀態」或「分類」欄位")
    
    # ========== Tab 5: 促銷方案成效分析 ==========
    with tab5:
        st.header("📈 促銷方案成效分析（A/B Testing）")
        st.info("💡 到底「買3送1」好賣，還是「買9送3」好賣？")
        
        if '銷售方案' in df.columns:
            # 透視表：品項 vs 銷售方案
            promo_matrix = df_year.groupby(['品項', '銷售方案']).agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            
            promo_pivot = promo_matrix.pivot_table(
                index='品項',
                columns='銷售方案',
                values='總價',
                fill_value=0
            )
            
            # 篩選有數據的品項
            promo_pivot = promo_pivot[promo_pivot.sum(axis=1) > 0].head(20)
            
            # 堆疊柱狀圖
            fig_promo = go.Figure()
            
            for plan in promo_pivot.columns:
                fig_promo.add_trace(go.Bar(
                    name=plan,
                    x=promo_pivot.index,
                    y=promo_pivot[plan],
                    text=promo_pivot[plan].apply(lambda x: f'${x:,.0f}' if x > 0 else ''),
                    textposition='inside'
                ))
            
            fig_promo.update_layout(
                title="各品項 x 銷售方案營收分佈",
                xaxis_title="品項",
                yaxis_title="總營收 ($)",
                barmode='stack',
                height=600
            )
            st.plotly_chart(fig_promo, use_container_width=True)
            
            # 方案偏好分析
            st.subheader("📊 方案偏好洞察")
            
            plan_summary = df_year.groupby('銷售方案').agg({
                '訂單號碼': 'nunique',
                '總價': 'sum'
            }).reset_index()
            plan_summary.columns = ['銷售方案', '訂單數', '總營收']
            plan_summary['平均客單'] = (plan_summary['總營收'] / plan_summary['訂單數']).round(0)
            plan_summary = plan_summary.sort_values('總營收', ascending=False)
            
            st.dataframe(plan_summary, use_container_width=True, hide_index=True)
            
            # 洞察
            if len(plan_summary) > 0:
                top_plan = plan_summary.iloc[0]
                st.success(f"""
                **💰 最賺錢方案：{top_plan['銷售方案']}**
                
                - 訂單數：{top_plan['訂單數']:,} 筆
                - 總營收：${top_plan['總營收']:,.0f}
                - 平均客單：${top_plan['平均客單']:,.0f}
                
                💡 **策略建議**：
                - 如果客人只願意買「體驗價」→ 代表對效果沒信心，推出「中型套餐（買3送1）」降低門檻
                - 如果「買9送3」賣得好 → 現金流漂亮，庫存囤在客人身上，繼續主推
                """)
        else:
            st.warning("⚠️ 資料中缺少「銷售方案」欄位")

else:
    st.info("👈 請從左側上傳交易資料檔案（可一次選擇 10-20 個檔案）")
    st.markdown("""
    ### 💅 美業 CRM 分析系統功能
    
    #### 🔹 會員深度分析（三大核心圖）
    1. **會員分佈圖**：拒絕平均值，看清過客 vs 鐵粉
    2. **留存斷崖圖**：尋找 Magic Number（要來第幾次才不會走）
    3. **帶路雞 vs 毒藥**：首購商品歸因分析
    
    #### 🔹 會員黏著度分析
    - 一年來幾次？會員金字塔分佈
    - 累積分佈曲線
    
    #### 🔹 產品波士頓矩陣（BCG Matrix）
    - ⭐ 明星商品（高人氣、高營收）
    - 🐔 帶路雞（高人氣、低營收）
    - 💎 潛力股（低人氣、高營收）
    - ❌ 拖油瓶（低人氣、低營收）
    
    #### 🔹 客群健康度雷達（RFM Analysis）
    - 各分類的流失率診斷
    - 針對「需喚醒」客戶的行動方案
    
    #### 🔹 促銷方案成效分析
    - 買3送1 vs 買9送3 哪個好賣？
    - A/B Testing 數據支持決策
    
    ---
    
    **📋 需要的資料欄位**：
    訂單號碼、訂單時間、會員、品項、總價、分類、銷售方案、客群狀態（選填）
    """)
