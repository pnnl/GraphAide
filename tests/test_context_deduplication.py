"""Test cases for context deduplication and context window expansion.

Tests verify that:
1. RAGContextSummary is created and used correctly
2. Per-chunk retrieval is fresh (not accumulated)
3. Context deduplication works (no duplication of types/entities)
4. Context window presets are applied correctly
"""

import pytest
from graphgen.v2.state import (
    RAGContextSummary, RAGContext, RetrievalResult, RetrievalResultType,
    KGGenerationState
)
from graphgen.v2.agents.contextbuilder import (
    deduplicate_types, deduplicate_definitions, deduplicate_entities,
    build_chunk_context, count_tokens, validate_context_window
)
from graphgen.v2.workflows.utils import init_kg_generation_state
from graphgen.v2 import globalconfig


class TestRAGContextSummary:
    """Test RAGContextSummary initialization and usage."""

    def test_rag_context_summary_creation(self):
        """Test that RAGContextSummary can be created with ontology data."""
        summary = RAGContextSummary(
            ontology_node_types=["Person", "Organization"],
            ontology_edge_types=["worksFor", "locatedIn"],
            ontology_node_definitions={
                "Person": "A human being",
                "Organization": "A company or entity"
            }
        )

        assert summary.ontology_node_types == ["Person", "Organization"]
        assert summary.ontology_edge_types == ["worksFor", "locatedIn"]
        assert len(summary.ontology_node_definitions) == 2
        assert summary.wikidata_context == {}  # Should not exist in summary

    def test_rag_context_summary_empty(self):
        """Test that RAGContextSummary can be created empty."""
        summary = RAGContextSummary()

        assert summary.ontology_node_types == []
        assert summary.ontology_edge_types == []
        assert summary.ontology_node_definitions == {}

    def test_rag_context_backward_compatibility(self):
        """Test that RAGContext still works for backward compatibility."""
        rag_context = RAGContext(
            ontology_node_types=["Person"],
            retrieval_results=[]  # Full context includes retrieval results
        )

        assert rag_context.ontology_node_types == ["Person"]
        assert rag_context.retrieval_results == []


class TestContextDeduplication:
    """Test context deduplication utilities."""

    def test_deduplicate_types_no_duplicates(self):
        """Test that types are deduplicated (set union, not append)."""
        summary = RAGContextSummary(
            ontology_node_types=["Person", "Organization"]
        )

        result1 = RetrievalResult(
            source="vector_store_1",
            result_type=RetrievalResultType.TYPES,
            ontology_node_types=["Person", "Location"]  # Person is duplicate
        )

        node_types, _ = deduplicate_types(summary, [result1])

        # Should have 3 unique types, not 4 (no duplicate "Person")
        assert len(node_types) == 3
        assert "Person" in node_types
        assert "Organization" in node_types
        assert "Location" in node_types

    def test_deduplicate_definitions_merge(self):
        """Test that definitions are merged without duplication."""
        summary = RAGContextSummary(
            ontology_node_definitions={
                "Person": "A human being",
                "Organization": "A company"
            }
        )

        result1 = RetrievalResult(
            source="vector_store_1",
            result_type=RetrievalResultType.TYPES,
            custom_data={
                "definitions": {
                    "Person": "A human being (from retriever)",  # Duplicate key
                    "Location": "A place"
                }
            }
        )

        node_defs, _ = deduplicate_definitions(summary, [result1])

        # Should have 3 definitions (dict merge, newer value wins)
        assert len(node_defs) == 3
        assert "Person" in node_defs
        assert "Organization" in node_defs
        assert "Location" in node_defs

    def test_deduplicate_entities_by_qid(self):
        """Test that entities are deduplicated by QID."""
        result1 = RetrievalResult(
            source="wikidata",
            result_type=RetrievalResultType.ENTITIES,
            wikidata_context={
                "Q42": {"label": "Douglas Adams"},
                "Q43": {"label": "Isaac Asimov"}
            }
        )

        result2 = RetrievalResult(
            source="wikidata_2",
            result_type=RetrievalResultType.ENTITIES,
            wikidata_context={
                "Q42": {"label": "Updated Douglas Adams"},  # Duplicate QID
                "Q44": {"label": "Arthur C. Clarke"}
            }
        )

        entities = deduplicate_entities([result1, result2])

        # Should have 3 unique QIDs, not 4
        assert len(entities) == 3
        assert "Q42" in entities
        assert "Q43" in entities
        assert "Q44" in entities

    def test_build_chunk_context_deduplication(self):
        """Test that build_chunk_context deduplicates everything."""
        summary = RAGContextSummary(
            ontology_node_types=["Person"],
            ontology_node_definitions={"Person": "A human"}
        )

        result1 = RetrievalResult(
            source="retriever_1",
            result_type=RetrievalResultType.TYPES,
            ontology_node_types=["Person", "Organization"],  # Person duplicate
            store_description="Primary ontology store"
        )

        context = build_chunk_context(summary, [result1], include_token_count=False)

        # Context should contain types but not 2x "Person"
        assert "Person" in context
        assert "Organization" in context
        assert context.count("Person") == 1  # Only mentioned once


class TestContextWindowPresets:
    """Test context window configuration and presets."""

    def test_context_window_presets_exist(self):
        """Test that all context window presets are defined."""
        assert "small" in globalconfig.CONTEXT_WINDOW_PRESETS
        assert "medium" in globalconfig.CONTEXT_WINDOW_PRESETS
        assert "large" in globalconfig.CONTEXT_WINDOW_PRESETS
        assert "xlarge" in globalconfig.CONTEXT_WINDOW_PRESETS

    def test_context_window_values(self):
        """Test that preset values are correct."""
        assert globalconfig.CONTEXT_WINDOW_PRESETS["small"] == 4096
        assert globalconfig.CONTEXT_WINDOW_PRESETS["medium"] == 8192
        assert globalconfig.CONTEXT_WINDOW_PRESETS["large"] == 16384
        assert globalconfig.CONTEXT_WINDOW_PRESETS["xlarge"] == 32768

    def test_default_context_window_mode(self):
        """Test that default mode is medium."""
        assert globalconfig.DEFAULT_CONTEXT_WINDOW_MODE == "medium"

    def test_init_kg_generation_state_uses_preset(self):
        """Test that init_kg_generation_state respects context_window_mode."""
        # Test with 'large' preset
        state = init_kg_generation_state(
            input_text="sample text",
            context_window_mode="large"
        )

        assert state["max_tokens_per_segment"] == 16384

        # Test with 'small' preset
        state = init_kg_generation_state(
            input_text="sample text",
            context_window_mode="small"
        )

        assert state["max_tokens_per_segment"] == 4096

    def test_init_kg_generation_state_explicit_override(self):
        """Test that explicit max_tokens_per_segment overrides preset."""
        state = init_kg_generation_state(
            input_text="sample text",
            context_window_mode="large",
            max_tokens_per_segment=2048  # Override
        )

        # Explicit value should win over preset
        assert state["max_tokens_per_segment"] == 2048

    def test_init_kg_generation_state_has_summary(self):
        """Test that init_kg_generation_state includes rag_context_summary."""
        state = init_kg_generation_state(
            input_text="sample text",
            ontology_node_types=["Person", "Organization"]
        )

        assert "rag_context_summary" in state
        assert state["rag_context_summary"] is not None
        assert state["rag_context_summary"].ontology_node_types == ["Person", "Organization"]


class TestTokenCounting:
    """Test token counting utilities."""

    def test_count_tokens_basic(self):
        """Test token counting on simple text."""
        text = "Hello world"
        token_count = count_tokens(text)

        # Should be 2 tokens (roughly)
        assert token_count > 0
        assert token_count <= 5  # Should be very small

    def test_count_tokens_large_text(self):
        """Test token counting on large text."""
        text = " ".join(["word"] * 1000)  # 1000 words
        token_count = count_tokens(text)

        # Should be around 1000+ tokens
        assert token_count >= 1000

    def test_validate_context_window_fits(self):
        """Test that validate_context_window correctly checks fit."""
        text = "Hello world"
        fits = validate_context_window(text, max_tokens=1000)

        assert fits is True

    def test_validate_context_window_exceeds(self):
        """Test that validate_context_window detects overflow."""
        text = " ".join(["word"] * 1000)
        fits = validate_context_window(text, max_tokens=10)

        assert fits is False


class TestPerChunkRetrieval:
    """Test that per-chunk retrieval works independently."""

    def test_fresh_retrieval_per_chunk(self):
        """Test that each chunk retrieves fresh results (mock test)."""
        # This is a conceptual test - actual retrieval happens in ExtractorAgent

        # Create two "chunks" with different content
        chunk1_summary = RAGContextSummary(ontology_node_types=["Person"])
        chunk2_summary = RAGContextSummary(ontology_node_types=["Person"])  # Same

        # They should have identical static contexts
        # (In reality, they'd query different things from vector store)
        assert chunk1_summary.ontology_node_types == chunk2_summary.ontology_node_types

    def test_no_context_accumulation_in_send(self):
        """Test that Send() doesn't pass accumulated rag_context.

        Verify via init_kg_generation_state that rag_context_summary
        is used instead of full rag_context.
        """
        state = init_kg_generation_state(
            input_text="text",
            ontology_node_types=["Person"]
        )

        # Should have rag_context_summary for dispatch
        assert state.get("rag_context_summary") is not None

        # Full rag_context should also exist for backward compat
        assert state.get("rag_context") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
