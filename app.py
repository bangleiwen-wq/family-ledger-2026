import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="2026 爱家记账 Pro", page_icon="🏠", layout="wide")

# --- 自定义样式 (让报表更专业) ---
st.markdown("""
    <style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; margin: 10px 0;}
    </style>
    """, unsafe_allow_html=True)

st.title("🏠 2026 家庭财务指挥中心 (Pro)")

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

# --- 工具函数：计算环比 ---
def calculate_delta(current_val, prev_val):
    if prev_val == 0:
        return 0
    return (current_val - prev_val) / prev_val * 100

# --- 侧边栏导航 ---
with st.sidebar:
    st.header("功能导航")
    menu = st.radio("", ["📝 日常记账", "🏦 资产盘点", "📊 深度报表"])
    st.divider()
    st.info("💡 这是一个专业版工具，支持多维度资产分析与环比数据对比。")

# ==========================================
# 模块 1: 日常记账 (Cash Flow)
# ==========================================
if menu == "📝 日常记账":
    st.header("📝 记一笔")
    
    df_logs = get_data("logs")

    with st.expander("录入交易", expanded=True):
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input("日期", datetime.now())
                txn_type = st.selectbox("类型", ["支出", "收入"], help="房贷车贷请选支出")
                amount = st.number_input("金额", min_value=0.01, step=10.0, format="%.2f")
            with col2:
                # 升级后的分类体系
                category_options = {
                    "刚性支出": ["房贷还款", "车贷还款", "房租物业", "水电煤网", "保险费"],
                    "家庭育儿": ["育儿-奶粉/食品", "育儿-尿裤/用品", "育儿-教育/课外", "育儿-医疗/疫苗", "育儿-玩具/书籍"],
                    "日常生活": ["餐饮美食", "交通出行", "超市购物", "服饰美容", "通讯费"],
                    "休闲人情": ["休闲娱乐", "人情红包", "孝敬长辈", "旅游度假"],
                    "其他": ["医疗保健", "投资亏损", "其他支出"],
                    "收入来源": ["工资收入", "奖金/分红", "投资收益", "兼职外快", "礼金收入"]
                }
                
                # 平铺分类用于下拉框 (也可以做二级联动，这里为了方便直接平铺)
                flat_categories = []
                for group, items in category_options.items():
                    flat_categories += items
                
                category = st.selectbox("分类", flat_categories)
                user = st.selectbox("经手人/对象", ["老公", "老婆", "家庭公用", "孩子"])
                note = st.text_input("备注 (必填: 具体的名目)")

            submitted = st.form_submit_button("💾 提交记录", use_container_width=True)

            if submitted:
                new_entry = pd.DataFrame([{
                    "date": pd.to_datetime(date),
                    "type": txn_type,
                    "amount": amount,
                    "category": category,
                    "user": user,
                    "note": note
                }])
                
                if df_logs.empty:
                    updated_df = new_entry
                else:
                    updated_df = pd.concat([df_logs, new_entry], ignore_index=True)
                
                save_data(updated_df, "logs")
                st.success("✅ 记账成功！")

    # 简单流水展示
    if not df_logs.empty:
        st.subheader("📋 最近 10 笔记录")
        st.dataframe(
            df_logs.sort_values(by="date", ascending=False).head(10), 
            use_container_width=True,
            hide_index=True
        )

# ==========================================
# 模块 2: 资产盘点 (Net Worth) - 升级版
# ==========================================
elif menu == "🏦 资产盘点":
    st.header("🏦 家庭资产负债表")
    st.caption("建议每月 1 号更新一次各项账户余额。")

    df_assets = get_data("assets")

    # --- 更新资产表单 ---
    with st.expander("➕ 更新账户余额", expanded=True):
        with st.form("asset_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                a_owner = st.selectbox("归属人", ["老公", "老婆", "家庭/联名"])
                a_name = st.text_input("账户名称", placeholder="例: 支付宝余额, 招行卡, 股票-茅台")
            with c2:
                a_type = st.selectbox("资产性质", 
                    ["流动资金 (现金/活期)", "低风险理财 (定期/债基)", "高风险投资 (股票/偏股)", "固定资产 (房/车估值)", "负债 (信用卡/贷款余额)"]
                )
            with c3:
                a_balance = st.number_input("当前总值 (负债填负数)", step=100.0)
                a_date = st.date_input("更新日期", datetime.now())

            asset_submitted = st.form_submit_button("💾 保存资产快照", use_container_width=True)

            if asset_submitted:
                if not a_name:
                    st.error("必须填写账户名称")
                else:
                    # 确保包含 owner 字段
                    new_asset = pd.DataFrame([{
                        "date": pd.to_datetime(a_date),
                        "asset_name": a_name,
                        "asset_type": a_type,
                        "owner": a_owner, 
                        "balance": a_balance
                    }])
                    
                    if df_assets.empty:
                        updated_assets = new_asset
                    else:
                        updated_assets = pd.concat([df_assets, new_asset], ignore_index=True)
                    
                    save_data(updated_assets, "assets")
                    st.success(f"✅ {a_owner} 的 {a_name} 更新成功！")

    # --- 资产透视 ---
    if not df_assets.empty:
        st.divider()
        
        # 逻辑：取每个账户最新的一条记录
        latest_assets = df_assets.sort_values('date').groupby(['asset_name', 'owner']).tail(1).reset_index(drop=True)
        
        total_net_worth = latest_assets['balance'].sum()
        
        # 核心大指标
        st.metric("💰 家庭当前净资产 (Net Worth)", f"¥ {total_net_worth:,.2f}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("按归属人分析")
            # 饼图：谁管的钱多？
            fig_owner = px.pie(latest_assets, values='balance', names='owner', hole=0.4, title="资金归属分布")
            st.plotly_chart(fig_owner, use_container_width=True)
            
        with col2:
            st.subheader("按资产性质分析")
            # 饼图：投资结构
            fig_type = px.pie(latest_assets, values='balance', names='asset_type', title="资产配置结构 (风险分布)")
            st.plotly_chart(fig_type, use_container_width=True)

        st.subheader("📊 各项资产明细")
        # 格式化表格
        display_df = latest_assets[['owner', 'asset_name', 'asset_type', 'balance', 'date']].sort_values(by='owner')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ==========================================
# 模块 3: 深度报表 (Analytics) - 专业级
# ==========================================
elif menu == "📊 深度报表":
    st.header("📊 财务深度分析")
    
    df_logs = get_data("logs")
    
    if df_logs.empty:
        st.info("请先录入数据")
    else:
        # --- 时间筛选与数据准备 ---
        now = datetime.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        
        # 本月数据
        df_this_month = df_logs[
            (df_logs['date'] >= this_month_start) & 
            (df_logs['date'] < (this_month_start + timedelta(days=32)).replace(day=1))
        ]
        
        # 上月数据 (用于环比)
        df_last_month = df_logs[
            (df_logs['date'] >= last_month_start) & 
            (df_logs['date'] < this_month_start)
        ]
        
        # --- 1. 核心 KPI 看板 (带环比) ---
        c1, c2, c3, c4 = st.columns(4)
        
        # 计算本月
        tm_income = df_this_month[df_this_month['type']=='收入']['amount'].sum()
        tm_expense = df_this_month[df_this_month['type']=='支出']['amount'].sum()
        tm_balance = tm_income - tm_expense
        tm_savings_rate = (tm_balance / tm_income * 100) if tm_income > 0 else 0
        
        # 计算上月
        lm_income = df_last_month[df_last_month['type']=='收入']['amount'].sum()
        lm_expense = df_last_month[df_last_month['type']=='支出']['amount'].sum()
        
        # 渲染指标
        c1.metric("本月收入", f"¥{tm_income:,.0f}", delta=f"{calculate_delta(tm_income, lm_income):.1f}% 环比", delta_color="normal")
        c2.metric("本月支出", f"¥{tm_expense:,.0f}", delta=f"{calculate_delta(tm_expense, lm_expense):.1f}% 环比", delta_color="inverse")
        c3.metric("本月结余", f"¥{tm_balance:,.0f}")
        c4.metric("本月储蓄率", f"{tm_savings_rate:.1f}%", help="理想储蓄率建议在 30% 以上")
        
        st.divider()
        
        # --- 2. 支出结构深度分析 ---
        col_main, col_sub = st.columns([2, 1])
        
        with col_main:
            st.subheader("💸 本月钱花哪儿了？")
            if not df_this_month[df_this_month['type']=='支出'].empty:
                # 旭日图：不仅看大类，还能看具体的备注（如果有数据量够大）或者直接看分类
                fig_sun = px.sunburst(
                    df_this_month[df_this_month['type']=='支出'], 
                    path=['category', 'user'], 
                    values='amount',
                    title="支出结构透视 (点击扇形可下钻)",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.info("本月暂无支出")
                
        with col_sub:
            st.subheader("🏆 支出排行榜")
            if not df_this_month.empty:
                top_expense = df_this_month[df_this_month['type']=='支出'].groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
                st.table(top_expense)

        # --- 3. 房贷/车贷/育儿 专项追踪 ---
        st.divider()
        st.subheader("🎯 重点项目追踪 (2026年度)")
        
        # 筛选特定关键词
        special_tags = ["房贷", "车贷", "育儿"]
        # 创建一个逻辑 mask
        mask = df_logs['category'].str.contains('|'.join(special_tags))
        df_special = df_logs[mask]
        
        if not df_special.empty:
            # 柱状图：按月堆叠
            df_special['month_str'] = df_special['date'].dt.strftime('%Y-%m')
            fig_special = px.bar(
                df_special, 
                x='month_str', 
                y='amount', 
                color='category', 
                title="房贷·车贷·育儿 趋势图",
                text_auto=True
            )
            st.plotly_chart(fig_special, use_container_width=True)
        else:
            st.caption("暂无房贷、车贷或育儿相关记录。")
