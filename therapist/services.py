# therapist/services.py
import pytesseract
import re
import logging

logger = logging.getLogger(__name__)


class TherapistVerificationService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def verify_license(self, document_path):
        """
        Verify license using OCR and pattern matching
        """
        try:
            from PIL import Image

            image = Image.open(document_path)
            image.verify()  # Validate image integrity
            image = Image.open(document_path)  # Reopen for processing

            # Extract text using Tesseract
            text = pytesseract.image_to_string(image)

            # Look for license number pattern (customize based on your needs)
            license_pattern = r"License[:\s]+([A-Z0-9-]+)"
            match = re.search(license_pattern, text, re.IGNORECASE)

            if match:
                license_number = match.group(1)
                return {"success": True, "license_number": license_number, "text": text}

            return {"success": False, "error": "No valid license number found"}

        except Exception as e:
            self.logger.error(f"License verification failed: {str(e)}")
            return {"success": False, "error": str(e)}
