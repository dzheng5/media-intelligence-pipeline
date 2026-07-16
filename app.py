import os
import json
import pandas as pd
import streamlit as st
import snowflake.connector
import plotly.express as px
from dotenv import load_dotenv
from nl_agent import ask

load_dotenv()

# Page config
st.set_page_config(
    page_title="Media Intelligence Dashboard",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stSidebar"] [data-testid="stChatInput"] {
    position: fixed;
    bottom: 20px;
    width: 280px;
}
[data-testid="stSidebar"] [data-testid="stChatMessageContainer"] {
    padding-bottom: 80px;
}
</style>
""", unsafe_allow_html=True)

# Connect to Snowflake
@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        schema="GOLD"
    )

conn = get_connection()

@st.cache_data
def load_news_sentiment():
    df = pd.read_sql("SELECT * FROM GOLD.mart_news_sentiment ORDER BY published_date", conn)
    df.columns = df.columns.str.lower()
    return df

@st.cache_data
def load_summary_cards():
    df = pd.read_sql("SELECT * FROM GOLD.ai_summary_cards", conn)
    df.columns = df.columns.str.lower()
    return df

@st.cache_data
def load_raw_news():
    df = pd.read_sql("""
        SELECT company, article_title as title, source_name, url, published_date, sentiment_label
        FROM BRONZE.news_articles_scored
        ORDER BY published_date DESC
    """, conn)
    df.columns = df.columns.str.lower()
    return df

# Load data
news_df = load_news_sentiment()
cards_df = load_summary_cards()
raw_news_df = load_raw_news()

# Header
st.title("Media Intelligence Dashboard")
st.markdown("Sentiment analysis across news coverage for the top 10 tech companies.")
st.divider()

# Filters
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 1, 2, 1])

with filter_col4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Reset Filters"):
        st.session_state["company_filter"] = "All Companies"
        st.session_state["sentiment_filter"] = "All"
        st.session_state["date_filter"] = (raw_news_df["published_date"].min(), raw_news_df["published_date"].max())
        st.session_state.card_page = 0
        st.rerun()

with filter_col1:
    companies = ["All Companies"] + sorted(news_df["company"].unique().tolist())
    selected_company = st.selectbox("Filter by company", companies, key="company_filter")

with filter_col2:
    selected_sentiment = st.selectbox("Filter by sentiment", ["All", "Positive", "Neutral", "Negative"], key="sentiment_filter")

with filter_col3:
    min_date = raw_news_df["published_date"].min()
    max_date = raw_news_df["published_date"].max()
    date_range = st.date_input("Filter by date range", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="date_filter")
st.divider()

# Filter data
filtered_news = news_df.copy()
filtered_cards = cards_df.copy()
filtered_raw = raw_news_df.copy()

if selected_company != "All Companies":
    filtered_news = filtered_news[filtered_news["company"] == selected_company]
    filtered_cards = filtered_cards[filtered_cards["company"] == selected_company]
    filtered_raw = filtered_raw[filtered_raw["company"] == selected_company]

if selected_sentiment != "All":
    filtered_cards = filtered_cards[filtered_cards["sentiment_trend"] == selected_sentiment]
    filtered_raw = filtered_raw[filtered_raw["sentiment_label"] == selected_sentiment.lower()]

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_raw["published_date"] = pd.to_datetime(filtered_raw["published_date"]).dt.date
    filtered_news["published_date"] = pd.to_datetime(filtered_news["published_date"]).dt.date
    filtered_raw = filtered_raw[(filtered_raw["published_date"] >= start_date) & (filtered_raw["published_date"] <= end_date)]
    filtered_news = filtered_news[(filtered_news["published_date"] >= start_date) & (filtered_news["published_date"] <= end_date)]

# Summary cards with carousel
st.subheader("AI Summary Cards")

if "card_page" not in st.session_state:
    st.session_state.card_page = 0

cards_list = list(filtered_cards.iterrows())
total_pages = (len(cards_list) + 4) // 5
current_page = st.session_state.card_page
page_cards = cards_list[current_page * 5:(current_page + 1) * 5]

import base64

cols = st.columns(5)
for i, (_, card) in enumerate(page_cards):
    with cols[i]:
        trend = card["sentiment_trend"]
        if trend == "Positive":
            icon = "🟢"
            color = "#2ecc71"
        elif trend == "Negative":
            icon = "🔴"
            color = "#e74c3c"
        else:
            icon = "🟡"
            color = "#f39c12"
        themes = json.loads(card["key_themes"])
        logo_path = f"assets/{card['company'].lower()}.png"

        logo_html = ""
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                logo_data = base64.b64encode(f.read()).decode()
            logo_html = f'<img src="data:image/png;base64,{logo_data}" style="width:48px; height:48px; object-fit:contain; display:block; margin:0 auto 12px auto;">'

        st.markdown(f"""
<div style="border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; height: 480px; display:flex; flex-direction:column; align-items:center; text-align:center; box-sizing:border-box;">
    {logo_html}
    <h4 style="margin: 0 0 8px 0; font-size:15px;">{card['company']}</h4>
    <p style="margin: 0 0 10px 0; color: {color}; font-size:13px;">
        {icon} <strong>{trend}</strong>
    </p>
    <p style="margin: 0 0 12px 0; font-size: 12px; color: #ffffff; line-height: 1.7; flex-grow:1;">{card['summary']}</p>
    <p style="margin: 0; font-size: 11px; color: #888;">{' · '.join(themes)}</p>
</div>
""", unsafe_allow_html=True)

# Navigate Buttons
if total_pages > 1:
    st.markdown("<br>", unsafe_allow_html=True)
    _, center, _ = st.columns([3, 2, 3])
    with center:
        btn_col1, text_col, btn_col2 = st.columns([1, 2, 1])
        with btn_col1:
            if st.button("← Prev") and st.session_state.card_page > 0:
                st.session_state.card_page -= 1
                st.rerun()
        with text_col:
            st.markdown(f"<p style='text-align:center; color:#888; margin-top:8px;'>{current_page + 1} / {total_pages}</p>", unsafe_allow_html=True)
        with btn_col2:
            if st.button("Next →") and st.session_state.card_page < total_pages - 1:
                st.session_state.card_page += 1
                st.rerun()

st.divider()

# Sentiment chart
st.subheader("Sentiment Score Comparison")

if selected_company == "All Companies":
    chart_data = news_df.groupby("company")["avg_sentiment_score"].mean().reset_index()
    chart_data.columns = ["Company", "Avg Sentiment"]
    sentiment_map = cards_df.set_index("company")["sentiment_trend"].to_dict()
    chart_data["Sentiment"] = chart_data["Company"].map(sentiment_map)

    fig = px.bar(
        chart_data,
        x="Company",
        y="Avg Sentiment",
        color="Sentiment",
        color_discrete_map={"Positive": "#2ecc71", "Neutral": "#f39c12", "Negative": "#e74c3c"},
        custom_data=["Sentiment"]
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>%{customdata[0]}<extra></extra>"
    )
    fig.update_layout(yaxis_title="", xaxis_title="", showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    fig = px.line(
        filtered_news,
        x="published_date",
        y="avg_sentiment_score",
        title=f"{selected_company} Sentiment Over Time",
        markers=True
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>%{customdata[0]}<extra></extra>",
        customdata=filtered_news["avg_sentiment_score"].apply(
            lambda x: ["Positive" if x > 0.05 else ("Negative" if x < -0.05 else "Neutral")]
        ).tolist(),
        line_color="#2ecc71"
    )
    fig.update_layout(yaxis_title="", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Articles table
st.subheader("📰 Latest News Articles")
if filtered_raw.empty:
    st.info("No articles found.")
else:
    def sentiment_badge(label):
        if label == "positive":
            return "🟢 Positive"
        elif label == "negative":
            return "🔴 Negative"
        else:
            return "🟡 Neutral"

    display_df = filtered_raw.copy()
    display_df["sentiment"] = display_df["sentiment_label"].apply(sentiment_badge)
    
    st.dataframe(
        display_df[["company", "source_name", "title", "sentiment", "url", "published_date"]].rename(columns={
            "company": "Company",
            "source_name": "Source",
            "title": "Title",
            "sentiment": "Sentiment",
            "url": "URL",
            "published_date": "Date"
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("URL")
        }
    )

st.divider()

# Chat interface in sidebar
with st.sidebar:
    st.header("Ask the Data")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    question = st.chat_input("Ask about sentiment trends...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = ask(question, st.session_state.chat_history)
            st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})