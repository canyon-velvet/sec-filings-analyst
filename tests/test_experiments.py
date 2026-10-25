import subprocess
import sys

import pytest
from fakes.embedder import WordHashEmbedder

from sec_filings_analyst.experiments import EXPERIMENTS, build_experiment


def test_an_unknown_experiment_is_refused_with_the_known_names():
    with pytest.raises(ValueError, match=r"'dense-basline'.*dense-baseline"):
        build_experiment("dense-basline", conn=None, embedder=WordHashEmbedder())


def test_only_the_oracle_experiment_filters_by_each_question_s_company_doc_type_and_year():
    def build(name):
        return build_experiment(name, conn=None, embedder=WordHashEmbedder())  # nothing searched

    assert build("dense-oracle-filter").oracle_filter
    assert not build("dense-baseline").oracle_filter


def test_each_headers_experiment_is_its_stack_expecting_contextual_headers():
    headers = {"header_format": "{company} {doc_type} FY{fiscal_year}, page {page}"}
    for name, bare in [
        ("dense-headers", "dense-baseline"),
        ("keyword-bm25-headers", "keyword-bm25"),
        ("hybrid-rrf-headers", "hybrid-rrf"),
    ]:
        (settings, build), (bare_settings, bare_build) = EXPERIMENTS[name], EXPERIMENTS[bare]
        assert settings == bare_settings | headers and build is bare_build


def test_the_experiments_load_without_the_cross_encoder_s_libraries():
    # CI doesn't install the `rerank` group: only building a rerank Experiment may import it
    heavy = "{'onnxruntime', 'tokenizers', 'huggingface_hub', 'numpy'}"
    probe = (
        f"import sys, sec_filings_analyst.experiments; print(sorted({heavy} & set(sys.modules)))"
    )

    loaded = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )

    assert loaded.stdout.strip() == "[]"
