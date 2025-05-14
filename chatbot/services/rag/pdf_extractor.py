#chatbot/services/rag/pdf_extractor.py
import os
import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
import re
import nltk
from nltk.tokenize import sent_tokenize

# Download required NLTK packages if not already downloaded
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract and process text from PDF files for RAG implementation."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Initialize the PDF extractor.

        Args:
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text as a single string
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if os.path.getsize(pdf_path) < 1024:  # Minimal size threshold
            raise ValueError("PDF file appears corrupted")

        try:
            doc = fitz.open(pdf_path)
            text_content = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                text_content.append(text)

            return "\n".join(text_content)

        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {str(e)}")
            raise

    def clean_text(self, text: str) -> str:
        """Clean extracted text to remove artifacts and normalize formatting.

        Args:
            text: Raw text from PDF

        Returns:
            Cleaned text
        """
        # Replace multiple newlines with a single one
        cleaned = re.sub(r"\n{2,}", "\n", text)

        # Remove header/footer artifacts (common patterns)
        cleaned = re.sub(r"^\d+\s*$", "", cleaned, flags=re.MULTILINE)  # Page numbers
        cleaned = re.sub(r"©.*?\d{4}.*?\n", "", cleaned)  # Copyright notices

        # Remove excessive whitespace
        cleaned = re.sub(r"\s{2,}", " ", cleaned)

        # Fix hyphenated words at line breaks
        cleaned = re.sub(r"(\w+)-\n(\w+)", r"\1\2", cleaned)

        return cleaned.strip()

    def create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """Split text into semantically meaningful chunks with metadata.

        Args:
            text: Text to split into chunks

        Returns:
            List of dictionaries with chunk text and metadata
        """
        # Split text into sentences
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            # Skip empty sentences
            if not sentence.strip():
                continue

            sentence_size = len(sentence)

            # If adding this sentence would exceed chunk size, save current chunk and start new one
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(
                    {
                        "text": chunk_text,
                        "metadata": {
                            "size": len(chunk_text),
                            "sentence_count": len(current_chunk),
                        },
                    }
                )

                # Start new chunk with overlap
                overlap_idx = max(
                    0, len(current_chunk) - self.chunk_overlap // 50
                )  # Approximate by sentences
                current_chunk = current_chunk[overlap_idx:]
                current_size = (
                    sum(len(s) for s in current_chunk) + len(current_chunk) - 1
                )  # -1 for spaces

            current_chunk.append(sentence)
            current_size += sentence_size + 1  # +1 for space

        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "size": len(chunk_text),
                        "sentence_count": len(current_chunk),
                    },
                }
            )

        return chunks

    def extract_and_process(self, pdf_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text from PDF, clean it, and split into chunks.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (full text, list of chunks)
        """
        raw_text = self.extract_text_from_pdf(pdf_path)
        cleaned_text = self.clean_text(raw_text)
        chunks = self.create_chunks(cleaned_text)

        return cleaned_text, chunks


# Instantiate extractor for easy import
pdf_extractor = PDFExtractor()
