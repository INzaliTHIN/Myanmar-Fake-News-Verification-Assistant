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


from services.nlp_service import MyanmarTextProcessor
from services.spelling_service import MyanmarSpellChecker

from services.url_service import URLService
from services.article_extractor import ArticleExtractor
from services.article_service import ArticleService
from services.vector_service import VectorService
from services.verification_service import VerificationService

from routes.verification import verification


# =========================
# Flask Setup
# =========================

app = Flask(__name__)

app.config.from_object(Config)


# Blueprint

app.register_blueprint(
    verification
)


# =========================
# Services
# =========================

url_service = URLService()

article_extractor = ArticleExtractor()

article_service = ArticleService()

vector_service = VectorService()

verification_service = VerificationService()



# Database

db.init_app(app)



with app.app_context():

    db.create_all()



# =========================
# Home
# =========================

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":


        claim = request.form.get("claim")

        url = request.form.get("url")



        # =====================
        # URL Processing
        # =====================

        if url:


            if not url_service.validate_url(url):

                return "Invalid URL"



            html = url_service.fetch_content(url)



            if html:


                article = article_extractor.extract(
                    html
                )


                if article:


                    claim = article.get(
                        "content"
                    )



                    # Save Database

                    saved_article = article_service.save_article(

                        title=article.get(
                            "title",
                            "Unknown"
                        ),

                        content=article.get(
                            "content"
                        ),

                        url=url,

                        source=url_service.get_domain(url)

                    )



                    # Save Vector DB

                    vector_service.add_article(
                        saved_article
                    )



        if not claim:

            return "No input found"



        return redirect(
            url_for(
                "verify",
                text=claim
            )
        )



    return render_template(
        "index.html"
    )



# =========================
# Verification
# =========================

@app.route("/verify", methods=["GET","POST"])
def verify():


    if request.method == "GET":

        text = request.args.get(
            "text"
        )

    else:

        text = request.form.get(
            "claim"
        )



    if not text:

        return redirect(
            url_for("home")
        )



    # RAG AI Verification

    result = verification_service.verify(
        text
    )



    # Save History

    history = VerificationHistory(

        input_text=text,

        status=result.get(
            "status"
        ),

        confidence=result.get(
            "confidence",
            0
        ),

        explanation=str(result)

    )


    db.session.add(history)

    db.session.commit()



    return render_template(

        "result.html",

        result=result

    )




# =========================
# History
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
# Test
# =========================

@app.route("/test")
def test():

    return {

        "status":"running",
        "system":
        "Myanmar AI Fact Verification"

    }



# =========================
# Run
# =========================

if __name__ == "__main__":

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True

    )