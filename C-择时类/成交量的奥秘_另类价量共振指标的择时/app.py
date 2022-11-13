from typing import Dict, List, Tuple, Union

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from scr.backtest_engine import get_backtesting
from scr.load_excel_data import (query_data, query_stock_index_classify,
                                 query_sw_classify)
from scr.tear import analysis_rets, analysis_trade, get_backtest_report

st.set_page_config(page_title='QRS Indicator BackTesting Report',
                   layout='wide',
                   page_icon=':ambulance:')

st.sidebar.subheader("选择行业或宽基")

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
    code, "2010-01-01", "2022-10-11", fields=["close",'low','high','open', "volume"], method=level
)
price.set_index("trade_date", inplace=True)

bt_result = get_backtesting(price,stock_selection)


# 计算回测相关风险信息
# Backtesting Risk Report
bt_risk_table, cumulative_chart, maxdrawdowns_chart, underwater_chart, annual_returns_chart, monthly_return_heatmap_chart, monthly_return_dist_chart = analysis_rets(price['close'],bt_result.result)

report_df: pd.DataFrame = get_backtest_report(price['close'], bt_result.result)

# 计算交易相关信息
# trade_report,orders_chart,pnl_chart
trade_report, orders_chart, pnl_chart = analysis_trade(price[['open','high','low','close']], bt_result.result)



def block_risk_report():
    
    st.header('Backtesting Risk Report')

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
    
    st.header('Backtesting Trading Report')

    st.subheader('trade report')
    st.plotly_chart(trade_report, use_container_width=True)

    st.subheader('order flag')
    st.plotly_chart(orders_chart, use_container_width=True)

    st.subheader('PnL statis')
    st.plotly_chart(pnl_chart, use_container_width=True)

    st.subheader('Trade Record')
    with st.expander("See explanation"):
        
        trade_record:pd.DataFrame = pd.DataFrame(
                bt_result.result[0].analyzers.tradelist.get_analysis())
        builder = GridOptionsBuilder.from_dataframe(trade_record)
        builder.configure_pagination()
        go = builder.build()
        AgGrid(trade_record, gridOptions=go)
    
tab1, tab2 = st.tabs(
    ["📈Backtesting Risk Report", "📌Backtesting Trading Report"])

with tab1:

    block_risk_report()
    

with tab2:

    block_trade_report()
    
   