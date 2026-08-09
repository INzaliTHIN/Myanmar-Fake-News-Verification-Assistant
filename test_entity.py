from services.entity_extractor import EntityExtractor



extractor = EntityExtractor()



text = """
ရန်ကုန်မြို့တွင် အစိုးရအဖွဲ့မှ
2026-08-09 ရက်နေ့တွင်
ကြေညာချက်ထုတ်ပြန်ခဲ့သည်။
"""



result = extractor.extract(
    text
)


print(result)