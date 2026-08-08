from services.dictionary_builder import DictionaryBuilder


texts = [

"""
ရန်ကုန်မြို့တွင် သတင်းစာရှင်းလင်းပွဲ ပြုလုပ်ခဲ့သည်။
အစိုးရအဖွဲ့မှ ကြေညာချက် ထုတ်ပြန်ခဲ့သည်။
မြန်မာနိုင်ငံတွင် လူမှုရေးနှင့် စီးပွားရေးဆိုင်ရာ
အခြေအနေများ ပြောင်းလဲလာသည်။
"""

]


builder = DictionaryBuilder()


words = builder.extract_words(texts[0])

print("Extract words:")
print(words)


count = builder.build_dictionary(
    texts
)


print(
    "Dictionary size:",
    count
)