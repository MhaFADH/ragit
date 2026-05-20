from __future__ import annotations

from dataclasses import dataclass

from docs_rag.embed.utils.embedder import MAX_TOKENS, count_tokens
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

_PREFIX_TOKEN_BUDGET = 32
_CHUNK_SIZE_TOKENS = MAX_TOKENS - _PREFIX_TOKEN_BUDGET
_CHUNK_OVERLAP_TOKENS = 50

_HEADERS_TO_SPLIT = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

_SEPARATORS = [
    "\n```\n",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    heading_path: str
    content: str
    token_count: int


def split_markdown(content: str) -> list[Chunk]:
    if not content.strip():
        return []

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT,
        strip_headers=False,
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE_TOKENS,
        chunk_overlap=_CHUNK_OVERLAP_TOKENS,
        separators=_SEPARATORS,
        length_function=count_tokens,
    )

    chunks: list[Chunk] = []
    for section in header_splitter.split_text(content):
        heading_path = _format_heading_path(section.metadata)
        prefix = f"> Section: {heading_path}\n\n" if heading_path else ""
        for text in char_splitter.split_text(section.page_content):
            body = prefix + text
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    heading_path=heading_path,
                    content=body,
                    token_count=count_tokens(body),
                )
            )
    return chunks


def _format_heading_path(meta: dict[str, str]) -> str:
    parts = [meta[k] for k in ("h1", "h2", "h3") if meta.get(k)]
    return " > ".join(parts)
