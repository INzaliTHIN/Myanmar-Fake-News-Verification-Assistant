from services.url_service import URLService
from services.article_extractor import ArticleExtractor



url_service = URLService()

extractor = ArticleExtractor()



url = "https://www.bbc.com"



html = url_service.fetch_content(url)



if html:


    article = extractor.extract(
        html
    )


    print(
        "TITLE:"
    )

    print(
        article["title"]
    )


    print(
        "\nCONTENT SAMPLE:"
    )


    print(
        article["content"][:500]
    )


else:

    print(
        "Cannot fetch"
    )