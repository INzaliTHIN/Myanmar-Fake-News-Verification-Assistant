from services.article_extractor import ArticleExtractor



extractor = ArticleExtractor()



url = "https://www.bbc.com/burmese"



links = extractor.get_article_links(
    url,
    limit=5
)



for link in links:

    print(link)