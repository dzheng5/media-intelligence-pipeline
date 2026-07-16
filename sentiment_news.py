import os
import json
import time
import snowflake.connector
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Connect to Snowflake
conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    schema="SILVER"
)

cursor = conn.cursor()

# Pull all news articles from stg_news
print("Fetching news articles from Snowflake...")
cursor.execute("SELECT company, article_title, article_description, full_text, published_date, source_name FROM SILVER.stg_news")
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]
print(f"Found {len(rows)} articles to process")

# Set up Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_sentiment(text):
    if not text or len(text.strip()) == 0:
        return 0.0, "neutral"
    
    prompt = f"""Analyze the sentiment of this text and return ONLY a JSON object with two fields:
- "score": a float between -1.0 (very negative) and 1.0 (very positive)
- "label": one of "positive", "neutral", or "negative"

Text: {text[:100]}

Return only the JSON object, nothing else. Example: {{"score": 0.5, "label": "positive"}}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    content = response.choices[0].message.content.strip()
    
    if not content:
        return 0.0, "neutral"
    
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    
    try:
        result = json.loads(content.strip())
        return result["score"], result["label"]
    except:
        return 0.0, "neutral"

# Process all rows
results = []
batch_size = 10

for i, row in enumerate(rows):
    data = dict(zip(columns, row))
    
    try:
        sentiment_score, sentiment_label = get_sentiment(data["FULL_TEXT"])
    except Exception as e:
        print(f"Error on row {i}: {e}, defaulting to neutral")
        sentiment_score, sentiment_label = 0.0, "neutral"
    
    results.append((
        data["COMPANY"],
        data["ARTICLE_TITLE"],
        data["ARTICLE_DESCRIPTION"],
        data["SOURCE_NAME"],
        data["PUBLISHED_DATE"],
        sentiment_score,
        sentiment_label
    ))
    
    if (i + 1) % batch_size == 0:
        print(f"Processed {i + 1}/{len(rows)} articles...")
        time.sleep(1)

print(f"Done scoring. Writing {len(results)} rows to Snowflake...")

# Write results to BRONZE
cursor.execute("""
    CREATE OR REPLACE TABLE BRONZE.news_sentiment_scores (
        company VARCHAR,
        article_title VARCHAR,
        article_description VARCHAR,
        source_name VARCHAR,
        published_date DATE,
        sentiment_score FLOAT,
        sentiment_label VARCHAR
    )
""")

cursor.executemany("""
    INSERT INTO BRONZE.news_sentiment_scores
    (company, article_title, article_description, source_name, published_date, sentiment_score, sentiment_label)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", results)

conn.commit()
print("Done! Data written to BRONZE.news_sentiment_scores")

cursor.close()
conn.close()