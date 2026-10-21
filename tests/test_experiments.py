import pytest
from fakes.embedder import WordHashEmbedder

from sec_filings_analyst.experiments import build_experiment


def test_an_unknown_experiment_is_refused_with_the_known_names():
    with pytest.raises(ValueError, match=r"'dense-basline'.*dense-baseline"):
        build_experiment("dense-basline", conn=None, embedder=WordHashEmbedder())
