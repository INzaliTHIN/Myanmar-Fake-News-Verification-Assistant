from datetime import datetime

from models.history import db



class Verification(db.Model):

    __tablename__ = "verifications"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    claim = db.Column(
        db.Text,
        nullable=False
    )


    result = db.Column(
        db.String(50)
    )


    confidence = db.Column(
        db.Float
    )


    reason = db.Column(
        db.Text
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )