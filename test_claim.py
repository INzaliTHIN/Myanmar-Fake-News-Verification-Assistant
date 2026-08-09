from services.claim_service import ClaimExtractor



extractor = ClaimExtractor()



text = """
ရန်ကုန်မြို့တွင် မြေငလျင်ဖြစ်ပွားခဲ့သည်။
လူ ၅၀၀ သေဆုံးခဲ့သည်။
အစိုးရက အရေးပေါ်ကြေညာခဲ့သည်။
"""



claims = extractor.extract(
    text
)



for i, claim in enumerate(claims):

    print(
        i+1,
        claim
    )