import altair as alt  # Graph
from streamlit_searchbox import st_searchbox  # Search box
import plotly.graph_objects as go  # Graph
import streamlit as st  # Deploy web
import yfinance as yf  # Data collecting from Yahoo Finance
import pandas as pd  # Table support
import requests  #  autocomplete search API
import torch #Sentiment predict
from transformers import AutoTokenizer, AutoModelForSequenceClassification

st.set_page_config(page_title="Stock Dashboard by SongChiTienQuan", layout="wide")


# FINBERT

@st.cache_resource
def load_finbert():
    
    model_name = "yiyanghkust/finbert-tone"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    return tokenizer, model

tokenizer, model = load_finbert()


def get_sentiment(text: str):
    if not text or not text.strip():
        return "neutral", 1.0

    text = text.strip()
    if len(text) > 2000:
        text = text[:2000]  

    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)[0].cpu().numpy()
        labels = ["negative", "neutral", "positive"]
        label = labels[int(probs.argmax())]
        confidence = float(probs.max())
        return label, confidence
    except Exception as e:
        # don't crash the UI; show neutral if model fails
        st.error(f"Sentiment model error: {e}")
        return "neutral", 0.0



#FETCH / UTILS 

@st.cache_data
def fetch_stock_info(symbol: str):
    try:
        ticker = yf.Ticker(symbol)

      
        fast = ticker.fast_info or {}

        
        safe = ticker.get_info() or {}

        info = {
            "longName": safe.get("longName") or safe.get("shortName") or symbol,
            "currency": fast.get("currency") or safe.get("currency") or "USD",
            "marketCap": fast.get("marketCap") or safe.get("marketCap") or 0,
            "regularMarketPrice": fast.get("lastPrice")
                or safe.get("regularMarketPrice")
                or safe.get("currentPrice"),
        }

        return info
    except Exception as e:
        return {}


@st.cache_data
def fetch_quarterly_financials(symbol: str):
    try:
        df = yf.Ticker(symbol).quarterly_financials
        if df is None or df.empty:
            return pd.DataFrame()
        return df.T
    except Exception:
        return pd.DataFrame()

@st.cache_data
def fetch_annual_financials(symbol: str):
    try:
        df = yf.Ticker(symbol).financials
        if df is None or df.empty:
            return pd.DataFrame()
        return df.T
    except Exception:
        return pd.DataFrame()

@st.cache_data
def fetch_daily_price_history(symbol: str):
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1h")
        if df is None:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


#AUTO-COMPLETE SEARCH

def search_wrapper(query: str, **kwargs):
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200:
            return []
        data = r.json()
        results = [
            f"{item.get('symbol')} - {item.get('shortname')}"
            for item in data.get("quotes", [])
            if item.get("symbol") and item.get("shortname")
        ]
        return results[:15]
    except Exception:
        return []



#Currency

def format_market_cap(value, currency="USD"):
    try:
        value = float(value)
    except Exception:
        return f"{currency} 0"
    if value >= 1_000_000_000_000:
        return f"{currency} {value/1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{currency} {value/1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{currency} {value/1_000_000:.2f}M"
    return f"{currency} {value:,.0f}"


def recommendation_from_sentiment(label: str, confidence: float):

    if label == "positive" and confidence >= 0.60:
        return "BUY", "green"
    if label == "negative" and confidence >= 0.60:
        return "SELL", "red"
    return "HOLD", "orange"



#DASHBOARD UI

st.title(" Stock Dashboard by SongChiTienQuan")

# Searchbox
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = ""

selected_option = st_searchbox(
    label="Enter a company name or stock symbol",
    search_function=search_wrapper,
    placeholder="Start typing (type company's name if you dont know)...",
    default_value=st.session_state.selected_symbol,
    clear_on_submit=False,
    key="stock_search_box"
)

if selected_option:
    st.session_state.selected_symbol = selected_option.split(" - ")[0].upper()

symbol = st.session_state.selected_symbol or st.text_input("Or type a symbol directly (e.g., AAPL):", value="").upper()


if symbol:

    with st.spinner("Fetching company info..."):
        info = fetch_stock_info(symbol) or {}

    if not info or info.get("regularMarketPrice") is None:
        st.warning("No company information found for that symbol.")
    else:

        st.header(" Company Information")
        st.subheader(f"Name: {info.get('longName', 'N/A')}")

        currency = info.get("currency", "USD")
        st.metric("Primary Trading Currency", currency)

        market_cap = info.get("marketCap", 0)
        st.subheader(f"Market Cap: {format_market_cap(market_cap, currency)}")
        st.caption(f"Raw Value: {market_cap:,}")


        # price chart
        with st.spinner("Fetching price history..."):
            history = fetch_daily_price_history(symbol)
        if history.empty:
            st.info("No intraday price history available.")
        else:
            st.header(" Daily Chart")
            df = history.rename_axis("Date").reset_index()
            # ensure required columns exist
            if all(col in df.columns for col in ["Open", "High", "Low", "Close"]):
                df["Date"] = pd.to_datetime(df["Date"])
                fig = go.Figure(data=[go.Candlestick(
                    x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"]
                )])
                fig.update_layout(xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Price history does not contain enough data for plotting.")

        # financials block
        q_fin = fetch_quarterly_financials(symbol)
        a_fin = fetch_annual_financials(symbol)

        if (q_fin is None or q_fin.empty) and (a_fin is None or a_fin.empty):
            st.info("No financial statements available.")
        else:
            st.header(" Financials")
            period = st.radio("Period", ["Quarterly", "Annual"], horizontal=True)
            df = q_fin if period == "Quarterly" else a_fin
            if df is None or df.empty:
                st.info(f"No {period.lower()} financials available.")
            else:
                # Make sure chart fields exist before plotting
                df_plot = df.rename_axis("Date").reset_index()
                df_plot["Date"] = df_plot["Date"].astype(str)

                # Columns may differ between tickers; check existence
                revenue_col = None
                net_col = None
                for cand in ["Total Revenue", "TotalRevenue", "Revenue", "Revenue (Total)"]:
                    if cand in df_plot.columns:
                        revenue_col = cand
                        break
                for cand in ["Net Income", "NetIncome", "Net Income (Loss)"]:
                    if cand in df_plot.columns:
                        net_col = cand
                        break

                if revenue_col:
                    st.write(" Revenue ")
                    st.altair_chart(
                        alt.Chart(df_plot).mark_bar(color="red").encode(x="Date:O", y=alt.Y(f"`{revenue_col}`:Q")),
                        use_container_width=True,
                    )
                else:
                    st.info("Revenue field not found in financials.")

                if net_col:
                    st.write(" Net Income ")
                    st.altair_chart(
                        alt.Chart(df_plot).mark_bar(color="orange").encode(x="Date:O", y=alt.Y(f"`{net_col}`:Q")),
                        use_container_width=True,
                    )
                else:
                    st.info("Net income field not found in financials.")

        
        # Sentiment analysis UI + recommendation
      
        st.header(" Financial Sentiment Analysis (FinBERT)")
        st.write("Paste news or headlines related to this company (or maybe summaries).")
        news_text = st.text_area("Write properly please", height=180)

        if st.button("Analyze Sentiment"):
            if not news_text or not news_text.strip():
                st.warning("Please paste some news or headlines to analyze.")
            else:
                with st.spinner("Analyzing sentiment..."):
                    label, conf = get_sentiment(news_text)
                    st.success(f"Sentiment: **{label.upper()}** (confidence {conf:.2f})")

                   
                    try:
                       
                        inputs = tokenizer(news_text, return_tensors="pt", truncation=True, padding=True)
                        with torch.no_grad():
                            outs = model(**inputs)
                        probs = torch.softmax(outs.logits, dim=1)[0].cpu().numpy()
                        probs_dict = dict(zip(["negative", "neutral", "positive"], probs.round(3).tolist()))
                        st.write("Probabilities:", probs_dict)
                    except Exception:
                        pass

                    
                    rec, color = recommendation_from_sentiment(label, conf)
                    st.markdown(f"<h2 style='text-align:center;color:{color};'>AI Recommendation: {rec}</h2>", unsafe_allow_html=True)

else:
    st.info("Type or select a stock symbol to begin.")
