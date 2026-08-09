from services.source_matcher import SourceMatcher



matcher = SourceMatcher()



claim = """
ရန်ကုန်မြို့တွင် မြေငလျင်ဖြစ်ပွားခဲ့သည်
"""



sources = [

    {
        "name":"BBC Myanmar",
        "text":
        "ရန်ကုန်မြို့တွင် မြေငလျင်ဖြစ်ပွားခဲ့ကြောင်း သတင်းဖော်ပြခဲ့သည်"
    },


    {
        "name":"DVB",
        "text":
        "နိုင်ငံရေးဆိုင်ရာ သတင်းများ ထုတ်ပြန်ခဲ့သည်"
    }

]



result = matcher.match_sources(
    claim,
    sources
)


print(result)