# therapist/services/therapist_verification_service.py
import numpy as np
import cv2
from deepface import DeepFace
import easyocr
import logging
from datetime import datetime
from PIL import Image
import io
import re
from django.core.files.uploadedfile import InMemoryUploadedFile
from pathlib import Path

logger = logging.getLogger(__name__)


class TherapistVerificationService:
    def __init__(self):
        self.reader = easyocr.Reader(["en"])
        self.face_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def verify_license(
        self, license_image, expected_number=None, issuing_authority=None
    ):
        """
        Verify license authenticity and extract information with enhanced validation

        Args:
            license_image: The license image file
            expected_number: The license number provided by the therapist
            issuing_authority: The authority that issued the license
        """
        try:
            # Validate input image
            if not isinstance(license_image, InMemoryUploadedFile):
                return {"success": False, "error": "Invalid image format"}

            # Convert to OpenCV format
            img_bytes = license_image.read()
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"success": False, "error": "Could not process license image"}

            # Read text from image
            results = self.reader.readtext(img)
            extracted_text = " ".join([text[1] for text in results])

            # Extract license information using regex patterns
            license_info = self._extract_license_info(extracted_text)

            # Validate against expected license number if provided
            if expected_number and license_info.get("license_number"):
                if not self._verify_license_number_match(
                    license_info["license_number"], expected_number
                ):
                    return {
                        "success": False,
                        "error": "Detected license number does not match provided number",
                    }

            # Validate issuing authority if provided
            if issuing_authority and not re.search(
                re.escape(issuing_authority), extracted_text, re.IGNORECASE
            ):
                return {
                    "success": False,
                    "error": "Could not verify issuing authority on license",
                }

            # Check for license expiration
            if (
                license_info.get("expiry_date")
                and license_info["expiry_date"] < datetime.now().date()
            ):
                return {
                    "success": False,
                    "error": "License has expired",
                    "expiry_date": license_info["expiry_date"].isoformat(),
                }

            # Successful verification
            return {
                "success": True,
                "license_number": license_info.get("license_number"),
                "license_expiry": license_info.get("expiry_date"),
                "extracted_text": extracted_text,
                "verification_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"License verification failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def verify_face_match(self, license_image, selfie_image, threshold=0.7):
        """
        Compare face in license with selfie using enhanced security measures

        Args:
            license_image: The license image containing the face
            selfie_image: The selfie image to verify against
            threshold: Confidence threshold for face matching (0.7 = 70% confidence required)
        """
        try:
            # Input validation
            if not all(
                isinstance(img, InMemoryUploadedFile)
                for img in [license_image, selfie_image]
            ):
                return {"success": False, "error": "Invalid image format"}

            # Convert images to PIL format
            license_bytes = license_image.read()
            selfie_bytes = selfie_image.read()

            try:
                license_img = Image.open(io.BytesIO(license_bytes))
                selfie_img = Image.open(io.BytesIO(selfie_bytes))
            except Exception as e:
                return {"success": False, "error": f"Error opening images: {str(e)}"}

            # Verify image dimensions and size
            for img, name in [(license_img, "license"), (selfie_img, "selfie")]:
                if not self._verify_image_requirements(img, name):
                    return {
                        "success": False,
                        "error": f"Invalid {name} image dimensions or size",
                    }

            # Save temporary files for DeepFace
            license_path = "temp_license.jpg"
            selfie_path = "temp_selfie.jpg"

            try:
                license_img.save(license_path)
                selfie_img.save(selfie_path)

                # Detect faces first
                if not self._verify_face_present(cv2.imread(license_path)):
                    return {
                        "success": False,
                        "error": "No face detected in license photo",
                    }
                if not self._verify_face_present(cv2.imread(selfie_path)):
                    return {"success": False, "error": "No face detected in selfie"}

                # Perform face verification with enhanced parameters
                result = DeepFace.verify(
                    img1_path=license_path,
                    img2_path=selfie_path,
                    enforce_detection=True,
                    detector_backend="opencv",
                    model_name="VGG-Face",
                    distance_metric="cosine",
                    align=True,
                )

                verified = result.get("verified", False)
                confidence = 1 - result.get(
                    "distance", 1.0
                )  # Convert distance to confidence

                # Apply stricter threshold
                if confidence < threshold:
                    return {
                        "success": True,
                        "match": False,
                        "confidence": confidence,
                        "error": "Face match confidence below threshold",
                        "details": result,
                    }

                return {
                    "success": True,
                    "match": verified,
                    "confidence": confidence,
                    "details": result,
                }

            finally:
                # Ensure cleanup
                try:
                    Path(license_path).unlink(missing_ok=True)
                    Path(selfie_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary files: {str(e)}")

        except Exception as e:
            logger.error(f"Face verification failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _verify_face_present(self, image):
        """Verify that exactly one face is present in the image"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.face_detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            return len(faces) == 1
        except Exception as e:
            logger.error(f"Face detection error: {str(e)}")
            return False

    def _verify_image_requirements(self, img, image_type):
        """Verify image meets minimum requirements"""
        try:
            # Check dimensions
            min_width = 300
            min_height = 300
            max_dimension = 4000
            width, height = img.size

            if width < min_width or height < min_height:
                logger.warning(f"{image_type} image too small: {width}x{height}")
                return False

            if width > max_dimension or height > max_dimension:
                logger.warning(f"{image_type} image too large: {width}x{height}")
                return False

            # Verify aspect ratio is reasonable (not extremely skewed)
            aspect_ratio = width / height
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                logger.warning(
                    f"Unusual aspect ratio in {image_type} image: {aspect_ratio}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking image requirements: {str(e)}")
            return False

    def _verify_license_number_match(self, detected_number, provided_number):
        """
        Compare detected license number with provided number using fuzzy matching
        to account for OCR variations
        """
        # Remove all non-alphanumeric characters for comparison
        clean_detected = re.sub(r"[^a-zA-Z0-9]", "", detected_number)
        clean_provided = re.sub(r"[^a-zA-Z0-9]", "", provided_number)

        # Case-insensitive comparison
        return clean_detected.lower() == clean_provided.lower()

    def _extract_license_info(self, text):
        """Extract license information from text using regex patterns"""
        # Common patterns for license numbers and dates
        license_patterns = [
            r"License[:\s]+([A-Z0-9-]+)",
            r"Registration[:\s]+([A-Z0-9-]+)",
            r"Number[:\s]+([A-Z0-9-]+)",
            r"#([A-Z0-9-]+)",
            r"Certificate[:\s]+([A-Z0-9-]+)",
            r"ID[:\s]+([A-Z0-9-]+)",
        ]

        date_patterns = [
            r"Expir\w+[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Valid[:\s]+(?:until|through)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"(?:End|Expiry)[:\s]+Date[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Expires[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ]

        license_number = None
        expiry_date = None

        # Search for license number
        for pattern in license_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                license_number = match.group(1).strip()
                break

        # Search for expiry date
        for pattern in date_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                date_str = match.group(1)
                try:
                    # Try different date formats
                    for fmt in [
                        "%m/%d/%Y",
                        "%m-%d-%Y",
                        "%d/%m/%Y",
                        "%d-%m/%Y",
                        "%m/%d/%y",
                        "%d/%m/%y",
                    ]:
                        try:
                            expiry_date = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Could not parse date '{date_str}': {str(e)}")
                break

        return {"license_number": license_number, "expiry_date": expiry_date}
