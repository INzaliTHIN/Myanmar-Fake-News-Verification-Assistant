from datetime import datetime

from models.history import db



class Article(db.Model):

    __tablename__ = "articles"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    title = db.Column(
        db.String(255),
        nullable=False
    )


    content = db.Column(
        db.Text,
        nullable=False
    )


    url = db.Column(
        db.String(500),
        unique=True
    )


    domain = db.Column(
        db.String(255)
    )


    source = db.Column(
        db.String(255)
    )


    author = db.Column(
        db.String(255)
    )


    published_date = db.Column(
        db.DateTime
    )


    trust_score = db.Column(
        db.Float,
        default=0
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    def __repr__(self):

        return f"<Article {self.title}>"