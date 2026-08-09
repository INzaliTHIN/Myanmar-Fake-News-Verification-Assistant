from services.confidence_service import ConfidenceService



service = ConfidenceService()



data = [

{

"claim":"ရန်ကုန်တွင်ငလျင်ဖြစ်",

"evidence":["BBC"]

},


{

"claim":"လူ၅၀၀သေဆုံး",

"evidence":[]

}

]



result = service.calculate(
    data
)


print(result)