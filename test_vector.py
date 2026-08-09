from services.vector_database import VectorDatabase



db = VectorDatabase()



db.add_article(

    "news001",

    """
    ရန်ကုန်မြို့တွင်
    မြေငလျင်ဖြစ်ပွားခဲ့ကြောင်း
    သတင်းထုတ်ပြန်ခဲ့သည်။
    """,

    {
    "source":"BBC Myanmar",
    "url":"https://www.bbc.com/burmese",
    "date":"2026-08-09",
    "trust_score":0.9
}

)



result = db.search(

    "ရန်ကုန် မြေငလျင် သတင်း"

)



print(result)