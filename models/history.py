from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class VerificationHistory(db.Model):

    tablename = "verification_history"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    input_text = db.Column(
        db.Text,
        nullable=False
    )


    status = db.Column(
        db.String(50),
        default="Pending"
    )


    confidence = db.Column(
        db.Float,
        default=0
    )


    explanation = db.Column(
        db.Text
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )