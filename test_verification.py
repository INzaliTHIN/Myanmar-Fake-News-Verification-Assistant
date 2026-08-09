from app import app

from services.verification_service import VerificationService



with app.app_context():


    service = VerificationService()


    result = service.verify(

        "ရန်ကုန်မြို့တွင် မြေငလျင်ဖြစ်ပွားခဲ့သည်"

    )


    print(result)