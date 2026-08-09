import re



class ClaimExtractor:


    def extract(self, text):


        if not text:

            return []



        # sentence ခွဲခြားခြင်း

        sentences = re.split(
            r'[။!?]',
            text
        )



        claims = []


        for sentence in sentences:


            sentence = sentence.strip()


            if len(sentence) > 10:


                claims.append(
                    sentence
                )



        return claims