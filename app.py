import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="2026 全能家庭CFO", page_icon="💰", layout="wide")

# --- 样式优化 ---
st.markdown("""
    <style>
    .metric-card {background-color: #f9f9f9; border-left: 5px solid #ff4b4b; padding: 10px; margin: 5px;}
    </style>
    """, unsafe_allow_html=True)

st.title("💰 2026 全能家庭 CFO (V3.0)")

# --- 连接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

# --- 侧边栏 ---
with st.sidebar:
    st.header("功能导航")
    menu = st.radio("", ["📝 流水记账 (Flow)", "🏦 资产盘点 (Stock)", "📈 投资与报表 (Report)"])
    st.info("💡 V3.0 新特性：\n1. 支出关联具体账户\n2. 投资盈亏自动计算\n3. 资产与账本联动")

# 读取资产数据用于下拉框 (全局复用)
df_assets_global = get_data("assets")
# 获取所有“归属人-资产名”的组合，做成列表
if not df_assets_global.empty:
    # 拼接一下名字，方便选择，例如 "老公-支付宝"
    df_assets_global['full_name'] = df_assets_global['owner'].astype(str) + " - " + df_assets_global['asset_name'].astype(str)
    # 获取去重后的资产列表
    asset_options = sorted(df_assets_global['full_name'].unique().tolist())
else:
    asset_options = ["现金", "银行卡", "支付宝", "微信"] # 默认兜底

# ==========================================
# 模块 1: 流水记账 (Flow) - 支持关联账户
# ==========================================
if menu == "📝 流水记账 (Flow)":
    st.header("📝 记一笔")
    
    df_logs = get_data("logs")

    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            date = st.date_input("日期", datetime.now())
            txn_type = st.selectbox("类型", ["支出", "收入", "投资投入"], help="买基金请选'投资投入'")
        with col2:
            amount = st.number_input("金额", min_value=0.01, format="%.2f")
            # 这里的账户列表来自资产表
            account = st.selectbox("支付/入账账户", asset_options, help="这笔钱是从哪个资产里出去/进来的？")
        with col3:
            # 动态分类
            if txn_type == "投资投入":
                category = "理财本金"
            else:
                category = st.selectbox("分类", [
                    "餐饮美食", "交通出行", "居家生活", "房贷还款", "车贷还款", 
                    "育儿-教育", "育儿-生活", "保险费", "人情红包", 
                    "工资收入", "兼职收入", "其他"
                ])
            user = st.selectbox("经手人", ["老公", "老婆", "家庭公用"])
        
        note = st.text_input("备注", placeholder="如果是定投，请备注具体基金名")

        submitted = st.form_submit_button("💾 提交记录", use_container_width=True)

        if submitted:
            # 数据结构需包含 account
            new_entry = pd.DataFrame([{
                "date": pd.to_datetime(date),
                "type": txn_type,
                "amount": amount,
                "category": category,
                "account": account, # 新增字段
                "user": user,
                "note": note
            }])
            
            if df_logs.empty:
                updated_df = new_entry
            else:
                updated_df = pd.concat([df_logs, new_entry], ignore_index=True)
            
            save_data(updated_df, "logs")
            st.success(f"✅ 已记录：从【{account}】{txn_type} {amount} 元")
            if txn_type == "投资投入":
                st.toast("💡 提示：'投资投入'已记录为本金，请记得去'资产盘点'更新该基金的最新市值！")

    # 展示最近记录
    if not df_logs.empty:
        st.subheader("📋 最近流水")
        # 简单处理一下显示顺序
        display_cols = ['date', 'type', 'amount', 'category', 'account', 'user', 'note']
        # 确保列存在，防止旧数据报错
        existing_cols = [c for c in display_cols if c in df_logs.columns]
        st.dataframe(df_logs[existing_cols].sort_values(by="date", ascending=False).head(10), use_container_width=True)

# ==========================================
# 模块 2: 资产盘点 (Stock)
# ==========================================
elif menu == "🏦 资产盘点 (Stock)":
    st.header("🏦 资产校准 (Snapshot)")
    st.info("💡 这是一个【校准】动作。请定期打开你的银行App/券商App，填入看到的【最终余额/市值】。")
    
    df_assets = get_data("assets")

    with st.expander("➕ 更新/新增资产", expanded=True):
        with st.form("asset_update"):
            c1, c2 = st.columns(2)
            with c1:
                owner = st.selectbox("归属人", ["老公", "老婆", "家庭/联名"])
                # 这里允许手动输入新名字，也允许选旧名字
                existing_names = df_assets['asset_name'].unique().tolist() if not df_assets.empty else []
                # 使用 selectbox 但允许输入不太容易，Streamlit建议直接用 text_input 配合 placeholder
                asset_name = st.text_input("资产名称", placeholder="如：易方达蓝筹、招行卡、借呗")
            with c2:
                asset_type = st.selectbox("类型", ["资金账户", "基金/股票", "固定资产", "负债"])
                balance = st.number_input("当前最新余额/市值", step=100.0)
            
            date_update = st.date_input("校准日期", datetime.now())
            
            if st.form_submit_button("💾 保存快照", use_container_width=True):
                if not asset_name:
                    st.error("请填写名称")
                else:
                    new_asset = pd.DataFrame([{
                        "date": pd.to_datetime(date_update),
                        "asset_name": asset_name,
                        "asset_type": asset_type,
                        "owner": owner,
                        "balance": balance
                    }])
                    if df_assets.empty:
                        df_new = new_asset
                    else:
                        df_new = pd.concat([df_assets, new_asset], ignore_index=True)
                    save_data(df_new, "assets")
                    st.success("资产数据已更新！")

    # 资产展示逻辑 (只取最新)
    if not df_assets.empty:
        latest = df_assets.sort_values('date').groupby(['asset_name', 'owner']).tail(1).reset_index(drop=True)
        st.divider()
        col1, col2 = st.columns([1, 2])
        with col1:
            total = latest['balance'].sum()
            st.metric("家庭总净值", f"¥ {total:,.2f}")
            # 投资类资产总值
            invest_total = latest[latest['asset_type'] == '基金/股票']['balance'].sum()
            st.metric("投资持仓市值", f"¥ {invest_total:,.2f}")
        with col2:
            fig = px.bar(latest, x='balance', y='asset_name', color='owner', orientation='h', title="各项资产分布")
            st.plotly_chart(fig, use_container_width=True)
# ==========================================
# 模块 3: 投资与报表 (Report) - V3.1 终极融合版
# ==========================================
elif menu == "📈 投资与报表 (Report)":
    st.header("📈 财务深度分析驾驶舱")
    
    df_logs = get_data("logs")
    df_assets = get_data("assets")

    # 定义三个子页面
    tab1, tab2, tab3 = st.tabs(["📊 收支透视", "🚀 投资仪表盘", "🏠 专项追踪"])

    # --- Tab 1: 收支透视 (日常开销去哪了？) ---
    with tab1:
        if not df_logs.empty:
            now = datetime.now()
            # 筛选本月
            this_month = df_logs[(df_logs['date'].dt.month == now.month) & (df_logs['date'].dt.year == now.year)]
            # 排除投资投入，只看消费
            expense_df = this_month[this_month['type'] == '支出']
            income_df = this_month[this_month['type'] == '收入']
            
            # 1. 核心指标
            c1, c2, c3 = st.columns(3)
            c1.metric("本月真实消费", f"¥ {expense_df['amount'].sum():,.2f}")
            c2.metric("本月入账", f"¥ {income_df['amount'].sum():,.2f}")
            balance = income_df['amount'].sum() - expense_df['amount'].sum()
            c3.metric("本月结余", f"¥ {balance:,.2f}", delta_color="normal" if balance > 0 else "inverse")
            
            st.divider()

            # 2. 图表分析区
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("🥧 钱花在什么地方？(分类)")
                if not expense_df.empty:
                    # 旭日图：同时显示一级分类和经手人
                    fig_cat = px.sunburst(
                        expense_df, 
                        path=['category', 'user'], 
                        values='amount',
                        color='category',
                        title=f"{now.month}月 支出结构细分"
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.info("本月暂无支出数据")

            with col_chart2:
                st.subheader("💳 钱从哪个账户出的？(渠道)")
                if 'account' in expense_df.columns and not expense_df.empty:
                    account_group = expense_df.groupby('account')['amount'].sum().reset_index()
                    fig_acc = px.pie(account_group, values='amount', names='account', hole=0.4, title="支付渠道占比")
                    st.plotly_chart(fig_acc, use_container_width=True)
            
            # 3. 年度趋势 (柱状图)
            st.subheader("📅 年度收支趋势")
            # 按月汇总
            df_logs['month_str'] = df_logs['date'].dt.strftime('%Y-%m')
            # 过滤掉投资投入，只看收支
            df_trend = df_logs[df_logs['type'].isin(['收入', '支出'])]
            if not df_trend.empty:
                monthly_trend = df_trend.groupby(['month_str', 'type'])['amount'].sum().reset_index()
                fig_trend = px.bar(
                    monthly_trend, 
                    x='month_str', y='amount', color='type', 
                    barmode='group',
                    color_discrete_map={'支出': '#EF553B', '收入': '#00CC96'},
                    title="2026 每月收支对比"
                )
                st.plotly_chart(fig_trend, use_container_width=True)

    # --- Tab 2: 投资仪表盘 (钱生钱了吗？) ---
    with tab2:
        st.subheader("🚀 财富增值中心")
        
        if not df_logs.empty and not df_assets.empty:
            # 1. 计算逻辑
            invest_logs = df_logs[df_logs['type'] == '投资投入']
            total_invested = invest_logs['amount'].sum()
            
            latest_assets = df_assets.sort_values('date').groupby(['asset_name', 'owner']).tail(1)
            # 筛选 基金/股票 类资产
            invest_assets = latest_assets[latest_assets['asset_type'].str.contains('基金|股票|理财')]
            current_market_value = invest_assets['balance'].sum()
            
            pnl = current_market_value - total_invested
            pnl_ratio = (pnl / total_invested * 100) if total_invested > 0 else 0
            
            # 2. 盈亏指标
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("累计投入本金", f"¥ {total_invested:,.2f}", help="所有记账流水中标记为'投资投入'的总和")
            kpi2.metric("当前持仓市值", f"¥ {current_market_value:,.2f}", help="资产盘点中所有'基金/股票'类资产的最新余额总和")
            kpi3.metric("总浮动盈亏", f"¥ {pnl:,.2f}", f"{pnl_ratio:.2f}%")
            
            st.divider()
            
            # 3. 投资分布图
            c1, c2 = st.columns(2)
            with c1:
                st.caption("📈 我们买了哪些基金/股票？")
                if not invest_assets.empty:
                    fig_inv = px.pie(invest_assets, values='balance', names='asset_name', title="投资持仓分布")
                    st.plotly_chart(fig_inv, use_container_width=True)
            
            with c2:
                st.caption("👤 谁的投资眼光更好？")
                if not invest_assets.empty:
                    owner_pnl = invest_assets.groupby('owner')['balance'].sum().reset_index()
                    fig_owner_inv = px.bar(owner_pnl, x='owner', y='balance', title="家庭成员持仓市值对比")
                    st.plotly_chart(fig_owner_inv, use_container_width=True)

    # --- Tab 3: 专项追踪 (房贷/车贷/育儿) ---
    with tab3:
        st.subheader("🎯 重点项目年度追踪")
        st.caption("自动筛选包含 '房贷', '车贷', '育儿', '保险' 关键词的支出")
        
        # 关键词筛选逻辑
        tags = ["房贷", "车贷", "育儿", "保险"]
        mask = df_logs['category'].astype(str).str.contains('|'.join(tags))
        df_special = df_logs[mask]
        
        if not df_special.empty:
            # 统计总额
            total_special = df_special['amount'].sum()
            st.metric("本年度重点项目总支出", f"¥ {total_special:,.2f}")
            
            # 趋势堆叠图
            df_special['month'] = df_special['date'].dt.strftime('%Y-%m')
            fig_special = px.bar(
                df_special, 
                x='month', y='amount', color='category', 
                title="重点支出月度变化",
                text_auto=True
            )
            st.plotly_chart(fig_special, use_container_width=True)
            
            # 明细表
            st.dataframe(df_special[['date', 'category', 'amount', 'note', 'user']].sort_values(by='date', ascending=False), use_container_width=True)
        else:
            st.info("暂无相关记录。请在记账时选择包含'房贷/育儿'等字样的分类。")
