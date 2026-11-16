"""Bounded public-site fetching, HTML extraction, and evidence-only brochures."""
from __future__ import annotations
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_BYTES = 600_000
MAX_PAGES = 4
TIMEOUT = 8

class InputError(ValueError):
    pass

@dataclass
class Page:
    url: str
    title: str
    text: str
    links: list[str]
    fetched_at: float
    sha256: str

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title_parts = [], [], []
        self.skip = []
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.skip.append(tag)
        if self.skip:
            return
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")
    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title_parts.append(data)
        else:
            self.parts.append(data)

def normalize_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        if p.scheme.lower() not in {"http", "https"} or not p.hostname:
            raise InputError("Enter a complete http:// or https:// website URL.")
        if p.username or p.password or p.port not in {None, 80, 443}:
            raise InputError("Credentials and nonstandard ports are not allowed.")
        if (p.scheme == "http" and p.port == 443) or (p.scheme == "https" and p.port == 80):
            raise InputError("The port must match the URL scheme.")
        host = p.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if any(c in host for c in ["\\", "%", "\r", "\n"]) or ":" in host:
            raise InputError("Use a public DNS hostname or IPv4 address.")
        return urlunsplit((p.scheme.lower(), host, p.path or "/", p.query, ""))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("Invalid website URL.") from exc

def origin(url: str) -> tuple[str, str]:
    p = urlsplit(normalize_url(url))
    return p.scheme, p.netloc

def public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise InputError("Website DNS lookup failed.") from exc
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise InputError("Only publicly routable website addresses are allowed.")
    return addresses

class PublicFetcher:
    """Resolve once and pin the TCP peer; validate redirects before every request."""
    def __call__(self, url: str, allowed_origin=None) -> tuple[str, str]:
        current = normalize_url(url)
        for _ in range(4):
            if allowed_origin and origin(current) != allowed_origin:
                raise InputError("Cross-origin redirects are not allowed.")
            p = urlsplit(current)
            port = 443 if p.scheme == "https" else 80
            ip = public_addresses(p.hostname, port)[0]
            conn = http.client.HTTPConnection(p.hostname, port, timeout=TIMEOUT)
            def connect():
                peer = socket.create_connection((ip, port), timeout=TIMEOUT)
                try:
                    conn.sock = ssl.create_default_context().wrap_socket(peer, server_hostname=p.hostname) if p.scheme == "https" else peer
                except Exception:
                    peer.close()
                    raise
            conn.connect = connect
            try:
                conn.request("GET", p.path + ("?" + p.query if p.query else ""), headers={"User-Agent": "SourceBrochure/0.1 (+educational portfolio)", "Accept": "text/html"})
                response = conn.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    target = response.getheader("Location")
                    if not target:
                        raise InputError("The website returned a redirect without a destination.")
                    current = normalize_url(urljoin(current, target))
                    continue
                if response.status != 200:
                    raise InputError(f"The website returned HTTP {response.status}.")
                if "text/html" not in response.getheader("Content-Type", "").lower():
                    raise InputError("Only HTML pages are supported.")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise InputError("The page exceeds the download limit.")
                return current, raw.decode("utf-8", errors="replace")
            except (OSError, http.client.HTTPException) as exc:
                raise InputError("The website could not be fetched within the connection limits.") from exc
            finally:
                conn.close()
        raise InputError("The website redirected too many times.")

def parse_page(url: str, raw: str) -> Page:
    parser = Extractor()
    parser.feed(raw)
    paragraphs = [re.sub(r"\s+", " ", x).strip() for x in "".join(parser.parts).splitlines()]
    text = "\n".join(x for x in paragraphs if x)
    links = []
    for ref in parser.links:
        try:
            candidate = normalize_url(urljoin(url, ref))
            if origin(candidate) == origin(url) and candidate not in links:
                links.append(candidate)
        except InputError:
            continue
    return Page(url, " ".join(parser.title_parts).strip(), text[:40_000], links,
                time.time(), hashlib.sha256(raw.encode()).hexdigest())

def evidence(pages: list[Page]) -> list[dict]:
    result, seen = [], set()
    for page in pages:
        for line in page.text.splitlines():
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                sentence = sentence.strip()
                if 30 <= len(sentence) <= 500 and sentence not in seen:
                    seen.add(sentence)
                    result.append({"id": f"E{len(result)+1}", "text": sentence, "url": page.url})
                if len(result) >= 60:
                    return result
    return result

DEMO_PAGES = {
    "https://demo.example/": '<title>Nashik Studio - fictional demo</title><h1>Nashik Studio</h1><p>Nashik Studio is a fictional software company used to demonstrate this application.</p><p>The studio builds inventory tools for small businesses.</p><a href="/about">About</a><a href="/products">Products</a><a href="/careers">Careers</a>',
    "https://demo.example/about": '<title>About Nashik Studio</title><p>The fictional team works on Python APIs and accessible web interfaces.</p><p>Every company detail in this demo is synthetic and is not a claim about a real business.</p>',
    "https://demo.example/products": '<title>Products</title><p>Showroom Desk tracks vehicle inventory and customer booking requests.</p><p>Document Desk organizes internal documents for search.</p>',
    "https://demo.example/careers": '<title>Careers</title><p>The fictional studio uses code review and practical learning exercises for its team.</p>'
}

class Engine:
    def __init__(self, store, fetcher=None):
        self.store = store
        self.fetcher = fetcher or PublicFetcher()
    def run(self, company: str, url: str, *, demo=False, ai=False, refresh=False, selector=None):
        if not company.strip() or len(company) > 120:
            raise InputError("Company name must contain 1 to 120 characters.")
        company = company.strip()
        url = "https://demo.example/" if demo else normalize_url(url)
        if len(url) > 2000:
            raise InputError("Website URL is too long.")
        warnings, pages, hits = [], [], 0
        def load(target, allowed=None):
            nonlocal hits
            cache_key = ('demo:' if demo else 'live:') + target
            cached = None if refresh else self.store.cached(cache_key)
            if cached and (not allowed or origin(cached['url']) == allowed):
                hits += 1
                return Page(**cached)
            final, raw = (target, DEMO_PAGES[target]) if demo else self.fetcher(target, allowed)
            page = parse_page(final, raw)
            self.store.cache(cache_key, asdict(page))
            return page
        first = load(url)
        pages.append(first)
        ranked = sorted(first.links, key=lambda u: (-sum(term in urlsplit(u).path.lower() for term in ('about', 'product', 'service', 'career', 'team')), u))
        targets = [u for u in ranked if u != first.url and not any(x in u.lower() for x in ('privacy', 'terms', 'logout'))][:MAX_PAGES-1]
        for target in targets:
            try:
                pages.append(load(target, origin(first.url)))
            except InputError as exc:
                warnings.append(f"Skipped {target}: {exc}")
        facts = evidence(pages)
        if not facts:
            raise InputError("No usable source passages were found. This site may require JavaScript or block automated access.")
        if ai:
            if selector is None:
                raise InputError("AI mode is not configured on this server.")
            ids = selector(company, facts)
            if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
                raise InputError("The model did not return a valid evidence selection.")
            valid = {f['id'] for f in facts}
            if any(x not in valid for x in ids):
                raise InputError("The model returned unsupported evidence IDs; no brochure was saved.")
            selected = list(dict.fromkeys(ids))[:8]
        else:
            selected = [f['id'] for f in facts[:8]]
        selected_facts = [next(f for f in facts if f['id'] == i) for i in selected]
        md = '# ' + company.replace('\n', ' ') + '\n\n'
        if demo:
            md += '> Fictional demo company. All example facts are synthetic.\n\n'
        md += '## Source-backed overview\n\n'
        for f in selected_facts:
            md += f"- {f['text']} [{f['id']}]({f['url']})\n\n"
        md += '## Source notes\n\nThese excerpts reflect the fetched pages, not independently verified company facts.\n'
        run = {"company": company, "url": first.url, "mode": "ai-selected excerpts" if ai else "extractive", "demo": demo,
               "created_at": time.time(), "pages": [asdict(p) for p in pages], "evidence": facts,
               "selected_ids": selected, "markdown": md, "warnings": warnings, "cache_hits": hits}
        return self.store.save(run)
