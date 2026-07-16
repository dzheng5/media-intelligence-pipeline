import os
import snowflake.connector
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SCHEMA_CONTEXT = """
You have access to these Snowflake tables:

1. GOLD.mart_news_sentiment
   - company (VARCHAR) — e.g. 'Apple', 'Google', 'Microsoft', 'Meta', 'Amazon', 'Netflix', 'Tesla', 'Nvidia', 'Samsung', 'Intel'
   - published_date (DATE)
   - total_articles (INT)
   - avg_sentiment_score (FLOAT) — average sentiment from -1.0 to 1.0
   - positive_count (INT)
   - neutral_count (INT)
   - negative_count (INT)

2. GOLD.ai_summary_cards
   - company (VARCHAR)
   - overall_sentiment_score (FLOAT)
   - summary (VARCHAR)
   - sentiment_trend (VARCHAR) — 'Positive', 'Neutral', or 'Negative'
   - key_themes (VARCHAR)

3. BRONZE.news_articles_scored
   - company (VARCHAR)
   - article_title (VARCHAR)
   - source_name (VARCHAR)
   - published_date (DATE)
   - sentiment_score (FLOAT)
   - sentiment_label (VARCHAR) — 'positive', 'neutral', or 'negative'
   - url (VARCHAR)
   - description (VARCHAR)
   NOTE: use this table for ALL article lookups. It has everything in one place.

IMPORTANT RULES:
- Return ONLY a valid Snowflake SQL query, no explanation, no markdown, no backticks
- Always use fully qualified table names
- Always LIMIT 10 when querying BRONZE tables
- For any article lookups always use BRONZE.news_articles_scored

EXAMPLE QUERIES:

-- Best sentiment company
SELECT company, AVG(avg_sentiment_score) as avg_score 
FROM GOLD.mart_news_sentiment 
GROUP BY company ORDER BY avg_score DESC LIMIT 1

-- Worst sentiment company
SELECT company, AVG(avg_sentiment_score) as avg_score 
FROM GOLD.mart_news_sentiment 
GROUP BY company ORDER BY avg_score ASC LIMIT 1

-- Compare two companies sentiment
SELECT company, AVG(avg_sentiment_score) as avg_score 
FROM GOLD.mart_news_sentiment 
WHERE company IN ('Apple', 'Google') 
GROUP BY company

-- Negative articles for a company
SELECT article_title, source_name, published_date, url 
FROM BRONZE.news_articles_scored 
WHERE company = 'Meta' AND sentiment_label = 'negative' 
LIMIT 10

-- Positive articles for a company
SELECT article_title, source_name, published_date, url 
FROM BRONZE.news_articles_scored 
WHERE company = 'Meta' AND sentiment_label = 'positive' 
LIMIT 10

-- All articles for a company
SELECT article_title, source_name, published_date, sentiment_label, url 
FROM BRONZE.news_articles_scored 
WHERE company = 'Apple' 
LIMIT 10

-- Sentiment over time for a company
SELECT published_date, avg_sentiment_score 
FROM GOLD.mart_news_sentiment 
WHERE company = 'Apple' 
ORDER BY published_date

-- Company AI summary
SELECT company, summary, sentiment_trend, key_themes 
FROM GOLD.ai_summary_cards 
WHERE company = 'Tesla'

-- Total articles per company
SELECT company, SUM(total_articles) as total 
FROM GOLD.mart_news_sentiment 
GROUP BY company ORDER BY total DESC

-- Count negative articles for a company
SELECT COUNT(*) as negative_count 
FROM BRONZE.news_articles_scored 
WHERE company = 'Meta' AND sentiment_label = 'negative'

-- All companies sentiment comparison
SELECT company, AVG(avg_sentiment_score) as avg_score 
FROM GOLD.mart_news_sentiment 
GROUP BY company ORDER BY avg_score DESC
"""

def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        schema="BRONZE"
    )

def ask(question, chat_history=None):
    messages = [{"role": "system", "content": SCHEMA_CONTEXT}]

    if chat_history:
        for msg in chat_history[:-1]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    # Step 1 — generate SQL
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0
    )

    sql = response.choices[0].message.content.strip()

    # Strip markdown if present
    if sql.startswith("```"):
        sql = sql.split("```")[1]
        if sql.startswith("sql"):
            sql = sql[3:]
        sql = sql.strip()

    # If response doesn't look like SQL, reject it
    if not sql.upper().startswith("SELECT"):
        return "I wasn't able to answer that. Try rephrasing your question."

    print(f"\nGenerated SQL:\n{sql}\n")

    # Step 2 — run SQL
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"SQL ERROR: {e}")
        return f"SQL error: {e}"

    cursor.close()
    conn.close()

    # Step 3 — summarize
    truncated_results = results[:10]

    user_wants_articles = any(word in question.lower() for word in ["article", "articles", "source", "sources", "list", "show", "provide", "support", "url", "link"])

    summary_prompt = f"""
You are a media intelligence assistant. The user asked: "{question}"

The database returned these results: {truncated_results}

Instructions:
- Answer the question directly and concisely
- If the user asked for articles, sources, or links, format each result as: [article title](url) — source_name — date
- If the user did NOT ask for articles (user_wants_articles={user_wants_articles}), just answer the question in 1 sentence — do not list articles or URLs even if they exist in the results
- Never make up data that is not in the results
- Keep the answer short and focused on exactly what was asked
"""

    summary_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0
    )

    return summary_response.choices[0].message.content.strip()