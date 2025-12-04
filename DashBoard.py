import altair as alt  # Graph
from streamlit_searchbox import st_searchbox  # Search box
import plotly.graph_objects as go  # Graph
import streamlit as st  # Deploy web
import yfinance as yf  # Data collecting from Yahoo Finance
import pandas as pd  # Table support
import requests  #  autocomplete search API
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

@st.cache_resource
def load_finbert():
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    return tokenizer, model

tokenizer, model = load_finbert()

def get_sentiment(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    outputs = model(**inputs)
    scores = torch.softmax(outputs.logits, dim=1)[0]
    labels = ["negative", "neutral", "positive"]
    return labels[scores.argmax().item()], scores.max().item()


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
        return yf.Ticker(symbol).quarterly_financials.T
    except:
        return pd.DataFrame()

@st.cache_data
def fetch_annual_financials(symbol):
    try:
        return yf.Ticker(symbol).financials.T
    except:
        return pd.DataFrame()

@st.cache_data
def fetch_daily_price_history(symbol):
    try:
        return yf.Ticker(symbol).history(period='1d', interval='1h')
    except:
        return pd.DataFrame()

# ================================================================
#                  AUTO-COMPLETE SEARCH (Yahoo)
# ================================================================

def search_wrapper(query: str, **kwargs):
    if not query or len(query.strip()) < 2:
        return []

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return []

        data = response.json()
        results = [
            f"{item['symbol']} - {item['shortname']}"
            for item in data.get("quotes", [])
            if item.get("symbol") and item.get("shortname")
        ]
        return results[:15]

    except:
        return []

# ================================================================
#                       FORMAT NUMBER
# ================================================================

def format_market_cap(value, currency):
    if value >= 1_000_000_000_000:
        return f"{currency} {value/1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{currency} {value/1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{currency} {value/1_000_000:.2f}M"
    else:
        return f"{currency} {value:,.0f}"


# ================================================================
#                       DASHBOARD UI
# ================================================================

st.title(" Stock Dashboard by SongChiTienQuan")

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = ''

selected_option = st_searchbox(
    label="Enter a company name or stock symbol",
    search_function=search_wrapper,
    placeholder="Start typing to see stock suggestions (AAPL, GOOGL)...",
    default_value=st.session_state.selected_symbol,
    clear_on_submit=False,
    key="stock_search_box"
)

if selected_option:
    st.session_state.selected_symbol = selected_option.split(" - ")[0]
symbol_to_display = st.session_state.selected_symbol

# ================================================================
#                      DISPLAY STOCK INFO
# ================================================================

if symbol_to_display:
    information = fetch_stock_info(symbol_to_display)

    if information:
        st.header(' Company Information')
        st.subheader(f"Name: {information.get('longName', 'N/A')}")

        currency = information.get("currency", "USD")
        st.metric("Primary Trading Currency", currency)

        market_cap = information.get("marketCap", 0)
        st.subheader(f"Market Cap: {format_market_cap(market_cap, currency)}")
        st.caption(f"Raw Value: {market_cap:,}")

        history = fetch_daily_price_history(symbol_to_display)
        if not history.empty:
            st.header(" Daily Chart")
            df = history.rename_axis("Date").reset_index()
            df["Date"] = pd.to_datetime(df["Date"])

            fig = go.Figure(data=[go.Candlestick(
                x=df["Date"],
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"]
            )])
            fig.update_layout(xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        # =========================================================
        #                       FINANCIALS
        # =========================================================
        
        q_fin = fetch_quarterly_financials(symbol_to_display)
        a_fin = fetch_annual_financials(symbol_to_display)

        if not q_fin.empty or not a_fin.empty:
            st.header("📑 Financials")

            try:
                from streamlit_option_menu import option_menu
                period = option_menu(
                    None, ["Quarterly", "Annual"],
                    icons=["calendar4-week", "calendar2-range"],
                    default_index=0, orientation="horizontal"
                )
            except:
                period = st.selectbox("Period", ["Quarterly", "Annual"])

            if period == "Quarterly" and not q_fin.empty:
                q_fin = q_fin.rename_axis("Quarter").reset_index()
                q_fin["Quarter"] = q_fin["Quarter"].astype(str)

                st.altair_chart(
                    alt.Chart(q_fin).mark_bar(color="red").encode(
                        x=alt.X("Quarter:O", sort="-x"),
                        y="Total Revenue"
                    ).properties(title="Total Revenue (Quarterly)"),
                    use_container_width=True
                )

                st.altair_chart(
                    alt.Chart(q_fin).mark_bar(color="orange").encode(
                        x=alt.X("Quarter:O", sort="-x"),
                        y="Net Income"
                    ).properties(title="Net Income (Quarterly)"),
                    use_container_width=True
                )

            if period == "Annual" and not a_fin.empty:
                a_fin = a_fin.rename_axis("Year").reset_index()
                a_fin["Year"] = pd.to_datetime(a_fin["Year"]).dt.year.astype(str)

                st.altair_chart(
                    alt.Chart(a_fin).mark_bar(color="red").encode(
                        x=alt.X("Year:O", sort="-x"),
                        y="Total Revenue"
                    ).properties(title="Total Revenue (Annual)"),
                    use_container_width=True
                )

                st.altair_chart(
                    alt.Chart(a_fin).mark_bar(color="orange").encode(
                        x=alt.X("Year:O", sort="-x"),
                        y="Net Income"
                    ).properties(title="Net Income (Annual)"),
                    use_container_width=True
                )


        # =========================================================
        #                       AI SENTIMENT
        # =========================================================
        st.header(" Sentiment Analysis ")

        text = st.text_area("Enter news/headlines about this stock:")

        if st.button("Analyze Sentiment"):
            if text.strip():
                sentiment, confidence = get_sentiment(text)
                st.success(f"**Sentiment: {sentiment.capitalize()}**")
                st.write(f"Confidence: {confidence:.2f}")
            else:
                st.warning("Please enter some text.")
