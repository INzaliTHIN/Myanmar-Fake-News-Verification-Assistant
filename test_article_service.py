from app import app

from services.article_service import ArticleService



with app.app_context():


    service = ArticleService()



    article = service.save_article(

        title="ရန်ကုန် မြေငလျင် သတင်း",

        content="""

        ရန်ကုန်မြို့တွင်
        မြေငလျင်ဖြစ်ပွားခဲ့ကြောင်း
        သတင်းထုတ်ပြန်ခဲ့သည်။

        """,

        url="https://www.bbc.com/burmese/example",

        source="BBC Myanmar",

        trust_score=0.9

    )


    print(
        "Saved Article ID:",
        article.id
    )


    print(
        "URL:",
        article.url
    )