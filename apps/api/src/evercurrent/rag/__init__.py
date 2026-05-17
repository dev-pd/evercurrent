"""Retrieval-augmented generation over project docs.

`embedder` wraps Voyage AI. `chunker` splits markdown into ~800-token
chunks. `indexer` runs the full doc → chunks → embeddings → pgvector
pipeline. `retriever` answers similarity searches.
"""

from evercurrent.rag.chunker import Chunk, chunk_markdown
from evercurrent.rag.embedder import EmbeddingProvider, VoyageEmbedder
from evercurrent.rag.indexer import index_document
from evercurrent.rag.retriever import ChunkResult, search_documents

__all__ = [
    "Chunk",
    "ChunkResult",
    "EmbeddingProvider",
    "VoyageEmbedder",
    "chunk_markdown",
    "index_document",
    "search_documents",
]
