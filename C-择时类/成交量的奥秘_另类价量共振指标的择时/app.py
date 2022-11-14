from typing import Dict, List, Union

import empyrical as ep
import pandas as pd
import streamlit as st
from scr.backtest_engine import get_backtesting
from scr.create_signal import bulk_signal, get_signal_status
from scr.load_excel_data import (
    query_data,
    query_stock_index_classify,
    query_sw_classify,
)
from scr.plotly_chart import GridPlotly, plot_candlestick, add_shape_to_ohlc
from scr.tear import analysis_rets, analysis_trade, get_backtest_report
from scr.utils import BACKTEST_CONFIG, transform_status_table
from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.graph_objects as go

st.set_page_config(page_title='量价共振信号', layout='wide', page_icon=':ambulance:')

st.sidebar.subheader("选择行业或宽基")

# 设置基础参数

INDEX_CLASSIFY: Dict = query_stock_index_classify()
INDEX_SEC2CODE: Dict = {v: k for k, v in INDEX_CLASSIFY.items()}
SW_CLASSIFY: Dict = query_sw_classify()
SW_SEC2CODE: Dict = {v: k for k, v in SW_CLASSIFY.items()}

SELECTIONS: Dict = {'申万一级行业': 'sw', '宽基指数': 'index'}
STOCK_POOL: Dict = {'sw': SW_CLASSIFY, 'index': INDEX_CLASSIFY}
SEC2CODE: Dict = {'sw': SW_SEC2CODE, 'index': INDEX_SEC2CODE}

selections: Union[str, List] = st.sidebar.selectbox("选择申万一级行业或宽基指数",
                                                    options=['申万一级行业', '宽基指数'],
                                                    index=1)

level: str = SELECTIONS[selections]  # 选择的sw或者index
stocks_pool: List = list(STOCK_POOL[level].values())
# 标的的名称
stock_selection = st.sidebar.selectbox("选择标的", options=stocks_pool, index=0)
# 获取需要回测的标的
code: str = SEC2CODE[level][stock_selection]

price: pd.DataFrame = query_data(
    code,
    "2010-01-01",
    "2022-10-11",
    fields=["close", 'low', 'high', 'open', "volume"],
    method=level)
price.set_index("trade_date", inplace=True)

bt_result = get_backtesting(price, stock_selection)

# 计算回测相关风险信息
# Backtesting Risk Report
bt_risk_table, cumulative_chart, maxdrawdowns_chart, underwater_chart, annual_returns_chart, monthly_return_heatmap_chart, monthly_return_dist_chart = analysis_rets(
    price['close'], bt_result.result)

report_df: pd.DataFrame = get_backtest_report(price['close'], bt_result.result)

# 计算交易相关信息
# trade_report,orders_chart,pnl_chart
trade_report, orders_chart, pnl_chart = analysis_trade(
    price[['open', 'high', 'low', 'close']], bt_result.result)


def block_risk_report():

    st.header('回测风险指标一览')

    col1, col2, col3 = st.columns(3)
    col1.metric(label="累计收益",
                value='{:.2%}'.format(report_df.loc['累计收益', '策略']),
                delta='{:.2%}'.format(report_df.loc['累计收益', '策略'] -
                                      report_df.loc['累计收益', 'benchmark']),
                delta_color="inverse")
    col2.metric(label="最大回撤",
                value='{:.2%}'.format(report_df.loc['最大回撤', '策略']),
                delta='{:.2%}'.format(report_df.loc['最大回撤', '策略'] -
                                      report_df.loc['最大回撤', 'benchmark']),
                delta_color="inverse")
    col3.metric(label="夏普",
                value='{:.2}'.format(report_df.loc['夏普', '策略']),
                delta='{:.2}'.format(report_df.loc['夏普', '策略'] -
                                     report_df.loc['夏普', 'benchmark']),
                delta_color="inverse")

    st.subheader('risk report')
    st.plotly_chart(bt_risk_table, use_container_width=True)
    st.subheader('cumulative chart')
    st.plotly_chart(cumulative_chart, use_container_width=True)
    st.subheader('annual returns')
    st.plotly_chart(annual_returns_chart, use_container_width=True)

    st.subheader('max drawdown')
    col1, col2 = st.columns((1, 1))
    col1.plotly_chart(maxdrawdowns_chart, use_container_width=True)
    col2.plotly_chart(underwater_chart, use_container_width=True)

    st.subheader('monthly returns')
    st.plotly_chart(monthly_return_heatmap_chart, use_container_width=True)
    st.plotly_chart(monthly_return_dist_chart, use_container_width=True)


def block_trade_report():

    st.header('交易分析')

    st.subheader('trade report')
    st.plotly_chart(trade_report, use_container_width=True)

    st.subheader('order flag')
    st.plotly_chart(orders_chart, use_container_width=True)

    st.subheader('PnL statis')
    st.plotly_chart(pnl_chart, use_container_width=True)

    st.subheader('交易明细')
    with st.expander("See explanation"):

        trade_record: pd.DataFrame = pd.DataFrame(
            bt_result.result[0].analyzers.tradelist.get_analysis())
        builder = GridOptionsBuilder.from_dataframe(trade_record)
        builder.configure_pagination()
        table = builder.build()
        AgGrid(trade_record, gridOptions=table)


def block_status():

    # 获取所有标的的数据
    classify: Dict = STOCK_POOL[level]
    stocks_pool: List = list(classify.keys())
    price: pd.DataFrame = query_data(
        stocks_pool,
        "2010-01-01",
        "2022-10-11",
        fields=["close", 'low', 'high', 'open', "volume"],
        method=level)
    price.set_index("trade_date", inplace=True)
    ## 添加sec_name
    if level == 'sw':
        price['sec_name'] = price['code'].apply(
            lambda x: f"{classify[x].replace('(申万)', '')}({x})")
    else:

        price['sec_name'] = price['code'].apply(
            lambda x: f"{classify[x]}({x})")

    # 批量获取持仓标记
    flag_ser: pd.Series = bulk_signal(price,
                                      **BACKTEST_CONFIG,
                                      level=level,
                                      method='flag')

    vol_mom: pd.Series = bulk_signal(price,
                                     **BACKTEST_CONFIG,
                                     level=level,
                                     method='vol_mom')
    # 获取当期信号情况
    status_ser: pd.Series = flag_ser.groupby(level=0).apply(get_signal_status)

    status_frame: pd.DataFrame = transform_status_table(status_ser)

    st.title('信号状态情况')

    st.subheader('当日信号汇总')
    # 标记有开仓信号及持仓部分
    target: pd.Series = status_ser.apply(lambda x: x[1]).dropna()

    ## 构建表格
    builder = GridOptionsBuilder.from_dataframe(status_frame)
    builder.configure_pagination()
    table = builder.build()
    AgGrid(status_frame, gridOptions=table)

    # 批量回测-不含手续费、滑点

    close_frame: pd.DataFrame = pd.pivot_table(price.reset_index(),
                                               index='trade_date',
                                               columns='sec_name',
                                               values='close')

    benchmark: pd.DataFrame = close_frame.pct_change()
    returns: pd.DataFrame = flag_ser.unstack(level=0).shift(1) * benchmark
    cum: pd.DataFrame = ep.cum_returns(returns)
    benchmark_cum: pd.DataFrame = ep.cum_returns(benchmark)

    st.subheader('收益及动量情况')
    if len(classify) <= 4:
        cols = 1
    else:
        cols = 4

    tab1, tab2, tab3 = st.tabs(['量价因子排名情况', '择时信号累计收益一览', '信号标记'])

    with tab1:
        score = vol_mom.unstack(level=0).iloc[-1].sort_values(ascending=False)
        fig = go.Figure(
            [go.Bar(y=score.values, x=score.index, marker_color='crimson')])
        fig.update_layout(title=dict(text='共振因子', font={"size": 30}))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = GridPlotly(cum, benchmark_cum, cols)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:

        for sec_name, row in target.items():
            fig = plot_candlestick(
                price.query('sec_name==@sec_name').iloc[-60:], True, sec_name)
            fig = add_shape_to_ohlc(fig, pd.Series(index=[row], data=[1]))
            st.plotly_chart(fig, use_container_width=True)


tab1, tab2, tab3 = st.tabs(["📈风险收益情况", "📌交易分析", "😉板块下标的信号状态"])

with tab1:

    block_risk_report()

with tab2:

    block_trade_report()

with tab3:

    block_status()
