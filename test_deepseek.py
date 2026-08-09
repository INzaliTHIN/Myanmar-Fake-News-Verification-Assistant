from dotenv import load_dotenv
import os

from services.deepseek_service import DeepSeekService



load_dotenv()
print( 
    "KEY:",
    os.getenv("DEEPSEEK_API_KEY")
)


ai = DeepSeekService()



result = ai.analyze_claim(

    "ရန်ကုန်မြို့တွင် မြေငလျင်ကြီး ဖြစ်ပွားခဲ့သည်",

    """
    BBC Myanmar reported earthquake information
    in Yangon area.
    """

)



print(result)