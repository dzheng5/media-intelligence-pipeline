import os
import json
import time
import snowflake.connector
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    schema="GOLD"
)

cursor = conn.cursor()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Get list of companies
cursor.execute("SELECT DISTINCT company FROM GOLD.mart_news_sentiment ORDER BY company")
companies = [row[0] for row in cursor.fetchall()]
print(f"Found {len(companies)} companies")

def get_articles_for_company(company):
    cursor.execute(f"""
        SELECT article_title, sentiment_label, source_name
        FROM BRONZE.news_articles_scored
        WHERE company = '{company}'
        ORDER BY published_date DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    return rows

def generate_summary_card(company, articles, overall_sentiment, total_articles, positive, negative, neutral):
    article_list = "\n".join([f"- [{row[1].upper()}] {row[0]} ({row[2]})" for row in articles])
    
    prompt = f"""You are a media intelligence analyst. Based on the following news articles about {company}, write a summary card.

Overall sentiment score: {overall_sentiment} (-1.0 very negative to 1.0 very positive)
Total articles: {total_articles} | Positive: {positive} | Neutral: {neutral} | Negative: {negative}

Recent articles:
{article_list}

Return ONLY a JSON object with these fields:
- "summary": 2-3 sentences describing what the news is actually saying about {company}. The overall sentiment score is {overall_sentiment} which means it is {"positive" if overall_sentiment > 0.05 else "negative" if overall_sentiment < -0.05 else "neutral"}. Make sure your summary reflects this accurately.
- "sentiment_trend": one of "Positive", "Neutral", or "Negative"
- "key_themes": a list of 3 specific themes based on the actual article headlines above

Example: {{"summary": "...", "sentiment_trend": "Positive", "key_themes": ["theme1", "theme2", "theme3"]}}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        return json.loads(content.strip())
    except:
        return {
            "summary": "Unable to generate summary.",
            "sentiment_trend": "Neutral",
            "key_themes": []
        }

# Get aggregated stats
cursor.execute("""
    SELECT 
        company,
        ROUND(AVG(avg_sentiment_score), 3) AS overall_sentiment,
        SUM(total_articles) AS total_articles,
        SUM(positive_count) AS positive_count,
        SUM(negative_count) AS negative_count,
        SUM(neutral_count) AS neutral_count
    FROM GOLD.mart_news_sentiment
    GROUP BY company
    ORDER BY company
""")
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]

results = []

for row in rows:
    data = dict(zip(columns, row))
    company = data["COMPANY"]
    print(f"Generating summary for {company}...")

    articles = get_articles_for_company(company)
    card = generate_summary_card(
        company=company,
        articles=articles,
        overall_sentiment=data["OVERALL_SENTIMENT"],
        total_articles=data["TOTAL_ARTICLES"],
        positive=data["POSITIVE_COUNT"],
        negative=data["NEGATIVE_COUNT"],
        neutral=data["NEUTRAL_COUNT"]
    )

    score = data["OVERALL_SENTIMENT"]
    if score > 0.05:
        trend = "Positive"
    elif score < -0.05:
        trend = "Negative"
    else:
        trend = "Neutral"

    results.append((
        company,
        score,
        card["summary"],
        trend,
        json.dumps(card["key_themes"])
    ))

    print(f"  {company} → {card['sentiment_trend']} | {card['summary'][:80]}...")
    time.sleep(1)

print(f"\nWriting {len(results)} summary cards to Snowflake...")

cursor.execute("""
    CREATE OR REPLACE TABLE GOLD.ai_summary_cards (
        company VARCHAR,
        overall_sentiment_score FLOAT,
        summary VARCHAR,
        sentiment_trend VARCHAR,
        key_themes VARCHAR
    )
""")

cursor.executemany("""
    INSERT INTO GOLD.ai_summary_cards
    (company, overall_sentiment_score, summary, sentiment_trend, key_themes)
    VALUES (%s, %s, %s, %s, %s)
""", results)

conn.commit()
print("Done! Summary cards written to GOLD.ai_summary_cards")

cursor.close()
conn.close()