"""Content-Security-Policy helpers.

The SvelteKit build emits a small inline `<script>` in `index.html`. Instead of
`'unsafe-inline'` we hash those blocks at startup and allow exactly them.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

_SCRIPT_RE = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.DOTALL | re.IGNORECASE)

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


def inline_script_hashes(index_html: Path) -> list[str]:
    """Return `'sha256-...'` tokens for every inline script block in the file."""
    if not index_html.is_file():
        return []
    html = index_html.read_text(encoding="utf-8")
    hashes: list[str] = []
    for match in _SCRIPT_RE.finditer(html):
        if re.search(r"\bsrc\s*=", match.group("attrs"), re.IGNORECASE):
            continue
        body = match.group("body")
        if not body.strip():
            continue
        digest = hashlib.sha256(body.encode("utf-8")).digest()
        hashes.append(f"'sha256-{base64.b64encode(digest).decode()}'")
    return hashes


def build_app_csp(script_hashes: list[str]) -> str:
    script_src = " ".join(["'self'", *script_hashes])
    return (
        f"default-src 'self'; script-src {script_src}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
