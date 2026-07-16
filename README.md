# Brand & Media Intelligence Pipeline

A production-style media intelligence platform that tracks news sentiment across the top 10 tech companies using a multi-layer data pipeline powered by Snowflake, dbt, and AI.

This project is an evolution of my [Big Tech Reddit Sentiment Tracker](https://github.com/dzheng5/tech-pulse), rebuilt with a cloud data warehouse, dbt transformations, and a multi-source news pipeline.

---

## What It Does

- Ingests live news articles for 10 major tech companies via NewsAPI
- Scores each article's sentiment using Groq (Llama 3.1 8B)
- Transforms and aggregates data using dbt Core on Snowflake (Bronze/Silver/Gold medallion architecture)
- Generates AI-powered summary cards per company based on actual article headlines
- Provides a natural language query agent that translates plain English questions into SQL
- Displays everything in an interactive Streamlit dashboard with filters and a chat interface

---

## Architecture
NewsAPI → ingest_news.py → Snowflake BRONZE
↓
dbt (stg_news.sql)
↓
Snowflake SILVER
↓
sentiment_news.py (Groq scoring)
↓
Snowflake BRONZE
(news_articles_scored)
↓
dbt (mart_news_sentiment.sql)
↓
Snowflake GOLD
↓
summary_cards.py + nl_agent.py + app.py

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data Warehouse | Snowflake |
| Transformation | dbt Core |
| Ingestion | Python, NewsAPI |
| AI Sentiment | Groq (llama-3.1-8b-instant) |
| NL Query Agent | LangChain-style Text-to-SQL |
| Dashboard | Streamlit, Plotly |
| Environment | Python 3.12, VS Code |

---

## Project Structure
media-intelligence-pipeline/
├── app.py                  # Streamlit dashboard
├── ingest_news.py          # NewsAPI ingestion script
├── sentiment_news.py       # Groq sentiment scoring
├── summary_cards.py        # AI summary card generation
├── nl_agent.py             # Natural language query agent
├── assets/                 # Company logos
├── media_intelligence/     # dbt project
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_news.sql
│   │   └── marts/
│   │       └── mart_news_sentiment.sql
│   ├── macros/
│   │   └── generate_schema_name.sql
│   └── dbt_project.yml
├── requirements.txt
└── .env                    # Not included — see setup

---

## Snowflake Schema

**BRONZE** — raw ingested data
- `news_articles` — raw NewsAPI articles
- `news_sentiment_scores` — Groq sentiment scores per article
- `news_articles_scored` — unified table joining articles + scores

**SILVER** — cleaned staging models
- `stg_news` — standardized news articles

**GOLD** — aggregated mart models
- `mart_news_sentiment` — sentiment aggregated by company and date
- `ai_summary_cards` — AI-generated summary cards per company

---

## Setup

1. Clone the repo
2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file in the root with the following:
GROQ_API_KEY=your_groq_key
NEWS_API_KEY=your_newsapi_key
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=MEDIA_INTELLIGENCE
SNOWFLAKE_WAREHOUSE=MEDIA_WH

4. Set up Snowflake with Bronze/Silver/Gold schemas and run the dbt project:
```bash
cd media_intelligence
dbt seed
dbt run
```

5. Run the pipeline scripts in order:
```bash
python ingest_news.py
python sentiment_news.py
python summary_cards.py
```

6. Launch the dashboard:
```bash
streamlit run app.py
```

---

## Companies Tracked

Apple · Google · Microsoft · Meta · Amazon · Netflix · Tesla · Nvidia · Samsung · Intel

---

## Pipeline Refresh

To refresh data with the latest news, run the pipeline scripts in order:
```bash
python ingest_news.py
python sentiment_news.py
python summary_cards.py
cd media_intelligence && dbt run
```

---

*Built by David Zheng — [LinkedIn](https://www.linkedin.com/in/dzheng5/) · [GitHub](https://github.com/dzheng5/media-intelligence-pipeline)*