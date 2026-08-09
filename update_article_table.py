from app import app
from models.history import db


with app.app_context():

    with db.engine.connect() as conn:

        try:

            conn.execute(
                db.text(
                    "ALTER TABLE articles ADD COLUMN domain VARCHAR(255)"
                )
            )

            print("domain column added")


        except Exception as e:

            print(
                "domain:",
                e
            )



        try:

            conn.execute(
                db.text(
                    "ALTER TABLE articles ADD COLUMN author VARCHAR(255)"
                )
            )

            print("author column added")


        except Exception as e:

            print(
                "author:",
                e
            )


        conn.commit()