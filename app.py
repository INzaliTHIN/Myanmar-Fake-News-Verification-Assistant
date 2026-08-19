import os
import re
import json
import base64
import sqlite3
import logging
import requests
import feedparser


from datetime import datetime
from urllib.parse import (
    urlparse,
    parse_qs,
    quote_plus
)


from bs4 import BeautifulSoup


from flask import (
    Flask,
    request,
    jsonify,
    render_template
)


from dotenv import load_dotenv



# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()



APP_NAME = (
    "Myanmar News Verification System"
)


DB_FILE = (
    "verification_history.db"
)



# ============================================================
# TELEGRAM CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
)


TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    ""
)



# ============================================================
# APP CONFIG
# ============================================================

REQUEST_TIMEOUT = 15


app = Flask(
    __name__
)



# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s | %(levelname)s | %(message)s"
)


logger = logging.getLogger(
    __name__
)



# ============================================================
# HTTP SESSION
# ============================================================


session = requests.Session()


session.headers.update({

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
        )

})



# ============================================================
# DATABASE
# ============================================================


def init_database():


    conn = sqlite3.connect(
        DB_FILE
    )


    cursor = conn.cursor()


    cursor.execute(
        """

        CREATE TABLE IF NOT EXISTS
        verification_history
        (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            claim TEXT,

            result TEXT,

            confidence REAL,

            evidence TEXT,

            created_at TEXT

        )

        """
    )


    conn.commit()

    conn.close()



init_database()



# ============================================================
# TEXT CLEANING
# ============================================================


def clean_text(text):


    if not text:

        return ""


    text = str(text)


    text = re.sub(
        r"\s+",
        " ",
        text
    )


    return text.strip()



# ============================================================
# TELEGRAM FUNCTIONS
# ============================================================


def telegram_enabled():


    return bool(

        TELEGRAM_BOT_TOKEN

        and

        TELEGRAM_CHAT_ID

    )





def send_telegram(message):


    if not telegram_enabled():

        logger.warning(
            "Telegram not configured"
        )

        return False



    try:


        url = (

            "https://api.telegram.org/bot"

            + TELEGRAM_BOT_TOKEN

            + "/sendMessage"

        )


        payload = {


            "chat_id":
                TELEGRAM_CHAT_ID,


            "text":
                message,


            "parse_mode":
                "HTML",


            "disable_web_page_preview":
                False

        }



        response = requests.post(

            url,

            json=payload,

            timeout=10

        )



        data = response.json()



        if data.get(
            "ok",
            False
        ):


            logger.info(
                "Telegram sent"
            )

            return True



        logger.error(
            "Telegram error: %s",
            data
        )


        return False



    except Exception as e:


        logger.error(
            "Telegram exception: %s",
            e
        )


        return False

# ============================================================
# DOMAIN FILTER
# ============================================================

BLOCKED_DOMAINS = {

    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",

    "instagram.com",
    "www.instagram.com",

    "x.com",
    "twitter.com",

    "t.me",
    "telegram.me",

    "youtube.com",
    "www.youtube.com",

    "bing.com",
    "www.bing.com",

    "google.com",
    "www.google.com"

}


def get_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        if "@" in domain:
            domain = domain.split("@")[-1]

        if ":" in domain:
            domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""



def is_blocked_domain(url):

    domain = get_domain(url)

    if not domain:
        return True

    if domain in BLOCKED_DOMAINS:
        return True

    for item in BLOCKED_DOMAINS:

        item = item.lower()

        if domain.endswith(
            "." + item
        ):
            return True

    return False


# ============================================================
# TRUSTED MYANMAR / INTERNATIONAL SOURCES
# ============================================================

TRUSTED_DOMAINS = {

    # Myanmar official
    "gov.mm",
    "moi.gov.mm",
    "mdn.gov.mm",
    "mrtv.gov.mm",

    # Myanmar news
    "mizzima.com",
    "irrawaddy.com",
    "myanmar-now.org",
    "elevenmyanmar.com",
    "gnlm.com.mm",
    "burmese.dvb.no",

    # International
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "apnews.com",
    "who.int",
    "un.org"

}


def source_trust_score(url):

    domain = get_domain(url)

    if not domain:
        return 0.0

    if domain in TRUSTED_DOMAINS:
        return 1.0

    if domain.endswith(
        ".gov.mm"
    ):
        return 0.9

    if domain.endswith(
        ".edu.mm"
    ):
        return 0.8

    if domain.endswith(
        ".edu"
    ):
        return 0.7

    if domain.endswith(
        ".mm"
    ):
        return 0.5

    return 0.2


# ============================================================
# MYANMAR LOCATION / NEWS KEYWORDS
# ============================================================

MYANMAR_KEYWORDS = [

    "မြန်မာ",
    "မြန်မာနိုင်ငံ",

    "ရန်ကုန်",
    "မန္တလေး",
    "နေပြည်တော်",

    "ပဲခူး",
    "ဧရာဝတီ",
    "မကွေး",
    "စစ်ကိုင်း",
    "တနင်္သာရီ",
    "မွန်",
    "ကရင်",
    "ကချင်",
    "ချင်း",
    "ရခိုင်",
    "ရှမ်း",
    "ကယား",

    "လေးမျက်နှာ",
    "လေးမျက်နှာမြို့",

    "ရေကြီး",
    "ရေဘေး",
    "ရေလွှမ်း",
    "ရေလွှမ်းမိုး",

    "မိုးသည်း",
    "မိုးရွာ",
    "မုန်တိုင်း",

    "သတင်း",
    "သတင်းစာ",
    "သတင်းဌာန",

    "flood",
    "flooding",
    "flash flood",
    "Myanmar",
    "Myanmar flood",
    "Myanmar news"

]


MYANMAR_SOURCE_HINTS = [

    "myanmar",
    "burma",
    "မြန်မာ",
    ".mm"

]


# ============================================================
# TEXT TOKENIZER
# ============================================================

def tokenize_text(text):

    text = clean_text(
        text
    ).lower()

    if not text:
        return []

    # Keep Myanmar Unicode characters,
    # English characters and numbers.

    tokens = re.findall(
        r"[\u1000-\u109F]+|[a-zA-Z0-9]+",
        text
    )

    return [
        token
        for token in tokens
        if len(token) >= 2
    ]


# ============================================================
# RELEVANCE SCORING
# ============================================================

def calculate_relevance(
    claim,
    result
):

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

    url = clean_text(
        result.get(
            "url",
            ""
        )
    )

    source = clean_text(
        result.get(
            "source",
            ""
        )
    )

    source_text = clean_text(
        result.get(
            "source_text",
            ""
        )
    )

    combined = (
        title
        + " "
        + snippet
        + " "
        + url
        + " "
        + source
        + " "
        + source_text
    ).lower()


    claim_lower = (
        clean_text(
            claim
        ).lower()
    )


    score = 0.0


    # --------------------------------------------------------
    # Exact claim phrase
    # --------------------------------------------------------

    if (
        claim_lower
        and claim_lower in combined
    ):

        score += 10.0


    # --------------------------------------------------------
    # Claim tokens
    # --------------------------------------------------------

    claim_tokens = tokenize_text(
        claim
    )


    combined_tokens = set(
        tokenize_text(
            combined
        )
    )


    matched = 0


    for token in claim_tokens:

        if token in combined_tokens:

            matched += 1


    if claim_tokens:

        token_ratio = (
            matched
            / len(claim_tokens)
        )

        score += (
            token_ratio * 8.0
        )


    # --------------------------------------------------------
    # Myanmar relevance
    # --------------------------------------------------------

    myanmar_matches = 0


    for keyword in MYANMAR_KEYWORDS:

        if keyword.lower() in combined:

            myanmar_matches += 1


    score += min(
        myanmar_matches * 1.5,
        6.0
    )


    # --------------------------------------------------------
    # Trusted source bonus
    # --------------------------------------------------------

    trust = source_trust_score(
        url
    )


    score += (
        trust * 4.0
    )


    # --------------------------------------------------------
    # Myanmar source bonus
    # --------------------------------------------------------

    domain = get_domain(
        url
    )


    if (
        domain.endswith(".mm")
        or domain in TRUSTED_DOMAINS
    ):

        score += 2.0


    # --------------------------------------------------------
    # Blocked domain
    # --------------------------------------------------------

    if is_blocked_domain(
        url
    ):

        return -100.0


    return score


# ============================================================
# RESULT VALIDATION
# ============================================================

def is_relevant_result(
    claim,
    result,
    minimum_score=2.5
):

    if not result:
        return False


    url = result.get(
        "url",
        ""
    )


    if not url:
        return False


    if is_blocked_domain(
        url
    ):

        return False


    score = calculate_relevance(
        claim,
        result
    )


    return score >= minimum_score


# ============================================================
# SOURCE NAME
# ============================================================

def source_name(url):

    domain = get_domain(
        url
    )

    if not domain:
        return "Unknown"


    source_map = {

        "moi.gov.mm":
            "Myanmar Ministry of Information",

        "mdn.gov.mm":
            "Myanmar Digital News",

        "mrtv.gov.mm":
            "MRTV",

        "mizzima.com":
            "Mizzima",

        "irrawaddy.com":
            "The Irrawaddy",

        "myanmar-now.org":
            "Myanmar Now",

        "elevenmyanmar.com":
            "Eleven Media",

        "gnlm.com.mm":
            "Global New Light of Myanmar",

        "burmese.dvb.no":
            "DVB",

        "bbc.com":
            "BBC",

        "bbc.co.uk":
            "BBC",

        "reuters.com":
            "Reuters",

        "apnews.com":
            "AP News",

        "who.int":
            "WHO",

        "un.org":
            "United Nations"

    }


    if domain in source_map:

        return source_map[
            domain
        ]


    return domain


# ============================================================
# RESULT BUILDER
# ============================================================

def make_result(
    title,
    url,
    snippet="",
    source=""
):

    title = clean_text(
        title
    )

    url = clean_text(
        url
    )

    snippet = clean_text(
        snippet
    )


    if not title or not url:

        return None


    if is_blocked_domain(
        url
    ):

        return None


    if not source:

        source = source_name(
            url
        )


    return {

        "title":
            title,

        "url":
            url,

        "snippet":
            snippet,

        "source":
            source,

        "domain":
            get_domain(
                url
            ),

        "trust":
            source_trust_score(
                url
            )

    }


# ============================================================
# SOURCE CONTENT EXTRACTION
# ============================================================

def extract_source_content(url):
    """Fetch readable article text from a trusted destination URL."""
    if not url or is_blocked_domain(url) or source_trust_score(url) < 0.5:
        return ""
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        final_url = response.url or url
        if response.status_code != 200 or is_blocked_domain(final_url):
            return ""
        if source_trust_score(final_url) < 0.5:
            return ""
        content_type = response.headers.get("Content-Type", "")
        if content_type and "html" not in content_type.lower():
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
            tag.decompose()
        candidates = []
        for selector in ["article", "main", ".article-content", ".entry-content", ".post-content", ".content", "[itemprop='articleBody']"]:
            for node in soup.select(selector):
                text = clean_text(node.get_text(" ", strip=True))
                if len(text) > 200:
                    candidates.append(text)
        text = max(candidates, key=len) if candidates else clean_text(soup.get_text(" ", strip=True))
        return text[:30000]
    except Exception as e:
        logger.debug("Source extraction failed for %s: %s", url, e)
        return ""

def enrich_result_with_source(result):
    if not result:
        return None
    text = extract_source_content(result.get("url", ""))
    if not text:
        return None
    result = dict(result)
    result["source_text"] = text
    result["snippet"] = clean_text(result.get("snippet", "") + " " + text[:1800])
    return result


# ============================================================
# BING URL DECODER
# ============================================================

def decode_bing_url(url):

    if not url:

        return ""


    if (
        "bing.com/ck/a"
        not in url.lower()
    ):

        return url


    try:

        parsed = urlparse(
            url
        )


        params = parse_qs(
            parsed.query
        )


        encoded = params.get(
            "u",
            [""]
        )[0]


        if not encoded:

            return ""


        if encoded.startswith(
            "a1"
        ):

            encoded = encoded[2:]


        padding = (
            "="
            * (
                4
                - len(encoded) % 4
            ) % 4
        )


        decoded = (
            base64.urlsafe_b64decode(
                encoded
                + padding
            )
            .decode(
                "utf-8",
                errors="ignore"
            )
        )


        if decoded.startswith(
            "http://"
        ) or decoded.startswith(
            "https://"
        ):

            return decoded


    except Exception as e:

        logger.debug(
            "Bing URL decode failed: %s",
            e
        )


    return ""

# ============================================================
# SEARCH ENGINE FUNCTIONS
# ============================================================


def search_bing(
    query,
    max_results=10
):

    results = []


    try:

        search_url = (
            "https://www.bing.com/search?q="
            + quote_plus(query)
        )


        response = session.get(
            search_url,
            timeout=REQUEST_TIMEOUT
        )


        if response.status_code != 200:

            logger.warning(
                "Bing returned HTTP %s",
                response.status_code
            )

            return results


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        for item in soup.select(
            "li.b_algo"
        ):

            link = item.select_one(
                "h2 a"
            )


            if not link:

                continue


            title = link.get_text(
                " ",
                strip=True
            )


            href = link.get(
                "href",
                ""
            ).strip()


            if not href:

                continue


            # --------------------------------------------
            # Decode Bing redirect URL
            # --------------------------------------------

            if (
                "bing.com/ck/a"
                in href.lower()
            ):

                real_url = (
                    decode_bing_url(
                        href
                    )
                )


                if real_url:

                    href = real_url

                else:

                    continue


            # --------------------------------------------
            # Never use Bing itself as evidence
            # --------------------------------------------

            if (
                get_domain(href)
                in {
                    "bing.com",
                    "www.bing.com"
                }
            ):

                continue


            # --------------------------------------------
            # Block social media
            # --------------------------------------------

            if is_blocked_domain(
                href
            ):

                continue


            snippet_el = item.select_one(
                ".b_caption p"
            )


            snippet = ""


            if snippet_el:

                snippet = snippet_el.get_text(
                    " ",
                    strip=True
                )


            result = make_result(
                title=title,
                url=href,
                snippet=snippet,
                source=source_name(
                    href
                )
            )


            if result:

                results.append(
                    result
                )


            if len(results) >= max_results:

                break


    except Exception as e:

        logger.warning(
            "Bing search failed: %s",
            e
        )


    return results


# ============================================================
# GOOGLE NEWS RSS
# ============================================================


def search_google_news(
    query,
    max_results=10
):

    results = []


    try:

        rss_url = (
            "https://news.google.com/rss/search?"
            "q="
            + quote_plus(query)
            + "&hl=en-US&gl=US&ceid=US:en"
        )


        feed = feedparser.parse(
            rss_url
        )


        for entry in feed.entries:

            title = clean_text(
                entry.get(
                    "title",
                    ""
                )
            )


            url = clean_text(
                entry.get(
                    "link",
                    ""
                )
            )


            if not title or not url:

                continue


            # Google News can sometimes provide
            # Google redirect links.
            #
            # Follow the redirect safely.

            try:

                parsed = urlparse(
                    url
                )


                if (
                    parsed.netloc
                    and
                    "news.google.com"
                    in parsed.netloc.lower()
                ):

                    response = session.get(
                        url,
                        timeout=10,
                        allow_redirects=True
                    )

                    final_url = (
                        response.url
                    )


                    if final_url:

                        url = final_url

            except Exception:

                pass


            if is_blocked_domain(
                url
            ):

                continue


            snippet = clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )


            result = make_result(
                title=title,
                url=url,
                snippet=snippet,
                source=source_name(
                    url
                )
            )


            if result:

                results.append(
                    result
                )


            if len(results) >= max_results:

                break


    except Exception as e:

        logger.warning(
            "Google News search failed: %s",
            e
        )


    return results


# ============================================================
# DUCKDUCKGO HTML SEARCH
# ============================================================


def search_duckduckgo(
    query,
    max_results=10
):

    results = []


    try:

        search_url = (
            "https://html.duckduckgo.com/html/?q="
            + quote_plus(query)
        )


        response = session.get(
            search_url,
            timeout=REQUEST_TIMEOUT
        )


        if response.status_code != 200:

            return results


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        items = soup.select(
            ".result"
        )


        for item in items:

            link = item.select_one(
                ".result__a"
            )


            if not link:

                continue


            title = link.get_text(
                " ",
                strip=True
            )


            url = link.get(
                "href",
                ""
            ).strip()


            if not url:

                continue


            # --------------------------------------------
            # DDG may return redirect URL
            # --------------------------------------------

            try:

                parsed = urlparse(
                    url
                )


                if (
                    "duckduckgo.com"
                    in parsed.netloc.lower()
                ):

                    params = parse_qs(
                        parsed.query
                    )


                    real_url = params.get(
                        "uddg",
                        [""]
                    )[0]


                    if real_url:

                        url = real_url

            except Exception:

                pass


            if is_blocked_domain(
                url
            ):

                continue


            snippet_el = item.select_one(
                ".result__snippet"
            )


            snippet = ""


            if snippet_el:

                snippet = snippet_el.get_text(
                    " ",
                    strip=True
                )


            result = make_result(
                title=title,
                url=url,
                snippet=snippet,
                source=source_name(
                    url
                )
            )


            if result:

                results.append(
                    result
                )


            if len(results) >= max_results:

                break


    except Exception as e:

        logger.warning(
            "DuckDuckGo search failed: %s",
            e
        )


    return results


# ============================================================
# SEARCH QUERY GENERATOR
# ============================================================


def generate_search_queries(
    claim
):

    claim = clean_text(
        claim
    )


    if not claim:

        return []


    queries = [

        # Exact Myanmar claim
        f'"{claim}"',

        # Myanmar news
        f'{claim} သတင်း',

        f'{claim} သတင်းဌာန',

        # Event-specific
        f'{claim} ရေကြီး',

        f'{claim} ရေဘေး',

        f'{claim} ရေလွှမ်း',

        # Myanmar + English
        f'{claim} Myanmar',

        f'{claim} Myanmar news',

        f'{claim} flood',

        f'{claim} flooding',

        # Myanmar official source
        f'site:gov.mm {claim}',

        f'site:moi.gov.mm {claim}',

        f'site:mrtv.gov.mm {claim}',

        # Myanmar news organizations
        f'site:mizzima.com {claim}',

        f'site:irrawaddy.com {claim}',

        f'site:myanmar-now.org {claim}',

        f'site:burmese.dvb.no {claim}',

        f'site:elevenmyanmar.com {claim}'

    ]


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


        seen.add(key)

        final_queries.append(
            query
        )


    return final_queries


# ============================================================
# RESULT DEDUPLICATION
# ============================================================


def normalize_url(
    url
):

    try:

        parsed = urlparse(
            url
        )


        scheme = (
            parsed.scheme
            or "https"
        ).lower()


        domain = (
            parsed.netloc
            .lower()
        )


        if domain.startswith(
            "www."
        ):

            domain = domain[4:]


        path = (
            parsed.path
            or "/"
        ).rstrip("/")


        return (
            scheme
            + "://"
            + domain
            + path
        )


    except Exception:

        return url


def deduplicate_results(
    results
):

    unique = {}

    for result in results:

        url = result.get(
            "url",
            ""
        )


        if not url:

            continue


        key = normalize_url(
            url
        )


        if key not in unique:

            unique[key] = result


        else:

            old = unique[key]


            # Keep the result with
            # the longer / better snippet.

            old_snippet = clean_text(
                old.get(
                    "snippet",
                    ""
                )
            )


            new_snippet = clean_text(
                result.get(
                    "snippet",
                    ""
                )
            )


            if len(new_snippet) > len(
                old_snippet
            ):

                unique[key] = result


    return list(
        unique.values()
    )


# ============================================================
# SEARCH ALL SOURCES
# ============================================================


def search_all_sources(
    claim,
    max_results=20
):
    """Use search engines for discovery, then check every trusted source page."""
    all_results = []
    queries = generate_search_queries(claim)[:12]

    for query in queries:
        logger.info("Searching: %s", query)
        all_results.extend(search_google_news(query, max_results=8))
        all_results.extend(search_duckduckgo(query, max_results=8))
        if len(all_results) >= max_results * 4:
            break

    all_results = deduplicate_results(all_results)
    trusted_candidates = []
    for result in all_results:
        url = result.get("url", "")
        domain = get_domain(url)
        if is_blocked_domain(url):
            continue
        if source_trust_score(url) < 0.5:
            continue
        if domain not in TRUSTED_DOMAINS and not domain.endswith(".gov.mm"):
            continue
        trusted_candidates.append(result)

    logger.info("Trusted candidates discovered: %d", len(trusted_candidates))
    checked_results = []
    for index, result in enumerate(trusted_candidates, start=1):
        logger.info("Checking trusted source %d/%d: %s", index, len(trusted_candidates), result.get("url", ""))
        enriched = enrich_result_with_source(result)
        if not enriched:
            logger.info("Unreadable source skipped: %s", result.get("url", ""))
            continue
        score = calculate_relevance(claim, enriched)
        if score < 2.5:
            continue
        enriched["relevance_score"] = round(score, 3)
        enriched["trust"] = source_trust_score(enriched.get("url", ""))
        checked_results.append(enriched)

    checked_results.sort(key=lambda item: (item.get("relevance_score", 0), item.get("trust", 0)), reverse=True)
    final_results = []
    for item in checked_results[:max_results]:
        clean_item = dict(item)
        clean_item.pop("source_text", None)
        final_results.append(clean_item)
    logger.info("Final trusted readable evidence: %d", len(final_results))
    return final_results


# ============================================================
# EVIDENCE DIRECTION
# ============================================================


def determine_direction(
    claim,
    result
):

    text = (

        clean_text(
            result.get(
                "title",
                ""
            )
        )
        + " "
        +
        clean_text(
            result.get(
                "snippet",
                ""
            )
        )

    ).lower()


    positive_words = [

        "confirmed",
        "confirm",
        "reported",
        "flood",
        "flooding",
        "ရေကြီး",
        "ရေဘေး",
        "ရေလွှမ်း",
        "ဖြစ်ပွား",
        "ဖြစ်နေ",
        "ဖြစ်ခဲ့",
        "အတည်ပြု"

    ]


    negative_words = [

        "false",
        "fake",
        "hoax",
        "denied",
        "not true",
        "မဟုတ်",
        "သတင်းမှား",
        "ငြင်းဆို",
        "မမှန်"

    ]


    positive = 0

    negative = 0


    for word in positive_words:

        if word in text:

            positive += 1


    for word in negative_words:

        if word in text:

            negative += 1


    if (
        negative > positive
        and negative > 0
    ):

        return "negative"


    if (
        positive > negative
        and positive > 0
    ):

        return "positive"


    return "neutral"

# ============================================================
# VERIFICATION ENGINE
# ============================================================


def calculate_confidence(
    evidence
):

    if not evidence:

        return 0.0


    total_weight = 0.0

    positive_weight = 0.0

    negative_weight = 0.0


    for item in evidence:

        trust = float(
            item.get(
                "trust",
                0.2
            )
        )


        relevance = float(
            item.get(
                "relevance_score",
                0
            )
        )


        # Normalize relevance.
        relevance_factor = min(
            relevance / 10.0,
            1.0
        )


        weight = (
            0.35 * trust
            +
            0.65 * relevance_factor
        )


        # Never allow zero weight.
        weight = max(
            weight,
            0.05
        )


        direction = item.get(
            "direction",
            "neutral"
        )


        total_weight += weight


        if direction == "positive":

            positive_weight += weight


        elif direction == "negative":

            negative_weight += weight


    if total_weight <= 0:

        return 0.0


    dominant_weight = max(
        positive_weight,
        negative_weight
    )


    confidence = (
        dominant_weight
        /
        total_weight
    )


    return round(
        confidence * 100,
        1
    )


# ============================================================
# VERIFICATION STATUS
# ============================================================


def determine_verification_status(
    evidence,
    confidence
):

    if not evidence:

        return (
            "UNVERIFIED",
            "No relevant evidence sources found."
        )


    positive = 0

    negative = 0


    for item in evidence:

        direction = item.get(
            "direction",
            "neutral"
        )


        if direction == "positive":

            positive += 1


        elif direction == "negative":

            negative += 1


    # --------------------------------------------------------
    # Strong negative evidence
    # --------------------------------------------------------

    if (
        negative >= 2
        and
        negative > positive
        and
        confidence >= 60
    ):

        return (
            "FALSE / DISPUTED",
            "Multiple relevant sources contradict the claim."
        )


    # --------------------------------------------------------
    # Strong positive evidence
    # --------------------------------------------------------

    if (
        positive >= 2
        and
        positive > negative
        and
        confidence >= 60
    ):

        return (
            "VERIFIED",
            "Multiple relevant sources support the claim."
        )


    # --------------------------------------------------------
    # One strong source
    # --------------------------------------------------------

    if (
        len(evidence) >= 1
        and
        confidence >= 75
    ):

        if positive > negative:

            return (
                "SUPPORTED",
                "Strong relevant evidence supports the claim."
            )


        if negative > positive:

            return (
                "DISPUTED",
                "Strong relevant evidence contradicts the claim."
            )


    # --------------------------------------------------------
    # Weak evidence
    # --------------------------------------------------------

    return (
        "UNVERIFIED",
        "Relevant evidence exists, but it is not strong enough for verification."
    )


# ============================================================
# MAIN CLAIM VERIFICATION
# ============================================================


def verify_claim(
    claim
):

    claim = clean_text(
        claim
    )


    if not claim:

        return {

            "claim":
                "",

            "status":
                "UNVERIFIED",

            "confidence":
                0.0,

            "reason":
                "Claim is empty.",

            "evidence":
                []

        }


    logger.info(
        "Starting verification: %s",
        claim
    )


    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    evidence = search_all_sources(
        claim,
        max_results=20
    )


    # --------------------------------------------------------
    # Determine evidence direction
    # --------------------------------------------------------

    final_evidence = []


    for item in evidence:

        item = dict(
            item
        )


        item[
            "direction"
        ] = determine_direction(
            claim,
            item
        )


        final_evidence.append(
            item
        )


    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = calculate_confidence(
        final_evidence
    )


    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status, reason = (
        determine_verification_status(
            final_evidence,
            confidence
        )
    )


    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {

        "claim":
            claim,

        "status":
            status,

        "confidence":
            confidence,

        "reason":
            reason,

        "evidence":
            final_evidence,

        "checked_at":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    }


    # --------------------------------------------------------
    # Save history
    # --------------------------------------------------------

    save_verification_history(
        result
    )


    return result


# ============================================================
# DATABASE SAVE
# ============================================================


def save_verification_history(
    result
):

    try:

        conn = sqlite3.connect(
            DB_FILE
        )


        cursor = conn.cursor()


        evidence_json = json.dumps(
            result.get(
                "evidence",
                []
            ),
            ensure_ascii=False
        )


        cursor.execute(
            """

            INSERT INTO
            verification_history
            (
                claim,
                result,
                confidence,
                evidence,
                created_at
            )

            VALUES (?, ?, ?, ?, ?)

            """,

            (

                result.get(
                    "claim",
                    ""
                ),

                result.get(
                    "status",
                    "UNVERIFIED"
                ),

                result.get(
                    "confidence",
                    0
                ),

                evidence_json,

                result.get(
                    "checked_at",
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

            )

        )


        conn.commit()

        conn.close()


    except Exception as e:

        logger.error(
            "Database save failed: %s",
            e
        )


# ============================================================
# TELEGRAM REPORT FORMATTER
# ============================================================


def escape_html(
    text
):

    text = str(
        text or ""
    )


    return (
        text
        .replace(
            "&",
            "&amp;"
        )
        .replace(
            "<",
            "&lt;"
        )
        .replace(
            ">",
            "&gt;"
        )
    )


def build_telegram_report(
    result
):

    claim = escape_html(
        result.get(
            "claim",
            ""
        )
    )


    status = escape_html(
        result.get(
            "status",
            "UNVERIFIED"
        )
    )


    confidence = result.get(
        "confidence",
        0
    )


    reason = escape_html(
        result.get(
            "reason",
            ""
        )
    )


    checked_at = escape_html(
        result.get(
            "checked_at",
            ""
        )
    )


    lines = []


    lines.append(
        "<b>🇲🇲 Myanmar News Verification</b>"
    )


    lines.append("")


    lines.append(
        "<b>Claim:</b>"
    )


    lines.append(
        claim
    )


    lines.append("")


    lines.append(
        f"<b>Result:</b> {status}"
    )


    lines.append(
        f"<b>Confidence:</b> {confidence}%"
    )


    lines.append(
        f"<b>Reason:</b> {reason}"
    )


    lines.append(
        f"<b>Checked:</b> {checked_at}"
    )


    lines.append("")


    evidence = result.get(
        "evidence",
        []
    )


    if evidence:

        lines.append(
            "<b>Evidence Sources</b>"
        )


        for index, item in enumerate(
            evidence[:10],
            start=1
        ):

            title = escape_html(
                item.get(
                    "title",
                    "Untitled"
                )
            )


            url = item.get(
                "url",
                ""
            )


            source = escape_html(
                item.get(
                    "source",
                    ""
                )
            )


            direction = escape_html(
                item.get(
                    "direction",
                    "neutral"
                )
            )


            trust = item.get(
                "trust",
                0
            )


            lines.append("")


            lines.append(
                f"<b>{index}. {title}</b>"
            )


            lines.append(
                f"{source} | {direction}"
            )


            lines.append(
                f"Trust: {round(trust, 2)}"
            )


            if url:

                safe_url = escape_html(
                    url
                )


                lines.append(
                    safe_url
                )


    else:

        lines.append(
            "<b>No evidence sources found.</b>"
        )


    return "\n".join(
        lines
    )


# ============================================================
# SEND VERIFICATION TO TELEGRAM
# ============================================================


def send_verification_to_telegram(
    result
):

    message = build_telegram_report(
        result
    )


    return send_telegram(
        message
    )

# ============================================================
# TELEGRAM REPORT
# ============================================================

def create_telegram_report(data):

    claim = escape_html(
        data.get("claim", "")
    )

    result = escape_html(
        data.get("result", "UNVERIFIED")
    )

    confidence = float(
        data.get("confidence_percent", data.get("confidence", 0))
        or 0
    )
    if confidence <= 1:
        confidence *= 100

    evidence = data.get(
        "evidence",
        []
    )


    lines = [

        "📰 <b>MYANMAR NEWS VERIFICATION</b>",

        "",

        "<b>Claim:</b>",

        claim,

        "",

        f"<b>Result:</b> {result}",

        (
            f"<b>Confidence:</b> "
            f"{confidence:.1f}%"
        ),

        "",

        (
            f"<b>Evidence:</b> "
            f"{len(evidence)} sources"
        ),

        ""
    ]


    if evidence:

        lines.append(
            "<b>Top Sources:</b>"
        )


        for i, item in enumerate(
            evidence[:5],
            start=1
        ):

            title = escape_html(
                item.get(
                    "title",
                    "Untitled"
                )
            )

            source = escape_html(
                item.get(
                    "source",
                    ""
                )
            )

            url = item.get(
                "url",
                ""
            )


            if url:

                safe_url = (
                    url
                    .replace("&", "&amp;")
                    .replace('"', "&quot;")
                )

                lines.append(
                    f'{i}. <a href="{safe_url}">'
                    f'{title}</a>'
                )

            else:

                lines.append(
                    f"{i}. {title}"
                )


            if source:

                lines.append(
                    f"   <i>{source}</i>"
                )


            lines.append("")


    lines.append(
        "🤖 <i>Myanmar News Verification System</i>"
    )


    return "\n".join(lines)



# ============================================================
# API - VERIFY
# ============================================================

@app.route(
    "/api/verify",
    methods=["POST"]
)
def api_verify():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success": False,

                "error":
                    "JSON data is required"

            }), 400


        claim = clean_text(
            data.get(
                "claim",
                ""
            )
        )


        if not claim:

            return jsonify({

                "success": False,

                "error":
                    "Please enter a news claim"

            }), 400


        logger.info(
            "Verification request: %s",
            claim
        )


        # ----------------------------------------------------
        # IMPORTANT
        #
        # ----------------------------------------------------

        verification = verify_claim(
            claim
        )


        if not isinstance(
            verification,
            dict
        ):

            verification = {

                "success": True,

                "claim": claim,

                "result":
                    "UNVERIFIED",

                "confidence":
                    0,

                "evidence": []

            }


        verification[
            "claim"
        ] = claim


        evidence = verification.get(
            "evidence",
            []
        )


        verification[
            "evidence_count"
        ] = len(evidence)


        # ----------------------------------------------------
        # SAVE TO DATABASE
        # ----------------------------------------------------

        try:

            conn = sqlite3.connect(
                DB_FILE
            )

            cursor = conn.cursor()


            cursor.execute(
                """
                INSERT INTO
                verification_history
                (
                    claim,
                    result,
                    confidence,
                    evidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    claim,

                    verification.get(
                        "result",
                        "UNVERIFIED"
                    ),

                    float(
                        verification.get(
                            "confidence",
                            0
                        )
                        or 0
                    ),

                    json.dumps(
                        evidence,
                        ensure_ascii=False
                    ),

                    datetime.now().isoformat(
                        timespec="seconds"
                    )
                )
            )


            conn.commit()
            conn.close()


        except Exception as e:

            logger.error(
                "Database save error: %s",
                e
            )


        # ----------------------------------------------------
        # TELEGRAM
        #
        # Verify လုပ်တာနဲ့ Telegram ပို့မယ်
        # ----------------------------------------------------

        telegram_sent = False


        if telegram_enabled():

            telegram_message = (
                create_telegram_report(
                    verification
                )
            )


            telegram_sent = (
                send_telegram(
                    telegram_message
                )
            )


        else:

            logger.warning(
                "Telegram is not configured"
            )


        verification[
            "telegram_sent"
        ] = telegram_sent

        confidence_percent = float(verification.get("confidence", 0) or 0)
        verification["success"] = True
        verification["result"] = verification.get("status", "UNVERIFIED")
        verification["confidence_percent"] = confidence_percent
        verification["confidence"] = confidence_percent / 100.0
        verification["evidence_count"] = len(verification.get("evidence", []))
        verification["telegram_error"] = (
            "Telegram is not configured. Check .env."
            if not telegram_enabled()
            else ("Telegram message failed." if not telegram_sent else "")
        )

        return jsonify(
            verification
        )


    except Exception as e:

        logger.exception(
            "Verification API error"
        )


        return jsonify({

            "success": False,

            "error":
                str(e),

            "telegram_sent":
                False

        }), 500



# ============================================================
# API - TELEGRAM TEST
# ============================================================

@app.route(
    "/api/telegram/test",
    methods=["GET", "POST"]
)
def telegram_test():

    if not telegram_enabled():

        return jsonify({

            "success": False,

            "sent": False,

            "error":
                (
                    "Telegram is not configured. "
                    "Check TELEGRAM_BOT_TOKEN "
                    "and TELEGRAM_CHAT_ID."
                )

        }), 400


    message = (
        "<b>🤖 Telegram Test</b>\n\n"
        "Myanmar News Verification System "
        "Telegram connection is working."
    )


    sent = send_telegram(
        message
    )


    return jsonify({

        "success":
            sent,

        "sent":
            sent,

        "message":
            (
                "Telegram message sent successfully."
                if sent
                else
                "Telegram message failed."
            )

    })

# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )

# ============================================================
# API - HISTORY
# ============================================================

@app.route(
    "/api/history",
    methods=["GET"]
)
def api_history():

    try:

        limit = request.args.get(
            "limit",
            "20"
        )


        try:

            limit = int(
                limit
            )

        except Exception:

            limit = 20


        limit = max(
            1,
            min(
                limit,
                100
            )
        )


        conn = sqlite3.connect(
            DB_FILE
        )

        conn.row_factory = sqlite3.Row


        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT
                id,
                claim,
                result,
                confidence,
                evidence,
                created_at
            FROM verification_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )


        rows = cursor.fetchall()


        conn.close()


        history = []


        for row in rows:

            try:

                evidence = json.loads(
                    row["evidence"]
                    or "[]"
                )

            except Exception:

                evidence = []


            history.append({

                "id":
                    row["id"],

                "claim":
                    row["claim"],

                "result":
                    row["result"],

                "confidence":
                    row["confidence"],

                "evidence":
                    evidence,

                "created_at":
                    row["created_at"]

            })


        return jsonify({

            "success": True,

            "history": history

        })


    except Exception as e:

        logger.exception(
            "History error"
        )


        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500



# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "success": False,

            "error":
                "API endpoint not found"

        }), 404


    return (
        "Page not found",
        404
    )



@app.errorhandler(500)
def internal_error(error):

    logger.exception(
        "Internal server error"
    )


    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "success": False,

            "error":
                "Internal server error"

        }), 500


    return (
        "Internal server error",
        500
    )



# ============================================================
# STARTUP CHECK
# ============================================================

def check_startup():

    print()
    print("=" * 60)

    print(
        "🇲🇲 Myanmar News Verification System"
    )

    print("=" * 60)


    print(
        f"Database: {DB_FILE}"
    )


    if telegram_enabled():

        print(
            "Telegram: CONFIGURED"
        )

    else:

        print(
            "Telegram: NOT CONFIGURED"
        )

        print(
            "Set TELEGRAM_BOT_TOKEN "
            "and TELEGRAM_CHAT_ID in .env"
        )


    print("=" * 60)
    print()



# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    check_startup()


    print(
        "Starting server..."
    )


    print(
        "Open in browser:"
    )


    print(
        "http://127.0.0.1:5000"
    )


    print()


    app.run(

        host="0.0.0.0",

        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        ),

        debug=False

    )