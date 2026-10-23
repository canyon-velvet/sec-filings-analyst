import subprocess
import sys

import pytest
from fakes.embedder import WordHashEmbedder

from sec_filings_analyst.experiments import build_experiment


def test_an_unknown_experiment_is_refused_with_the_known_names():
    with pytest.raises(ValueError, match=r"'dense-basline'.*dense-baseline"):
        build_experiment("dense-basline", conn=None, embedder=WordHashEmbedder())


def test_the_experiments_load_without_the_cross_encoder_s_libraries():
    # CI doesn't install the `rerank` group: only building a rerank Experiment may import it
    heavy = "{'onnxruntime', 'tokenizers', 'huggingface_hub'}"
    probe = (
        f"import sys, sec_filings_analyst.experiments; print(sorted({heavy} & set(sys.modules)))"
    )

    loaded = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )

    assert loaded.stdout.strip() == "[]"
