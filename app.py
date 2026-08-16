import os
import re
import json
import logging
import requests
import numpy as np
import unicodedata
import base64

from datetime import datetime, timezone
from urllib.parse import (
    urlparse,
    quote_plus,
    parse_qs,
    unquote
)

from bs4 import BeautifulSoup

from flask import (
    Flask,
    render_template,
    request
)

from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

from newspaper import Article

from sentence_transformers import SentenceTransformer

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)

import torch


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# FLASK CONFIGURATION
# ============================================================

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


# ============================================================
# DATABASE
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
        db.Text
    )

    result = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


with app.app_context():
    db.create_all()


# ============================================================
# AI MODELS
# ============================================================

SEMANTIC_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

NLI_MODEL_NAME = (
    "MoritzLaurer/"
    "mDeBERTa-v3-base-mnli-xnli"
)


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
# SEARCH HEADERS
# ============================================================

SEARCH_HEADERS = {

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 "
            "Safari/537.36"
        ),

    "Accept":
        (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8"
        ),

    "Accept-Language":
        "my,en-US;q=0.9,en;q=0.8",

    "Connection":
        "keep-alive"

}


# ============================================================
# TRUSTED DOMAINS
# ============================================================

TRUSTED_DOMAINS = [

    # Myanmar government
    "moi.gov.mm",
    "myanmar.gov.mm",
    "mrtv.gov.mm",
    "mdn.gov.mm",
    "ddm.gov.mm",
    "myanmar-president-office.gov.mm",

    # International / established news
    "bbc.com",
    "bbc.co.uk",
    "rfa.org",
    "voanews.com",

    # Myanmar news
    "irrawaddy.com",
    "mizzima.com",
    "elevenmyanmar.com",
    "frontiermyanmar.net",
    "dvb.no"

]


# ============================================================
# BLOCKED DOMAINS
# ============================================================

BLOCKED_DOMAINS = [

    "bing.com",
    "google.com",
    "duckduckgo.com",
    "yahoo.com",

    "facebook.com",
    "youtube.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",

    "linkedin.com",

]


# ============================================================
# DOMAIN QUALITY
# ============================================================

HIGH_TRUST_DOMAINS = [

    "moi.gov.mm",
    "ddm.gov.mm",
    "myanmar.gov.mm",
    "mrtv.gov.mm",
    "myanmar-president-office.gov.mm",

    "bbc.com",
    "bbc.co.uk",
    "rfa.org",
    "voanews.com"

]


# ============================================================
# GENERAL LIMITS
# ============================================================

MAX_SEARCH_RESULTS = 40

MAX_EVIDENCE = 10

MAX_ARTICLE_CHARS = 12000

MAX_MODEL_CHARS = 5000

MAX_SENTENCE_CHARS = 700


# ============================================================
# TEXT CLEANING
# ============================================================

def unicode_normalize(text):

    if not text:
        return ""

    try:

        return unicodedata.normalize(
            "NFC",
            str(text)
        )

    except Exception:

        return str(text)


def normalize_text(text):

    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def clean_text(text):

    text = unicode_normalize(
        text
    )

    text = normalize_text(
        text
    )

    return text


# ============================================================
# URL CHECK
# ============================================================

def is_url(text):

    if not text:
        return False

    try:

        parsed = urlparse(
            text.strip()
        )

        return (
            parsed.scheme.lower()
            in ("http", "https")
            and
            bool(parsed.netloc)
        )

    except Exception:

        return False


# ============================================================
# DOMAIN HELPERS
# ============================================================

def get_domain(url):

    if not url:
        return ""

    try:

        parsed = urlparse(
            url
        )

        domain = parsed.netloc.lower().strip()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


def is_blocked_domain(url):

    domain = get_domain(
        url
    )

    if not domain:
        return False

    for blocked in BLOCKED_DOMAINS:

        if (
            domain == blocked
            or
            domain.endswith(
                "." + blocked
            )
        ):

            return True

    return False


def is_trusted_domain(url):

    domain = get_domain(
        url
    )

    if not domain:
        return False

    for trusted in TRUSTED_DOMAINS:

        if (
            domain == trusted
            or
            domain.endswith(
                "." + trusted
            )
        ):

            return True

    return False


def is_high_trust_domain(url):

    domain = get_domain(
        url
    )

    if not domain:
        return False

    for trusted in HIGH_TRUST_DOMAINS:

        if (
            domain == trusted
            or
            domain.endswith(
                "." + trusted
            )
        ):

            return True

    return False

# ============================================================
# BING REDIRECT URL RESOLVER
# ============================================================

def resolve_search_url(url):

    if not url:
        return ""

    url = unquote(
        url.strip()
    )

    if not is_url(url):
        return ""

    domain = get_domain(
        url
    )

    # --------------------------------------------------------
    # If this is already a normal website URL,
    # do not touch it.
    # --------------------------------------------------------

    if domain not in (
        "bing.com",
        "www.bing.com"
    ):

        return url


    # --------------------------------------------------------
    # Bing redirect URLs normally contain:
    # ?u=a1....
    # --------------------------------------------------------

    try:

        parsed = urlparse(
            url
        )

        query = parse_qs(
            parsed.query
        )

        encoded_url = query.get(
            "u",
            [""]
        )[0]


        if encoded_url:

            encoded_url = unquote(
                encoded_url
            )

            if encoded_url.startswith(
                "a1"
            ):

                encoded_url = encoded_url[2:]


            # Base64 decode

            try:

                padding = (
                    "="
                    *
                    (
                        4
                        -
                        len(encoded_url) % 4
                    ) % 4
                )

                decoded = base64.urlsafe_b64decode(
                    encoded_url + padding
                ).decode(
                    "utf-8",
                    errors="ignore"
                )


                if is_url(decoded):

                    decoded_domain = get_domain(
                        decoded
                    )

                    if (
                        decoded_domain
                        and
                        decoded_domain
                        not in BLOCKED_DOMAINS
                    ):

                        return decoded


            except Exception:

                pass


        # ----------------------------------------------------
        # Fallback: follow redirect
        # ----------------------------------------------------

        response = requests.get(

            url,

            headers=SEARCH_HEADERS,

            timeout=10,

            allow_redirects=True

        )


        final_url = response.url


        if (
            final_url
            and
            is_url(final_url)
            and
            not is_blocked_domain(final_url)
        ):

            return final_url


    except Exception:

        pass


    return ""


# ============================================================
# URL VALIDATION
# ============================================================

def valid_result_url(url):

    if not url:
        return False

    url = resolve_search_url(
        url
    )

    if not url:
        return False

    if not is_url(url):
        return False

    if is_blocked_domain(url):
        return False

    domain = get_domain(
        url
    )

    if not domain:
        return False

    # --------------------------------------------------------
    # Reject obvious search pages
    # --------------------------------------------------------

    parsed = urlparse(
        url
    )

    path = (
        parsed.path
        + "?"
        + parsed.query
    ).lower()


    blocked_patterns = [

        "/search",
        "?q=",
        "&q=",
        "/results",
        "/ck/",
        "bing.com",
        "google.com"

    ]


    for pattern in blocked_patterns:

        if pattern in path:

            return False


    return True


# ============================================================
# MYANMAR TOKENIZER
# ============================================================

def myanmar_tokenize(text):

    text = clean_text(
        text
    )

    if not text:
        return []


    text = text.lower()


    tokens = re.findall(

        r"[\u1000-\u109F]+|"
        r"[A-Za-z]+|"
        r"[0-9၀-၉]+",

        text

    )


    result = []


    for token in tokens:

        token = token.strip()

        if len(token) <= 1:
            continue

        result.append(
            token
        )


    return result


# ============================================================
# SENTENCE SPLITTER
# ============================================================

def sentence_split(text):

    text = clean_text(
        text
    )

    if not text:
        return []


    # Myanmar sentence marker + English punctuation
    parts = re.split(

        r"[။!?！？\n]+",

        text

    )


    sentences = []


    for part in parts:

        part = clean_text(
            part
        )

        if len(part) >= 20:

            sentences.append(
                part
            )


    return sentences


# ============================================================
# CLAIM KEYWORDS
# ============================================================

def claim_keywords(claim):

    tokens = myanmar_tokenize(
        claim
    )

    # Remove very generic words
    stop_words = {

        "မှာ",
        "သည်",
        "ဖြစ်",
        "နေ",
        "တယ်",
        "ပြီး",
        "သော",
        "အတွက်",
        "ကို",
        "က",
        "နဲ့",
        "နှင့်",
        "တွင်",
        "လည်း",
        "ရှိ",
        "မည်",
        "နိုင်",
        "ပြော",
        "သည့်",
        "ခဲ့",
        "ပါ"

    }


    result = []


    for token in tokens:

        if token in stop_words:
            continue

        if len(token) < 2:
            continue

        if token not in result:

            result.append(
                token
            )


    return result


# ============================================================
# SEARCH QUERY GENERATOR
# ============================================================

def build_search_queries(claim):

    claim = clean_text(
        claim
    )

    if not claim:
        return []


    queries = []


    # Main claim

    queries.append(
        claim
    )


    # Claim + news

    queries.append(
        claim + " သတင်း"
    )


    # Claim + Myanmar

    queries.append(
        claim + " မြန်မာ"
    )


    # Current year

    current_year = datetime.now().year


    queries.append(
        claim
        + " "
        + str(current_year)
    )


    # Important keywords

    keywords = claim_keywords(
        claim
    )


    if len(keywords) >= 3:

        compact = " ".join(
            keywords[:12]
        )

        queries.append(
            compact
        )


        queries.append(
            compact
            + " သတင်း"
        )


    # Remove duplicates

    final_queries = []

    seen = set()


    for query in queries:

        query = clean_text(
            query
        )

        if not query:
            continue

        key = query.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        final_queries.append(
            query
        )


    return final_queries[:6]


# ============================================================
# SEARCH RESULT TEXT EXTRACTION
# ============================================================

def extract_search_result_text(result):

    title = clean_text(
        result.get(
            "title",
            ""
        )
    )

    snippet = clean_text(
        result.get(
            "snippet",
            ""
        )
    )


    return clean_text(
        title
        + " "
        + snippet
    )


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


            # DDG redirect

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
# SEARCH RESULT DEDUPLICATION
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


        # DDG

        ddg_results = search_duckduckgo(
            query
        )

        all_results.extend(
            ddg_results
        )


        # Bing

        bing_results = search_bing(
            query
        )

        all_results.extend(
            bing_results
        )


    # --------------------------------------------------------
    # Deduplicate URLs
    # --------------------------------------------------------

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


        item["url"] = url


        key = normalize_url_for_compare(
            url
        )


        if not key:
            continue


        item["search_quality"] = round(
            search_result_quality(item),
            4
        )


        old = unique.get(
            key
        )


        if old is None:

            unique[key] = item

        else:

            # Keep the better result

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


    # --------------------------------------------------------
    # Sort trusted sources first
    # --------------------------------------------------------

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


    # OpenGraph

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


    # Standard meta

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


    # Time tag

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


    # ISO date

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        pass


    # YYYY-MM-DD

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


    # English date

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


        # ----------------------------------------------------
        # Remove unwanted HTML
        # ----------------------------------------------------

        for tag in soup.find_all(

            [

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

            ]

        ):

            tag.decompose()


        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        published_date = extract_article_date(
            soup
        )


        # ----------------------------------------------------
        # ARTICLE PARAGRAPHS
        # ----------------------------------------------------

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


            # Avoid tiny menu-like text

            if len(value) < 25:
                continue


            # Avoid obvious navigation

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


        # ----------------------------------------------------
        # ARTICLE TAG FALLBACK
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # NEWSPAPER3K FALLBACK
        # ----------------------------------------------------

        if len(content) < 300:

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


        # ----------------------------------------------------
        # Final cleaning
        # ----------------------------------------------------

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
# ARTICLE SENTENCE / CHUNK GENERATOR
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


    # --------------------------------------------------------
    # Individual sentences
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Two-sentence chunks
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

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
# FIND BEST EVIDENCE CHUNKS
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


    # --------------------------------------------------------
    # Search actual model labels
    # --------------------------------------------------------

    for label, index in labels.items():

        if "entail" in label:

            entailment_index = index


        elif "contrad" in label:

            contradiction_index = index


        elif "neutral" in label:

            neutral_index = index


    # --------------------------------------------------------
    # Fallback for standard 3-label NLI
    # --------------------------------------------------------

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


        # ====================================================
        # IMPORTANT
        #
        # Premise = EVIDENCE
        # Hypothesis = CLAIM
        #
        # This was reversed in the old code.
        # ====================================================

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


    # High trust

    if is_high_trust_domain(
        url
    ):

        score = 0.90


    elif is_trusted_domain(
        url
    ):

        score = 0.70


    # Myanmar domain

    if domain.endswith(
        ".mm"
    ):

        score += 0.10


    # Government

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
# SOURCE FRESHNESS
# ============================================================

def freshness_score(date_value):

    if not date_value:

        # Unknown date should NOT get
        # a large advantage.

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


    # Future / malformed

    if days < 0:

        return 0.50


    # Current

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


    # Old article

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


    # --------------------------------------------------------
    # Main score
    #
    # Semantic = whether article passage is about claim
    # NLI = whether passage supports/contradicts
    # Snippet = search engine relevance
    # Quality = reliability
    # Freshness = important for current claims
    # --------------------------------------------------------

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
# CLAIM / EVIDENCE KEYWORD OVERLAP
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


        # ----------------------------------------------------
        # If article cannot be extracted,
        # snippet can be used only as weak evidence.
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # Select the MOST RELEVANT passages.
        #
        # Do NOT send the entire article to NLI.
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # NLI on the best relevant passage
        # ----------------------------------------------------

        nli = nli_prediction(

            claim,

            best_text

        )


        # ----------------------------------------------------
        # Search snippet relevance
        # ----------------------------------------------------

        snippet_score = snippet_similarity(

            claim,

            item.get(
                "snippet",
                ""
            )

        )


        # ----------------------------------------------------
        # Keyword overlap
        # ----------------------------------------------------

        overlap = keyword_overlap(

            claim,

            best_text

        )


        # ----------------------------------------------------
        # Source quality
        # ----------------------------------------------------

        quality = source_quality_score(
            url
        )


        # ----------------------------------------------------
        # Freshness
        # ----------------------------------------------------

        article_date = article.get(
            "date",
            ""
        )


        freshness = freshness_score(
            article_date
        )


        # ----------------------------------------------------
        # Final retrieval score
        # ----------------------------------------------------

        retrieval = relevance_score(

            semantic,

            nli,

            snippet_score,

            quality,

            freshness

        )


        # ----------------------------------------------------
        # Strong relevance filter
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # Weak NLI + weak semantic = reject
        # ----------------------------------------------------

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


    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

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


    return evidence[
        :MAX_EVIDENCE
    ]

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


    # ========================================================
    # FILTER WEAK EVIDENCE
    # ========================================================

    for item in evidence:

        semantic = float(

            item.get(
                "semantic_score",
                0
            )

        )


        retrieval = float(

            item.get(
                "retrieval_score",
                0
            )

        )


        quality = float(

            item.get(
                "source_quality",
                0
            )

        )


        entailment = float(

            item.get(
                "entailment",
                0
            )

        )


        contradiction = float(

            item.get(
                "contradiction",
                0
            )

        )


        # Evidence must have actual relevance.

        if semantic < 0.25:

            continue


        if retrieval < 0.25:

            continue


        # For low quality source, demand stronger semantic match.

        if quality < 0.50:

            if semantic < 0.40:

                continue


        # NLI should have meaningful signal.

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


    # ========================================================
    # CALCULATE WEIGHTED EVIDENCE
    # ========================================================

    for item in usable:

        retrieval = float(

            item.get(
                "retrieval_score",
                0
            )

        )


        quality = float(

            item.get(
                "source_quality",
                0
            )

        )


        freshness = float(

            item.get(
                "freshness",
                0.35
            )

        )


        entailment = float(

            item.get(
                "entailment",
                0
            )

        )


        contradiction = float(

            item.get(
                "contradiction",
                0
            )

        )


        neutral_score = float(

            item.get(
                "neutral",
                0
            )

        )


        # ----------------------------------------------------
        # Weight
        #
        # High quality + fresh + relevant = stronger evidence
        # ----------------------------------------------------

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

            entailment
            *
            weight

        )


        contradicting += (

            contradiction
            *
            weight

        )


        neutral += (

            neutral_score
            *
            weight

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


    # ========================================================
    # COUNT INDEPENDENT SOURCES
    # ========================================================

    domains = set()


    for item in usable:

        domain = item.get(
            "domain",
            ""
        )


        if domain:

            domains.add(
                domain
            )


    independent_sources = len(
        domains
    )


    # ========================================================
    # STRONG SUPPORT / CONTRADICTION
    # ========================================================

    best_support = max(

        [

            float(
                item.get(
                    "entailment",
                    0
                )
            )

            for item in usable

        ],

        default=0

    )


    best_contradiction = max(

        [

            float(
                item.get(
                    "contradiction",
                    0
                )
            )

            for item in usable

        ],

        default=0

    )


    # ========================================================
    # DECISION
    # ========================================================

    status = "Unverified"


    # --------------------------------------------------------
    # Supported
    #
    # Require:
    # - enough evidence
    # - support > contradiction
    # - weighted support >= 0.60
    # - at least one strong source
    # --------------------------------------------------------

    if (

        supporting >= 0.60

        and

        supporting >
        contradicting + 0.10

        and

        best_support >= 0.60

        and

        (
            evidence_count >= 2
            or
            independent_sources >= 2
            or
            (
                evidence_count >= 1
                and
                any(
                    item.get(
                        "source_quality",
                        0
                    ) >= 0.90
                    for item in usable
                )
            )
        )

    ):

        status = "Supported"


    # --------------------------------------------------------
    # Contradicted
    # --------------------------------------------------------

    elif (

        contradicting >= 0.60

        and

        contradicting >
        supporting + 0.10

        and

        best_contradiction >= 0.60

        and

        (
            evidence_count >= 2
            or
            independent_sources >= 2
            or
            (
                evidence_count >= 1
                and
                any(
                    item.get(
                        "source_quality",
                        0
                    ) >= 0.90
                    for item in usable
                )
            )
        )

    ):

        status = "Contradicted"


    # ========================================================
    # CONFIDENCE
    # ========================================================

    best = max(

        supporting,

        contradicting

    )


    if status == "Supported":

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


    elif status == "Contradicted":

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

        # Unverified should not pretend to be highly certain.

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


    # If user entered a long article,
    # use only meaningful first sentences.

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


    # Myanmar words

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


        if len(
            entities
        ) >= 10:

            break


    return entities


# ============================================================
# EXPLANATION GENERATOR
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
    print(
        "=" * 70
    )

    print(
        "AI FACT VERIFICATION"
    )

    print(
        "=" * 70
    )


    print(
        "CLAIM:",
        claim
    )


    print(
        "Searching public web..."
    )


    # ========================================================
    # SEARCH
    # ========================================================

    search_results = search_public_web(
        claim
    )


    print(
        "Search results:",
        len(search_results)
    )


    # ========================================================
    # PREPARE EVIDENCE
    # ========================================================

    evidence = prepare_web_evidence(

        claim,

        search_results

    )


    print(
        "Readable evidence:",
        len(evidence)
    )


    # ========================================================
    # USER-SUPPLIED SOURCE URL
    # ========================================================

    if source_url:

        source_url = resolve_search_url(
            source_url
        )


        if valid_result_url(
            source_url
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


                # Best relevant passage

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


                    source_key = (
                        normalize_url_for_compare(
                            source_url
                        )
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
    # CLASSIFICATION
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


    # ========================================================
    # FINAL RESULT OBJECT
    # ========================================================

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
    print(
        "=" * 70
    )

    print(
        "FINAL VERIFICATION RESULT"
    )

    print(
        "=" * 70
    )


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
    print(
        "EVIDENCE SOURCES"
    )


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


        # ====================================================
        # EMPTY INPUT
        # ====================================================

        if not user_input:

            return render_template(

                "index.html",

                result=None

            )


        extracted = None

        analysis_text = user_input

        source_url = None


        # ====================================================
        # URL INPUT
        # ====================================================

        if is_url(
            user_input
        ):

            source_url = user_input


            print()
            print(
                "=" * 70
            )

            print(
                "URL INPUT"
            )

            print(
                source_url
            )

            print(
                "=" * 70
            )


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

                # If URL cannot be extracted,
                # still verify the URL itself
                # only if there is no article text.

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


    return render_template(

        "index.html",

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
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    logging.getLogger(
        "werkzeug"
    ).setLevel(
        logging.WARNING
    )


    print()
    print(
        "=" * 70
    )

    print(
        "AI FACT VERIFICATION SYSTEM"
    )

    print(
        "=" * 70
    )

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

    print(
        "=" * 70
    )

    print()


    app.run(

        debug=True,

        use_reloader=False,

        host="127.0.0.1",

        port=5000

    )