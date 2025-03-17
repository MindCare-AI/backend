# services/therapist_verification_service.py
import pytesseract
import re
import logging

logger = logging.getLogger(__name__)


class TherapistVerificationService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def verify_license(self, document_path):
        try:
            from PIL import Image

            image = Image.open(document_path)
            image.verify()
            image = Image.open(document_path)

            text = pytesseract.image_to_string(image)

            license_pattern = r"License[:\s]+([A-Z0-9-]+)"
            match = re.search(license_pattern, text, re.IGNORECASE)

            if match:
                license_number = match.group(1)
                return {"success": True, "license_number": license_number, "text": text}

            return {"success": False, "error": "No valid license number found"}

        except Exception as e:
            self.logger.error(f"License verification failed: {str(e)}")
            return {"success": False, "error": str(e)}
