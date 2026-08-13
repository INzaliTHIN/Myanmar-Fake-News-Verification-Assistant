import os
import json
import re
import requests
from urllib.parse import urlparse
from flask import (
    Flask,
    render_template,
    request
)
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from bs4 import BeautifulSoup
from datetime import datetime
from rank_bm25 import BM25Okapi
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# =========================
# ENV
# =========================

load_dotenv()

# =========================
# FLASK CONFIG
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

# =========================
# TRUSTED SOURCE
# =========================

TRUSTED_SOURCE_FILE = (
    "data/trusted_source.json"
)

def load_trusted_sources():

    try:

        with open(
            TRUSTED_SOURCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            "Trusted source loading error:",
            e
        )

        return []

def get_source_trust(url):

    sources = load_trusted_sources()

    domain = urlparse(url).netloc

    for source in sources:

        trusted_domain = source["domain"]

        if trusted_domain in domain:


            return source["trust_score"]

    return 0.5

# =========================
# URL EXTRACTION + NLP
# =========================

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


        # remove noise

        for tag in soup.find_all(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside"
            ]
        ):
            tag.decompose()



        title=""

        if soup.title:
            title=soup.title.text.strip()



        paragraphs=soup.find_all("p")


        content=" ".join(
            p.get_text(
                " ",
                strip=True
            )
            for p in paragraphs
        )


        content=clean_text(content)



        domain = urlparse(url).netloc


        if "bbc" in domain:

            source = "BBC Myanmar"


        elif "dvb" in domain:

            source = "DVB"


        elif "mizzima" in domain:

            source = "Mizzima"


        elif "myanmar-now" in domain:

            source = "Myanmar Now"


        else:

            source = domain



        return {

            "title": title,

            "content": content,

            "source": source,

            "url": url,

            "date":
            datetime.now().strftime("%Y-%m-%d")

        }



    except Exception as e:

        print(
            "Extraction Error:",
            e
        )

        return None

def save_to_corpus(article):

    file="data/news_corpus.json"


    try:

        with open(
            file,
            "r",
            encoding="utf-8"
        ) as f:

            corpus=json.load(f)


    except:

        corpus=[]



    for item in corpus:


        if (
            item.get("url")
            ==
            article.get("url")
        ):


            print(
                "Already exists"
            )

            return False



    corpus.append(article)



    with open(
        file,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(
            corpus,
            f,
            ensure_ascii=False,
            indent=4
        )


    print(
        "New article saved"
    )


    return True

# =========================
# TEXT CLEANING
# =========================


def unicode_normalize(text):

    import unicodedata

    try:

        return unicodedata.normalize(
            "NFC",
            text
        )

    except:

        return text

def clean_text(text):

    if not text:

        return ""

    text = unicode_normalize(
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = re.sub(
        r"<.*?>",
        "",
        text
    )

    return text.strip()

# =========================
# SENTENCE SPLIT
# =========================

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

# =========================
# MYANMAR TOKENIZER
# =========================

def myanmar_tokenize(text):

    text = text.lower()

    text = re.sub(
        r"[။၊,.!?]",
        "",
        text
    )

    tokens = re.findall(

        r"[\u1000-\u109F]+|[0-9၀-၉]+",

        text

    )

    result = []

    for token in tokens:


        for suffix in [

            "နှင့်ပတ်သက်သော",
            "အကြောင်း",
            "များ",
            "တွင်",
            "၏",
            "သည်"

        ]:


            if token.endswith(
                suffix
            ):


                token = token.replace(
                    suffix,
                    ""
                )

        if token:

            result.append(
                token
            )

    return result

# =========================
# PREPROCESS
# =========================

def preprocess_text(text):


    cleaned = clean_text(
        text
    )

    return {


        "clean_text":
        cleaned,


        "sentences":
        sentence_split(
            cleaned
        ),


        "tokens":
        myanmar_tokenize(
            cleaned
        )

    }

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
# ENTITY EXTRACTION
# =========================

def extract_entities(text):

    entities = []

    # Date

    dates = re.findall(

        r"\d{4}|[၀-၉]{4}",

        text

    )

    for d in dates:

        entities.append({

            "type":
            "DATE",

            "value":
            d

        })

    # Location

    locations = [

        "မြန်မာနိုင်ငံ",

        "ရန်ကုန်",

        "မန္တလေး",

        "နေပြည်တော်"

    ]

    for loc in locations:


        if loc in text:


            entities.append({

                "type":
                "LOCATION",

                "value":
                loc

            })

    return entities

# =========================
# SEARCH ENGINE
# =========================

# =========================
# TRUSTED SOURCE
# =========================

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

        print(
            "Trusted source error:",
            e
        )

        return []


def get_source_trust(url):

    sources = load_trusted_sources()

    domain = urlparse(
        url
    ).netloc

    for item in sources:


        if item["domain"] in domain:


            return item["trust_score"]

    return 0.5


# =========================
# TRUSTED CORPUS
# =========================

def build_trusted_corpus():

    sources = load_trusted_sources()

    corpus = []

    for source in sources:

        url = (
            "https://"
            +
            source["domain"]
        )

        article = extract_article(
            url
        )

        if article and article["content"]:

            corpus.append({

                "title":
                source["name"],

                "content":
                article["content"],

                "source":
                source["name"],

                "url":
                url,

                "trust_score":
                source["trust_score"]

            })

    return corpus


# =========================
# BM25 BUILD
# =========================

def build_bm25():

    corpus = load_corpus()


    documents = [

        item["content"]

        for item in corpus

    ]


    tokenized = [

        myanmar_tokenize(doc)

        for doc in documents

    ]


    print("================")
    print("BM25 CORPUS SIZE:")
    print(len(corpus))
    print("================")


    if not tokenized:

        return None, []


    bm25 = BM25Okapi(
        tokenized
    )


    return bm25, corpus

# =========================
# SCORE NORMALIZATION
# =========================

def normalize_scores(results,key):

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
                    item[key]
                    -
                    min_score

                )
                /
                (
                    max_score
                    -
                    min_score
                ),

                3

            )

    return results

# =========================
# BM25 SEARCH
# =========================

def lexical_search(
        query,
        limit=5
):

    bm25, corpus = build_bm25()

    if not bm25:


        return []

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

    results=[]

    for item,score in ranked[:limit]:


        results.append({


            "title":
            item["title"],


            "source":
            item["source"],


            "url":
            item["url"],


            "content":
            item["content"][:500],


            "score":
            float(score)

        })

    results = normalize_scores(
        results,
        "score"
    )

    print("================")
    print("BM25:")
    print(results)
    print("================")

    return results

# =========================
# SEMANTIC SEARCH
# =========================

def build_faiss_index():

    corpus = load_corpus()

    documents=[


        item["content"]

        for item in corpus

    ]

    if not documents:


        return None, []

    embeddings = semantic_model.encode(

        documents,

        convert_to_numpy=True

    )

    embeddings = (

        embeddings
        /
        np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True
        )

    )

    index = faiss.IndexFlatIP(

        embeddings.shape[1]

    )

    index.add(
        embeddings
    )

    return index, corpus

def semantic_search(
        query,
        limit=3
):


    index, corpus = build_faiss_index()



    if index is None:

        return []



    query_vector = semantic_model.encode(

        [query],

        convert_to_numpy=True

    )


    query_vector = (

        query_vector
        /
        np.linalg.norm(
            query_vector,
            axis=1,
            keepdims=True
        )

    )



    scores, ids = index.search(

        query_vector,

        limit

    )



    results = []



    for idx, score in zip(

        ids[0],

        scores[0]

    ):


        if idx == -1:

            continue



        similarity = float(score)



        # remove unrelated evidence

        if similarity < 0.35:

            continue



        item = corpus[idx]



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
            )[:500],


            "date":
            item.get(
                "date",
                ""
            ),


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

    merged=[]

    for item in semantic_results:

        lexical_score = 0

        for lex in lexical_results:


            if lex["url"] == item["url"]:


                lexical_score = lex["score"]

        trust_score = get_source_trust(
            item["url"]
        )

        final_score = (

            lexical_score * 0.3

            +

            item["semantic_score"] * 0.5

            +

            trust_score * 0.2

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
            round(
                lexical_score,
                3
            ),


            "semantic_score":
            item["semantic_score"],


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
# ANALYSIS + FLASK ROUTE
# =========================

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
# ENTITY EXTRACTION
# =========================

def extract_entities(text):

    entities=[]

    # Date

    dates = re.findall(

        r"\d{4}|[၀-၉]+ခုနှစ်",

        text

    )


    for d in dates:

        entities.append({

            "type":"DATE",

            "value":d

        })

    locations=[

        "မြန်မာနိုင်ငံ",

        "ရန်ကုန်",

        "မန္တလေး",

        "နေပြည်တော်",

        "ရှမ်း",

        "ကချင်"

    ]

    for loc in locations:

        if loc in text:

            entities.append({

                "type":"LOCATION",

                "value":loc

            })

    return entities

# =========================
# LOAD NEWS CORPUS
# =========================

def load_corpus():

    try:

        with open(
            "data/news_corpus.json",
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        clean_corpus = []


        for item in data:


            if (
                item.get("title")
                and
                item.get("content")
                and
                item.get("url")
            ):


                clean_corpus.append({

                    "title":
                    item.get(
                        "title",
                        ""
                    ),


                    "content":
                    item.get(
                        "content",
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


                    "date":
                    item.get(
                        "date",
                        ""
                    )

                })



        print("================")
        print(
            "Corpus size:",
            len(clean_corpus)
        )
        print("================")


        return clean_corpus



    except Exception as e:


        print(
            "Corpus Error:",
            e
        )


        return []


# =========================
# FINAL ANALYSIS
# =========================

def analyze(text):


    claim = extract_claim(
        text
    )


    entities = extract_entities(
        text
    )

    print("====================")
    print("CLAIM:")
    print(claim)

    print()

    print("ENTITIES:")
    print(entities)

    print("====================")

    # lexical

    lexical = lexical_search(
        claim
    )

    # semantic

    semantic = semantic_search(
        claim
    )

    # combine

    evidence = hybrid_rank(

        lexical,

        semantic

    )

    print("====================")

    print("FINAL EVIDENCE")

    print(evidence)

    print("====================")

    # confidence

    if evidence:

        confidence = int(

            evidence[0]["final_score"]

            *

            100

        )

    else:

        confidence = 0

    if confidence >= 75:

        status="Likely True"

    elif confidence >=40:

        status="Needs Verification"

    else:

        status="Unverified"

    return {

        "status":

        status,

        "confidence":

        confidence,

        "evidence":

        evidence,

        "entities":

        entities,

        "explanation":

        "Hybrid ranking based on BM25, semantic similarity and trusted source score."

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

    result=None

    if request.method=="POST":

        user_input = request.form.get(

            "content"

        )

        extracted=None

        # URL input

        if is_url(user_input):

            extracted = extract_article(

                user_input

            )

            if extracted:

                save_to_corpus(
                    extracted
                )

                analysis_text = extracted["content"]

            else:

                analysis_text=user_input

        else:

            analysis_text=user_input

        processed = preprocess_text(

            analysis_text

        )

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

        db.session.add(

            history

        )

        db.session.commit()

    return render_template(
        "index.html",

        result=result

    )

# =========================
# RUN APP
# =========================


if __name__=="__main__":


    app.run(

        debug=True

    )