from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for
)

from config import Config


from models.history import (
    db,
    VerificationHistory
)


from services.nlp_service import (
    MyanmarTextProcessor
)


from services.spelling_service import (
    MyanmarSpellChecker
)



# =========================
# Flask App Setup
# =========================

app = Flask(__name__)

app.config.from_object(Config)


# Database initialize

db.init_app(app)



# Create database tables

with app.app_context():

    db.create_all()



# =========================
# Home Page
# =========================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )



# =========================
# Verification Process
# =========================

@app.route(
    "/verify",
    methods=["POST"]
)
def verify():


    # Get user input

    text = request.form.get(
        "text"
    )


    if not text:

        return redirect(
            url_for("home")
        )



    # ---------------------
    # Text Processing
    # ---------------------

    processor = MyanmarTextProcessor()


    processed = processor.process(
        text
    )



    # ---------------------
    # Spelling Check
    # ---------------------

    spell_checker = MyanmarSpellChecker()


    corrections = spell_checker.check_text(
        processed["cleaned"]
    )



    # ---------------------
    # Save History
    # ---------------------

    history = VerificationHistory(

        input_text=
        processed["cleaned"],


        status=
        "Processed",


        confidence=
        0.0,


        explanation=
        str({

            "cleaned_text":
            processed["cleaned"],


            "sentences":
            processed["sentences"],


            "spelling":
            corrections

        })

    )


    db.session.add(
        history
    )


    db.session.commit()



    return redirect(
        url_for(
            "history"
        )
    )



# =========================
# History Page
# =========================

@app.route("/history")
def history():


    records = VerificationHistory.query.order_by(

        VerificationHistory.created_at.desc()

    ).all()



    return render_template(

        "history.html",

        data=records

    )



# =========================
# Test Route
# =========================

@app.route("/test")
def test():

    return {

        "status":
        "running",

        "system":
        "Myanmar AI Fact Verification"

    }



# =========================
# Run Server
# =========================

if __name__ == "__main__":


    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True

    )