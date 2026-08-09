from services.local_ai_engine import LocalAIEngine


engine = LocalAIEngine()


sources = [

    {
        "source":"BBC Myanmar",
        "score":85
    },

    {
        "source":"DVB",
        "score":30
    }

]


result = engine.analyze(

    "ရန်ကုန်တွင် မြေငလျင်ဖြစ်ပွားခဲ့သည်",

    sources

)


print(result)