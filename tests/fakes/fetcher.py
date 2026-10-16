class FakeFetcher:
    """Offline fetch(url) -> bytes: serves canned responses by URL and records every URL asked for.
    A URL without a response fails like a network error."""

    def __init__(self, responses: dict[str, bytes]):
        self._responses = responses
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url not in self._responses:
            raise OSError(f"404 Not Found: {url}")
        return self._responses[url]
