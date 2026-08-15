"""
In-Memory BM25 Knowledge Base Retriever
Indexes all Markdown guides in data/knowledge_base/ into tokenized chunks with BM25 Okapi ranking.
"""

import os
import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from rank_bm25 import BM25Okapi

logger = logging.getLogger("kb_retriever")


class KBSnippet:
    def __init__(self, doc_path: str, section_title: str, content: str):
        self.doc_path = doc_path
        self.section_title = section_title
        self.content = content.strip()

    def __repr__(self):
        return f"<KBSnippet doc={self.doc_path} section='{self.section_title}'>"


class KBRetriever:
    def __init__(self, kb_dir: str = "data/knowledge_base/", score_threshold: float = 1.5):
        self.kb_dir = kb_dir
        self.score_threshold = score_threshold
        self.snippets: List[KBSnippet] = []
        self.corpus_tokens: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.index_knowledge_base()

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenizes alphanumeric terms, error codes (e.g. ERR_TIMEOUT), and snake_case / kebab-case symbols.
        """
        # Split on non-alphanumeric except underscores and hyphens
        tokens = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
        return [t for t in tokens if len(t) > 1]

    def index_knowledge_base(self) -> None:
        """
        Walks kb_dir, chunks Markdown documents by headers or horizontal rules, and builds BM25 index.
        """
        kb_path = self.kb_dir
        if not os.path.exists(kb_path):
            kb_path = os.path.join("dataset", "starter-repo", "knowledge-base")

        if not os.path.exists(kb_path):
            logger.error(f"Knowledge base directory not found at {kb_path}")
            return

        self.snippets = []
        self.corpus_tokens = []

        for root, _, files in os.walk(kb_path):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, kb_path).replace("\\", "/")
                    self._parse_markdown_file(full_path, rel_path)

        if self.snippets:
            self.bm25 = BM25Okapi(self.corpus_tokens)
            logger.info(f"KBRetriever indexed {len(self.snippets)} chunks across {kb_path}")
        else:
            logger.warning("No knowledge base documents found to index.")

    def _parse_markdown_file(self, full_path: str, rel_path: str) -> None:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Split on markdown headers (# or ## or ###) or horizontal rules (---)
        sections = re.split(r'\n(?=#{1,3}\s+|---)', text)
        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue

            # Extract title if present
            lines = sec_clean.splitlines()
            first_line = lines[0].strip()
            title = first_line.lstrip("#- ").strip() if first_line.startswith(("#", "-")) else "Overview"
            
            snippet = KBSnippet(
                doc_path=rel_path,
                section_title=title,
                content=sec_clean
            )
            tokens = self.tokenize(sec_clean)
            if tokens:
                self.snippets.append(snippet)
                self.corpus_tokens.append(tokens)

    def search(self, query: str, top_k: int = 1) -> List[Tuple[KBSnippet, float]]:
        """
        Performs BM25 search and returns top-k matching snippets exceeding score_threshold.
        """
        if not self.bm25 or not self.snippets:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        scored_pairs = list(zip(self.snippets, scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for snippet, score in scored_pairs[:top_k]:
            if score >= self.score_threshold:
                results.append((snippet, float(score)))

        return results

    def get_top_snippet_context(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Convenience method: returns (doc_path, snippet_content) if match exceeds threshold, else (None, None).
        """
        matches = self.search(query, top_k=1)
        if matches:
            top_match, score = matches[0]
            # Format snippet content cleanly
            return top_match.doc_path, top_match.content
        return None, None


kb_retriever = KBRetriever()
