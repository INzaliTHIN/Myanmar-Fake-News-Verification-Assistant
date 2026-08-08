from services.source_manager import SourceManager
from services.news_collector import NewsCollector
from services.dictionary_builder import DictionaryBuilder



source_manager = SourceManager()

collector = NewsCollector()

builder = DictionaryBuilder()



sources = source_manager.load_sources()



total = 0



for source in sources:


    print(
        "\nCollecting:",
        source["name"]
    )


    url = source["url"]


    article = collector.get_article_text(
        url
    )


    if article:


        print(
            "Article length:",
            len(article)
        )


        count = builder.update_dictionary(
            article
        )


        print(
            "Dictionary words:",
            count
        )


        total += 1



    else:


        print(
            "No article found"
        )



print(
    "\nCompleted sources:",
    total
)