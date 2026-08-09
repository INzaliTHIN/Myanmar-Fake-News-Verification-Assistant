from services.claim_verification_service import (
    ClaimVerificationService
)



service = ClaimVerificationService()



text = """
ရန်ကုန်မြို့တွင် မြေငလျင်ဖြစ်ပွားခဲ့သည်။
လူ ၅၀၀ သေဆုံးခဲ့သည်။
"""



result = service.verify_claims(
    text
)



for item in result:

    print("================")

    print(
        "CLAIM:"
    )

    print(
        item["claim"]
    )


    print(
        "EVIDENCE:"
    )

    print(
        item["evidence"]
    )