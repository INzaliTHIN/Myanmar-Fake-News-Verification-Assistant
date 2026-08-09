from services.vector_database import VectorDatabase


class RAGEngine:


    def __init__(self):

        self.vector_db = VectorDatabase()



    def retrieve_evidence(
        self,
        claim,
        limit=3
    ):


        result = self.vector_db.search(
            claim,
            limit
        )


        evidence = []

        seen = set()   # ဒီနေရာမှာ ထည့်ပါ


        documents = result.get(
            "documents",
            [[]]
        )[0]


        metadatas = result.get(
            "metadatas",
            [[]]
        )[0]


        distances = result.get(
            "distances",
            [[]]
        )[0]



        for i, text in enumerate(documents):


            meta = (
                metadatas[i]
                if i < len(metadatas)
                else {}
            )


            distance = (
                distances[i]
                if i < len(distances)
                else None
            )


            key = (
                meta.get("source"),
                meta.get("url"),
            )


            if key in seen:
                continue


            seen.add(key)



            evidence.append(

                {

                    "content": text,

                    "source":
                    meta.get("source"),

                    "url":
                    meta.get("url"),

                    "distance":
                    distance

                }

            )


        return evidence