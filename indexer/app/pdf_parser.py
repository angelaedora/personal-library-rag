"""PDF document extraction."""

import logging
from typing import List, Tuple
import pypdf
import pdfplumber

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF documents."""

    @staticmethod
    def extract_text_with_pages(pdf_bytes: bytes) -> Tuple[str, int]:
        """
        Extract full text and page count from PDF.

        Returns:
            Tuple of (full_text, page_count)
        """
        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                full_text = ""
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        # Add page marker for better context
                        full_text += f"\n--- Page {page_num} ---\n{text}\n"

                logger.info(f"Extracted text from {page_count} pages")
                return full_text, page_count

        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise

    @staticmethod
    def extract_text_by_page(pdf_bytes: bytes) -> List[str]:
        """
        Extract text page by page.

        Returns:
            List of page texts
        """
        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                pages = []

                for page in pdf.pages:
                    text = page.extract_text()
                    pages.append(text or "")

                logger.info(f"Extracted {len(pages)} pages")
                return pages

        except Exception as e:
            logger.error(f"Error extracting PDF by page: {str(e)}")
            raise
