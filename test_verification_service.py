from services.verification_service import VerificationService



service = VerificationService()



result = service.verify(

    """
    ရန်ကုန်မြို့တွင်
    မြေငလျင်ဖြစ်ပွားခဲ့သည်။
    """

)



print(result)