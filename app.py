import os
import re
import json
import logging
from datetime import datetime
from urllib.parse import (
    quote_plus,
    urlparse,
    parse_qs,
    unquote
)

import requests
import numpy as np

from bs4 import BeautifulSoup

from flask import (
    Flask,
    request,
    jsonify,
    render_template_string
)

from flask_sqlalchemy import SQLAlchemy

import torch

from sentence_transformers import SentenceTransformer

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)

try:
    from newspaper import Article
except Exception:
    Article = None


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///database.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# DATABASE MODEL
# ============================================================

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
        db.Text,
        nullable=True
    )

    result = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

with app.app_context():

    db.create_all()


# ============================================================
# MODEL CONFIGURATION
# ============================================================

SEMANTIC_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

NLI_MODEL_NAME = (
    "MoritzLaurer/"
    "mDeBERTa-v3-base-mnli-xnli"
)


# ============================================================
# LIMITS
# ============================================================

MAX_SEARCH_RESULTS = 20

MAX_EVIDENCE = 8

MAX_ARTICLE_CHARS = 12000

MAX_SENTENCE_CHARS = 700


# ============================================================
# SEARCH HEADERS
# ============================================================

SEARCH_HEADERS = {

    "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "en-US,en;q=0.9,my;q=0.8"

}


# ============================================================
# MODELS
# ============================================================

print()
print("=" * 70)
print("Loading Semantic Model...")
print("=" * 70)

semantic_model = SentenceTransformer(
    SEMANTIC_MODEL_NAME
)


print()
print("=" * 70)
print("Loading NLI Model...")
print("=" * 70)

nli_tokenizer = AutoTokenizer.from_pretrained(
    NLI_MODEL_NAME
)

nli_model = AutoModelForSequenceClassification.from_pretrained(
    NLI_MODEL_NAME
)

nli_model.eval()


# ============================================================
# BASIC TEXT CLEANING
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# SENTENCE SPLITTER
# ============================================================

def sentence_split(text):

    text = clean_text(text)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?။！？])\s+",
        text
    )

    return [
        clean_text(x)
        for x in parts
        if clean_text(x)
    ]


# ============================================================
# URL CHECK
# ============================================================

def is_url(value):

    if not value:
        return False

    value = value.strip()

    return bool(
        re.match(
            r"^https?://",
            value,
            re.IGNORECASE
        )
    )


# ============================================================
# DOMAIN
# ============================================================

def get_domain(url):

    if not url:
        return ""

    try:

        parsed = urlparse(
            url
        )

        domain = parsed.netloc.lower()

        if "@" in domain:
            domain = domain.split("@")[-1]

        if ":" in domain:
            domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


# ============================================================
# SOCIAL DOMAINS
# ============================================================

SOCIAL_DOMAINS = {

    "facebook.com",
    "www.facebook.com",

    "fb.com",
    "www.fb.com",

    "m.facebook.com",

    "m.me",

    "instagram.com",
    "www.instagram.com",

    "x.com",
    "www.x.com",

    "twitter.com",
    "www.twitter.com"

}


# ============================================================
# SOCIAL DOMAIN CHECK
# ============================================================

def is_social_domain(url):

    domain = get_domain(
        url
    )

    domain = domain.lower()

    if domain in SOCIAL_DOMAINS:
        return True

    if domain.endswith(
        ".facebook.com"
    ):
        return True

    if domain.endswith(
        ".instagram.com"
    ):
        return True

    if domain.endswith(
        ".twitter.com"
    ):
        return True

    if domain.endswith(
        ".x.com"
    ):
        return True

    return False


# ============================================================
# SOCIAL URL CHECK
# ============================================================

def is_social_url(url):

    return is_social_domain(
        url
    )


# ============================================================
# VALID SOCIAL INPUT URL
# ============================================================

def valid_social_input_url(url):

    if not is_url(url):
        return False

    return is_social_url(
        url
    )


# ============================================================
# BLOCKED SOCIAL RESULT URL
# ============================================================

def is_blocked_social_result(url):

    if not url:
        return True

    domain = get_domain(
        url
    ).lower()

    blocked = {

        "facebook.com",
        "www.facebook.com",

        "m.facebook.com",

        "fb.com",
        "www.fb.com",

        "m.me",

        "instagram.com",
        "www.instagram.com",

        "x.com",
        "www.x.com",

        "twitter.com",
        "www.twitter.com"

    }

    if domain in blocked:
        return True

    if domain.endswith(
        ".facebook.com"
    ):
        return True

    if domain.endswith(
        ".instagram.com"
    ):
        return True

    if domain.endswith(
        ".twitter.com"
    ):
        return True

    if domain.endswith(
        ".x.com"
    ):
        return True

    return False


# ============================================================
# BLOCKED DOMAINS
# ============================================================

BLOCKED_DOMAINS = {

    "m.me",
    "facebook.com",
    "www.facebook.com",
    "fb.com",
    "www.fb.com",

    "instagram.com",
    "www.instagram.com",

    "twitter.com",
    "www.twitter.com",

    "x.com",
    "www.x.com"

}


# ============================================================
# BLOCKED DOMAIN CHECK
# ============================================================

def is_blocked_domain(url):

    domain = get_domain(
        url
    ).lower()

    if domain in BLOCKED_DOMAINS:
        return True

    if domain.endswith(
        ".facebook.com"
    ):
        return True

    if domain.endswith(
        ".instagram.com"
    ):
        return True

    if domain.endswith(
        ".twitter.com"
    ):
        return True

    if domain.endswith(
        ".x.com"
    ):
        return True

    return False


# ============================================================
# VALID RESULT URL
# ============================================================

def valid_result_url(url):

    if not url:
        return False

    if not is_url(url):
        return False

    domain = get_domain(
        url
    )

    if not domain:
        return False

    if is_blocked_domain(
        url
    ):
        return False

    return True


# ============================================================
# RESOLVE SEARCH URL
# ============================================================

def resolve_search_url(url):

    if not url:
        return ""

    url = unquote(
        url
    ).strip()

    try:

        parsed = urlparse(
            url
        )

        query = parse_qs(
            parsed.query
        )

        for key in [
            "uddg",
            "url",
            "u"
        ]:

            if key in query:

                candidate = query[key][0]

                candidate = unquote(
                    candidate
                )

                if candidate.startswith(
                    "http"
                ):

                    return candidate

    except Exception:
        pass

    return url


# ============================================================
# TRUSTED DOMAINS
# ============================================================

HIGH_TRUST_DOMAINS = {

    "who.int",
    "www.who.int",

    "un.org",
    "www.un.org",

    "unesco.org",
    "www.unesco.org",

    "worldbank.org",
    "www.worldbank.org",

    "imf.org",
    "www.imf.org",

    "reuters.com",
    "www.reuters.com",

    "apnews.com",
    "www.apnews.com",

    "bbc.com",
    "www.bbc.com",

    "nature.com",
    "www.nature.com",

    "science.org",
    "www.science.org",

    "nih.gov",
    "www.nih.gov",

    "cdc.gov",
    "www.cdc.gov",

    "gov.uk",
    "www.gov.uk",

    "gov.mm",
    "www.gov.mm"

}


TRUSTED_DOMAIN_KEYWORDS = {

    "edu",
    "ac",
    "gov",

    "who.int",
    "un.org",
    "reuters.com",
    "apnews.com",
    "bbc.com",

    "nature.com",
    "science.org",

    "nih.gov",
    "cdc.gov"

}


# ============================================================
# HIGH TRUST
# ============================================================

def is_high_trust_domain(url):

    domain = get_domain(
        url
    ).lower()

    if domain in HIGH_TRUST_DOMAINS:
        return True

    return False


# ============================================================
# TRUSTED DOMAIN
# ============================================================

def is_trusted_domain(url):

    domain = get_domain(
        url
    ).lower()

    if is_high_trust_domain(
        url
    ):
        return True

    for keyword in TRUSTED_DOMAIN_KEYWORDS:

        if (
            domain.endswith(
                "." + keyword
            )
            or
            domain == keyword
            or
            keyword in domain
        ):

            return True

    return False


# ============================================================
# CLAIM KEYWORDS
# ============================================================

def claim_keywords(text):

    text = clean_text(
        text
    ).lower()

    if not text:
        return []

    words = re.findall(

        r"[\u1000-\u109f]+|"
        r"[a-zA-Z]{2,}|"
        r"\d+",

        text

    )

    stop_words = {

        "the",
        "this",
        "that",
        "with",
        "from",
        "have",
        "has",
        "been",
        "were",
        "was",
        "are",
        "and",
        "for",
        "into",
        "about",
        "which",
        "will",
        "would",
        "could",
        "should",

        "is",
        "in",
        "of",
        "to",
        "a",
        "an",
        "on",
        "at",
        "by"

    }

    return [

        word

        for word in words

        if word not in stop_words

    ]


# ============================================================
# BUILD SEARCH QUERIES
# ============================================================

def build_search_queries(claim):

    claim = clean_text(
        claim
    )

    if not claim:
        return []

    queries = [

        claim,

        claim + " သတင်း",

        claim + " မြန်မာ",

        claim + " 2026"

    ]

    keywords = claim_keywords(
        claim
    )

    if keywords:

        short_query = " ".join(
            keywords[:12]
        )

        queries.append(
            short_query
        )

        queries.append(
            short_query + " သတင်း"
        )

    unique = []

    seen = set()

    for query in queries:

        query = clean_text(
            query
        )

        key = query.lower()

        if not query:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            query
        )

    return unique[:6]


# ============================================================
# DUCKDUCKGO SEARCH
# ============================================================

def search_duckduckgo(query):

    results = []

    try:

        url = (
            "https://html.duckduckgo.com/html/?q="
            + quote_plus(query)
        )

        response = requests.get(

            url,

            headers=SEARCH_HEADERS,

            timeout=20

        )

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(

            response.text,

            "html.parser"

        )

        for result in soup.select(
            ".result"
        )[:15]:

            link_node = result.select_one(
                ".result__a"
            )

            if not link_node:
                continue

            href = link_node.get(
                "href",
                ""
            )

            if href.startswith(
                "//duckduckgo.com/l/"
            ):

                try:

                    parsed = urlparse(
                        "https:" + href
                    )

                    query_data = parse_qs(
                        parsed.query
                    )

                    href = query_data.get(
                        "uddg",
                        [""]
                    )[0]

                except Exception:

                    href = ""

            href = unquote(
                href
            )

            href = resolve_search_url(
                href
            )

            if not valid_result_url(
                href
            ):

                continue

            title_node = result.select_one(
                ".result__title"
            )

            snippet_node = result.select_one(
                ".result__snippet"
            )

            title = clean_text(

                title_node.get_text(
                    " ",
                    strip=True
                )

                if title_node

                else link_node.get_text(
                    " ",
                    strip=True
                )

            )

            snippet = clean_text(

                snippet_node.get_text(
                    " ",
                    strip=True
                )

                if snippet_node

                else ""

            )

            if not title:
                continue

            results.append({

                "title":
                    title,

                "url":
                    href,

                "snippet":
                    snippet,

                "engine":
                    "DuckDuckGo"

            })

    except Exception as e:

        print(
            "DuckDuckGo search error:",
            e
        )

    return results


# ============================================================
# BING SEARCH
# ============================================================

def search_bing(query):

    results = []

    try:

        url = (
            "https://www.bing.com/search?q="
            + quote_plus(query)
            + "&count=20"
            + "&setlang=my"
        )

        response = requests.get(

            url,

            headers=SEARCH_HEADERS,

            timeout=20

        )

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(

            response.text,

            "html.parser"

        )

        for item in soup.select(
            "li.b_algo"
        )[:20]:

            link = item.select_one(
                "h2 a"
            )

            if not link:
                continue

            href = link.get(
                "href",
                ""
            )

            href = resolve_search_url(
                href
            )

            if not valid_result_url(
                href
            ):

                continue

            title = clean_text(

                link.get_text(
                    " ",
                    strip=True
                )

            )

            snippet_node = item.select_one(
                ".b_caption p"
            )

            snippet = clean_text(

                snippet_node.get_text(
                    " ",
                    strip=True
                )

                if snippet_node

                else ""

            )

            if not title:
                continue

            results.append({

                "title":
                    title,

                "url":
                    href,

                "snippet":
                    snippet,

                "engine":
                    "Bing"

            })

    except Exception as e:

        print(
            "Bing search error:",
            e
        )

    return results


# ============================================================
# NORMALIZE URL
# ============================================================

def normalize_url_for_compare(url):

    if not url:
        return ""

    try:

        parsed = urlparse(
            url
        )

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        path = parsed.path.rstrip("/")

        return (
            parsed.scheme.lower()
            + "://"
            + domain
            + path
        )

    except Exception:

        return url.lower().rstrip("/")


# ============================================================
# SEARCH RESULT QUALITY
# ============================================================

def search_result_quality(item):

    url = item.get(
        "url",
        ""
    )

    title = clean_text(
        item.get(
            "title",
            ""
        )
    )

    snippet = clean_text(
        item.get(
            "snippet",
            ""
        )
    )

    if is_blocked_social_result(
        url
    ):
        return 0.0

    score = 0.0

    if is_high_trust_domain(
        url
    ):

        score += 0.50

    elif is_trusted_domain(
        url
    ):

        score += 0.35

    domain = get_domain(
        url
    )

    if domain.endswith(
        ".gov.mm"
    ):

        score += 0.25

    elif domain.endswith(
        ".mm"
    ):

        score += 0.10

    if len(title) >= 10:
        score += 0.05

    if len(snippet) >= 50:
        score += 0.05

    return min(
        score,
        1.0
    )


# ============================================================
# PUBLIC WEB SEARCH
# ============================================================

def search_public_web(claim):

    all_results = []

    queries = build_search_queries(
        claim
    )

    print(
        "Search queries:",
        len(queries)
    )

    for query in queries:

        print(
            "Searching:",
            query
        )

        ddg_results = search_duckduckgo(
            query
        )

        all_results.extend(
            ddg_results
        )

        bing_results = search_bing(
            query
        )

        all_results.extend(
            bing_results
        )

    unique = {}

    for item in all_results:

        url = item.get(
            "url",
            ""
        )

        url = resolve_search_url(
            url
        )

        if not valid_result_url(
            url
        ):
            continue

        # ----------------------------------------------------
        # IMPORTANT:
        # Never allow Facebook / m.me / Instagram / X
        # search results into evidence.
        # ----------------------------------------------------

        if is_blocked_social_result(
            url
        ):
            continue

        item["url"] = url

        key = normalize_url_for_compare(
            url
        )

        if not key:
            continue

        item["search_quality"] = round(

            search_result_quality(
                item
            ),

            4

        )

        if item["search_quality"] <= 0:
            continue

        old = unique.get(
            key
        )

        if old is None:

            unique[key] = item

        else:

            if (
                item["search_quality"]
                >
                old.get(
                    "search_quality",
                    0
                )
            ):

                unique[key] = item

    results = list(
        unique.values()
    )

    results.sort(

        key=lambda x: (

            x.get(
                "search_quality",
                0
            ),

            len(
                x.get(
                    "snippet",
                    ""
                )
            )

        ),

        reverse=True

    )

    print(
        "Valid web results:",
        len(results)
    )

    return results[:MAX_SEARCH_RESULTS]


# ============================================================
# ARTICLE DATE EXTRACTION
# ============================================================

def extract_article_date(soup):

    date_value = ""

    for attr_name in [

        "article:published_time",
        "article:modified_time"

    ]:

        meta = soup.find(

            "meta",

            attrs={
                "property":
                    attr_name
            }

        )

        if meta:

            value = clean_text(
                meta.get(
                    "content",
                    ""
                )
            )

            if value:

                date_value = value

                break

    if not date_value:

        for attr_name in [

            "datePublished",
            "date",
            "pubdate"

        ]:

            meta = soup.find(

                "meta",

                attrs={
                    "name":
                        attr_name
                }

            )

            if meta:

                value = clean_text(
                    meta.get(
                        "content",
                        ""
                    )
                )

                if value:

                    date_value = value

                    break

    if not date_value:

        time_tag = soup.find(
            "time"
        )

        if time_tag:

            date_value = clean_text(

                time_tag.get(
                    "datetime",
                    ""
                )

                or

                time_tag.get_text(
                    " ",
                    strip=True
                )

            )

    return date_value


# ============================================================
# DATE PARSER
# ============================================================

def parse_date_value(value):

    if not value:
        return None

    value = clean_text(
        value
    )

    try:

        return datetime.fromisoformat(

            value.replace(
                "Z",
                "+00:00"
            )

        )

    except Exception:
        pass

    match = re.search(

        r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",

        value

    )

    if match:

        try:

            return datetime(

                int(match.group(1)),

                int(match.group(2)),

                int(match.group(3))

            )

        except Exception:
            pass

    for fmt in [

        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y"

    ]:

        try:

            return datetime.strptime(
                value,
                fmt
            )

        except Exception:
            pass

    return None


# ============================================================
# SOCIAL TEXT EXTRACTION
# ============================================================

def extract_social_text(url):

    if not valid_social_input_url(
        url
    ):

        return None

    try:

        response = requests.get(

            url,

            headers=SEARCH_HEADERS,

            timeout=15,

            allow_redirects=True

        )

        if response.status_code != 200:

            print(
                "Social page status:",
                response.status_code
            )

            return None

        final_url = response.url

        # ----------------------------------------------------
        # IMPORTANT
        # Final URL must still be social.
        # ----------------------------------------------------

        if not is_social_url(
            final_url
        ):

            return None

        soup = BeautifulSoup(

            response.text,

            "html.parser"

        )

        for tag in soup.find_all([

            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
            "video",
            "audio",
            "source"

        ]):

            tag.decompose()

        title = ""

        if soup.title:

            title = clean_text(

                soup.title.get_text(
                    " ",
                    strip=True
                )

            )

        og_title = soup.find(

            "meta",

            attrs={
                "property":
                    "og:title"
            }

        )

        if og_title:

            title = (

                clean_text(

                    og_title.get(
                        "content",
                        ""
                    )

                )

                or

                title

            )

        description = ""

        og_description = soup.find(

            "meta",

            attrs={
                "property":
                    "og:description"
            }

        )

        if og_description:

            description = clean_text(

                og_description.get(
                    "content",
                    ""
                )

            )

        if not description:

            meta_description = soup.find(

                "meta",

                attrs={
                    "name":
                        "description"
                }

            )

            if meta_description:

                description = clean_text(

                    meta_description.get(
                        "content",
                        ""
                    )

                )

        visible_text = clean_text(

            soup.get_text(
                " ",
                strip=True
            )

        )

        candidates = []

        if description:
            candidates.append(
                description
            )

        if visible_text:
            candidates.append(
                visible_text
            )

        post_text = ""

        for candidate in candidates:

            candidate = clean_text(
                candidate
            )

            if len(candidate) > len(
                post_text
            ):

                post_text = candidate

        # ----------------------------------------------------
        # Reject Facebook generic homepage text.
        # ----------------------------------------------------

        generic_social_text = [

            "Connect with friends and the world around you on Facebook.",

            "Facebook helps you connect and share with the people in your life.",

            "Log in or sign up to Facebook."

        ]

        if post_text in generic_social_text:

            return None

        if len(post_text) > MAX_ARTICLE_CHARS:

            post_text = post_text[
                :MAX_ARTICLE_CHARS
            ]

        if len(post_text) < 40:

            return None

        return {

            "title":
                title,

            "content":
                post_text,

            "description":
                description,

            "source":
                get_domain(final_url),

            "domain":
                get_domain(final_url),

            "url":
                final_url,

            "date":
                "",

            "social":
                True

        }

    except Exception as e:

        print(
            "Social extraction error:",
            e
        )

        return None


# ============================================================
# ARTICLE EXTRACTION
# ============================================================

def extract_article(url):

    if not valid_result_url(
        url
    ):

        return None

    try:

        response = requests.get(

            url,

            headers=SEARCH_HEADERS,

            timeout=20,

            allow_redirects=True

        )

        response.raise_for_status()

        final_url = response.url

        if not valid_result_url(
            final_url
        ):

            return None

        if is_blocked_domain(
            final_url
        ):

            return None

        soup = BeautifulSoup(

            response.text,

            "html.parser"

        )

        for tag in soup.find_all([

            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "form",
            "aside",
            "iframe",
            "advertisement"

        ]):

            tag.decompose()

        title = ""

        if soup.title:

            title = clean_text(

                soup.title.get_text(
                    " ",
                    strip=True
                )

            )

        og_title = soup.find(

            "meta",

            attrs={
                "property":
                    "og:title"
            }

        )

        if og_title:

            title = (

                clean_text(

                    og_title.get(
                        "content",
                        ""
                    )

                )

                or

                title

            )

        description = ""

        meta_description = soup.find(

            "meta",

            attrs={
                "name":
                    "description"
            }

        )

        if meta_description:

            description = clean_text(

                meta_description.get(
                    "content",
                    ""
                )

            )

        published_date = extract_article_date(
            soup
        )

        paragraphs = soup.find_all(
            "p"
        )

        paragraph_text = []

        for p in paragraphs:

            value = clean_text(

                p.get_text(
                    " ",
                    strip=True
                )

            )

            if len(value) < 25:
                continue

            if value.lower() in [

                "home",
                "menu",
                "search",
                "login",
                "subscribe"

            ]:

                continue

            paragraph_text.append(
                value
            )

        content = " ".join(
            paragraph_text
        )

        if len(content) < 300:

            article_tag = soup.find(
                "article"
            )

            if article_tag:

                article_text = clean_text(

                    article_tag.get_text(
                        " ",
                        strip=True
                    )

                )

                if len(article_text) > len(
                    content
                ):

                    content = article_text

        if (
            len(content) < 300
            and
            Article is not None
        ):

            try:

                article = Article(

                    final_url,

                    request_timeout=20

                )

                article.download()
                article.parse()

                if article.title:

                    title = clean_text(
                        article.title
                    )

                newspaper_text = clean_text(
                    article.text
                )

                if len(newspaper_text) > len(
                    content
                ):

                    content = newspaper_text

            except Exception as e:

                print(
                    "Newspaper extraction error:",
                    get_domain(final_url),
                    e
                )

        content = clean_text(
            content
        )

        if len(content) < 80:

            return None

        if len(content) > MAX_ARTICLE_CHARS:

            content = content[
                :MAX_ARTICLE_CHARS
            ]

        domain = get_domain(
            final_url
        )

        return {

            "title":
                title,

            "content":
                content,

            "description":
                description,

            "source":
                domain,

            "domain":
                domain,

            "url":
                final_url,

            "date":
                published_date

        }

    except Exception as e:

        print(
            "Article extraction error:",
            get_domain(url),
            e
        )

        return None


# ============================================================
# ARTICLE CHUNKS
# ============================================================

def make_evidence_chunks(content):

    content = clean_text(
        content
    )

    if not content:
        return []

    sentences = sentence_split(
        content
    )

    chunks = []

    for sentence in sentences:

        if len(sentence) < 25:
            continue

        if len(sentence) > MAX_SENTENCE_CHARS:

            sentence = sentence[
                :MAX_SENTENCE_CHARS
            ]

        chunks.append(
            sentence
        )

    for i in range(
        len(sentences) - 1
    ):

        combined = clean_text(

            sentences[i]
            + " "
            + sentences[i + 1]

        )

        if len(combined) > 1000:

            combined = combined[
                :1000
            ]

        if len(combined) >= 40:

            chunks.append(
                combined
            )

    unique = []

    seen = set()

    for chunk in chunks:

        key = chunk.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            chunk
        )

    return unique


# ============================================================
# SEMANTIC SIMILARITY
# ============================================================

def semantic_similarity(
    claim,
    evidence
):

    try:

        claim = clean_text(
            claim
        )

        evidence = clean_text(
            evidence
        )

        if not claim or not evidence:

            return 0.0

        vectors = semantic_model.encode(

            [
                claim,
                evidence
            ],

            convert_to_numpy=True,

            normalize_embeddings=True

        )

        score = float(

            np.dot(

                vectors[0],

                vectors[1]

            )

        )

        return max(

            0.0,

            min(
                1.0,
                score
            )

        )

    except Exception as e:

        print(
            "Semantic similarity error:",
            e
        )

        return 0.0


# ============================================================
# SNIPPET SIMILARITY
# ============================================================

def snippet_similarity(
    claim,
    snippet
):

    if not snippet:
        return 0.0

    return semantic_similarity(
        claim,
        snippet
    )


# ============================================================
# BEST CHUNKS
# ============================================================

def select_best_chunks(
    claim,
    content,
    limit=5
):

    chunks = make_evidence_chunks(
        content
    )

    if not chunks:
        return []

    scored = []

    for chunk in chunks:

        score = semantic_similarity(

            claim,

            chunk

        )

        scored.append({

            "text":
                chunk,

            "score":
                score

        })

    scored.sort(

        key=lambda x:
            x["score"],

        reverse=True

    )

    return scored[:limit]


# ============================================================
# NLI LABEL INDEX
# ============================================================

def get_nli_label_indexes():

    labels = {}

    for index, label in (
        nli_model.config.id2label.items()
    ):

        labels[
            str(label).lower()
        ] = int(index)

    entailment_index = None
    contradiction_index = None
    neutral_index = None

    for label, index in labels.items():

        if "entail" in label:

            entailment_index = index

        elif "contrad" in label:

            contradiction_index = index

        elif "neutral" in label:

            neutral_index = index

    if entailment_index is None:
        entailment_index = 2

    if contradiction_index is None:
        contradiction_index = 0

    if neutral_index is None:
        neutral_index = 1

    return (

        contradiction_index,
        neutral_index,
        entailment_index

    )


# ============================================================
# NLI PREDICTION
# ============================================================

def nli_prediction(
    claim,
    evidence
):

    try:

        claim = clean_text(
            claim
        )

        evidence = clean_text(
            evidence
        )

        if not claim or not evidence:

            return {

                "label":
                    "neutral",

                "entailment":
                    0.0,

                "contradiction":
                    0.0,

                "neutral":
                    1.0

            }

        # ----------------------------------------------------
        # Premise = Evidence
        # Hypothesis = Claim
        # ----------------------------------------------------

        inputs = nli_tokenizer(

            evidence,

            claim,

            return_tensors="pt",

            truncation=True,

            max_length=512

        )

        with torch.no_grad():

            output = nli_model(
                **inputs
            )

        probabilities = torch.softmax(

            output.logits,

            dim=-1

        )[0]

        (

            contradiction_index,
            neutral_index,
            entailment_index

        ) = get_nli_label_indexes()

        num_labels = len(
            probabilities
        )

        if contradiction_index >= num_labels:
            contradiction_index = 0

        if neutral_index >= num_labels:
            neutral_index = 1

        if entailment_index >= num_labels:
            entailment_index = 2

        contradiction = float(

            probabilities[
                contradiction_index
            ]

        )

        neutral = float(

            probabilities[
                neutral_index
            ]

        )

        entailment = float(

            probabilities[
                entailment_index
            ]

        )

        scores = {

            "entailment":
                entailment,

            "contradiction":
                contradiction,

            "neutral":
                neutral

        }

        label = max(

            scores,

            key=scores.get

        )

        return {

            "label":
                label,

            "entailment":
                round(
                    entailment,
                    4
                ),

            "contradiction":
                round(
                    contradiction,
                    4
                ),

            "neutral":
                round(
                    neutral,
                    4
                )

        }

    except Exception as e:

        print(
            "NLI error:",
            e
        )

        return {

            "label":
                "neutral",

            "entailment":
                0.0,

            "contradiction":
                0.0,

            "neutral":
                1.0

        }


# ============================================================
# SOURCE QUALITY
# ============================================================

def source_quality_score(url):

    domain = get_domain(
        url
    )

    if not domain:
        return 0.0

    if is_blocked_domain(
        url
    ):
        return 0.0

    score = 0.0

    if is_high_trust_domain(
        url
    ):

        score = 0.90

    elif is_trusted_domain(
        url
    ):

        score = 0.70

    if domain.endswith(
        ".mm"
    ):

        score += 0.10

    if (

        domain.endswith(
            ".gov.mm"
        )

        or

        ".gov." in domain

    ):

        score += 0.10

    return min(
        score,
        1.0
    )


# ============================================================
# FRESHNESS
# ============================================================

def freshness_score(date_value):

    if not date_value:
        return 0.35

    parsed = parse_date_value(
        date_value
    )

    if parsed is None:
        return 0.35

    if parsed.tzinfo:

        parsed = parsed.replace(
            tzinfo=None
        )

    now = datetime.now()

    days = (
        now - parsed
    ).days

    if days < 0:
        return 0.50

    if days <= 3:
        return 1.00

    if days <= 7:
        return 0.90

    if days <= 30:
        return 0.75

    if days <= 90:
        return 0.55

    if days <= 365:
        return 0.30

    return 0.10


# ============================================================
# RELEVANCE SCORE
# ============================================================

def relevance_score(

    semantic,

    nli,

    snippet_score,

    source_quality,

    freshness

):

    entailment = float(

        nli.get(
            "entailment",
            0
        )

    )

    contradiction = float(

        nli.get(
            "contradiction",
            0
        )

    )

    nli_relevance = max(

        entailment,

        contradiction

    )

    score = (

        semantic * 0.35

        +

        nli_relevance * 0.30

        +

        snippet_score * 0.10

        +

        source_quality * 0.15

        +

        freshness * 0.10

    )

    return max(

        0.0,

        min(
            1.0,
            score
        )

    )


# ============================================================
# KEYWORD OVERLAP
# ============================================================

def keyword_overlap(
    claim,
    evidence
):

    claim_words = set(
        claim_keywords(
            claim
        )
    )

    evidence_words = set(
        claim_keywords(
            evidence
        )
    )

    if not claim_words:
        return 0.0

    common = (
        claim_words
        &
        evidence_words
    )

    return min(

        1.0,

        len(common)
        /
        max(
            1,
            len(claim_words)
        )

    )


# ============================================================
# PREPARE WEB EVIDENCE
# ============================================================

def prepare_web_evidence(
    claim,
    search_results
):

    evidence = []

    if not search_results:
        return []

    for index, item in enumerate(

        search_results,

        start=1

    ):

        url = item.get(
            "url",
            ""
        )

        if not valid_result_url(
            url
        ):
            continue

        # ----------------------------------------------------
        # Extra protection against social results
        # ----------------------------------------------------

        if is_blocked_social_result(
            url
        ):
            continue

        domain = get_domain(
            url
        )

        print(
            f"Reading source {index}:",
            domain
        )

        article = extract_article(
            url
        )

        if not article:

            snippet = clean_text(

                item.get(
                    "snippet",
                    ""
                )

            )

            title = clean_text(

                item.get(
                    "title",
                    ""
                )

            )

            if len(snippet) < 50:
                continue

            article = {

                "title":
                    title,

                "content":
                    snippet,

                "description":
                    snippet,

                "source":
                    domain,

                "domain":
                    domain,

                "url":
                    url,

                "date":
                    ""

            }

        content = clean_text(

            article.get(
                "content",
                ""
            )

        )

        if len(content) < 30:
            continue

        best_chunks = select_best_chunks(

            claim,

            content,

            limit=5

        )

        if not best_chunks:
            continue

        best_chunk = best_chunks[0]

        best_text = best_chunk[
            "text"
        ]

        semantic = best_chunk[
            "score"
        ]

        nli = nli_prediction(

            claim,

            best_text

        )

        snippet_score = snippet_similarity(

            claim,

            item.get(
                "snippet",
                ""
            )

        )

        overlap = keyword_overlap(

            claim,

            best_text

        )

        quality = source_quality_score(
            url
        )

        article_date = article.get(
            "date",
            ""
        )

        freshness = freshness_score(
            article_date
        )

        retrieval = relevance_score(

            semantic,

            nli,

            snippet_score,

            quality,

            freshness

        )

        relevant_enough = (

            semantic >= 0.35

            or

            (
                semantic >= 0.25
                and
                overlap >= 0.20
            )

            or

            (
                snippet_score >= 0.35
                and
                overlap >= 0.20
            )

        )

        if not relevant_enough:

            print(

                "Skipped irrelevant:",

                domain,

                "semantic=",

                round(
                    semantic,
                    3
                )

            )

            continue

        if (

            semantic < 0.30

            and

            max(
                nli["entailment"],
                nli["contradiction"]
            ) < 0.25

            and

            quality < 0.70

        ):

            print(
                "Skipped weak evidence:",
                domain
            )

            continue

        evidence.append({

            "title":
                article.get(
                    "title",
                    ""
                )
                or
                item.get(
                    "title",
                    ""
                ),

            "content":
                content,

            "best_evidence":
                best_text,

            "source":
                article.get(
                    "source",
                    domain
                ),

            "domain":
                article.get(
                    "domain",
                    domain
                ),

            "url":
                article.get(
                    "url",
                    url
                ),

            "snippet":
                item.get(
                    "snippet",
                    ""
                ),

            "engine":
                item.get(
                    "engine",
                    ""
                ),

            "date":
                article_date,

            "source_quality":
                round(
                    quality,
                    4
                ),

            "freshness":
                round(
                    freshness,
                    4
                ),

            "keyword_overlap":
                round(
                    overlap,
                    4
                ),

            "semantic_score":
                round(
                    semantic,
                    4
                ),

            "entailment":
                nli["entailment"],

            "contradiction":
                nli["contradiction"],

            "neutral":
                nli["neutral"],

            "nli_label":
                nli["label"],

            "retrieval_score":
                round(
                    retrieval,
                    4
                )

        })

    unique = {}

    for item in evidence:

        url = item.get(
            "url",
            ""
        )

        key = normalize_url_for_compare(
            url
        )

        if not key:
            continue

        old = unique.get(
            key
        )

        if old is None:

            unique[key] = item

        elif (

            item[
                "retrieval_score"
            ]

            >

            old[
                "retrieval_score"
            ]

        ):

            unique[key] = item

    evidence = list(
        unique.values()
    )

    evidence.sort(

        key=lambda x: (

            x.get(
                "retrieval_score",
                0
            ),

            x.get(
                "source_quality",
                0
            ),

            x.get(
                "semantic_score",
                0
            )

        ),

        reverse=True

    )

    print(
        "Final relevant evidence:",
        len(evidence)
    )

    return evidence[:MAX_EVIDENCE]


# ============================================================
# CLASSIFY RESULT
# ============================================================

def classify_result(evidence):

    if not evidence:

        return (

            "Unverified",
            0,
            0.0,
            0.0,
            1.0

        )

    supporting = 0.0
    contradicting = 0.0
    neutral = 0.0

    usable = []

    for item in evidence:

        semantic = float(
            item.get(
                "semantic_score",
                0
            ) or 0
        )

        retrieval = float(
            item.get(
                "retrieval_score",
                0
            ) or 0
        )

        quality = float(
            item.get(
                "source_quality",
                0
            ) or 0
        )

        entailment = float(
            item.get(
                "entailment",
                0
            ) or 0
        )

        contradiction = float(
            item.get(
                "contradiction",
                0
            ) or 0
        )

        if semantic < 0.25:
            continue

        if retrieval < 0.25:
            continue

        if quality < 0.50 and semantic < 0.40:
            continue

        if max(
            entailment,
            contradiction
        ) < 0.20:

            continue

        usable.append(
            item
        )

    if not usable:

        return (

            "Unverified",
            0,
            0.0,
            0.0,
            1.0

        )

    for item in usable:

        retrieval = float(
            item.get(
                "retrieval_score",
                0
            ) or 0
        )

        quality = float(
            item.get(
                "source_quality",
                0
            ) or 0
        )

        freshness = float(
            item.get(
                "freshness",
                0.35
            ) or 0.35
        )

        entailment = float(
            item.get(
                "entailment",
                0
            ) or 0
        )

        contradiction = float(
            item.get(
                "contradiction",
                0
            ) or 0
        )

        neutral_score = float(
            item.get(
                "neutral",
                0
            ) or 0
        )

        weight = (

            retrieval

            *

            (

                0.60

                +

                0.25 * quality

                +

                0.15 * freshness

            )

        )

        supporting += (
            entailment * weight
        )

        contradicting += (
            contradiction * weight
        )

        neutral += (
            neutral_score * weight
        )

    total = (

        supporting
        +
        contradicting
        +
        neutral

    )

    if total <= 0:

        return (

            "Unverified",
            0,
            0.0,
            0.0,
            1.0

        )

    supporting /= total
    contradicting /= total
    neutral /= total

    evidence_count = len(
        usable
    )

    domains = set()

    for item in usable:

        domain = str(

            item.get(
                "domain",
                ""
            )
            or
            ""

        ).strip().lower()

        if domain:

            domains.add(
                domain
            )

    independent_sources = len(
        domains
    )

    best_support = max(

        (

            float(
                item.get(
                    "entailment",
                    0
                )
                or
                0
            )

            for item in usable

        ),

        default=0.0

    )

    best_contradiction = max(

        (

            float(
                item.get(
                    "contradiction",
                    0
                )
                or
                0
            )

            for item in usable

        ),

        default=0.0

    )

    has_strong_source = any(

        float(
            item.get(
                "source_quality",
                0
            )
            or
            0
        ) >= 0.90

        for item in usable

    )

    enough_support_evidence = (

        evidence_count >= 2

        or

        independent_sources >= 2

        or

        (
            evidence_count >= 1
            and
            has_strong_source
        )

    )

    status = "Unverified"

    if (

        supporting >= 0.60

        and

        supporting > contradicting + 0.10

        and

        best_support >= 0.60

        and

        enough_support_evidence

    ):

        status = "Supported"

    elif (

        contradicting >= 0.60

        and

        contradicting > supporting + 0.10

        and

        best_contradiction >= 0.60

        and

        enough_support_evidence

    ):

        status = "Contradicted"

    best = max(

        supporting,
        contradicting

    )

    if status in (

        "Supported",
        "Contradicted"

    ):

        confidence = int(
            round(
                best * 100
            )
        )

        confidence = max(

            60,

            min(
                confidence,
                99
            )

        )

    else:

        confidence = int(
            round(
                best * 100
            )
        )

        confidence = min(
            confidence,
            49
        )

    return (

        status,

        confidence,

        round(
            supporting,
            4
        ),

        round(
            contradicting,
            4
        ),

        round(
            neutral,
            4
        )

    )


# ============================================================
# CLAIM EXTRACTION
# ============================================================

def extract_claim(text):

    text = clean_text(
        text
    )

    if not text:
        return ""

    sentences = sentence_split(
        text
    )

    if not sentences:
        return text

    if len(sentences) == 1:
        return sentences[0]

    return clean_text(

        " ".join(
            sentences[:3]
        )

    )


# ============================================================
# ENTITY EXTRACTION
# ============================================================

def extract_entities(text):

    entities = []

    if not text:
        return entities

    words = re.findall(

        r"[\u1000-\u109F]{3,}",

        text

    )

    seen = set()

    for word in words:

        word = word.strip()

        if word in seen:
            continue

        seen.add(
            word
        )

        entities.append({

            "type":
                "TERM",

            "value":
                word

        })

        if len(entities) >= 10:
            break

    return entities


# ============================================================
# EXPLANATION
# ============================================================

def build_explanation(
    status,
    evidence
):

    if status == "Supported":

        return (

            "The claim is supported by relevant "
            "and sufficiently strong web evidence. "
            "The supporting evidence is stronger "
            "than the contradictory evidence."

        )

    if status == "Contradicted":

        return (

            "The claim is contradicted by relevant "
            "web evidence. The contradictory evidence "
            "is stronger than the supporting evidence."

        )

    if not evidence:

        return (

            "No sufficiently relevant and readable "
            "web evidence was found to verify this claim."

        )

    return (

        "Relevant web sources were found, but the "
        "available evidence is not strong or consistent "
        "enough to classify the claim as Supported or "
        "Contradicted."

    )


# ============================================================
# EMPTY / FAILED RESULT
# ============================================================

def empty_result(
    claim="",
    explanation=None
):

    if explanation is None:

        explanation = (

            "No sufficiently relevant and readable "
            "web evidence was found to verify this claim."

        )

    return {

        "status":
            "Unverified",

        "confidence":
            0,

        "claim":
            claim,

        "supporting":
            0.0,

        "contradicting":
            0.0,

        "neutral":
            1.0,

        "evidence":
            [],

        "entities":
            extract_entities(
                claim
            ),

        "evidence_count":
            0,

        "explanation":
            explanation

    }


# ============================================================
# SOCIAL URL SEARCH FALLBACK
#
# IMPORTANT:
# This function intentionally does NOT search the social URL.
#
# Searching:
#     "https://facebook.com/share/..."
#
# causes Bing/DDG to return:
#     m.me
#     Facebook homepage
#     generic Facebook pages
#
# Therefore failed social extraction means NO evidence.
# ============================================================

def search_social_url_text(url):

    print(
        "Social search fallback disabled for verification."
    )

    return None


# ============================================================
# VERIFY ARTICLE
# ============================================================

def verify_article(

    text,

    source_url=None

):

    claim = extract_claim(
        text
    )

    print()
    print("=" * 70)
    print("AI FACT VERIFICATION")
    print("=" * 70)

    print(
        "CLAIM:",
        claim
    )

    # ========================================================
    # IMPORTANT SAFETY CHECK
    #
    # Never verify a social URL string itself.
    # ========================================================

    if source_url and is_social_url(
        source_url
    ):

        if not claim:

            return empty_result(
                "",
                "The social media content could not be extracted."
            )

        if is_url(
            claim
        ):

            print(
                "Social content unavailable."
            )

            return empty_result(

                "",

                "The social media content could not be "
                "extracted, so the URL itself was not used "
                "as a claim."

            )

    if not claim:

        return empty_result()

    print(
        "Searching public web..."
    )

    search_results = search_public_web(
        claim
    )

    print(
        "Search results:",
        len(search_results)
    )

    evidence = prepare_web_evidence(

        claim,

        search_results

    )

    print(
        "Readable evidence:",
        len(evidence)
    )

    # ========================================================
    # USER NORMAL WEBSITE SOURCE
    # ========================================================

    if (

        source_url

        and

        not is_social_url(
            source_url
        )

        and

        valid_result_url(
            source_url
        )

    ):

        print(
            "Checking user source:",
            source_url
        )

        source_article = extract_article(
            source_url
        )

        if source_article:

            source_text = clean_text(

                source_article.get(
                    "content",
                    ""
                )

            )

            best_chunks = select_best_chunks(

                claim,

                source_text,

                limit=3

            )

            if best_chunks:

                best_chunk = best_chunks[0]

                best_text = best_chunk[
                    "text"
                ]

                source_semantic = best_chunk[
                    "score"
                ]

                source_nli = nli_prediction(

                    claim,

                    best_text

                )

                source_quality = source_quality_score(

                    source_url

                )

                source_freshness = freshness_score(

                    source_article.get(
                        "date",
                        ""
                    )

                )

                source_retrieval = relevance_score(

                    source_semantic,

                    source_nli,

                    0.50,

                    source_quality,

                    source_freshness

                )

                source_evidence = {

                    "title":
                        source_article.get(
                            "title",
                            ""
                        ),

                    "content":
                        source_text,

                    "best_evidence":
                        best_text,

                    "source":
                        source_article.get(
                            "source",
                            get_domain(
                                source_url
                            )
                        ),

                    "domain":
                        source_article.get(
                            "domain",
                            get_domain(
                                source_url
                            )
                        ),

                    "url":
                        source_url,

                    "snippet":
                        "",

                    "engine":
                        "User Source",

                    "date":
                        source_article.get(
                            "date",
                            ""
                        ),

                    "source_quality":
                        round(
                            source_quality,
                            4
                        ),

                    "freshness":
                        round(
                            source_freshness,
                            4
                        ),

                    "keyword_overlap":
                        round(

                            keyword_overlap(
                                claim,
                                best_text
                            ),

                            4

                        ),

                    "semantic_score":
                        round(
                            source_semantic,
                            4
                        ),

                    "entailment":
                        source_nli[
                            "entailment"
                        ],

                    "contradiction":
                        source_nli[
                            "contradiction"
                        ],

                    "neutral":
                        source_nli[
                            "neutral"
                        ],

                    "nli_label":
                        source_nli[
                            "label"
                        ],

                    "retrieval_score":
                        round(
                            source_retrieval,
                            4
                        )

                }

                source_key = normalize_url_for_compare(

                    source_url

                )

                exists = any(

                    normalize_url_for_compare(

                        item.get(
                            "url",
                            ""
                        )

                    )

                    ==

                    source_key

                    for item in evidence

                )

                if not exists:

                    evidence.append(
                        source_evidence
                    )

    # ========================================================
    # FINAL SORT
    # ========================================================

    evidence.sort(

        key=lambda x: (

            x.get(
                "retrieval_score",
                0
            ),

            x.get(
                "source_quality",
                0
            ),

            x.get(
                "semantic_score",
                0
            )

        ),

        reverse=True

    )

    evidence = evidence[
        :MAX_EVIDENCE
    ]

    # ========================================================
    # CLASSIFY
    # ========================================================

    (

        status,

        confidence,

        supporting,

        contradicting,

        neutral

    ) = classify_result(
        evidence
    )

    # ========================================================
    # EXPLANATION
    # ========================================================

    explanation = build_explanation(

        status,

        evidence

    )

    result = {

        "status":
            status,

        "confidence":
            confidence,

        "claim":
            claim,

        "supporting":
            supporting,

        "contradicting":
            contradicting,

        "neutral":
            neutral,

        "evidence":
            evidence,

        "entities":
            extract_entities(
                claim
            ),

        "evidence_count":
            len(evidence),

        "explanation":
            explanation

    }

    # ========================================================
    # TERMINAL OUTPUT
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL VERIFICATION RESULT")
    print("=" * 70)

    print(
        "Status:",
        status
    )

    print(
        "Confidence:",
        confidence,
        "%"
    )

    print(
        "Supporting:",
        round(
            supporting,
            4
        )
    )

    print(
        "Contradicting:",
        round(
            contradicting,
            4
        )
    )

    print(
        "Neutral:",
        round(
            neutral,
            4
        )
    )

    print(
        "Evidence:",
        len(evidence)
    )

    print()
    print("EVIDENCE SOURCES")

    if not evidence:

        print(
            "No reliable evidence found."
        )

    for index, item in enumerate(

        evidence,

        start=1

    ):

        print()

        print(
            f"{index}.",
            item.get(
                "source",
                ""
            )
        )

        print(
            "   Title:",
            item.get(
                "title",
                ""
            )
        )

        print(
            "   Date:",
            item.get(
                "date",
                ""
            )
        )

        print(
            "   Semantic:",
            item.get(
                "semantic_score",
                0
            )
        )

        print(
            "   Source Quality:",
            item.get(
                "source_quality",
                0
            )
        )

        print(
            "   Freshness:",
            item.get(
                "freshness",
                0
            )
        )

        print(
            "   Keyword Overlap:",
            item.get(
                "keyword_overlap",
                0
            )
        )

        print(
            "   Entailment:",
            item.get(
                "entailment",
                0
            )
        )

        print(
            "   Contradiction:",
            item.get(
                "contradiction",
                0
            )
        )

        print(
            "   Neutral:",
            item.get(
                "neutral",
                0
            )
        )

        print(
            "   NLI Label:",
            item.get(
                "nli_label",
                ""
            )
        )

        print(
            "   Retrieval:",
            item.get(
                "retrieval_score",
                0
            )
        )

        print(
            "   URL:",
            item.get(
                "url",
                ""
            )
        )

        print(
            "   Best Evidence:",
            item.get(
                "best_evidence",
                ""
            )[:500]
        )

    print(
        "=" * 70
    )

    return result


# ============================================================
# HTML TEMPLATE
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>AI Fact Verification</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
        Arial,
        "Noto Sans Myanmar",
        sans-serif;

    background:
        #f5f7fb;

    color:
        #202124;

}

.container {

    width: 92%;

    max-width: 1100px;

    margin:
        40px auto;

}

.header {

    background:
        white;

    border-radius:
        18px;

    padding:
        28px;

    box-shadow:
        0 5px 20px rgba(
            0,
            0,
            0,
            0.07
        );

    margin-bottom:
        20px;

}

.header h1 {

    margin:
        0 0 8px;

}

.header p {

    margin:
        0;

    color:
        #666;

}

.card {

    background:
        white;

    border-radius:
        18px;

    padding:
        25px;

    box-shadow:
        0 5px 20px rgba(
            0,
            0,
            0,
            0.07
        );

    margin-bottom:
        20px;

}

textarea {

    width:
        100%;

    min-height:
        180px;

    padding:
        15px;

    border:
        1px solid #ddd;

    border-radius:
        12px;

    font-size:
        16px;

    resize:
        vertical;

    outline:
        none;

}

textarea:focus {

    border-color:
        #777;

}

button {

    margin-top:
        15px;

    padding:
        12px 25px;

    border:
        none;

    border-radius:
        10px;

    background:
        #222;

    color:
        white;

    font-size:
        15px;

    cursor:
        pointer;

}

.result {

    padding:
        20px;

    border-radius:
        14px;

    background:
        #fafafa;

}

.status {

    font-size:
        26px;

    font-weight:
        bold;

    margin-bottom:
        8px;

}

.status.Supported {

    color:
        #16803c;

}

.status.Contradicted {

    color:
        #c62828;

}

.status.Unverified {

    color:
        #777;

}

.stats {

    display:
        grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(
                160px,
                1fr
            )
        );

    gap:
        12px;

    margin:
        20px 0;

}

.stat {

    padding:
        15px;

    border:
        1px solid #eee;

    border-radius:
        12px;

    background:
        white;

}

.stat strong {

    display:
        block;

    font-size:
        20px;

    margin-top:
        5px;

}

.evidence {

    margin-top:
        20px;

}

.source {

    border:
        1px solid #e5e5e5;

    border-radius:
        14px;

    padding:
        18px;

    margin-bottom:
        14px;

    background:
        white;

}

.source h3 {

    margin:
        0 0 8px;

}

.source a {

    color:
        #3157a6;

    word-break:
        break-all;

}

.evidence-text {

    margin-top:
        12px;

    padding:
        12px;

    background:
        #f5f5f5;

    border-radius:
        10px;

    line-height:
        1.6;

}

label {

    display:
        block;

    font-weight:
        bold;

    margin-bottom:
        8px;

}

.empty {

    color:
        #777;

}

</style>

</head>

<body>

<div class="container">

    <div class="header">

        <h1>
            AI Fact Verification System
        </h1>

        <p>
            Verify text or webpage claims using
            semantic similarity, NLI and web evidence.
        </p>

    </div>


    <div class="card">

        <form method="POST">

            <label>
                Enter text or URL
            </label>

            <textarea
                name="content"
                placeholder="Enter a claim or paste a URL..."
            ></textarea>

            <button type="submit">
                Verify
            </button>

        </form>

    </div>


    {% if result %}

    <div class="card">

        <div class="result">

            <div class="status {{ result.status }}">

                {{ result.status }}

            </div>

            <p>
                {{ result.explanation }}
            </p>


            <div class="stats">

                <div class="stat">
                    Status
                    <strong>
                        {{ result.status }}
                    </strong>
                </div>

                <div class="stat">
                    Confidence
                    <strong>
                        {{ result.confidence }}%
                    </strong>
                </div>

                <div class="stat">
                    Supporting
                    <strong>
                        {{ result.supporting }}
                    </strong>
                </div>

                <div class="stat">
                    Contradicting
                    <strong>
                        {{ result.contradicting }}
                    </strong>
                </div>

                <div class="stat">
                    Neutral
                    <strong>
                        {{ result.neutral }}
                    </strong>
                </div>

                <div class="stat">
                    Evidence
                    <strong>
                        {{ result.evidence_count }}
                    </strong>
                </div>

            </div>


            <h3>
                Claim
            </h3>

            <div class="evidence-text">
                {{ result.claim }}
            </div>


            <div class="evidence">

                <h2>
                    Evidence Sources
                </h2>

                {% if result.evidence %}

                    {% for item in result.evidence %}

                    <div class="source">

                        <h3>
                            {{ loop.index }}.
                            {{ item.source }}
                        </h3>

                        <p>
                            <strong>
                                {{ item.title }}
                            </strong>
                        </p>

                        <p>
                            Date:
                            {{ item.date or "Unknown" }}
                        </p>

                        <p>
                            Semantic:
                            {{ item.semantic_score }}
                        </p>

                        <p>
                            Source Quality:
                            {{ item.source_quality }}
                        </p>

                        <p>
                            Freshness:
                            {{ item.freshness }}
                        </p>

                        <p>
                            Entailment:
                            {{ item.entailment }}
                        </p>

                        <p>
                            Contradiction:
                            {{ item.contradiction }}
                        </p>

                        <p>
                            NLI:
                            {{ item.nli_label }}
                        </p>

                        <p>
                            Retrieval:
                            {{ item.retrieval_score }}
                        </p>

                        <p>
                            <a
                                href="{{ item.url }}"
                                target="_blank"
                            >
                                {{ item.url }}
                            </a>
                        </p>

                        <div class="evidence-text">

                            {{ item.best_evidence }}

                        </div>

                    </div>

                    {% endfor %}

                {% else %}

                    <p class="empty">
                        No reliable evidence found.
                    </p>

                {% endif %}

            </div>

        </div>

    </div>

    {% endif %}

</div>

</body>

</html>
"""


# ============================================================
# FLASK HOME
# ============================================================

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

            "content",

            ""

        ).strip()

        if not user_input:

            return render_template_string(

                HTML,

                result=None

            )

        extracted = None

        analysis_text = ""

        source_url = None

        # ====================================================
        # URL INPUT
        # ====================================================

        if is_url(
            user_input
        ):

            source_url = user_input

            print()
            print("=" * 70)
            print("URL INPUT")
            print(source_url)
            print("=" * 70)

            # =================================================
            # SOCIAL MEDIA URL
            # =================================================

            if is_social_url(
                source_url
            ):

                print(
                    "Social URL detected."
                )

                extracted = extract_social_text(
                    source_url
                )

                # ------------------------------------------------
                # IMPORTANT:
                # DO NOT use the URL itself as claim.
                # ------------------------------------------------

                if extracted:

                    analysis_text = clean_text(

                        extracted.get(
                            "content",
                            ""
                        )

                    )

                    print(
                        "Extracted social text:"
                    )

                    print(
                        analysis_text[:1000]
                    )

                else:

                    print(
                        "Social extraction failed."
                    )

                    print(
                        "URL will NOT be used as claim."
                    )

                    # ------------------------------------------------
                    # Directly return Unverified / Evidence 0.
                    # ------------------------------------------------

                    result = empty_result(

                        "",

                        "The social media content could not "
                        "be extracted. The URL itself was not "
                        "used as a claim."

                    )

                    # ------------------------------------------------
                    # Save history
                    # ------------------------------------------------

                    try:

                        history = History(

                            input_text=user_input,

                            extracted_text=None,

                            result=json.dumps(

                                result,

                                ensure_ascii=False

                            )

                        )

                        db.session.add(
                            history
                        )

                        db.session.commit()

                    except Exception as e:

                        db.session.rollback()

                        print(
                            "Database save error:",
                            e
                        )

                    return render_template_string(

                        HTML,

                        result=result

                    )

            # =================================================
            # NORMAL WEBSITE
            # =================================================

            else:

                extracted = extract_article(
                    source_url
                )

                if extracted:

                    analysis_text = clean_text(

                        extracted.get(
                            "title",
                            ""
                        )

                        + " "

                        + extracted.get(
                            "content",
                            ""
                        )

                    )

                else:

                    print(
                        "Website extraction failed."
                    )

                    result = empty_result(

                        "",

                        "The webpage content could not "
                        "be extracted, so it could not "
                        "be verified."

                    )

                    try:

                        history = History(

                            input_text=user_input,

                            extracted_text=None,

                            result=json.dumps(

                                result,

                                ensure_ascii=False

                            )

                        )

                        db.session.add(
                            history
                        )

                        db.session.commit()

                    except Exception as e:

                        db.session.rollback()

                        print(
                            "Database save error:",
                            e
                        )

                    return render_template_string(

                        HTML,

                        result=result

                    )

        # ====================================================
        # NORMAL TEXT INPUT
        # ====================================================

        else:

            analysis_text = user_input

        # ====================================================
        # VERIFY
        # ====================================================

        result = verify_article(

            analysis_text,

            source_url

        )

        # ====================================================
        # SAVE HISTORY
        # ====================================================

        try:

            history = History(

                input_text=user_input,

                extracted_text=(

                    json.dumps(

                        extracted,

                        ensure_ascii=False

                    )

                    if extracted

                    else None

                ),

                result=json.dumps(

                    result,

                    ensure_ascii=False

                )

            )

            db.session.add(
                history
            )

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print(
                "Database save error:",
                e
            )

    return render_template_string(

        HTML,

        result=result

    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)

def health():

    return {

        "status":
            "ok",

        "service":
            "AI Fact Verification",

        "time":
            datetime.now().isoformat()

    }


# ============================================================
# API VERIFY
# ============================================================

@app.route(
    "/api/verify",
    methods=["POST"]
)

def api_verify():

    data = request.get_json(
        silent=True
    ) or {}

    user_input = clean_text(

        data.get(
            "content",
            ""
        )

    )

    if not user_input:

        return jsonify({

            "error":
                "content is required"

        }), 400

    # --------------------------------------------------------
    # Social URL
    # --------------------------------------------------------

    if is_url(
        user_input
    ) and is_social_url(
        user_input
    ):

        extracted = extract_social_text(
            user_input
        )

        if not extracted:

            return jsonify(
                empty_result(

                    "",

                    "The social media content could not "
                    "be extracted. The URL itself was not "
                    "used as a claim."

                )
            )

        text = clean_text(

            extracted.get(
                "content",
                ""
            )

        )

        result = verify_article(

            text,

            user_input

        )

        return jsonify(
            result
        )

    # --------------------------------------------------------
    # Normal URL
    # --------------------------------------------------------

    if is_url(
        user_input
    ):

        article = extract_article(
            user_input
        )

        if not article:

            return jsonify(

                empty_result(

                    "",

                    "The webpage content could not "
                    "be extracted."

                )

            )

        text = clean_text(

            article.get(
                "title",
                ""
            )

            + " "

            + article.get(
                "content",
                ""
            )

        )

        result = verify_article(

            text,

            user_input

        )

        return jsonify(
            result
        )

    # --------------------------------------------------------
    # Normal claim
    # --------------------------------------------------------

    result = verify_article(
        user_input
    )

    return jsonify(
        result
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    logging.getLogger(
        "werkzeug"
    ).setLevel(
        logging.WARNING
    )

    print()
    print("=" * 70)
    print("AI FACT VERIFICATION SYSTEM")
    print("=" * 70)

    print(
        "Server: http://127.0.0.1:5000"
    )

    print(
        "Database: database.db"
    )

    print(
        "Semantic Model:",
        SEMANTIC_MODEL_NAME
    )

    print(
        "NLI Model:",
        NLI_MODEL_NAME
    )

    print("=" * 70)
    print()

    app.run(

        debug=True,

        use_reloader=False,

        host="127.0.0.1",

        port=5000

    )