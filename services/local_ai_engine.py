class LocalAIEngine:


    def analyze(
        self,
        claim,
        matched_sources
    ):


        if not matched_sources:

            return {

                "result":
                "Uncertain",

                "confidence":
                30,

                "reason":
                "No supporting evidence found"

            }



        best_score = max(
            item["score"]
            for item in matched_sources
        )



        if best_score >= 70:

            result = "Likely True"

            confidence = best_score


            reason = (
                "Similar information found "
                "from available sources."
            )


        elif best_score >= 40:

            result = "Uncertain"

            confidence = best_score


            reason = (
                "Partial matching evidence found."
            )


        else:

            result = "Likely False"

            confidence = 100 - best_score


            reason = (
                "No strong supporting evidence found."
            )



        return {

            "result": result,

            "confidence":
            round(confidence,2),

            "reason":
            reason

        }