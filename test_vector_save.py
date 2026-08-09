from app import app

from models.article import Article

from services.vector_service import VectorService



vector = VectorService()



with app.app_context():


    article = Article.query.first()


    print(
        "Article:",
        article.title
    )


    vector.add_article(
        article
    )