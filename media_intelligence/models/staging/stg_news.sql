WITH source AS (
    SELECT * FROM MEDIA_INTELLIGENCE.BRONZE.news_articles
),

cleaned AS (
    SELECT
        company,
        title AS article_title,
        description AS article_description,
        source_name,
        url,
        published_date,
        CONCAT(COALESCE(title, ''), ' ', COALESCE(description, '')) AS full_text
    FROM source
    WHERE title IS NOT NULL
    AND published_date IS NOT NULL
)

SELECT * FROM cleaned