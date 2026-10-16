class WordTokenizer:
    """Offline Tokenizer: one token per whitespace-separated word, so counts are word counts."""

    def __init__(self):
        self._ids: dict[str, int] = {}
        self._words: list[str] = []

    def encode(self, text: str) -> list[int]:
        for word in text.split():
            if word not in self._ids:
                self._ids[word] = len(self._words)
                self._words.append(word)
        return [self._ids[word] for word in text.split()]

    def decode(self, tokens: list[int]) -> str:
        return " ".join(self._words[token] for token in tokens)
