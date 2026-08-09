from services.claim_service import ClaimExtractor
from services.vector_service import VectorService



class ClaimVerificationService:


    def __init__(self):

        self.extractor = ClaimExtractor()

        self.vector = VectorService()



    def verify_claims(self, text):


        claims = self.extractor.extract(
            text
        )


        results = []


        for claim in claims:


            evidence = self.vector.search(
                claim
            )


            results.append({

                "claim": claim,

                "evidence": evidence

            })


        return results