"""PDF extraction for Lambda context."""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF documents."""

    @staticmethod
    def extract_text_with_pages(pdf_bytes: bytes) -> Tuple[str, int]:
        """
        Extract full text and page count from PDF.

        Args:
            pdf_bytes: Binary PDF data

        Returns:
            Tuple of (full_text, page_count)
        """
        try:
            import pdfplumber

            with pdfplumber.open(pdf_bytes) as pdf:
                full_text = ""
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        full_text += f"\n--- Page {page_num} ---\n{text}\n"

                logger.info(f"Extracted text from {page_count} pages")
                return full_text, page_count

        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise
