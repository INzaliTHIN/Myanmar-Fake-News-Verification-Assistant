from services.news_collector import NewsCollector
from services.dictionary_builder import DictionaryBuilder



url = "https://example.com"



collector = NewsCollector()


article = collector.get_article_text(
    url
)



if article:


    builder = DictionaryBuilder()


    count = builder.update_dictionary(
        article
    )


    print(
        "Dictionary total words:",
        count
    )


else:

    print(
        "No article text found"
    )