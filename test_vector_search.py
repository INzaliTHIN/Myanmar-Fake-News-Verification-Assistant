from services.vector_service import VectorService



vector = VectorService()



query = """
ရန်ကုန်မြို့တွင်
မြေငလျင်ဖြစ်ပွားခဲ့သည်။
"""



result = vector.search(
    query
)



print(result)