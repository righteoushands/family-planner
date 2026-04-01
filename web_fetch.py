"""
web_fetch.py — Fetch and extract readable text from URLs for Lucy.

Usage:
    urls   = extract_urls(user_message)
    chunks = fetch_urls(urls, max_chars=6000)
    # chunks is a list of (url, text_or_error) tuples
"""

import re
import urllib.request
import html
from html.parser import HTMLParser

# Max characters to include per page in Lucy's context
_PER_URL_MAX = 5000
# Timeout for fetching
_TIMEOUT = 12

_URL_RE = re.compile(
    r'https?://[^\s\)\]\'"<>]+',
    re.IGNORECASE
)


def extract_urls(text: str) -> list:
    """Return list of unique URLs found in text."""
    return list(dict.fromkeys(_URL_RE.findall(text)))


class _TextExtractor(HTMLParser):
    """
    Minimal HTML → plain text extractor.
    Strips script/style blocks; collapses whitespace.
    """
    _SKIP = {"script", "style", "head", "noscript", "nav", "footer", "form"}

    def __init__(self):
        super().__init__()
        self._buf = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag.lower() in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "div"):
            if not self._skip_depth:
                self._buf.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self._buf.append(data)

    def get_text(self) -> str:
        raw = "".join(self._buf)
        raw = html.unescape(raw)
        # Collapse runs of whitespace / blank lines
        lines = [l.strip() for l in raw.splitlines()]
        lines = [l for l in lines if l]
        return "\n".join(lines)


def _fetch_one(url: str, max_chars: int = _PER_URL_MAX) -> str:
    """
    Fetch a single URL and return cleaned plain text, or an error string.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; FamilyDashboard/1.0)"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(300_000)  # max 300 KB
        # Detect encoding
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            html_text = raw.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html_text = raw.decode("utf-8", errors="replace")

        # Extract text
        parser = _TextExtractor()
        parser.feed(html_text)
        text = parser.get_text()

        if not text.strip():
            return "(Page loaded but no readable text found.)"

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n...[content trimmed at {max_chars} chars]"
        return text
    except urllib.error.HTTPError as e:
        return f"(HTTP {e.code} when fetching page)"
    except urllib.error.URLError as e:
        return f"(Could not reach page: {e.reason})"
    except Exception as e:
        return f"(Error fetching page: {e})"


def fetch_urls(urls: list, max_chars: int = _PER_URL_MAX) -> list:
    """
    Fetch each URL and return list of (url, text) tuples.
    Skips obvious non-HTML resources (pdf, zip, etc.) with a note.
    """
    results = []
    _NON_HTML_EXT = (".pdf", ".zip", ".mp3", ".mp4", ".jpg", ".jpeg",
                     ".png", ".gif", ".svg", ".doc", ".docx", ".xls")
    for url in urls:
        lower = url.lower().split("?")[0]
        if any(lower.endswith(ext) for ext in _NON_HTML_EXT):
            results.append((url, "(Non-HTML file — cannot read contents directly)"))
        else:
            results.append((url, _fetch_one(url, max_chars)))
    return results


def build_url_context(urls_with_text: list) -> str:
    """
    Format fetched URL content as a block to inject into Lucy's system prompt.
    """
    if not urls_with_text:
        return ""
    parts = ["", "== WEB PAGES FETCHED FOR THIS MESSAGE =="]
    for url, text in urls_with_text:
        parts.append(f"\n--- {url} ---")
        parts.append(text)
    parts.append("== END OF FETCHED CONTENT ==")
    return "\n".join(parts)
