#chatbot/services/rag/pdf_extractor.py
import os
import logging
import pdfplumber
from typing import List, Dict, Any, Tuple
import re
import spacy
import gc  # Add garbage collector
from tqdm import tqdm
import pytesseract
import unicodedata

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
        
        # Try to load the spaCy model, but have a fallback
        try:
            self.nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "attribute_ruler"])
            # Add sentencizer component to avoid the warning about sentence boundaries
            if "sentencizer" not in [pipe_name for pipe_name, _ in self.nlp.pipeline]:
                self.nlp.add_pipe("sentencizer")
            # Increase maximum text length to process longer documents
            self.nlp.max_length = 2000000
            self.use_spacy = True
            logger.info("Using spaCy for sentence tokenization with sentencizer")
        except IOError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Using regex fallback for sentence splitting.")
            self.nlp = None
            self.use_spacy = False
            logger.info("To install the spaCy model, run: python manage.py download_spacy_model")
        
        self.max_workers = min(2, os.cpu_count() or 2)  # Limit workers to reduce memory usage
        # simple in-memory cache for OCRed pages
        self.ocr_cache: Dict[str, str] = {}

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file using pdfplumber, with OCR fallback.

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
            text_content = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    # if embedded text is too short, run OCR
                    if len(text.strip()) < 50:
                        cache_key = f"{pdf_path}::page_{i}"
                        if cache_key in self.ocr_cache:
                            ocr_text = self.ocr_cache[cache_key]
                        else:
                            img = page.to_image(resolution=300).original
                            ocr_text = pytesseract.image_to_string(img)
                            self.ocr_cache[cache_key] = ocr_text
                        text = ocr_text or text
                    if text:
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

        # Unicode normalization
        cleaned = unicodedata.normalize("NFC", cleaned)

        return cleaned.strip()

    def create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """Split text into semantically meaningful chunks with metadata.

        Args:
            text: Text to split into chunks

        Returns:
            List of dictionaries with chunk text and metadata
        """
        # Process text in smaller chunks if it's very large to reduce memory usage
        if len(text) > 500000 and self.use_spacy and self.nlp:
            logger.info(f"Text is very large ({len(text)} chars), processing in batches")
            return self._create_chunks_in_batches(text)
        
        if self.use_spacy and self.nlp:
            # Use spaCy for sentence splitting if available
            try:
                doc = self.nlp(text)
                sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            except Exception as e:
                logger.warning(f"Error using spaCy: {str(e)}. Falling back to regex")
                # Fall back to regex if spaCy fails
                sentence_endings = r'(?<=[.!?])\s+'
                sentences = [s.strip() for s in re.split(sentence_endings, text) if s.strip()]
        else:
            # Fallback to regex-based sentence splitting
            sentence_endings = r'(?<=[.!?])\s+'
            sentences = [s.strip() for s in re.split(sentence_endings, text) if s.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            if not sentence:
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

    def _create_chunks_in_batches(self, text: str) -> List[Dict[str, Any]]:
        """Process large text in smaller batches to reduce memory usage."""
        all_chunks = []
        batch_size = 200000  # Process 200k characters at a time
        
        for i in range(0, len(text), batch_size):
            batch_text = text[i:i+batch_size]
            
            # Find sentence boundaries for better splits
            if i > 0:
                # Find the first sentence break after the start point
                match = re.search(r'(?<=[.!?])\s+', batch_text[:1000])
                if match:
                    batch_text = batch_text[match.end():]
            
            # Use regex for better memory usage on batches
            sentence_endings = r'(?<=[.!?])\s+'
            sentences = [s.strip() for s in re.split(sentence_endings, batch_text) if s.strip()]
            
            current_chunk = []
            current_size = 0
            
            for sentence in sentences:
                if not sentence:
                    continue
                    
                sentence_size = len(sentence)
                
                # If adding this sentence would exceed chunk size, save current chunk and start new one
                if current_size + sentence_size > self.chunk_size and current_chunk:
                    chunk_text = " ".join(current_chunk)
                    all_chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            "size": len(chunk_text),
                            "sentence_count": len(current_chunk),
                        },
                    })
                    
                    # Start new chunk with overlap
                    overlap_idx = max(0, len(current_chunk) - self.chunk_overlap // 50)
                    current_chunk = current_chunk[overlap_idx:]
                    current_size = sum(len(s) for s in current_chunk) + len(current_chunk) - 1
                    
                current_chunk.append(sentence)
                current_size += sentence_size + 1  # +1 for space
            
            # Add the last chunk from this batch if not empty
            if current_chunk:
                chunk_text = " ".join(current_chunk)
                all_chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "size": len(chunk_text),
                        "sentence_count": len(current_chunk),
                    },
                })
                
            # Force garbage collection after each batch
            gc.collect()
            
        return all_chunks

    def extract_text(self, pdf_path: str) -> str:
        """Extract text from a PDF using pdfplumber without modifying any words via LLM.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Cleaned text as a single string without LLM modifications
        """
        raw_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                raw_text += page.extract_text() + "\n"
        cleaned_raw_text = self.clean_text(raw_text)
        # Do not use LLM to change any words from the original PDF.
        return cleaned_raw_text

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

    def extract_and_process_batch(self, pdf_paths: List[str], max_workers: int = None) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """Extract and process multiple PDFs with optimized memory usage.

        Args:
            pdf_paths: List of paths to PDF files
            max_workers: Maximum number of threads to use (default: CPU count)

        Returns:
            List of tuples containing (full text, list of chunks) for each PDF
        """
        if max_workers is None:
            max_workers = self.max_workers
        
        # Process one file at a time to reduce memory usage
        max_workers = 1
        
        logger.info(f"Processing {len(pdf_paths)} PDFs using {max_workers} workers")
        results = []
        
        # Process one file at a time with garbage collection between files
        with tqdm(total=len(pdf_paths), desc="Processing PDF files", ncols=100) as pbar:
            for i, path in enumerate(pdf_paths):
                try:
                    # Log memory usage before processing
                    filename = os.path.basename(path)
                    file_size = os.path.getsize(path) / (1024 * 1024)  # Convert to MB
                    
                    # Process the file
                    result = self.extract_and_process(path)
                    chunks_count = len(result[1]) if result[1] else 0
                    
                    # Update progress
                    pbar.set_postfix_str(f"File: {filename} ({file_size:.1f}MB) - {chunks_count} chunks")
                    pbar.update(1)
                    
                    results.append(result)
                    
                    # Force garbage collection after each file
                    gc.collect()
                    
                except Exception as e:
                    logger.error(f"Error processing {os.path.basename(path)}: {str(e)}")
                    results.append((None, []))
                    pbar.update(1)
        
        return results


# Instantiate extractor for easy import
pdf_extractor = PDFExtractor()
