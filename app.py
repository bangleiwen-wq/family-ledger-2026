import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 页面配置 ---
st.set_page_config(page_title="2026 爱家记账 & 资产管理", page_icon="💰", layout="wide")
st.title("🏡 2026 家庭财务中心")

# --- 连接 Google Sheets ---
# 使用 ttl=0 确保每次读取都是最新的数据
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        # 确保日期列是 datetime 类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception:
        # 如果表是空的，返回空的 DataFrame
        return pd.DataFrame()

def save_data(df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear() # 强制清除缓存

# --- 侧边栏导航 ---
menu = st.sidebar.radio("导航菜单", ["日常记账 (Cash Flow)", "资产管理 (Net Worth)", "统计报表 (Dashboard)"])

# ==========================================
# 模块 1: 日常记账 (Cash Flow)
# ==========================================
if menu == "日常记账 (Cash Flow)":
    st.header("📝 记一笔")
    
    # 现有数据读取
    df_logs = get_data("logs")

    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("日期", datetime.now())
            txn_type = st.selectbox("类型", ["支出", "收入"])
            amount = st.number_input("金额", min_value=0.01, step=0.01, format="%.2f")
        with col2:
            category = st.selectbox("分类", [
                "餐饮美食", "交通出行", "居家生活", "服饰美容", 
                "休闲娱乐", "医疗保健", "人情往来", "投资亏损", 
                "工资收入", "投资收益", "兼职外快", "其他"
            ])
            user = st.selectbox("成员", ["老公", "老婆", "家庭公用"])
            note = st.text_input("备注 (选填)")

        submitted = st.form_submit_button("💾 提交记录")

        if submitted:
            new_entry = pd.DataFrame([{
                "date": pd.to_datetime(date),
                "type": txn_type,
                "amount": amount,
                "category": category,
                "user": user,
                "note": note
            }])
            
            # 如果 df_logs 为空，直接使用 new_entry，否则拼接
            if df_logs.empty:
                updated_df = new_entry
            else:
                updated_df = pd.concat([df_logs, new_entry], ignore_index=True)
                
            save_data(updated_df, "logs")
            st.success("✅ 记账成功！已同步至云端。")

    # 显示最近 5 条记录
    if not df_logs.empty:
        st.subheader("📋 最近记录")
        st.dataframe(df_logs.sort_values(by="date", ascending=False).head(5), use_container_width=True)

# ==========================================
# 模块 2: 资产盘点 (Net Worth)
# ==========================================
elif menu == "资产管理 (Net Worth)":
    st.header("🏦 资产盘点")
    st.info("💡 建议每月盘点一次。输入各项资产（如银行卡、股票账户）当前的**总余额**。")

    df_assets = get_data("assets")

    # --- 功能 A: 更新资产 ---
    with st.expander("➕ 更新资产余额", expanded=True):
        with st.form("asset_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                a_date = st.date_input("盘点日期", datetime.now())
                a_name = st.text_input("资产名称", placeholder="例如：招商银行、股票-三一光电")
            with col2:
                a_type = st.selectbox("资产类型", ["现金/存款", "股票/基金", "理财产品", "房产/车产", "负债/信用卡"])
                a_balance = st.number_input("当前余额 (负债请填负数)", step=100.0)

            asset_submitted = st.form_submit_button("💾 更新资产快照")

            if asset_submitted:
                if not a_name:
                    st.error("请输入资产名称")
                else:
                    new_asset = pd.DataFrame([{
                        "date": pd.to_datetime(a_date),
                        "asset_name": a_name,
                        "asset_type": a_type,
                        "balance": a_balance
                    }])
                    
                    if df_assets.empty:
                        updated_assets = new_asset
                    else:
                        updated_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                    
                    save_data(updated_assets, "assets")
                    st.success(f"✅ {a_name} 余额已更新！")

    # --- 功能 B: 资产看板 ---
    if not df_assets.empty:
        st.divider()
        st.subheader("💰 资产概览 (最新快照)")
        
        # 逻辑：按资产名称分组，取日期最近的一条
        latest_assets = df_assets.sort_values('date').groupby('asset_name').tail(1)
        
        # 计算总资产
        total_net_worth = latest_assets['balance'].sum()
        
        # 指标卡
        st.metric(label="当前家庭总净值", value=f"¥ {total_net_worth:,.2f}")

        # 资产分布图
        if not latest_assets.empty:
            fig_pie = px.pie(
                latest_assets, 
                values='balance', 
                names='asset_type', 
                title='资产类型分布',
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # 显示明细表
            st.caption("各项资产最新余额：")
            st.dataframe(latest_assets[['asset_name', 'asset_type', 'balance', 'date']].sort_values(by='balance', ascending=False), use_container_width=True)

# ==========================================
# 模块 3: 统计报表 (Dashboard)
# ==========================================
elif menu == "统计报表 (Dashboard)":
    st.header("📊 财务分析报表")
    
    df_logs = get_data("logs")
    df_assets = get_data("assets")

    if df_logs.empty:
        st.warning("暂无记账数据，请先去“日常记账”录入。")
    else:
        # --- 1. 核心指标 ---
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # 筛选本月数据
        mask_month = (df_logs['date'].dt.month == current_month) & (df_logs['date'].dt.year == current_year)
        df_month = df_logs[mask_month]
        
        monthly_income = df_month[df_month['type'] == '收入']['amount'].sum()
        monthly_expense = df_month[df_month['type'] == '支出']['amount'].sum()
        monthly_balance = monthly_income - monthly_expense

        col1, col2, col3 = st.columns(3)
        col1.metric("本月收入", f"¥ {monthly_income:,.2f}")
        col2.metric("本月支出", f"¥ {monthly_expense:,.2f}", delta_color="inverse")
        col3.metric("本月结余", f"¥ {monthly_balance:,.2f}", delta=f"{monthly_balance:,.2f}")

        st.divider()

        # --- 2. 收支分析图表 ---
        c1, c2 = st.columns(2)
        
        with c1:
            # 本月支出分类饼图
            expense_df = df_month[df_month['type'] == '支出']
            if not expense_df.empty:
                fig_cat = px.pie(expense_df, values='amount', names='category', title=f'{current_month}月 支出结构')
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info("本月暂无支出记录")

        with c2:
            # 年度月度趋势图 (Bar)
            df_year = df_logs[df_logs['date'].dt.year == current_year]
            if not df_year.empty:
                # 按月和类型汇总
                df_year['month'] = df_year['date'].dt.strftime('%Y-%m')
                monthly_trend = df_year.groupby(['month', 'type'])['amount'].sum().reset_index()
                
                fig_trend = px.bar(
                    monthly_trend, 
                    x='month', 
                    y='amount', 
                    color='type', 
                    barmode='group',
                    title=f'{current_year}年 收支趋势',
                    color_discrete_map={'支出': '#EF553B', '收入': '#00CC96'}
                )
                st.plotly_chart(fig_trend, use_container_width=True)

        # --- 3. 净值趋势 (可选高级功能) ---
        if not df_assets.empty:
            st.divider()
            st.subheader("📈 净值增长趋势")
            # 逻辑：按日期汇总当天的所有资产总和
            # 注意：这里做简化处理，直接按记录日期的总和展示。更精确的做法是插值，但作为家庭版足够了。
            net_worth_trend = df_assets.groupby('date')['balance'].sum().reset_index()
            
            fig_line = px.line(
                net_worth_trend, 
                x='date', 
                y='balance', 
                title='家庭总资产变化',
                markers=True
            )
            st.plotly_chart(fig_line, use_container_width=True)
