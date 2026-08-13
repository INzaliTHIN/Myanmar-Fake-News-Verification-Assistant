from dotenv import load_dotenv

load_dotenv()


from services.ai_service import AIService


ai = AIService()


print(
    "KEY:",
    ai.api_key[:10] if ai.api_key else None
)


result = ai.extract_claim(
    "ရန်ကုန်မြို့တွင် မြေငလျင်ကြီးဖြစ်ပွားခဲ့သည်"
)


print(result)