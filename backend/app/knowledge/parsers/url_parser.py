import ipaddress
import re
import socket
import urllib.parse
import httpx
from app.knowledge.parsers.base import BaseDocumentParser


def validate_safe_url(url: str) -> None:
    """Validates that a URL does not resolve to private, loopback, or cloud-metadata IPs (SSRF protection)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a valid hostname")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {str(e)}") from None

    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(
                f"Security violation: Access to internal, private, or restricted IP ({ip_str}) is forbidden."
            )


class URLParser(BaseDocumentParser):
    """Parses web URLs or HTML content by fetching, stripping markup, and extracting clean textual content."""

    def __init__(self, timeout: float = 15.0, max_redirects: int = 3):
        self.timeout = timeout
        self.max_redirects = max_redirects

    def _html_to_clean_text(self, html: str) -> str:
        # Remove scripts, styles, head, nav, footer, and comments
        cleaned = re.sub(r"<(script|style|head|nav|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)

        # Extract headings and paragraphs with line breaks
        cleaned = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n# \1\n", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)

        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", cleaned)

        # Normalize HTML entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

        # Normalize whitespace
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(l for l in lines if l).strip()

    def parse(self, file_bytes: bytes, filename: str | None = None) -> str:
        raw = file_bytes.decode("utf-8", errors="ignore").strip()
        if not raw:
            raise ValueError("URL content is empty")

        # If it's a web URL, fetch it safely via HTTP with SSRF safeguards
        if raw.startswith("http://") or raw.startswith("https://"):
            current_url = raw
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    for _ in range(self.max_redirects + 1):
                        validate_safe_url(current_url)
                        resp = client.get(
                            current_url,
                            headers={"User-Agent": "CortexCX-Crawler/1.0"},
                            follow_redirects=False,
                        )
                        if resp.is_redirect and "location" in resp.headers:
                            current_url = urllib.parse.urljoin(current_url, resp.headers["location"])
                            continue
                        resp.raise_for_status()
                        return self._html_to_clean_text(resp.text)
                    raise ValueError(f"Too many redirects while fetching URL '{raw}'")
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Failed to fetch content from URL '{raw}': {str(e)}") from None

        # Otherwise treat input as raw HTML text
        return self._html_to_clean_text(raw)
