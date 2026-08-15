"""
Unit tests for In-Memory BM25 Knowledge Base Retriever.
"""

import pytest
from src.kb_retriever import kb_retriever


def test_kb_retriever_initialization():
    assert len(kb_retriever.snippets) > 0, "Expected indexed snippets in knowledge base"
    assert kb_retriever.bm25 is not None


def test_kb_retriever_search_database_timeout():
    query = "ERR_CONNECTION_TIMEOUT after 30s DataBridge Pro"
    results = kb_retriever.search(query, top_k=2)
    assert len(results) > 0
    top_snippet, score = results[0]
    assert score >= kb_retriever.score_threshold
    assert "databridge-pro" in top_snippet.doc_path.lower() or "performance" in top_snippet.doc_path.lower()


def test_kb_retriever_sso_search():
    query = "SEC_SAML_INVALID_SIG SAML 2.0 signature verification failed Okta"
    doc_path, snippet = kb_retriever.get_top_snippet_context(query)
    assert doc_path is not None
    # SecureVault and Authentication-SSO both handle authentication
    assert "securevault" in doc_path.lower() or "authentication" in doc_path.lower() or "sso" in doc_path.lower()


def test_kb_retriever_low_confidence_dropout():
    query = "xyz987randomgibberishqwertynonexistent"
    results = kb_retriever.search(query, top_k=1)
    assert len(results) == 0
    doc, snip = kb_retriever.get_top_snippet_context(query)
    assert doc is None
    assert snip is None
