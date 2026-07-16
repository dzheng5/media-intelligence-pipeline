WITH news AS (
    SELECT
        company,
        published_date,
        sentiment_score,
        sentiment_label,
        source_name
    FROM MEDIA_INTELLIGENCE.BRONZE.news_sentiment_scores
)

SELECT
    company,
    published_date,
    COUNT(*) AS total_articles,
    ROUND(AVG(sentiment_score), 3) AS avg_sentiment_score,
    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) AS neutral_count,
    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative_count
FROM news
GROUP BY company, published_date
ORDER BY company, published_date