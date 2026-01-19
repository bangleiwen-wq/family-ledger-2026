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
# 模块 3: 投资与报表 (Report) - V4.1 最终完美版
# ==========================================
elif menu == "📈 投资与报表 (Report)":
    st.header("📊 财务深度分析 (V4.1)")
    
    df_logs = get_data("logs")
    df_assets = get_data("assets")

    # --- 1. 顶部全局筛选栏 ---
    with st.expander("🗓️ 报表筛选设置", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # 获取数据中存在的所有月份
            if not df_logs.empty:
                df_logs['month_str'] = df_logs['date'].dt.strftime('%Y-%m')
                all_months = sorted(df_logs['month_str'].unique(), reverse=True)
                # 默认选最近一个月
                selected_month = st.selectbox("选择月份", all_months, index=0)
            else:
                selected_month = datetime.now().strftime('%Y-%m')
        with col_f2:
            # 默认全选
            all_users = ["老公", "老婆", "家庭公用"]
            selected_user = st.multiselect("筛选成员", all_users, default=all_users)

    # --- 2. 数据准备与过滤 ---
    if not df_logs.empty:
        # 按月份过滤
        df_view = df_logs[df_logs['month_str'] == selected_month]
        # 按成员过滤
        if selected_user:
            df_view = df_view[df_view['user'].isin(selected_user)]
        
        # 分离收支
        expense_df = df_view[df_view['type'] == '支出'].copy()
        income_df = df_view[df_view['type'] == '收入'].copy()
    else:
        expense_df = pd.DataFrame()
        income_df = pd.DataFrame()

    # --- 3. 核心页面 Tabs ---
    tab1, tab2, tab3 = st.tabs(["📊 支出透视 (消费)", "💰 资产与投资", "📅 趋势对比"])

    # === Tab 1: 支出透视 (修复了空值报错问题) ===
    with tab1:
        if expense_df.empty:
            st.info(f"{selected_month} 暂无支出记录")
        else:
            # A. 核心大数字
            total_exp = expense_df['amount'].sum()
            total_inc = income_df['amount'].sum()
            balance = total_inc - total_exp
            
            k1, k2, k3 = st.columns(3)
            k1.metric("本月总支出", f"¥ {total_exp:,.2f}", border=True)
            k2.metric("本月总收入", f"¥ {total_inc:,.2f}", border=True)
            k3.metric("本月结余", f"¥ {balance:,.2f}", delta_color="normal" if balance>0 else "inverse", border=True)

            st.divider()

            # B. 矩形树图 (Treemap) - 含防报错逻辑
            st.subheader("🗺️ 消费结构全景图 (点击方块可查看细项)")
            st.caption("矩形越大代表花钱越多。点击某个分类（如'餐饮'），可自动展开查看具体的备注。")
            
            # =========== 🛡️ 防报错清洗代码 START ===========
            # 1. 填充空值：把所有的 NaN 变成空字符串
            expense_df['note'] = expense_df['note'].fillna("")
            expense_df['category'] = expense_df['category'].fillna("未分类")
            
            # 2. 强制转为字符串：防止数字或日期格式导致 Plotly 崩溃
            expense_df['note'] = expense_df['note'].astype(str)
            expense_df['category'] = expense_df['category'].astype(str)
            
            # 3. 优化显示：如果备注是空的，显示“无备注”，否则图表上是个很难看的空白
            expense_df['note_display'] = expense_df['note'].apply(lambda x: "无备注" if x.strip() == "" else x)
            # =========== 🛡️ 防报错清洗代码 END =============
            
            fig_tree = px.treemap(
                expense_df, 
                path=[px.Constant("总支出"), 'category', 'note_display'], # 层次：总 -> 分类 -> 备注
                values='amount',
                color='category', 
                hover_data=['user', 'date'],
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_tree.update_traces(textinfo="label+value") 
            st.plotly_chart(fig_tree, use_container_width=True)

            # C. 透视明细表 (含合计)
            st.divider()
            st.subheader("🧾 分类支出明细表 (含小计)")
            
            # 左侧：分类排行榜
            category_group = expense_df.groupby('category')['amount'].sum().reset_index()
            category_group = category_group.sort_values('amount', ascending=False)
            
            c_sel1, c_sel2 = st.columns([1, 2])
            
            with c_sel1:
                st.markdown("**1️⃣ 各类汇总排行榜**")
                category_group['占比'] = (category_group['amount'] / total_exp * 100).map('{:.1f}%'.format)
                category_group['金额'] = category_group['amount'].map('¥ {:,.2f}'.format)
                
                st.dataframe(
                    category_group[['category', '金额', '占比']], 
                    hide_index=True, 
                    use_container_width=True,
                    height=400
                )

            with c_sel2:
                st.markdown("**2️⃣ 详细流水 (含合计)**")
                # 下拉筛选
                cat_options = ["(查看全部)"] + category_group['category'].tolist()
                selected_cat_detail = st.selectbox("🔍 筛选分类查看明细:", cat_options)
                
                if selected_cat_detail == "(查看全部)":
                    detail_data = expense_df
                else:
                    detail_data = expense_df[expense_df['category'] == selected_cat_detail]
                
                # 准备显示数据
                display_cols = detail_data[['date', 'category', 'note', 'user', 'account', 'amount']].copy()
                display_cols['date'] = display_cols['date'].dt.strftime('%m-%d')
                display_cols = display_cols.sort_values('date', ascending=False)
                
                # --- 增加合计行 ---
                current_total = display_cols['amount'].sum()
                total_row = pd.DataFrame([{
                    'date': '🔴 合计', 
                    'category': '', 'note': '', 'user': '', 'account': '', 
                    'amount': current_total
                }])
                final_display = pd.concat([display_cols, total_row], ignore_index=True)
                
                st.dataframe(
                    final_display, 
                    column_config={
                        "date": "日期",
                        "category": "分类",
                        "note": "备注说明",
                        "user": "经手人",
                        "account": "支付账户",
                        "amount": st.column_config.NumberColumn("金额", format="¥ %.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )

    # === Tab 2: 资产与投资 (保留 V3.0 逻辑) ===
    with tab2:
        st.subheader("🚀 资产净值与投资")
        if not df_assets.empty:
            # 取最新资产快照
            latest_assets = df_assets.sort_values('date').groupby(['asset_name', 'owner']).tail(1)
            total_net_worth = latest_assets['balance'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("家庭当前净资产", f"¥ {total_net_worth:,.2f}")
            
            # 计算投资盈亏
            invest_logs = df_logs[df_logs['type'] == '投资投入']
            total_invested = invest_logs['amount'].sum()
            
            invest_assets = latest_assets[latest_assets['asset_type'].str.contains('基金|股票|理财')]
            current_market_value = invest_assets['balance'].sum()
            
            pnl = current_market_value - total_invested
            pnl_ratio = (pnl / total_invested * 100) if total_invested > 0 else 0
            
            c2.metric("投资浮动盈亏", f"¥ {pnl:,.2f}", f"{pnl_ratio:.2f}%")
            
            st.divider()
            st.subheader("📈 Top 5 资产账户")
            top_assets = latest_assets.sort_values('balance', ascending=False).head(5)
            fig_bar = px.bar(top_assets, x='balance', y='asset_name', color='owner', orientation='h')
            st.plotly_chart(fig_bar, use_container_width=True)

    # === Tab 3: 趋势对比 (年度视角) ===
    with tab3:
        st.subheader("📅 年度收支趋势")
        # 排除投资投入，只看收支
        df_trend = df_logs[df_logs['type'].isin(['收入', '支出'])].copy()
        
        if not df_trend.empty:
            # 重新计算 month_str 确保不受顶部筛选影响
            df_trend['month_str'] = df_trend['date'].dt.strftime('%Y-%m')
            
            monthly_trend = df_trend.groupby(['month_str', 'type'])['amount'].sum().reset_index()
            
            fig_trend = px.bar(
                monthly_trend, 
                x='month_str', y='amount', color='type', 
                barmode='group',
                color_discrete_map={'支出': '#EF553B', '收入': '#00CC96'},
                title="每月收支对比",
                text_auto='.2s'
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.divider()
            st.subheader("📉 结余走势")
            df_pivot = monthly_trend.pivot(index='month_str', columns='type', values='amount').fillna(0)
            df_pivot['结余'] = df_pivot.get('收入', 0) - df_pivot.get('支出', 0)
            st.line_chart(df_pivot['结余'])
