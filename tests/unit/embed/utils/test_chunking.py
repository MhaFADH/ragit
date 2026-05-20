from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_token_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(text: str) -> int:
        return max(1, len(text) // 4)

    monkeypatch.setattr("docs_rag.embed.utils.chunking.count_tokens", fake)


def test_split_markdown_empty_returns_empty() -> None:
    from docs_rag.embed.utils.chunking import split_markdown

    assert split_markdown("") == []
    assert split_markdown("   \n  \n") == []


def test_split_markdown_no_headings() -> None:
    from docs_rag.embed.utils.chunking import split_markdown

    chunks = split_markdown("plain paragraph with no headings.")
    assert len(chunks) == 1
    assert chunks[0].heading_path == ""
    assert "plain paragraph" in chunks[0].content
    assert chunks[0].chunk_index == 0
    assert chunks[0].token_count > 0


def test_split_markdown_single_h1_prefix_present() -> None:
    from docs_rag.embed.utils.chunking import split_markdown

    chunks = split_markdown("# Intro\n\nHello world.")
    assert len(chunks) == 1
    assert chunks[0].heading_path == "Intro"
    assert chunks[0].content.startswith("> Section: Intro\n\n")


def test_split_markdown_nested_headings_path() -> None:
    from docs_rag.embed.utils.chunking import split_markdown

    content = "# Top\n\n## Mid\n\n### Leaf\n\nbody"
    chunks = split_markdown(content)
    leaf = [c for c in chunks if "body" in c.content]
    assert leaf, chunks
    assert leaf[0].heading_path == "Top > Mid > Leaf"


def test_split_markdown_indices_monotonic_per_document() -> None:
    from docs_rag.embed.utils.chunking import split_markdown

    content = "# A\n\nalpha\n\n# B\n\nbeta\n\n# C\n\ngamma"
    chunks = split_markdown(content)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
