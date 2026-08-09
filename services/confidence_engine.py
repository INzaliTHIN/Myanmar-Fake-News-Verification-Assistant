class ConfidenceEngine:


    def calculate(
        self,
        source_score,
        trust_score,
        evidence_count,
        entity_score
    ):


        # Evidence score

        if evidence_count >= 3:

            evidence_score = 100

        elif evidence_count == 2:

            evidence_score = 80

        elif evidence_count == 1:

            evidence_score = 60

        else:

            evidence_score = 0



        confidence = (

            (source_score * 0.4)
            +
            (trust_score * 0.25)
            +
            (evidence_score * 0.2)
            +
            (entity_score * 0.15)

        )


        return round(
            confidence,
            2
        )



    def classify(
        self,
        confidence
    ):


        if confidence >= 80:

            return "Likely True"


        elif confidence >= 50:

            return "Uncertain"


        else:

            return "Likely False"