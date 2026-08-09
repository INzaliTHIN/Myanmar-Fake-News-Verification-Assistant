import re



class ClaimExtractor:


    def extract(self, text):


        result = {

            "original_text": text,

            "keywords": [],

            "entities": []

        }



        words = re.findall(
            r'[\u1000-\u109F]+',
            text
        )


        result["keywords"] = list(
            set(words)
        )


        return result