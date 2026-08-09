from services.vector_service import VectorService



class VerificationService:


    def __init__(self):

        self.vector = VectorService()



    def verify(self, claim):


        result = self.vector.search(
            claim,
            limit=3
        )


        documents = result.get(
            "documents",
            []
        )

        metadatas = result.get(
            "metadatas",
            []
        )

        distances = result.get(
            "distances",
            []
        )



        evidence = []



        if documents and documents[0]:


            for i, doc in enumerate(documents[0]):


                meta = {}


                if metadatas and metadatas[0]:

                    meta = metadatas[0][i]



                distance = 0


                if distances and distances[0]:

                    distance = distances[0][i]



                confidence = max(
                    0,
                    min(
                        100,
                        round(
                            100 - distance,
                            2
                        )
                    )
                )



                evidence.append({

                    "content":
                    doc,


                    "source":
                    meta.get(
                        "source",
                        "Unknown"
                    ),


                    "url":
                    meta.get(
                        "url"
                    ),


                    "confidence":
                    confidence

                })



        if not evidence:


            return {

                "status":
                "Uncertain",


                "confidence":
                30,


                "evidence":
                []

            }



        return {


            "status":
            "Likely True",


            "confidence":
            evidence[0]["confidence"],


            "evidence":
            evidence

        }