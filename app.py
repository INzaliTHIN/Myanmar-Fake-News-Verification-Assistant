import os
import json
import re
import requests
import numpy as np
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from flask import (
    Flask,
    render_template,
    request
)
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from newspaper import Article
from rank_bm25 import BM25Okapi
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

# =========================
# DATABASE CONFIG
# =========================

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///database.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# DATABASE MODEL
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


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# create database

with app.app_context():

    db.create_all()

# =========================
# AI MODEL
# =========================

semantic_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# =========================
# FILE PATH
# =========================

CORPUS_FILE = (
    "data/news_corpus.json"
)

TRUSTED_SOURCE_FILE = (
    "data/trusted_source.json"
)

# =========================
# LOAD TRUSTED SOURCES
# =========================

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
            "Trusted Source Error:",
            e
        )

        return []
    
# =========================
# SOURCE TRUST CHECK
# =========================

def get_source_trust(url):

    with open(
        "data/trusted_source.json",
        "r",
        encoding="utf-8"
    ) as f:

        sources = json.load(f)



    domain = urlparse(url).netloc.lower()



    for item in sources:


        source_domain = item.get(
            "domain",
            ""
        ).lower()



        if source_domain in domain:


            return item.get(
                "trust_score",
                0
            )



    return 0

# =========================
# SOURCE VERIFICATION
# =========================

def check_source_trust(url):

    trusted_sources = load_trusted_sources()


    domain = urlparse(url).netloc.lower()


    for source in trusted_sources:


        for d in source.get(
            "domains",
            []
        ):


            if d in domain:


                return {

                    "name":
                    source["name"],


                    "type":
                    source["type"],


                    "trust_score":
                    source["trust_score"],


                    "trusted":
                    True

                }



    return {

        "name":
        "Unknown Source",


        "type":
        "unknown",


        "trust_score":
        0.3,


        "trusted":
        False

    }

# =========================
# LOAD CORPUS
# =========================

def load_corpus():

    try:

        if not os.path.exists(
            CORPUS_FILE
        ):


            return []

        with open(
            CORPUS_FILE,
            "r",
            encoding="utf-8"
        ) as f:


            return json.load(f)

    except Exception as e:


        print(
            "Corpus Load Error:",
            e
        )

        return []


# =========================
# SAVE CORPUS
# =========================

def save_corpus(data):


    os.makedirs(
        "data",
        exist_ok=True
    )


    with open(
        CORPUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

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

def is_blocked_source(url):

    blocked = [
        "facebook.com",
        "tiktok.com",
        "youtube.com"
    ]

    domain = urlparse(url).netloc.lower()


    for item in blocked:

        if item in domain:

            return True


    return False

def detect_url_type(url):

    domain = urlparse(url).netloc.lower()


    if "facebook.com" in domain:
        return "facebook"


    elif "x.com" in domain or "twitter.com" in domain:
        return "x"


    elif "t.me" in domain or "telegram" in domain:
        return "telegram"


    else:
        return "news"

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

        # remove unwanted html

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

        paragraphs = soup.find_all(
            "p"
        )

        content = " ".join(

            p.get_text(
                " ",
                strip=True
            )

            for p in paragraphs

        )

        # fallback newspaper

        if len(content) < 100:

            article = Article(url)

            article.download()

            article.parse()

            title = article.title

            content = article.text

        return {

            "title":
            title,

            "content":
            content,

            "source":
            urlparse(url).netloc,

            "url":
            url,

            "domain":
            urlparse(url).netloc,

            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),

            "saved_time":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        }

    except Exception as e:

        print(
            "Article Extraction Error:",
            e
        )

        return None

def extract_social_url(url):

    data = {

        "title":"",
        "content":"",
        "source":urlparse(url).netloc,
        "url":url,
        "date":datetime.now().strftime("%Y-%m-%d")

    }


    try:

        response=requests.get(
            url,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            },
            timeout=10
        )


        soup=BeautifulSoup(
            response.text,
            "html.parser"
        )


        text=soup.get_text(
            " ",
            strip=True
        )


        data["content"]=clean_text(text)


        if len(data["content"]) < 50:

            data["content"] = (
                "Social media post. "
                "Content extraction limited."
            )


        return data


    except Exception as e:

        print(
            "Social Extraction Error:",
            e
        )

        return None

# =========================
# DUPLICATE CHECK
# =========================

def check_duplicate(article):

    corpus = load_corpus()


    new_url = article.get(
        "url",
        ""
    )


    new_title = article.get(
        "title",
        ""
    ).strip().lower()


    new_content = article.get(
        "content",
        ""
    ).strip().lower()



    for item in corpus:


        old_url = item.get(
            "url",
            ""
        )


        old_title = item.get(
            "title",
            ""
        ).strip().lower()


        old_content = item.get(
            "content",
            ""
        ).strip().lower()



        # 1. URL duplicate

        if new_url and old_url == new_url:

            return True



        # 2. Title duplicate

        if (
            new_title
            and old_title
            and new_title == old_title
        ):

            return True



        # 3. Content duplicate
        # first 100 characters compare

        if (
            len(new_content) > 100
            and len(old_content) > 100
            and new_content[:100] == old_content[:100]
        ):

            return True



    return False

# =========================
# SAVE NEW ARTICLE
# =========================

def save_article(article):

    corpus = load_corpus()


    # =====================
    # DUPLICATE CHECK
    # =====================

    if check_duplicate(
        article
    ):

        print(
            "Already exists"
        )

        return False



    # =====================
    # CLEAN ARTICLE DATA
    # =====================

    new_article = {

        "title":
        article.get(
            "title",
            ""
        ),


        "content":
        article.get(
            "content",
            ""
        ),


        "source":
        article.get(
            "source",
            ""
        ),


        "url":
        article.get(
            "url",
            ""
        ),


        "date":
        article.get(
            "date",
            datetime.now().strftime("%Y-%m-%d")
        ),


        "type":
        article.get(
            "type",
            "news"
        )

    }



    # =====================
    # SAVE
    # =====================

    corpus.append(
        new_article
    )


    save_corpus(
        corpus
    )


    print(
        "New article saved"
    )


    return True
# =========================
# GET ARTICLE FROM URL
# =========================

def process_url(url):


    article = extract_article(
        url
    )

    if not article:

        return None

    save_article(
        article
    )

    return article

# =========================
# NLP PROCESSING
# =========================

def unicode_normalize(text):

    import unicodedata


    try:

        return unicodedata.normalize(
            "NFC",
            text
        )

    except Exception as e:


        print(
            "Unicode Error:",
            e
        )

        return text


def clean_text(text):


    if not text:

        return ""

    text = unicode_normalize(
        text
    )

    # remove html

    text = re.sub(
        r"<.*?>",
        "",
        text
    )

    # remove extra spaces

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()

# =========================
# MYANMAR TOKENIZER
# =========================

def myanmar_tokenize(text):

    text = clean_text(
        text
    )

    text = text.lower()

    # remove punctuation

    text = re.sub(
        r"[။၊,.!?]",
        "",
        text
    )

    tokens = re.findall(

        r"[\u1000-\u109F]+|[0-9၀-၉]+",

        text
    )

    clean_tokens = []

    stop_words = [

        "သည်",

        "များ",

        "မှာ",

        "ကို",

        "နှင့်",

        "၏",

        "ဟု",

        "လို့"

    ]

    for token in tokens:

        if token in stop_words:

            continue

        if len(token) > 1:

            clean_tokens.append(
                token
            )

    return clean_tokens

# =========================
# BM25 SEARCH
# =========================

def build_bm25():

    corpus = load_corpus()

    if not corpus:

        return None, []

    documents = [

        item["content"]

        for item in corpus

    ]

    tokenized = [

        myanmar_tokenize(
            doc
        )

        for doc in documents
    ]

    bm25 = BM25Okapi(
        tokenized
    )

    print(
        "BM25 Corpus Size:",
        len(corpus)
    )

    return bm25, corpus

def normalize_score(score):

    if score < 0:

        return 0

    if score > 1:

        return 1

    return round(
        score,
        3
    )

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

    max_score = max(
        scores
    )

    for item,score in ranked[:limit]:

        if max_score > 0:

            final_score = (
                score / max_score
            )

        else:

            final_score = 0

        results.append({

            "title":
            item["title"],

            "content":
            item["content"],

            "source":
            item["source"],

            "url":
            item["url"],

            "lexical_score":
            normalize_score(
                final_score
            )

        })

    return results

# =========================
# FAISS SEMANTIC SEARCH
# =========================

def build_faiss_index():

    corpus = load_corpus()

    if not corpus:

        return None, []

    texts = [

        item["content"]

        for item in corpus

    ]

    embeddings = semantic_model.encode(

        texts,

        convert_to_numpy=True

    )

    embeddings = (

        embeddings /

        np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True
        )

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

    query_vector = (

        query_vector /

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

    results=[]

    for idx,score in zip(

        ids[0],

        scores[0]

    ):

        if idx == -1:

            continue

        item = corpus[idx]

        results.append({

            "title":
            item["title"],

            "content":
            item["content"],

            "source":
            item["source"],

            "url":
            item["url"],

            "semantic_score":
            round(
                float(score),
                3
            )

        })

    return results

# =========================
# TRUSTED SOURCE SEARCH
# =========================

def search_trusted_news(
        claim,
        limit=5
):

    corpus = load_corpus()

    results = []


    for item in corpus:


        source_info = check_source_trust(
            item.get("url","")
        )


        # trusted source only

        if not source_info["trusted"]:

            continue


        content = item.get(
            "content",
            ""
        )


        similarity = semantic_similarity(
            claim,
            content
        )


        keyword_score = keyword_overlap(
            claim,
            content
        )


        entity_score = entity_overlap(
            extract_entities(claim),
            content
        )


        results.append({

            "title":
            item.get(
                "title",
                ""
            ),


            "content":
            content,


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
            ),


            "source_name":
            source_info["name"],


            "trust_score":
            source_info["trust_score"],


            "similarity":
            similarity,


            "keyword_score":
            keyword_score,


            "entity_score":
            entity_score

        })


    results.sort(

        key=lambda x:
        x["similarity"],

        reverse=True

    )


    return results[:limit]

# =========================
# SEMANTIC SIMILARITY
# =========================

def semantic_similarity(
        text1,
        text2
):


    embeddings = semantic_model.encode(
        [
            text1,
            text2
        ],
        convert_to_numpy=True
    )


    a = embeddings[0]
    b = embeddings[1]


    score = np.dot(
        a,
        b
    ) / (
        np.linalg.norm(a)
        *
        np.linalg.norm(b)
    )


    return round(
        float(score),
        3
    )

# =========================
# KEYWORD OVERLAP
# =========================

def keyword_overlap(
        text1,
        text2
):


    words1 = set(
        myanmar_tokenize(
            text1
        )
    )


    words2 = set(
        myanmar_tokenize(
            text2
        )
    )


    if not words1:

        return 0



    common = words1.intersection(
        words2
    )


    score = len(common) / len(words1)


    return round(
        score,
        3
    )

# =========================
# FINAL VERIFICATION
# =========================

def verify_with_trusted_sources(
        claim
):


    evidence = search_trusted_news(
        claim
    )


    if not evidence:

        return {

            "status":
            "Unverified",

            "confidence":
            0,

            "evidence":[]

        }



    best = evidence[0]


    similarity = best["similarity"]

    trust = best["trust_score"]

    keyword = best.get(
        "keyword_score",
        0
    )

    entity = best.get(
        "entity_score",
        0
    )

    final_score = (

        similarity * 0.5 + keyword * 0.2 + entity * 0.1 + trust * 0.2
    )



    if final_score >=0.75:

        status="Correct News"


    elif final_score >=0.5:

        status="Needs Verification"


    else:

        status="Likely False"



    return {


        "status":
        status,


        "confidence":
        int(
            final_score*100
        ),


        "evidence":
        evidence

    }

# =========================
# HYBRID RANKING
# =========================

def hybrid_rank(
    lexical_results,
    semantic_results
):

    final=[]


    for item in semantic_results:


        lexical_score = 0


        for lex in lexical_results:


            if lex["url"] == item["url"]:

                lexical_score = lex[
                    "lexical_score"
                ]



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



        # =========================
        # FILTER IRRELEVANT NEWS
        # =========================

        if final_score < 0.4:

            continue



        final.append({


            **item,


            "lexical_score":

            round(
                lexical_score,
                3
            ),



            "trust_score":

            round(
                trust_score,
                3
            ),



            "final_score":

            round(
                final_score,
                3
            )

        })



    return sorted(

        final,

        key=lambda x:x["final_score"],

        reverse=True

    )

# =========================
# CLAIM EXTRACTION
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

    locations=[

        "ရန်ကုန်",

        "မန္တလေး",

        "နေပြည်တော်",

        "မြန်မာနိုင်ငံ"

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
# ENTITY MATCH CHECK
# =========================

def entity_overlap(
        claim_entities,
        evidence_text
):

    if not claim_entities:

        return 0.5


    matched = 0


    for entity in claim_entities:


        value = entity["value"]


        if value in evidence_text:

            matched += 1



    score = matched / len(
        claim_entities
    )


    return round(
        score,
        3
    )

# =========================
# VERIFICATION ENGINE
# =========================

def verify_article(text):


    claim = extract_claim(
        text
    )


    # =====================
    # TRUSTED SOURCE CHECK
    # =====================

    trusted_result = verify_with_trusted_sources(
        claim
    )


    evidence = trusted_result.get(
        "evidence",
        []
    )


    confidence = trusted_result.get(
        "confidence",
        0
    )


    status = trusted_result.get(
        "status",
        "Unverified"
    )


    # =====================
    # ENTITY EXTRACTION
    # =====================

    entities = extract_entities(
        claim
    )


    # =====================
    # RETURN RESULT
    # =====================

    return {


        "status":

        status,


        "confidence":

        confidence,


        "claim":

        claim,


        "evidence":

        evidence,


        "entities":

        entities,


        "explanation":

        (
            "Verification based on "
            "trusted media sources, "
            "semantic similarity, "
            "source reliability "
            "and content matching."
        )

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

    if request.method == "POST":

        user_input = request.form.get(

            "content"

        )

        analysis_text = user_input

        extracted=None

        # URL input

        if is_url(user_input):


            url_type = detect_url_type(
                user_input
            )


            if url_type in [
                "facebook",
                "x",
                "telegram"
            ]:

                extracted = extract_social_url(
                    user_input
                )


            else:

                extracted = extract_article(
                    user_input
                )



            if extracted:

                analysis_text = (

                    extracted.get(

                        "title",
                        ""
                    )
                    +
                    " "
                    +

                    extracted.get(
                        "content",
                        ""
                    )


                                 )
            else:
                analysis_text = user_input


        result = verify_article(

            analysis_text

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
# RUN
# =========================

if __name__ == "__main__":

    app.run(

        debug=True

    )