"""Extract user-stated places and normalize names for Open-Meteo geocoding.

Aliases are place names only. Coordinates and weather always come from the API.
"""

import re

WEATHER_WORD = r"날씨|기온|강수(?:량)?|풍속|일기\s*예보|weather|forecast"
LEADING_CONTEXT = re.compile(
    r"^(?:(?:자비스|jarvis)[,，]?\s*|(?:혹시|그럼|그러면|지금|현재|실시간|오늘|내일|모레)\s*"
    r"|(?:이번|다음)\s*주(?:말)?\s*|(?:구글|네이버|인터넷|웹)(?:에서|으로|로)?\s*"
    r"|(?:today|tomorrow|this\s+week|next\s+week)\b\s*)",
    re.I,
)
KOREAN_CITIES = {
    "Seoul": ("서울", "서울시", "서울특별시"),
    "Busan": ("부산", "부산시", "부산광역시"),
    "Incheon": ("인천", "인천시", "인천광역시"),
    "Daegu": ("대구", "대구시", "대구광역시"),
    "Daejeon": ("대전", "대전시", "대전광역시"),
    "Gwangju": ("광주", "광주광역시"),
    "Ulsan": ("울산", "울산시", "울산광역시"),
    "Sejong": ("세종", "세종시", "세종특별자치시"),
    "Jeju": ("제주", "제주시", "제주도"),
    "Suwon": ("수원", "수원시"),
    "Seongnam": ("성남", "성남시"),
    "Yongin": ("용인", "용인시"),
    "Goyang": ("고양", "고양시"),
    "Changwon": ("창원", "창원시"),
    "Cheongju": ("청주", "청주시"),
    "Jeonju": ("전주", "전주시"),
    "Chuncheon": ("춘천", "춘천시"),
    "Gangneung": ("강릉", "강릉시"),
    "Pohang": ("포항", "포항시"),
}
COUNTRIES = {
    "KR": ("대한민국", "한국", "South Korea", "Republic of Korea", "KR"),
    "US": ("미국", "United States", "USA", "US"),
    "JP": ("일본", "Japan", "JP"),
    "CN": ("중국", "China", "CN"),
    "GB": ("영국", "United Kingdom", "UK", "GB"),
    "FR": ("프랑스", "France", "FR"),
    "DE": ("독일", "Germany", "DE"),
}


def extract_location(text):
    text = text.strip()
    command = re.match(r"^/(?:날씨|weather)\s+(.+)$", text, re.I)
    if command:
        text = command.group(1)
    # Remove request context only at the beginning, not from inside place names.
    while True:
        cleaned = LEADING_CONTEXT.sub("", text).strip()
        if cleaned == text:
            break
        text = cleaned
    parts = re.split(WEATHER_WORD, text, maxsplit=1, flags=re.I)
    place = parts[0].strip()
    if not place and len(parts) == 2:
        # Also accept 'weather in Seoul' and '날씨 서울 알려줘'.
        place = re.sub(r"^(?:in\b|for\b|는|를)\s*", "", parts[1].strip(), flags=re.I)
    place = re.split(
        r"\s*(?:알려|확인해|검색해|어때|어떻|부탁|보여|말해|조회해)", place
    )[0]
    # Do not strip a bare '로': it is part of names such as 오슬로 and 삿포로.
    place = re.sub(r"(?:에서|의|은|는|을|를)\s*$", "", place.strip())
    place = place.strip(" ,，.?!")
    if place.replace(" ", "") in (
        "",
        "여기",
        "여긴",
        "위치",
        "내위치",
        "현재위치",
        "우리동네",
        "집",
        "어디",
    ):
        return ""
    return place[:120] if len(place.split()) <= 4 else ""


def geocoding_names(location):
    """Return at most two query names and an explicit/known country filter."""
    name = re.sub(r"\s+", " ", location).strip(" ,，.?!")
    country = None
    for code, aliases in COUNTRIES.items():
        for alias in aliases:
            # Korean country names may be joined to the city; ASCII names need a boundary.
            separator = r"[\s,]*" if re.search(r"[가-힣]", alias) else r"(?:[\s,]+|$)"
            prefix = re.match(r"^" + re.escape(alias) + separator, name, re.I)
            suffix = re.search(r"[\s,]+" + re.escape(alias) + r"$", name, re.I)
            if prefix or suffix:
                name = name[prefix.end() :] if prefix else name[: suffix.start()]
                name, country = name.strip(" ,"), code
                break
        if country:
            break
    names = [name] if name else []
    for english, korean in KOREAN_CITIES.items():
        if name.casefold() in {english.casefold(), *korean}:
            country = country or "KR"
            if english.casefold() != name.casefold():
                names.append(english)
            break
    return names, country
