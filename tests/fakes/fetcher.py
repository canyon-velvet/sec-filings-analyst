class FakeFetcher:
    """Offline fetch(url) -> bytes: serves canned responses by URL and records every URL asked for.
    A response that is an exception is raised; a URL without a response fails like a 404."""

    def __init__(self, responses: dict[str, bytes | Exception]):
        self._responses = responses
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url not in self._responses:
            raise OSError(f"404 Not Found: {url}")
        if isinstance(self._responses[url], Exception):
            raise self._responses[url]
        return self._responses[url]
