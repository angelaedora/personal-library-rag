"""Text chunking with token awareness."""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunk documents with overlap and token awareness."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n",
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Tokens to overlap between chunks
            separator: Primary text separator (newline, space, etc.)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (words * 1.3 for Bedrock)."""
        words = len(text.split())
        return int(words * 1.3)

    def _split_text(self, text: str, separator: str) -> List[str]:
        """Split text by separator."""
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        return [s for s in splits if s]

    def chunk(self, text: str) -> List[str]:
        """
        Chunk text into overlapping segments.

        Returns:
            List of chunk strings
        """
        try:
            chunks = []
            separators = ["\n\n", "\n", " ", ""]

            good_splits = []
            separator = separators[-1]

            for sep in separators:
                if sep == "":
                    good_splits = [text]
                    break

                splits = self._split_text(text, sep)
                good_splits = [s for s in splits if self._estimate_tokens(s) < self.chunk_size]

                if good_splits:
                    separator = sep
                    break

            merged_text = ""
            for split in good_splits:
                split_tokens = self._estimate_tokens(split)
                merged_tokens = self._estimate_tokens(merged_text)

                if merged_tokens + split_tokens > self.chunk_size:
                    if merged_text:
                        chunk_text = merged_text.strip()
                        if chunk_text:
                            chunks.append(chunk_text)

                    # Overlap handling
                    overlap_tokens = 0
                    overlap_text = ""
                    for prev_split in reversed(good_splits):
                        if prev_split == split:
                            break
                        prev_tokens = self._estimate_tokens(prev_split)
                        if overlap_tokens + prev_tokens <= self.chunk_overlap:
                            overlap_text = prev_split + separator + overlap_text
                            overlap_tokens += prev_tokens
                        else:
                            break

                    merged_text = overlap_text + split
                else:
                    merged_text += separator + split if merged_text else split

            if merged_text.strip():
                chunks.append(merged_text.strip())

            logger.info(f"Chunked text into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            raise

    def chunk_with_metadata(
        self,
        text: str,
        page_number: int = 1,
    ) -> List[Tuple[str, dict]]:
        """
        Chunk text and include metadata.

        Returns:
            List of (chunk_text, metadata) tuples
        """
        chunks = self.chunk(text)

        chunked_with_metadata = []
        for chunk_index, chunk in enumerate(chunks):
            metadata = {
                "page_number": page_number,
                "chunk_index": chunk_index,
                "chunk_count": len(chunks),
            }
            chunked_with_metadata.append((chunk, metadata))

        return chunked_with_metadata
