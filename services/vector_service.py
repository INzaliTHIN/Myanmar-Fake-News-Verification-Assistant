import chromadb
from sentence_transformers import SentenceTransformer



class VectorService:


    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="vector_db"
        )


        self.collection = self.client.get_or_create_collection(
            name="news_articles"
        )


        self.model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )



    def add_article(
        self,
        article
    ):


        text = (
            article.title
            + "\n"
            + article.content
        )


        embedding = self.model.encode(
            text
        ).tolist()



        self.collection.add(

            ids=[
                str(article.id)
            ],


            embeddings=[
                embedding
            ],


            documents=[
                article.content
            ],


            metadatas=[

                {

                    "title":
                    str(article.title or ""),


                    "url":
                    str(article.url or ""),


                    "domain":
                    str(article.domain or ""),


                    "source":
                    str(article.source or "")

                }

            ]

        )


        print(
            "Vector saved:",
            article.id
        )



        return True

    def search(
        self,
        query,
        limit=3
    ):

        embedding = self.model.encode(
            query
        ).tolist()


        results = self.collection.query(

            query_embeddings=[
                embedding
            ],

            n_results=limit

        )


        return results