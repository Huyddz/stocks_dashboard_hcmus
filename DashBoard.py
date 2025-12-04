import altair as alt
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import pandas as pd
import finnhub


finnhub_client = finnhub.Client(api_key="d4o6bmhr01qtrbsism90d4o6bmhr01qtrbsism9g")


@st.cache_data
def fetch_stock_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        return stock.info
    except Exception as e:
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
        return stock.history(period='1d', interval='1h')
    except Exception:
        return pd.DataFrame()
   
@st.cache_data
def search_stock_symbols(query):
    if not query:
        return []
    try:
        result = finnhub_client.search(query)
      
        stocks = [item for item in result.get('result', []) if item.get('type') == 'common stock']
        return stocks
    except Exception as e:

        return []

def format_market_cap(value, currency):
   
    if currency == 'VND':
        value = value / 25000  
        currency = 'USD (approx)'
    elif currency == 'JPY':
        value = value / 150  
        currency = 'USD (approx)'
   
    if value >= 1_000_000_000_000:
        return f"{currency} {value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{currency} {value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{currency} {value / 1_000_000:.2f}M"
    else:
        return f"{currency} {value:,.0f}"

# Dashboard
st.title('Stock Dashboard by SongChiTienQuan')


if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = ''


search_query = st.text_input('Enter a company name or stock symbol', '').upper()


if search_query:
    results = search_stock_symbols(search_query)

    if results:
        
        options = [f"{item['symbol']} - {item['description']}" for item in results]
       
        
        selected_option = st.selectbox("Select a stock:", options)
       
        
        st.session_state.selected_symbol = selected_option.split(' - ')[0] if selected_option else ''
    else:
       
        st.session_state.selected_symbol = ''



symbol_to_display = st.session_state.selected_symbol

if symbol_to_display:
    information = fetch_stock_info(symbol_to_display)

    if information:
        st.header('Company Information')
        st.subheader(f'Name: {information.get("longName", "N/A")}')
       
        currency = information.get('currency', 'USD')
        market_cap = information.get('marketCap', 0)
       
        st.subheader(f'Market Cap: {format_market_cap(market_cap, currency)}')
        st.caption(f'Native Currency: {currency} | Raw Value: {market_cap:,}')

        # Daily Chart
        price_history = fetch_daily_price_history(symbol_to_display)
        if not price_history.empty:
            st.header('Daily Chart')
            price_history = price_history.rename_axis('Date').reset_index()
           
            
            price_history['Date'] = pd.to_datetime(price_history['Date'])
           
            candle_stick_chart = go.Figure(data=[go.Candlestick(x=price_history['Date'],
                                           open=price_history['Open'],
                                           low=price_history['Low'],
                                           high=price_history['High'],
                                           close=price_history['Close'])])
            candle_stick_chart.update_layout(xaxis_rangeslider_visible=False)
            st.plotly_chart(candle_stick_chart, use_container_width=True)

        
        quarterly_financials = fetch_quarterly_financials(symbol_to_display)
        annual_financials = fetch_annual_financials(symbol_to_display)
       
        if not quarterly_financials.empty or not annual_financials.empty:
            st.header('Financials')
            try:
                from streamlit_option_menu import option_menu
                selection = option_menu(
                    menu_title=None,
                    options=['Quarterly', 'Annual'],
                    icons=['calendar4-quarter', 'calendar-range'],
                    default_index=0,
                    orientation='horizontal'
                )
            except ImportError:
                 selection = st.selectbox('Period', ['Quarterly', 'Annual'])

            if selection == 'Quarterly' and not quarterly_financials.empty:
               
                quarterly_financials = quarterly_financials.rename_axis('Quarter').reset_index()
                quarterly_financials['Quarter'] = quarterly_financials['Quarter'].astype(str)
               
                revenue_chart = alt.Chart(quarterly_financials).mark_bar(color='red').encode(
                    x='Quarter:O',
                    y='Total Revenue'
                )
                net_income_chart = alt.Chart(quarterly_financials).mark_bar(color='orange').encode(
                    x='Quarter:O',
                    y='Net Income'
                )
                st.altair_chart(revenue_chart, use_container_width=True)
                st.altair_chart(net_income_chart, use_container_width=True)
           
            elif selection == 'Annual' and not annual_financials.empty:
                
                annual_financials = annual_financials.rename_axis('Year').reset_index()
                annual_financials['Year'] = pd.to_datetime(annual_financials['Year']).dt.year.astype(str)

                revenue_chart = alt.Chart(annual_financials).mark_bar(color='red').encode(
                    x='Year:O',
                    y='Total Revenue'
                )
                net_income_chart = alt.Chart(annual_financials).mark_bar(color='orange').encode(
                    x='Year:O',
                    y='Net Income'
                )
                st.altair_chart(revenue_chart, use_container_width=True)
                st.altair_chart(net_income_chart, use_container_width=True)