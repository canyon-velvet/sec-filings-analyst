class WordTokenizer:
    """Offline Tokenizer: one token per whitespace-separated word, so counts are word counts."""

    def __init__(self):
        self._words: list[str] = []

    def encode(self, text: str) -> list[int]:
        tokens = []
        for word in text.split():
            if word not in self._words:
                self._words.append(word)
            tokens.append(self._words.index(word))
        return tokens

    def decode(self, tokens: list[int]) -> str:
        return " ".join(self._words[token] for token in tokens)
