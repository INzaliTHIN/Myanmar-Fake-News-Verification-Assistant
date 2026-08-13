from html import entities
import os
import json
import requests
import re
from rank_bm25 import BM25Okapi
import numpy as np
import faiss
from newspaper import Article

from sentence_transformers import SentenceTransformer

from flask import (
    Flask,
    render_template,
    request
)

from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy

from urllib.parse import urlparse
from bs4 import BeautifulSoup


# =========================
# ENV
# =========================

load_dotenv()


# =========================
# APP CONFIG
# =========================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "secret"
)


app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///database.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)



# =========================
# DATABASE
# =========================


class History(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    input_text = db.Column(
        db.Text,
        nullable=False
    )


    extracted_text = db.Column(
        db.Text
    )


    result = db.Column(
        db.Text
    )


with app.app_context():

    db.create_all()

# =========================
# SEMANTIC MODEL
# =========================

semantic_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

TRUSTED_SOURCE_FILE = "data/trusted_source.json"


def load_trusted_sources():

    try:

        with open(
            TRUSTED_SOURCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print("Trusted source error:", e)

        return []

def get_source_trust(source_url):


    trusted_sources = load_trusted_sources()


    for item in trusted_sources:


        domain = item["domain"]


        if domain in source_url:


            return item["trust_score"]


    return 0.5

def check_source_trust(url):

    try:

        with open(
            "data/trusted_source.json",
            encoding="utf-8"
        ) as f:

            sources=json.load(f)



        domain=urlparse(url).netloc


        for item in sources:

            if item["domain"] in domain:

                return item["trust_score"]


        return 0.5


    except Exception as e:

        print("Trusted source error:",e)

        return 0.5

def extract_article(url):

    try:

        article = Article(url)

        article.download()
        article.parse()


        data = {

            "title": article.title,

            "content": article.text,

            "url": url,

            "source": urlparse(url).netloc

        }


        return data


    except Exception as e:

        print("ARTICLE ERROR:", e)

        return None

# =========================
# URL CHECK
# =========================


def is_url(text):

    try:

        result = urlparse(text)

        return (
            result.scheme in [
                "http",
                "https"
            ]
            and result.netloc
        )


    except:

        return False



# =========================
# ARTICLE EXTRACTION
# =========================


def extract_article(url):

    try:

        headers = {

            "User-Agent":
            "Mozilla/5.0"

        }


        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # remove unnecessary parts

        for tag in soup.find_all(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header"
            ]
        ):

            tag.decompose()



        title = ""

        if soup.title:

            title = soup.title.text.strip()



        paragraphs = soup.find_all("p")


        content = " ".join(

            p.get_text(
                " ",
                strip=True
            )

            for p in paragraphs

        )


        return {

            "title": title,

            "content": content,

            "url": url

        }


    except Exception as e:

        print(
            "Extraction Error:",
            e
        )

        return None
    


# =========================
# NLP PROCESSING
# =========================


def unicode_normalize(text):

    try:

        import unicodedata

        return unicodedata.normalize(
            "NFC",
            text
        )

    except Exception as e:

        print(
            "Unicode Normalize Error:",
            e
        )

        return text


def clean_text(text):

    if not text:
        return ""


    # unicode

    text = unicode_normalize(text)


    # remove extra spaces

    text = re.sub(
        r"\s+",
        " ",
        text
    )


    # remove html leftovers

    text = re.sub(
        r"<.*?>",
        "",
        text
    )


    return text.strip()



def sentence_split(text):

    if not text:
        return []


    sentences = re.split(
        r"[။!?]",
        text
    )


    return [

        s.strip()

        for s in sentences

        if s.strip()

    ]



def tokenize_myanmar(text):

    sentences = sentence_split(
        text
    )


    tokens = []


    for sentence in sentences:

        words = sentence.split()

        tokens.extend(words)


    return tokens



def preprocess_text(text):


    cleaned = clean_text(
        text
    )


    sentences = sentence_split(
        cleaned
    )


    tokens = tokenize_myanmar(
        cleaned
    )


    return {

        "clean_text": cleaned,

        "sentences": sentences,

        "tokens": tokens

    }

def myanmar_tokenize(text):

    text = text.lower()


    # remove punctuation
    text = re.sub(
        r'[။၊,.!?]',
        '',
        text
    )


    tokens = re.findall(
        r'[\u1000-\u109F]+|[0-9၀-၉]+',
        text
    )


    normalized=[]


    for token in tokens:

        # common Myanmar suffix removal

        for suffix in [
            "နှင့်ပတ်သက်သော",
            "အကြောင်း",
            "များ",
            "တွင်",
            "၏",
            "သည်"
        ]:

            if token.endswith(suffix):

                token = token.replace(
                    suffix,
                    ""
                )


        if token:
            normalized.append(token)


    return normalized

# =========================
# CORPUS + BM25 SEARCH
# =========================


def build_trusted_corpus():

    sources = load_trusted_sources()


    corpus=[]


    for source in sources:


        url = "https://" + source["domain"]


        text = extract_source_page(
            url
        )


        if text:


            corpus.append({

                "title":
                source["name"],


                "content":
                text,


                "source":
                source["name"],


                "url":
                url,


                "trust_score":
                source["trust_score"]

            })


    return corpus

def extract_source_page(url):

    try:

        article = Article(url)

        article.download()
        article.parse()


        return article.text


    except Exception as e:

        print("SOURCE EXTRACT ERROR:", e)

        return ""

def build_bm25():

    corpus = build_trusted_corpus()


    documents = [

        item["content"]

        for item in corpus

    ]


    tokenized = [

        myanmar_tokenize(doc)

        for doc in documents

    ]

    print("===============")
    print("CORPUS TOKENS:")
    print(tokenized)
    print("===============")

    if not tokenized:

        return None, []


    bm25 = BM25Okapi(
        tokenized
    )


    return bm25, corpus

# =========================
# SCORE NORMALIZATION
# =========================

def normalize_scores(results, key):

    if not results:
        return results


    scores = [
        item[key]
        for item in results
    ]


    min_score = min(scores)
    max_score = max(scores)


    for item in results:


        if max_score == min_score:

            item[key] = 0.5


        else:

            item[key] = round(

                (
                    item[key] - min_score
                )
                /
                (
                    max_score - min_score
                ),

                3
            )


    return results




# =========================
# BM25 LEXICAL SEARCH
# =========================

def lexical_search(
    query,
    limit=5
):


    bm25, corpus = build_bm25()



    if not bm25:

        return []



    # Myanmar tokenizer

    query_tokens = myanmar_tokenize(
        query
    )



    print("================")
    print("QUERY TOKENS:")
    print(query_tokens)
    print("================")



    scores = bm25.get_scores(
        query_tokens
    )



    ranked = sorted(

        zip(
            corpus,
            scores
        ),

        key=lambda x:x[1],

        reverse=True

    )



    results = []



    for item, score in ranked[:limit]:


        results.append({

            "title":
            item.get(
                "title",
                ""
            ),


            "source":
            item.get(
                "source",
                ""
            ),


            "url":
            item.get(
                "url",
                ""
            ),


            "content":
            item.get(
                "content",
                ""
            ),


            "score":
            float(score)

        })



    print("================")
    print("RAW BM25:")
    print(results)
    print("================")



    # normalize BM25 score 0-1

    results = normalize_scores(
        results,
        "score"
    )



    print("================")
    print("NORMALIZED BM25:")
    print(results)
    print("================")



    return results

# =========================
# SEMANTIC INDEX
# =========================


def build_faiss_index():

    corpus = load_corpus()


    documents = [

        item["content"]

        for item in corpus

    ]


    if not documents:

        return None, []


    embeddings = semantic_model.encode(
        documents,
        convert_to_numpy=True
    )

    embeddings = embeddings / np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True
    )


    dimension = embeddings.shape[1]


    index = faiss.IndexFlatIP(
        dimension
    )


    index.add(
        embeddings
    )


    return index, corpus

def semantic_search(
    query,
    limit=5
):

    index, corpus = build_faiss_index()


    if index is None:

        return []


    query_vector = semantic_model.encode(
        [query],
        convert_to_numpy=True
    )

    query_vector = query_vector / np.linalg.norm(
        query_vector,
        axis=1,
        keepdims=True
    )


    distances, ids = index.search(
        query_vector,
        limit
    )


    results = []


    for i, distance in zip(
        ids[0],
        distances[0]
    ):

        if i == -1:
            continue


        item = corpus[i]


        similarity = float(distance)


        results.append({

            "title":
            item["title"],

            "source":
            item["source"],

            "url":
            item["url"],

            "content":
            item["content"],

            "semantic_score":
            round(
                similarity,
                3
            )

        })


    return results

# =========================
# HYBRID RANKING
# =========================

def hybrid_rank(
    lexical_results,
    semantic_results
):


    merged = []


    for item in semantic_results:


        lexical_score = 0


        for lex in lexical_results:

            if lex["url"] == item["url"]:

                lexical_score = lex["score"]



        trust_score = get_source_trust(
            item["url"]
        )


        final_score = (

            (lexical_score * 0.3)

            +

            (item["semantic_score"] * 0.5)

            +

            (trust_score * 0.2)

        )


        merged.append({

            "title":
            item["title"],


            "source":
            item["source"],


            "url":
            item["url"],


            "content":
            item["content"],


            "lexical_score":
            round(lexical_score,3),


            "semantic_score":
            round(
                item["semantic_score"],
                3
            ),


            "trust_score":
            trust_score,


            "final_score":
            round(
                final_score,
                3
            )

        })


    return sorted(

        merged,

        key=lambda x:x["final_score"],

        reverse=True

    )

# =========================
# ENTITY EXTRACTION
# =========================


def extract_entities(text):

    entities = []


    # Date pattern

    dates = re.findall(
        r"\d{4}|\d{1,2}ခုနှစ်",
        text
    )


    for d in dates:

        entities.append({

            "type": "DATE",

            "value": d

        })



    # Location keyword (initial version)

    locations = [

        "မြန်မာနိုင်ငံ",
        "ရန်ကုန်",
        "မန္တလေး",
        "နေပြည်တော်"

    ]


    for loc in locations:

        if loc in text:

            entities.append({

                "type":"LOCATION",

                "value":loc

            })



    return entities

# =========================
# CLAIM EXTRACTION
# =========================


def extract_claim(text):


    sentences = sentence_split(
        text
    )


    if sentences:

        return sentences[0]


    return text

# =========================
# TEMP ANALYSIS
# =========================

def analyze(text):

    claim = extract_claim(text)

    entities = extract_entities(text)


    evidence = lexical_search(
        claim
    )


    semantic_evidence = semantic_search(
        claim
    )


    final_evidence = hybrid_rank(
        evidence,
        semantic_evidence
    )


    print("====================")
    print("BM25:")
    print(evidence)

    print("\nSEMANTIC:")
    print(semantic_evidence)

    print("\nHYBRID:")
    print(final_evidence)

    print("====================")


    # =====================
    # CONFIDENCE
    # =====================

    if final_evidence:

        confidence = int(
            final_evidence[0]["final_score"] * 100
        )

    else:

        confidence = 0



    # =====================
    # STATUS
    # =====================

    if confidence >= 75:

        status = "Likely True"

    elif confidence >= 40:

        status = "Needs Verification"

    else:

        status = "Unverified"



    return {


        "status":
        status,


        "confidence":
        confidence,


        "evidence":
        final_evidence,


        "entities":
        entities,


        "impact":
        "",


        "insight":
        "",


        "explanation":
        "Evidence ranked using BM25 lexical search and semantic similarity."

    }

# =========================
# HOME ROUTE
# =========================


@app.route(
    "/",
    methods=[
        "GET",
        "POST"
    ]
)

def home():


    result = None


    if request.method == "POST":


        user_input = request.form.get(
            "content"
        )


        extracted = None


        if is_url(user_input):

            extracted = extract_article(
                user_input
            )


            if extracted:

                analysis_text = extracted["content"]

            else:

                analysis_text = user_input


        else:

            analysis_text = user_input



        processed = preprocess_text(
            analysis_text
        )

        claim = extract_claim(
            processed["clean_text"]
        )


        entities = extract_entities(
            processed["clean_text"]
        )


        print("====================")
        print("CLAIM:")
        print(claim)

        print("\nENTITIES:")
        print(entities)

        print("====================")

        result = analyze(
            processed["clean_text"]
        )



        history = History(

            input_text=user_input,

            extracted_text=json.dumps(
                extracted,
                ensure_ascii=False
            )
            if extracted
            else None,


            result=json.dumps(
                result,
                ensure_ascii=False
            )

        )


        db.session.add(history)

        db.session.commit()

    return render_template(
        "index.html",
        result=result
    )

def load_corpus():

    try:

        with open(
            "data/news_corpus.json",
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            print("================")
            print(type(data))
            print(data[:1])
            print("================")

            return data


    except Exception as e:

        print(
            "Corpus Load Error:",
            e
        )

        return []

# =========================
# RUN
# =========================


if __name__ == "__main__":

    app.run(
        debug=True
    )