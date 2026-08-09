from models.article import Article
from models.history import db
from urllib.parse import urlparse
from datetime import datetime



class ArticleService:


    def get_domain(self, url):

        try:

            parsed = urlparse(url)

            return parsed.netloc

        except:

            return None



    def save_article(
        self,
        title,
        content,
        url,
        source=None,
        author=None
    ):


        # =====================
        # Duplicate Check
        # =====================

        existing = Article.query.filter_by(
            url=url
        ).first()



        if existing:

            print(
                "Article already exists"
            )

            return existing



        # =====================
        # Create Article
        # =====================


        article = Article(

            title=title,

            content=content,

            url=url,

            domain=self.get_domain(url),

            source=source,

            author=author,

            published_date=datetime.utcnow(),

            trust_score=0.0

        )



        db.session.add(
            article
        )


        db.session.commit()



        print(
            "Article saved:",
            article.id
        )


        return article