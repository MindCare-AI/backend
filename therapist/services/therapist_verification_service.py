# therapist/services/therapist_verification_service.py
import easyocr
import face_recognition
import torch
import logging
import numpy as np
from PIL import Image
from datetime import datetime
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TherapistVerificationService:
    """Service for verifying therapist licenses and identity"""

    def __init__(self):
        try:
            # First try to use GPU if available
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info("Using CUDA for verification service")
            else:
                self.device = "cpu"
                logger.info("CUDA not available, using CPU for verification service")

            # Initialize EasyOCR with selected device
            try:
                self.reader = easyocr.Reader(["en"], gpu=self.device=="cuda")
                logger.info(f"Successfully initialized EasyOCR on {self.device}")
            except RuntimeError as e:
                logger.warning(f"Failed to initialize EasyOCR with {self.device}, falling back to CPU: {str(e)}")
                self.device = "cpu"
                self.reader = easyocr.Reader(["en"], gpu=False)

        except Exception as e:
            logger.error(f"Error initializing verification service: {str(e)}")
            raise

    def verify_license(self, license_image, expected_number: str, issuing_authority: str) -> Dict[str, Any]:
        """Verify license details using OCR"""
        try:
            # Convert InMemoryUploadedFile to numpy array
            image = Image.open(license_image)
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            # Convert to numpy array
            image_np = np.array(image)

            # Use EasyOCR to read text
            results = self.reader.readtext(image_np)
            
            # Extract text from results
            text = " ".join([result[1] for result in results])
            
            # Look for license number
            license_found = any(
                expected_number.lower() in result[1].lower() 
                for result in results
            )
            
            # Look for issuing authority
            authority_found = any(
                issuing_authority.lower() in result[1].lower() 
                for result in results
            )

            # Look for expiry date
            expiry_date = self._extract_expiry_date(text)

            if license_found and authority_found:
                return {
                    "success": True,
                    "license_number": expected_number,
                    "issuing_authority": issuing_authority,
                    "license_expiry": expiry_date,
                    "confidence": "high" if expiry_date else "medium"
                }
            else:
                return {
                    "success": False,
                    "error": "Could not verify license number or issuing authority"
                }

        except Exception as e:
            logger.error(f"License verification error: {str(e)}")
            return {
                "success": False,
                "error": "Error processing license image"
            }

    def verify_face_match(self, license_image, selfie_image, threshold: float = 0.6) -> Dict[str, Any]:
        """Verify face match between license and selfie"""
        try:
            # Convert InMemoryUploadedFile objects to numpy arrays
            license_face = Image.open(license_image)
            selfie_face = Image.open(selfie_image)

            # Convert to RGB if necessary
            if license_face.mode != 'RGB':
                license_face = license_face.convert('RGB')
            if selfie_face.mode != 'RGB':
                selfie_face = selfie_face.convert('RGB')

            # Convert to numpy arrays
            license_np = np.array(license_face)
            selfie_np = np.array(selfie_face)

            # Get face encodings
            license_encoding = face_recognition.face_encodings(license_np)
            selfie_encoding = face_recognition.face_encodings(selfie_np)

            if not license_encoding or not selfie_encoding:
                return {
                    "success": False,
                    "error": "Could not detect faces in one or both images",
                    "details": {
                        "license_face_found": bool(license_encoding),
                        "selfie_face_found": bool(selfie_encoding)
                    }
                }

            # Compare faces
            match = face_recognition.compare_faces(
                [license_encoding[0]], selfie_encoding[0], tolerance=threshold
            )[0]

            # Get face distance for confidence score
            face_distance = face_recognition.face_distance(
                [license_encoding[0]], selfie_encoding[0]
            )[0]

            # Convert distance to similarity score (0-1)
            confidence = 1 - face_distance

            return {
                "success": True,
                "match": bool(match),
                "confidence": float(confidence),
                "details": {
                    "distance_score": float(face_distance),
                    "threshold_used": threshold
                }
            }

        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return {
                "success": False,
                "error": "Error processing face verification",
                "details": {"error_message": str(e)}
            }

    def _extract_expiry_date(self, text: str) -> str:
        """Extract expiry date from license text"""
        date_patterns = [
            r'(?:Expir(?:es|y|ation)(?:\s+(?:date|on))?:?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(?:Valid\s+(?:through|until):?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Try different date formats
                    for date_format in ["%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y"]:
                        try:
                            date_obj = datetime.strptime(matches[0], date_format)
                            return date_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                except Exception as e:
                    logger.error(f"Error parsing date: {str(e)}")

        return None
