import os
import requests
import snowflake.connector
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Companies to track
COMPANIES = {
    "Apple": "Apple Inc",
    "Google": "Google",
    "Microsoft": "Microsoft",
    "Meta": "Meta Facebook",
    "Amazon": "Amazon",
    "Netflix": "Netflix",
    "Tesla": "Tesla",
    "Nvidia": "Nvidia",
    "Samsung": "Samsung",
    "Intel": "Intel"
}

# NewsAPI config
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
BASE_URL = "https://newsapi.org/v2/everything"

# Date range — last 30 days
end_date = datetime.today().strftime("%Y-%m-%d")
start_date = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

def fetch_news(company_label, query):
    params = {
        "q": query,
        "from": start_date,
        "to": end_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
        "apiKey": NEWS_API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if data.get("status") != "ok":
        print(f"Error fetching {company_label}: {data.get('message')}")
        return []
    
    articles = []
    for article in data.get("articles", []):
        articles.append((
            company_label,
            article.get("title", ""),
            article.get("description", ""),
            article.get("source", {}).get("name", ""),
            article.get("url", ""),
            article.get("publishedAt", "")[:10]
        ))
    
    print(f"Fetched {len(articles)} articles for {company_label}")
    return articles

# Fetch all companies
all_articles = []
for company_label, query in COMPANIES.items():
    articles = fetch_news(company_label, query)
    all_articles.extend(articles)

print(f"\nTotal articles fetched: {len(all_articles)}")

# Connect to Snowflake and write
conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    schema="BRONZE"
)

cursor = conn.cursor()

cursor.execute("""
    CREATE OR REPLACE TABLE BRONZE.news_articles (
        company VARCHAR,
        title VARCHAR,
        description VARCHAR,
        source_name VARCHAR,
        url VARCHAR,
        published_date DATE
    )
""")

cursor.executemany("""
    INSERT INTO BRONZE.news_articles
    (company, title, description, source_name, url, published_date)
    VALUES (%s, %s, %s, %s, %s, %s)
""", all_articles)

conn.commit()
print("Done! News articles written to BRONZE.news_articles")

cursor.close()
conn.close()