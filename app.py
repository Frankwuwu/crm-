import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="門店 CRM 數據分析系統", layout="wide")
st.title("🏥 醫美診所 CRM 數據分析系統")

# 側邊欄：上傳檔案
st.sidebar.header("📁 資料上傳")
uploaded_file = st.sidebar.file_uploader(
    "上傳交易資料 (Excel/CSV)", 
    type=['xlsx', 'csv', 'parquet']
)

if uploaded_file is not None:
    # 讀取資料
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.parquet'):
        df = pd.read_parquet(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    st.success(f"✅ 成功載入 {len(df):,} 筆交易資料")
    
    # 資料預處理
    df['訂單時間'] = pd.to_datetime(df['訂單時間'])
    df['年份'] = df['訂單時間'].dt.year
    
    # 選擇分析年度
    years = sorted(df['年份'].unique())
    selected_year = st.sidebar.selectbox("選擇分析年度", years, index=len(years)-1)
    
    # 建立頁籤
    tab1, tab2, tab3 = st.tabs([
        "📊 步驟一：交易次數分佈分析", 
        "🔄 步驟二：會員流動分析", 
        "🎯 步驟三：商品歸因分析"
    ])
    
    # ========== 步驟一：交易次數分佈分析 ==========
    with tab1:
        st.header(f"{selected_year} 年度交易次數分佈分析")
        st.info("💡 別看平均值，看清楚誰是金主、誰是過客")
        
        # 計算每個會員的交易次數
        member_stats = df[df['年份'] == selected_year].groupby('會員').agg({
            '訂單號碼': 'nunique',  # 訂單數
            '總價': ['sum', 'mean'],  # 總營收、平均客單
        }).reset_index()
        
        member_stats.columns = ['會員', '交易次數', '年度消費額', '平均客單']
        
        # 按交易次數分群
        max_freq = int(member_stats['交易次數'].max())
        freq_groups = []
        
        for freq in range(1, min(11, max_freq + 1)):  # 1-10 次
            group_data = member_stats[member_stats['交易次數'] == freq]
            freq_groups.append({
                '交易次數': f'= {freq}',
                '人數': len(group_data),
                '營收': group_data['年度消費額'].sum(),
                '訂單數': group_data['交易次數'].sum(),
                '人均貢獻': group_data['年度消費額'].mean(),
                '平均客單': group_data['平均客單'].mean()
            })
        
        # > 10 次
        if max_freq > 10:
            group_data = member_stats[member_stats['交易次數'] > 10]
            freq_groups.append({
                '交易次數': '> 10',
                '人數': len(group_data),
                '營收': group_data['年度消費額'].sum(),
                '訂單數': group_data['交易次數'].sum(),
                '人均貢獻': group_data['年度消費額'].mean(),
                '平均客單': group_data['平均客單'].mean()
            })
        
        # 轉為 DataFrame
        analysis_df = pd.DataFrame(freq_groups)
        total_members = analysis_df['人數'].sum()
        total_revenue = analysis_df['營收'].sum()
        total_orders = analysis_df['訂單數'].sum()
        
        # 計算佔比
        analysis_df['人數佔比'] = (analysis_df['人數'] / total_members * 100).round(1)
        analysis_df['營收佔比'] = (analysis_df['營收'] / total_revenue * 100).round(1)
        analysis_df['訂單佔比'] = (analysis_df['訂單數'] / total_orders * 100).round(1)
        
        # 格式化顯示
        display_df = analysis_df.copy()
        display_df['營收'] = display_df['營收'].apply(lambda x: f"${x:,.0f}")
        display_df['人均貢獻'] = display_df['人均貢獻'].apply(lambda x: f"${x:,.0f}")
        display_df['平均客單'] = display_df['平均客單'].apply(lambda x: f"${x:,.0f}")
        display_df['人數佔比'] = display_df['人數佔比'].apply(lambda x: f"{x}%")
        display_df['營收佔比'] = display_df['營收佔比'].apply(lambda x: f"{x}%")
        display_df['訂單佔比'] = display_df['訂單佔比'].apply(lambda x: f"{x}%")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # 視覺化：雙軸圖
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                x=analysis_df['交易次數'], 
                y=analysis_df['人數'],
                name='人數',
                marker_color='lightblue'
            ))
            fig1.add_trace(go.Scatter(
                x=analysis_df['交易次數'], 
                y=analysis_df['人均貢獻'],
                name='人均貢獻',
                yaxis='y2',
                marker_color='red',
                line=dict(width=3)
            ))
            fig1.update_layout(
                title="人數分佈 vs 人均貢獻",
                yaxis=dict(title='人數'),
                yaxis2=dict(title='人均貢獻($)', overlaying='y', side='right'),
                hovermode='x unified'
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.pie(
                analysis_df, 
                values='營收', 
                names='交易次數',
                title='營收貢獻佔比'
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # 自動洞察
        st.subheader("🔍 自動洞察")
        one_time = analysis_df[analysis_df['交易次數'] == '= 1'].iloc[0]
        vip = analysis_df[analysis_df['交易次數'].isin(['> 10', '= 10', '= 9', '= 8'])]['營收'].sum()
        vip_pct = (vip / total_revenue * 100)
        
        st.warning(f"""
        **⚠️ 一次性過客陷阱**  
        - 只買 1 次的客人有 **{one_time['人數']:,} 人** ({one_time['人數佔比']}%)
        - 但只貢獻 **{one_time['營收佔比']}** 的營收
        - 💡 建議：設計「首購後 7 天內第二單優惠」機制
        """)
        
        st.success(f"""
        **✅ 80/20 法則驗證**  
        - 高頻客戶（8次以上）貢獻了 **{vip_pct:.1f}%** 的營收
        - 💡 建議：為高頻客戶建立 VIP 專屬服務流程
        """)
    
    # ========== 步驟二：會員流動分析 ==========
    with tab2:
        st.header("🔄 跨年度會員流動分析")
        
        if len(years) < 2:
            st.warning("⚠️ 需要至少兩年的資料才能進行流動分析")
        else:
            prev_year = st.selectbox("選擇基準年", years[:-1], index=len(years)-2)
            curr_year = prev_year + 1
            
            st.info(f"💡 追蹤 {prev_year} 年的客戶在 {curr_year} 年的行為變化")
            
            # 計算兩年的會員交易次數
            prev_members = df[df['年份'] == prev_year].groupby('會員')['訂單號碼'].nunique()
            curr_members = df[df['年份'] == curr_year].groupby('會員')['訂單號碼'].nunique()
            
            # 建立流動矩陣
            flow_data = pd.DataFrame({
                f'{prev_year}年次數': prev_members,
                f'{curr_year}年次數': 0
            })
            flow_data.loc[curr_members.index, f'{curr_year}年次數'] = curr_members
            
            # VIP 定義（> 5 次）
            vip_threshold = 5
            prev_vip = flow_data[flow_data[f'{prev_year}年次數'] > vip_threshold]
            
            # 分類 VIP 流向
            vip_flow = {
                '流失（0次）': len(prev_vip[prev_vip[f'{curr_year}年次數'] == 0]),
                '降級（1-2次）': len(prev_vip[prev_vip[f'{curr_year}年次數'].between(1, 2)]),
                '維持（3-5次）': len(prev_vip[prev_vip[f'{curr_year}年次數'].between(3, 5)]),
                '留存/升級（>5次）': len(prev_vip[prev_vip[f'{curr_year}年次數'] > vip_threshold])
            }
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("流失", f"{vip_flow['流失（0次）']} 人", 
                       delta=f"-{vip_flow['流失（0次）']/len(prev_vip)*100:.1f}%",
                       delta_color="inverse")
            col2.metric("降級", f"{vip_flow['降級（1-2次）']} 人")
            col3.metric("維持", f"{vip_flow['維持（3-5次）']} 人")
            col4.metric("留存/升級", f"{vip_flow['留存/升級（>5次）']} 人",
                       delta=f"+{vip_flow['留存/升級（>5次）']/len(prev_vip)*100:.1f}%")
            
            # 魔法數字分析
            st.subheader("🎯 尋找魔法數字（回購率曲線）")
            
            repurchase_rates = []
            for freq in range(1, 11):
                cohort = flow_data[flow_data[f'{prev_year}年次數'] == freq]
                if len(cohort) > 0:
                    repurchase_rate = (cohort[f'{curr_year}年次數'] > 0).sum() / len(cohort) * 100
                    repurchase_rates.append({
                        '購買次數': freq,
                        '回購率': repurchase_rate,
                        '樣本數': len(cohort)
                    })
            
            repurchase_df = pd.DataFrame(repurchase_rates)
            
            fig3 = px.line(
                repurchase_df, 
                x='購買次數', 
                y='回購率',
                markers=True,
                title=f'{prev_year} 年各次數級距的 {curr_year} 年回購率'
            )
            fig3.update_traces(line_color='#FF6B6B', line_width=3)
            fig3.update_layout(yaxis_title='回購率 (%)', xaxis_title='購買次數')
            st.plotly_chart(fig3, use_container_width=True)
            
            # 找出魔法數字
            magic_number = repurchase_df[repurchase_df['回購率'] > 60]['購買次數'].min()
            if pd.notna(magic_number):
                st.success(f"""
                🎯 **找到魔法數字：{int(magic_number)} 次**  
                當客戶購買達到 {int(magic_number)} 次後，回購率達到 {repurchase_df[repurchase_df['購買次數']==magic_number]['回購率'].values[0]:.1f}%
                
                💡 **2026 核心 KPI：讓客人買到第 {int(magic_number)} 次**
                """)
    
    # ========== 步驟三：商品歸因分析 ==========
    with tab3:
        st.header("🎯 商品歸因分析：帶路雞 vs 毒藥")
        st.info("💡 找出讓人上癮的「帶路雞」與讓人離開的「毒藥」")
        
        if len(years) < 2:
            st.warning("⚠️ 需要至少兩年的資料才能進行歸因分析")
        else:
            # 取得會員首購商品
            first_purchase = df.sort_values('訂單時間').groupby('會員').first().reset_index()
            
            # 計算每個會員的總交易次數
            member_lifetime = df.groupby('會員')['訂單號碼'].nunique().reset_index()
            member_lifetime.columns = ['會員', '終身交易次數']
            
            # 合併首購商品與終身價值
            attribution = first_purchase[['會員', '品項', '訂單時間']].merge(
                member_lifetime, on='會員'
            )
            
            # 分析各品項的帶客能力
            product_performance = attribution.groupby('品項').agg({
                '會員': 'count',
                '終身交易次數': ['mean', 'median']
            }).reset_index()
            
            product_performance.columns = ['品項', '首購人數', '平均終身次數', '中位數終身次數']
            product_performance = product_performance[product_performance['首購人數'] >= 5]  # 至少 5 人
            product_performance = product_performance.sort_values('平均終身次數', ascending=False)
            
            # 標記帶路雞與毒藥
            threshold_high = product_performance['平均終身次數'].quantile(0.75)
            threshold_low = product_performance['平均終身次數'].quantile(0.25)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🐔 帶路雞商品（高留存）")
                winners = product_performance[product_performance['平均終身次數'] >= threshold_high].head(10)
                winners['標籤'] = '🌟 帶路雞'
                st.dataframe(winners, use_container_width=True, hide_index=True)
                
                if len(winners) > 0:
                    top_product = winners.iloc[0]
                    st.success(f"""
                    **明星商品：{top_product['品項']}**  
                    - 首購人數：{top_product['首購人數']:.0f} 人
                    - 平均終身交易：{top_product['平均終身次數']:.1f} 次
                    - 💡 建議：加大廣告預算推廣此商品
                    """)
            
            with col2:
                st.subheader("☠️ 毒藥商品（高流失）")
                losers = product_performance[product_performance['平均終身次數'] <= threshold_low].head(10)
                losers['標籤'] = '⚠️ 毒藥'
                st.dataframe(losers, use_container_width=True, hide_index=True)
                
                if len(losers) > 0:
                    worst_product = losers.iloc[0]
                    st.error(f"""
                    **高風險商品：{worst_product['品項']}**  
                    - 首購人數：{worst_product['首購人數']:.0f} 人
                    - 平均終身交易：{worst_product['平均終身次數']:.1f} 次
                    - ⚠️ 建議：停止對新客推廣，檢討品質或定位
                    """)
            
            # 散點圖
            fig4 = px.scatter(
                product_performance, 
                x='首購人數', 
                y='平均終身次數',
                size='首購人數',
                hover_data=['品項'],
                title='商品首購人數 vs 終身價值',
                color='平均終身次數',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig4, use_container_width=True)

else:
    st.info("👈 請從左側上傳交易資料檔案開始分析")
    st.markdown("""
    ### 📋 需要的資料欄位
    請確保您的資料包含以下欄位：
    - 訂單號碼、訂單時間、會員、品項、總價
    
    ### 🎯 系統功能
    1. **交易次數分佈分析**：別看平均值，看清楚誰是金主
    2. **會員流動分析**：追蹤 VIP 留存與魔法數字
    3. **商品歸因分析**：找出帶路雞與毒藥商品
    """)
