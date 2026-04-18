import re
from html.parser import HTMLParser

NOTE_MAX_CHARS = 3000

# Content types we can handle. Anything else returns None.
_SUPPORTED_TYPES = {"text/html", "text/plain"}


class _TextExtractor(HTMLParser):
    """Minimal HTMLParser subclass that collects visible text content."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_tags = {"script", "style", "head"}
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip += 1
        # Block-level tags: insert a newline so sections stay separated.
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._skip == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of 3+ newlines to 2, strip trailing spaces per line.
        raw = re.sub(r" +\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def strip_to_text(content: "str | bytes", content_type: str) -> "str | None":
    """
    Convert Binary note content to plain text.

    Returns:
        Cleaned plain text string, truncated to NOTE_MAX_CHARS.
        Empty string if content is empty.
        None if the content_type is not supported (e.g. PDF, RTF).
    """
    # Normalise content_type: strip parameters like '; charset=utf-8'
    mime = content_type.split(";")[0].strip().lower()

    if mime not in _SUPPORTED_TYPES:
        return None

    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    if not content:
        return ""

    if mime == "text/html":
        extractor = _TextExtractor()
        extractor.feed(content)
        text = extractor.get_text()
    else:
        text = content

    return text[:NOTE_MAX_CHARS]
