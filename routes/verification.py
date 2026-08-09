from flask import (
    Blueprint,
    render_template,
    request
)


from services.verification_service import VerificationService
from services.input_detector import InputDetector
from services.url_service import URLService
from services.article_extractor import ArticleExtractor



verification = Blueprint(
    "verification",
    __name__
)



service = VerificationService()

detector = InputDetector()

url_service = URLService()

extractor = ArticleExtractor()



@verification.route(
    "/",
    methods=[
        "GET",
        "POST"
    ]
)
def index():


    result = None



    if request.method == "POST":


        text = request.form.get(
            "claim"
        )



        if text:


            # URL detect

            if detector.is_url(text):


                html = url_service.fetch_content(
                    text
                )


                if html:


                    article = extractor.extract(
                        html
                    )


                    text = article.get(
                        "content"
                    )



            result = service.verify(
                text
            )



    return render_template(
        "index.html",
        result=result
    )