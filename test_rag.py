from app import app

from services.rag_engine import RAGEngine



with app.app_context():


    rag = RAGEngine()



    result = rag.retrieve_evidence(

        "ရန်ကုန် မြေငလျင် သတင်း"

    )


    for item in result:

        print("================")

        print(
            "Source:",
            item["source"]
        )

        print(
            "URL:",
            item["url"]
        )

        print(
            "Content:",
            item["content"]
        )

        print(
            "Distance:",
            item["distance"]
        )