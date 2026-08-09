from app import app
from services.article_service import ArticleService



service = ArticleService()



with app.app_context():


    article = service.save_article(

        title="ရန်ကုန်မြေငလျင်သတင်း",

        content="""
        ရန်ကုန်မြို့တွင်
        မြေငလျင်ဖြစ်ပွားခဲ့ကြောင်း
        သတင်းထုတ်ပြန်ခဲ့သည်။
        """,

        url="https://example.com/test-news",

        source="Test Source"

    )


    print(
        "ID:",
        article.id
    )


    print(
        "TITLE:",
        article.title
    )


    print(
        "URL:",
        article.url
    )


    print(
        "DOMAIN:",
        article.domain
    )