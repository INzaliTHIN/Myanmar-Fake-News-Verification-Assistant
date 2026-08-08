from services.news_collector import NewsCollector



collector = NewsCollector()



url = "https://example.com"



text = collector.get_article_text(
    url
)



print(text[:500])