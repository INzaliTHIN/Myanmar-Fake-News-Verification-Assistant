class ConfidenceService:


    def calculate(self, claims):


        if not claims:

            return {

                "status":"Uncertain",

                "confidence":0

            }



        scores = []


        for claim in claims:


            evidence = claim.get(
                "evidence"
            )


            if evidence:

                score = 90


            else:

                score = 30



            scores.append(
                score
            )



        final_score = sum(scores) / len(scores)



        if final_score >= 80:


            status = "Likely True"



        elif final_score >= 40:


            status = "Uncertain"



        else:


            status = "Likely False"



        return {


            "status": status,


            "confidence": round(
                final_score,
                2
            )

        }