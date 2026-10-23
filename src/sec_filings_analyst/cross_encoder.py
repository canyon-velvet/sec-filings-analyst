"""Cross-encoder Scorer: a local model reads each (query, Chunk text) pair together and scores how
well the text answers the query. Runs on CPU with ONNX Runtime; no API cost. See docs/adr/0001."""

MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"  # Apache-2.0, 22.7M parameters
REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"  # pinned: the weights and tokenizer
MAX_TOKENS = 512  # the model's limit (its own tokenizer): longer Chunk texts are cut
BATCH_SIZE = 16


class CrossEncoderScorer:
    """Downloads the pinned model once (Hugging Face cache) when built. Needs the `rerank`
    dependency group: its libraries are imported here, so tests and CI never load them."""

    def __init__(self):
        import onnxruntime
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(
            hf_hub_download(MODEL, "tokenizer.json", revision=REVISION)
        )
        self._tokenizer.enable_truncation(MAX_TOKENS)
        self._tokenizer.enable_padding()
        self._session = onnxruntime.InferenceSession(
            hf_hub_download(MODEL, "onnx/model.onnx", revision=REVISION),
            providers=["CPUExecutionProvider"],
        )

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        import numpy as np

        scores: list[float] = []
        for start in range(0, len(pairs), BATCH_SIZE):
            encodings = self._tokenizer.encode_batch(pairs[start : start + BATCH_SIZE])
            inputs = {
                "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
            }
            (logits,) = self._session.run(None, inputs)  # one relevance logit per pair
            scores.extend(float(logit) for logit in logits[:, 0])
        return scores
