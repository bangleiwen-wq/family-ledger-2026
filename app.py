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
# 模块 3: 投资与报表 (Report) - V5.1 预算预警版
# ==========================================
elif menu == "📈 投资与报表 (Report)":
    st.header("📊 财务深度分析 (V5.1)")
    
    df_logs = get_data("logs")
    df_assets = get_data("assets")

    # --- 1. 预算设置中心 (新增) ---
    with st.sidebar.expander("⚙️ 每月预算设置", expanded=False):
        st.write("设置每月固定支出预算：")
        b_house = st.number_input("房贷预算", value=5000)
        b_car = st.number_input("车贷预算", value=2000)
        b_life = st.number_input("生活费(伙食等)预算", value=3000)
        # 你可以根据自己的分类名修改下面的 key
        budget_map = {
            "房贷": b_house,
            "车贷": b_car,
            "餐饮伙食": b_life, # 确保这里的名称和你记账时选的分类名一致
            "生活费": b_life
        }

    # --- 2. 顶部全局筛选栏 ---
    with st.expander("🗓️ 报表筛选设置", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if not df_logs.empty:
                df_logs['month_str'] = df_logs['date'].dt.strftime('%Y-%m')
                all_months = sorted(df_logs['month_str'].unique(), reverse=True)
                selected_month = st.selectbox("选择月份", all_months, index=0)
            else:
                selected_month = datetime.now().strftime('%Y-%m')
        with col_f2:
            all_users = ["老公", "老婆", "家庭公用"]
            selected_user = st.multiselect("筛选成员", all_users, default=all_users)

    # --- 3. 数据准备 ---
    if not df_logs.empty:
        df_view = df_logs[df_logs['month_str'] == selected_month]
        if selected_user:
            df_view = df_view[df_view['user'].isin(selected_user)]
        
        expense_df = df_view[df_view['type'] == '支出'].copy()
        income_df = df_view[df_view['type'] == '收入'].copy()
    else:
        expense_df = pd.DataFrame()
        income_df = pd.DataFrame()

    # --- 4. 预算进度条分析 (新增核心功能) ---
    if not expense_df.empty:
        st.subheader("⚠️ 关键预算执行进度")
        cols = st.columns(len(budget_map))
        
        for idx, (cat_name, b_amount) in enumerate(budget_map.items()):
            # 计算该分类已花的钱
            actual_spent = expense_df[expense_df['category'].str.contains(cat_name, na=False)]['amount'].sum()
            percent = min(actual_spent / b_amount, 1.2) if b_amount > 0 else 0 # 最高显示120%
            
            with cols[idx % len(cols)]:
                # 颜色逻辑：超过90%变橙色，超过100%变红色
                bar_color = "normal"
                if percent >= 1.0:
                    st.error(f"**{cat_name}·超支**")
                elif percent >= 0.8:
                    st.warning(f"**{cat_name}·告急**")
                else:
                    st.success(f"**{cat_name}·正常**")
                
                st.progress(percent if percent <= 1.0 else 1.0)
                st.caption(f"预算 ¥{b_amount:,.0f} | 已花 ¥{actual_spent:,.0f}")

    # --- 5. 核心页面 Tabs ---
    tab1, tab_inc, tab2, tab3 = st.tabs(["📊 支出透视", "💰 收入透视", "🏦 资产与投资", "📅 趋势对比"])

    # === Tab 1: 支出透视 ===
    with tab1:
        if expense_df.empty:
            st.info(f"{selected_month} 暂无支出记录")
        else:
            total_exp = expense_df['amount'].sum()
            total_inc = income_df['amount'].sum()
            balance = total_inc - total_exp
            
            # 顶部大数字看板
            k1, k2, k3 = st.columns(3)
            k1.metric("本月总支出", f"¥ {total_exp:,.2f}")
            # 计算总储蓄率
            save_rate = (balance/total_inc*100) if total_inc > 0 else 0
            k2.metric("本月结余", f"¥ {balance:,.2f}", delta=f"{save_rate:.1f}% 储蓄率")
            k3.metric("支出笔数", f"{len(expense_df)} 笔")

            st.divider()
            
            # 矩形树图
            expense_df['note'] = expense_df['note'].fillna("").astype(str)
            expense_df['category'] = expense_df['category'].fillna("未分类").astype(str)
            expense_df['note_display'] = expense_df['note'].apply(lambda x: "无备注" if x.strip() == "" else x)
            
            fig_tree_exp = px.treemap(
                expense_df, 
                path=[px.Constant("总支出"), 'category', 'note_display'],
                values='amount',
                color='category', 
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_tree_exp, use_container_width=True)

            # 详细列表
            st.markdown("**🔍 支出详细流水**")
            st.dataframe(
                expense_df[['date', 'category', 'amount', 'note', 'user', 'account']].sort_values('date', ascending=False),
                hide_index=True,
                use_container_width=True
            )

    # === Tab 2: 收入透视 ===
    with tab_inc:
        if income_df.empty:
            st.info(f"{selected_month} 暂无收入记录")
        else:
            total_inc = income_df['amount'].sum()
            st.metric("本月总收入", f"¥ {total_inc:,.2f}")
            
            income_df['note'] = income_df['note'].fillna("").astype(str)
            income_df['category'] = income_df['category'].fillna("其他收入").astype(str)
            income_df['note_display'] = income_df['note'].apply(lambda x: "无备注" if x.strip() == "" else x)

            fig_tree
