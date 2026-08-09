import re



class EntityExtractor:


    def extract(self, text):


        result = {

            "location": [],
            "person": [],
            "organization": [],
            "date": []

        }


        # Location basic detection

        location_pattern = r'([\u1000-\u109F]+မြို့)'


        result["location"] = re.findall(
            location_pattern,
            text
        )



        # Organization basic detection

        org_keywords = [
            "အစိုးရ",
            "အဖွဲ့",
            "ကုမ္ပဏီ",
            "ဌာန"
        ]


        for word in org_keywords:

            if word in text:

                result["organization"].append(
                    word
                )



        # Date detection

        date_pattern = r'\d{1,4}[\-/]\d{1,2}[\-/]\d{1,2}'


        result["date"] = re.findall(
            date_pattern,
            text
        )



        return result