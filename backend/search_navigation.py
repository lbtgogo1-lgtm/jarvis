"""Known search destinations; never turn model/web text into browser commands."""

import re
from urllib.parse import urlencode

ENGINES = {"google": "Google", "naver": "네이버"}


def search_links(query, engine=""):
    query = query.strip()[:500]
    links = []
    for selected in ([engine] if engine else ENGINES):
        if selected not in ENGINES:
            raise ValueError("Unknown search engine")
        if selected == "google":
            url = (
                "https://www.google.com/search?" + urlencode({"q": query})
                if query
                else "https://www.google.com/"
            )
        else:
            url = (
                "https://search.naver.com/search.naver?" + urlencode({"query": query})
                if query
                else "https://www.naver.com/"
            )
        links.append(
            {
                "engine": selected,
                "query": query,
                "label": ENGINES[selected] + "에서 열기",
                "url": url,
            }
        )
    return links


def browser_request(text):
    match = re.match(
        r"^\s*/?(구글|google|네이버|naver)(?:에서|으로|로|을|를)?(?:\s+|$)(.*)$",
        text,
        re.I,
    )
    if not match:
        return None
    engine = "google" if match[1].lower() in ("google", "구글") else "naver"
    body = match[2].strip()
    opening = bool(re.search(r"(?:열어|띄워)\s*(?:줘|주세요)?\s*[.!?]*$", body))
    summarize = bool(re.search(r"요약|알려|정리|설명|summari[sz]e", body, re.I))
    # Strip only a request suffix, preserving terms in the user's actual query.
    query = re.sub(
        r"\s*(?:(?:검색\s*)?(?:결과\s*)?(?:창|페이지|새\s*탭)?\s*(?:을|를)?\s*(?:열어|띄워)\s*(?:줘|주세요)?"
        r"|검색\s*(?:해\s*(?:줘|주세요)|해서\s*(?:알려\s*줘|요약\s*해\s*줘|정리\s*해\s*줘))"
        r"|(?:알려|요약해|정리해)\s*(?:줘|주세요))\s*[.!?]*$",
        "",
        body,
    ).strip()
    query = re.sub(r"^(?:검색|search)\s+", "", query, flags=re.I)
    return {
        "engine": engine,
        "query": query[:500],
        "open_only": opening and not summarize,
    }
