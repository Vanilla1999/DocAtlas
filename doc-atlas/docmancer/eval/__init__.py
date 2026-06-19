"""Minimal retrieval eval harness used for smoke-testing hybrid retrieval.

Not the production TTAB harness. Lives here so phase 4 can compare
lexical / dense / sparse / hybrid against the public-domain story corpus.
"""

from .story_corpus import run_story_corpus_eval

__all__ = ["run_story_corpus_eval"]
