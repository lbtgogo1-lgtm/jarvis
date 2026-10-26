"""Bounded public-page reader. DNS is validated and pinned at TCP connection time."""

import asyncio
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

import certifi
import httpcore
import httpx
from bs4 import BeautifulSoup


class WebError(RuntimeError):
    pass


def public_url(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(ord(c) < 33 for c in value)
        or "\\" in value
    ):
        raise WebError("올바른 공개 HTTP/HTTPS 주소를 입력하세요.")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").rstrip(".").lower()
        port = parts.port
    except ValueError as error:
        raise WebError("올바르지 않은 URL입니다.") from error
    if (
        parts.scheme not in ("http", "https")
        or not host
        or parts.username is not None
        or parts.password is not None
    ):
        raise WebError("인증 정보가 없는 공개 HTTP/HTTPS 주소만 허용합니다.")
    if (
        port not in (None, 80, 443)
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal", ".lan", ".home"))
        or "." not in host
        and ":" not in host
    ):
        raise WebError("로컬·내부망 주소와 비표준 포트는 읽을 수 없습니다.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        require_global(address)
    try:
        return str(httpx.URL(value))
    except httpx.InvalidURL as error:
        raise WebError("올바르지 않은 URL입니다.") from error


def require_global(address):
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or getattr(address, "ipv4_mapped", None)
        or getattr(address, "sixtofour", None)
        or getattr(address, "teredo", None)
    ):
        raise WebError("로컬·사설·예약 IP 주소 접근이 차단되었습니다.")


async def resolve_public(host, port):
    async with asyncio.timeout(3):
        records = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses:
        raise WebError("웹사이트 주소를 확인할 수 없습니다.")
    for address in addresses:
        require_global(ipaddress.ip_address(address))
    return addresses


class PublicBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        if port not in (80, 443):
            raise WebError("허용되지 않은 포트입니다.")
        addresses = await resolve_public(host, port)
        # Passing the vetted numeric IP prevents a second DNS resolution/rebinding.
        # httpcore retains the original hostname for Host, TLS SNI and certificate checks.
        last_error = None
        for address in addresses[:4]:
            try:
                return await self.backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as error:
                last_error = error
        raise last_error

    async def connect_unix_socket(self, *args, **kwargs):
        raise WebError("로컬 소켓 접근은 허용하지 않습니다.")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


async def read_public_page(url):
    url = public_url(url)
    context = ssl.create_default_context(cafile=certifi.where())
    async with asyncio.timeout(15):
        async with httpcore.AsyncConnectionPool(
            ssl_context=context, network_backend=PublicBackend(), max_connections=2
        ) as pool:
            for redirect in range(4):
                async with pool.stream(
                    "GET",
                    url,
                    headers={
                        "User-Agent": "JARVIS-Local/1.0 (public page reader)",
                        "Accept": "text/html,text/plain",
                        "Accept-Encoding": "identity",
                    },
                    extensions={
                        "timeout": {"connect": 4, "read": 5, "write": 5, "pool": 5}
                    },
                ) as response:
                    headers = {
                        key.decode().lower(): value.decode("latin1")
                        for key, value in response.headers
                    }
                    if response.status in (301, 302, 303, 307, 308):
                        if redirect == 3 or not headers.get("location"):
                            raise WebError("페이지 이동 횟수가 너무 많습니다.")
                        url = public_url(urljoin(url, headers["location"]))
                        continue
                    if response.status != 200:
                        raise WebError(
                            f"원문 사이트가 HTTP {response.status}로 응답했습니다."
                        )
                    if not any(
                        t in headers.get("content-type", "").lower()
                        for t in ("text/html", "text/plain", "application/xhtml+xml")
                    ):
                        raise WebError("HTML·텍스트 본문만 읽을 수 있습니다.")
                    if headers.get("content-encoding", "identity") != "identity":
                        raise WebError("압축된 원문 응답은 지원하지 않습니다.")
                    body = bytearray()
                    async for chunk in response.aiter_stream():
                        body.extend(chunk)
                        if len(body) > 1_000_000:
                            raise WebError(
                                "페이지가 읽기 크기 제한(1MB)을 초과했습니다."
                            )
                    return extract_page(bytes(body), url)
    raise WebError("페이지를 읽을 수 없습니다.")


def extract_page(body, url):
    soup = BeautifulSoup(body, "html.parser")
    title = (
        soup.title.get_text(" ", strip=True)[:240]
        if soup.title
        else urlsplit(url).hostname
    )
    date = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find(
        "meta", attrs={"name": "datePublished"}
    )
    published = str(date.get("content", ""))[:80] if date else None
    for element in soup(
        ["script", "style", "nav", "footer", "header", "form", "iframe", "noscript"]
    ):
        element.decompose()
    main = soup.find("article") or soup.find("main") or soup
    text = " ".join(main.stripped_strings)[:6000]
    if not text:
        raise WebError("요약 가능한 공개 본문을 찾지 못했습니다.")
    return {
        "title": title,
        "url": url,
        "published_at": published or None,
        "event_date": None,
        "summary": text,
        "kind": "page",
    }
