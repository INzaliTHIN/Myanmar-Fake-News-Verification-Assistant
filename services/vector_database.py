import chromadb

from sentence_transformers import SentenceTransformer



class VectorDatabase:


    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="data/vector_db"
        )


        self.collection = (
            self.client
            .get_or_create_collection(
                name="news_articles"
            )
        )


        self.model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )



    def add_article(
        self,
        article_id,
        text,
        metadata=None
    ):


        embedding = self.model.encode(
            text
        ).tolist()



        self.collection.add(

            ids=[
                article_id
            ],

            embeddings=[
                embedding
            ],

            documents=[
                text
            ],

            metadatas=[
                metadata or {}
            ]

        )



    def search(
        self,
        query,
        limit=3
    ):


        embedding = self.model.encode(
            query
        ).tolist()



        result = self.collection.query(

            query_embeddings=[
                embedding
            ],

            n_results=limit

        )


        return result