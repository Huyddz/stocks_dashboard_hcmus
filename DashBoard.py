import altair as alt  # Graph
from streamlit_searchbox import st_searchbox  # Search box
import plotly.graph_objects as go  # Graph
import streamlit as st  # Deploy web
import yfinance as yf  # Data collecting from Yahoo Finance
import pandas as pd  # Table support
import requests  # 🔥 NEW — used for autocomplete search API

# ================================================================
#                    FETCH STOCK INFO
# ================================================================

@st.cache_data
def fetch_stock_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        if not info or info.get('regularMarketPrice') is None:
            st.warning(f"No current market data found for {symbol}.")
            return None
        return info
    except Exception as e:
        st.error(f"FATAL ERROR: Failed to fetch yfinance data for {symbol}. Error: {e}")
        return None


@st.cache_data
def fetch_quarterly_financials(symbol):
    try:
        stock = yf.Ticker(symbol)
        return stock.quarterly_financials.T
    except Exception:
        return pd.DataFrame()


@st.cache_data
def fetch_annual_financials(symbol):
    try:
        stock = yf.Ticker(symbol)
        return stock.financials.T
    except Exception:
        return pd.DataFrame()


@st.cache_data
def fetch_daily_price_history(symbol):
    try:
        stock = yf.Ticker(symbol)
        history = stock.history(period='1d', interval='1h')
        return history
    except Exception as e:
        st.error(f"Error fetching price history for {symbol}. Error: {e}")
        return pd.DataFrame()

# ================================================================
#                  AUTO-COMPLETE SEARCH (Yahoo)
# ================================================================

def search_wrapper(query: str, **kwargs):
    if not query or len(query.strip()) < 2:
        return []

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for item in data.get("quotes", []):
            if item.get("symbol") and item.get("shortname"):
                results.append(f"{item['symbol']} - {item['shortname']}")

        return results[:15]

    except Exception as e:
        return []

# ================================================================
#                       FORMAT NUMBER
# ================================================================

def format_market_cap(value, currency):
    if value >= 1_000_000_000_000:
        return f"{currency} {value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{currency} {value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{currency} {value / 1_000_000:.2f}M"
    else:
        return f"{currency} {value:,.0f}"

# ================================================================
#                       DASHBOARD UI
# ================================================================

st.title('📊 Stock Dashboard by SongChiTienQuan')

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = ''

selected_option = st_searchbox(
    label="Enter a company name or stock symbol",
    search_function=search_wrapper,
    placeholder="Start typing to see stock suggestions (e.g., AAPL, GOOGL)...",
    default_value=st.session_state.selected_symbol,
    clear_on_submit=False,
    key="stock_search_box"
)

if selected_option:
    st.session_state.selected_symbol = selected_option.split(' - ')[0]
else:
    st.session_state.selected_symbol = ''

symbol_to_display = st.session_state.selected_symbol

if symbol_to_display:
    information = fetch_stock_info(symbol_to_display)

    if information:
        st.header('🏢 Company Information')
        st.subheader(f'Name: {information.get("longName", "N/A")}')
        
        currency = information.get('currency', 'USD')
        st.metric(label="Primary Trading Currency", value=currency)
        
        market_cap = information.get('marketCap', 0)
        st.subheader(f'Market Cap: {format_market_cap(market_cap, currency)}')
        st.caption(f'Native Currency: {currency} | Raw Value: {market_cap:,}')

        price_history = fetch_daily_price_history(symbol_to_display)
        if not price_history.empty:
            st.header('📈 Daily Chart')
            price_history = price_history.rename_axis('Date').reset_index()
            price_history['Date'] = pd.to_datetime(price_history['Date'])
            
            candle_stick_chart = go.Figure(data=[go.Candlestick(
                x=price_history['Date'],
                open=price_history['Open'],
                low=price_history['Low'],
                high=price_history['High'],
                close=price_history['Close']
            )])
            candle_stick_chart.update_layout(xaxis_rangeslider_visible=False)
            st.plotly_chart(candle_stick_chart, use_container_width=True)

        quarterly_financials = fetch_quarterly_financials(symbol_to_display)
        annual_financials = fetch_annual_financials(symbol_to_display)

        if not quarterly_financials.empty or not annual_financials.empty:
            st.header('📑 Financials')

            try:
                from streamlit_option_menu import option_menu
                selection = option_menu(
                    menu_title=None,
                    options=['Quarterly', 'Annual'],
                    icons=['calendar4-week', 'calendar2-range'],
                    default_index=0,
                    orientation='horizontal'
                )
            except:
                selection = st.selectbox('Period', ['Quarterly', 'Annual'])

            if selection == 'Quarterly' and not quarterly_financials.empty:
                quarterly_financials = quarterly_financials.rename_axis('Quarter').reset_index()
                quarterly_financials['Quarter'] = quarterly_financials['Quarter'].astype(str)

                revenue_chart = alt.Chart(quarterly_financials).mark_bar(color='red').encode(
                    x=alt.X('Quarter:O', sort='-x'),
                    y='Total Revenue'
                ).properties(title='Total Revenue (Quarterly)')

                net_income_chart = alt.Chart(quarterly_financials).mark_bar(color='orange').encode(
                    x=alt.X('Quarter:O', sort='-x'),
                    y='Net Income'
                ).properties(title='Net Income (Quarterly)')

                st.altair_chart(revenue_chart, use_container_width=True)
                st.altair_chart(net_income_chart, use_container_width=True)

            if selection == 'Annual' and not annual_financials.empty:
                annual_financials = annual_financials.rename_axis('Year').reset_index()
                annual_financials['Year'] = pd.to_datetime(annual_financials['Year']).dt.year.astype(str)

                revenue_chart = alt.Chart(annual_financials).mark_bar(color='red').encode(
                    x=alt.X('Year:O', sort='-x'),
                    y='Total Revenue'
                ).properties(title='Total Revenue (Annual)')

                net_income_chart = alt.Chart(annual_financials).mark_bar(color='orange').encode(
                    x=alt.X('Year:O', sort='-x'),
                    y='Net Income'
                ).properties(title='Net Income (Annual)')

                st.altair_chart(revenue_chart, use_container_width=True)
                st.altair_chart(net_income_chart, use_container_width=True)
