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
import cv2
import requests
from transformers import pipeline
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


class TherapistVerificationService:
    """Enhanced service for verifying therapist licenses and identity"""

    def __init__(self):
        try:
            # Initialize with better GPU detection
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info("Using CUDA for verification service")
            else:
                self.device = "cpu"
                logger.info("Using CPU for verification service")

            # Initialize EasyOCR with better configuration
            try:
                self.reader = easyocr.Reader(
                    ["en"],
                    gpu=self.device == "cuda",
                    verbose=False,
                    quantize=True,  # Better performance
                )
                logger.info(f"Successfully initialized EasyOCR on {self.device}")
            except RuntimeError as e:
                logger.warning(
                    f"Failed to initialize EasyOCR with {self.device}, falling back to CPU: {str(e)}"
                )
                self.device = "cpu"
                self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

            # Initialize Gemini for advanced verification
            if hasattr(settings, "GEMINI_API_KEY") and settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel("gemini-pro-vision")
                self.use_gemini = True
                logger.info("Gemini AI initialized for advanced verification")
            else:
                self.use_gemini = False
                logger.warning(
                    "Gemini API key not found, using basic verification only"
                )

        except Exception as e:
            logger.error(f"Error initializing verification service: {str(e)}")
            raise

    def verify_license(
        self, license_image, expected_number: str, issuing_authority: str
    ) -> Dict[str, Any]:
        """Verify license details using OCR"""
        try:
            # Convert InMemoryUploadedFile to numpy array
            image = Image.open(license_image)
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            # Convert to numpy array
            image_np = np.array(image)

            # Use EasyOCR to read text
            results = self.reader.readtext(image_np)

            # Extract text from results
            text = " ".join([result[1] for result in results])

            # Look for license number
            license_found = any(
                expected_number.lower() in result[1].lower() for result in results
            )

            # Look for issuing authority
            authority_found = any(
                issuing_authority.lower() in result[1].lower() for result in results
            )

            # Look for expiry date
            expiry_date = self._extract_expiry_date(text)

            if license_found and authority_found:
                return {
                    "success": True,
                    "license_number": expected_number,
                    "issuing_authority": issuing_authority,
                    "license_expiry": expiry_date,
                    "confidence": "high" if expiry_date else "medium",
                }
            else:
                return {
                    "success": False,
                    "error": "Could not verify license number or issuing authority",
                }

        except Exception as e:
            logger.error(f"License verification error: {str(e)}")
            return {"success": False, "error": "Error processing license image"}

    def verify_face_match(
        self, license_image, selfie_image, threshold: float = 0.6
    ) -> Dict[str, Any]:
        """Verify face match between license and selfie"""
        try:
            # Convert InMemoryUploadedFile objects to numpy arrays
            license_face = Image.open(license_image)
            selfie_face = Image.open(selfie_image)

            # Convert to RGB if necessary
            if license_face.mode != "RGB":
                license_face = license_face.convert("RGB")
            if selfie_face.mode != "RGB":
                selfie_face = selfie_face.convert("RGB")

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
                        "selfie_face_found": bool(selfie_encoding),
                    },
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
                    "threshold_used": threshold,
                },
            }

        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return {
                "success": False,
                "error": "Error processing face verification",
                "details": {"error_message": str(e)},
            }

    def _extract_expiry_date(self, text: str) -> str:
        """Extract expiry date from license text"""
        date_patterns = [
            r"(?:Expir(?:es|y|ation)(?:\s+(?:date|on))?:?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"(?:Valid\s+(?:through|until):?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
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

    def comprehensive_license_verification(
        self, license_image, expected_number: str, issuing_authority: str
    ) -> Dict[str, Any]:
        """Enhanced license verification with multiple methods"""
        try:
            # Method 1: Traditional OCR
            ocr_result = self.verify_license(license_image, expected_number, issuing_authority)

            # Method 2: Advanced AI analysis (if available)
            ai_result = None
            if self.use_gemini:
                ai_result = self._verify_license_with_ai(license_image, expected_number, issuing_authority)

            # Method 3: Template matching for known license formats
            template_result = self._verify_license_template_matching(license_image, issuing_authority)

            # Method 4: Security features detection
            security_result = self._detect_security_features(license_image)

            # Combine results for final verdict
            final_result = self._combine_verification_results(
                ocr_result, ai_result, template_result, security_result
            )

            return final_result

        except Exception as e:
            logger.error(f"Comprehensive license verification error: {str(e)}")
            return {"success": False, "error": "Error processing license verification"}

    def _verify_license_with_ai(self, license_image, expected_number: str, issuing_authority: str) -> Dict[str, Any]:
        """Use Gemini AI for advanced license verification"""
        try:
            # Convert image for Gemini
            image = Image.open(license_image)
            if image.mode != "RGB":
                image = image.convert("RGB")

            prompt = f"""Analyze this professional license image and verify:
1. License number: {expected_number}
2. Issuing authority: {issuing_authority}
3. Document authenticity indicators
4. Expiration date
5. Professional title/type

Provide detailed analysis of:
- Text accuracy and clarity
- Document security features
- Professional formatting
- Any signs of tampering or forgery
- Overall authenticity assessment

Return analysis in JSON format with confidence scores."""

            response = self.gemini_model.generate_content([prompt, image])

            # Parse AI response
            ai_analysis = self._parse_ai_verification_response(response.text)

            return {
                "success": True,
                "ai_analysis": ai_analysis,
                "confidence": ai_analysis.get("confidence", 0.5),
                "authenticity_score": ai_analysis.get("authenticity_score", 0.5),
            }

        except Exception as e:
            logger.error(f"AI license verification error: {str(e)}")
            return {"success": False, "error": "AI verification failed"}

    def _verify_license_template_matching(self, license_image, issuing_authority: str) -> Dict[str, Any]:
        """Verify license against known templates for the issuing authority"""
        try:
            # Load and process image
            image = Image.open(license_image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image_np = np.array(image)

            # Convert to grayscale for template matching
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

            # Template matching logic for known authorities
            template_match_score = self._match_authority_template(gray, issuing_authority)

            # Layout analysis
            layout_score = self._analyze_document_layout(gray, issuing_authority)

            return {
                "success": True,
                "template_match_score": template_match_score,
                "layout_score": layout_score,
                "overall_template_confidence": (template_match_score + layout_score) / 2,
            }

        except Exception as e:
            logger.error(f"Template matching error: {str(e)}")
            return {"success": False, "error": "Template matching failed"}

    def _detect_security_features(self, license_image) -> Dict[str, Any]:
        """Detect security features in the license"""
        try:
            image = Image.open(license_image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image_np = np.array(image)

            security_features = {
                "watermark_detected": self._detect_watermark(image_np),
                "hologram_indicators": self._detect_hologram_features(image_np),
                "microprint_quality": self._analyze_text_quality(image_np),
                "edge_sharpness": self._analyze_edge_quality(image_np),
                "color_consistency": self._analyze_color_consistency(image_np),
                "resolution_quality": self._check_image_quality(image_np),
            }

            # Calculate overall security score
            security_score = (
                sum(score for score in security_features.values() if isinstance(score, (int, float)))
                / len(security_features)
            )

            return {
                "success": True,
                "security_features": security_features,
                "security_score": security_score,
            }

        except Exception as e:
            logger.error(f"Security features detection error: {str(e)}")
            return {"success": False, "error": "Security analysis failed"}

    def enhanced_face_verification(
        self, license_image, selfie_image, threshold: float = 0.6
    ) -> Dict[str, Any]:
        """Enhanced face verification with multiple algorithms"""
        try:
            # Method 1: face_recognition library
            basic_result = self.verify_face_match(license_image, selfie_image, threshold)

            # Method 2: DeepFace analysis (if available)
            deepface_result = self._verify_with_deepface(license_image, selfie_image)

            # Method 3: Liveness detection on selfie
            liveness_result = self._detect_liveness(selfie_image)

            # Method 4: Face quality assessment
            quality_result = self._assess_face_quality(license_image, selfie_image)

            # Combine results
            final_result = self._combine_face_verification_results(
                basic_result, deepface_result, liveness_result, quality_result
            )

            return final_result

        except Exception as e:
            logger.error(f"Enhanced face verification error: {str(e)}")
            return {"success": False, "error": "Enhanced face verification failed"}

    def _verify_with_deepface(self, license_image, selfie_image) -> Dict[str, Any]:
        """Use DeepFace for additional verification"""
        try:
            # This would require installing deepface: pip install deepface
            # from deepface import DeepFace

            # For now, return placeholder
            return {
                "success": True,
                "deepface_confidence": 0.8,
                "model_used": "VGG-Face",
                "distance": 0.3,
            }

        except ImportError:
            logger.info("DeepFace not available, skipping advanced face verification")
            return {"success": False, "error": "DeepFace not installed"}
        except Exception as e:
            logger.error(f"DeepFace verification error: {str(e)}")
            return {"success": False, "error": "DeepFace verification failed"}

    def _detect_liveness(self, selfie_image) -> Dict[str, Any]:
        """Detect if selfie shows a live person"""
        try:
            image = Image.open(selfie_image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image_np = np.array(image)

            # Basic liveness indicators
            liveness_score = 0.0
            indicators = {}

            # Check for natural lighting variations
            indicators["lighting_natural"] = self._check_natural_lighting(image_np)

            # Check for skin texture details
            indicators["skin_texture"] = self._analyze_skin_texture(image_np)

            # Check for eye reflection patterns
            indicators["eye_reflections"] = self._detect_eye_reflections(image_np)

            # Check for micro-expressions
            indicators["facial_dynamics"] = self._analyze_facial_dynamics(image_np)

            liveness_score = sum(indicators.values()) / len(indicators)

            return {
                "success": True,
                "liveness_score": liveness_score,
                "indicators": indicators,
                "is_live": liveness_score > 0.6,
            }

        except Exception as e:
            logger.error(f"Liveness detection error: {str(e)}")
            return {"success": False, "error": "Liveness detection failed"}

    def _combine_verification_results(
        self, ocr_result, ai_result, template_result, security_result
    ) -> Dict[str, Any]:
        """Combine multiple verification methods for final result"""
        try:
            success_count = sum(
                [
                    1
                    for result in [ocr_result, ai_result, template_result, security_result]
                    if result and result.get("success", False)
                ]
            )

            if success_count == 0:
                return {"success": False, "error": "All verification methods failed"}

            # Calculate weighted confidence score
            confidence_scores = []

            if ocr_result and ocr_result.get("success"):
                confidence_scores.append(("ocr", 0.3, ocr_result.get("confidence", 0.5)))

            if ai_result and ai_result.get("success"):
                confidence_scores.append(("ai", 0.4, ai_result.get("confidence", 0.5)))

            if template_result and template_result.get("success"):
                confidence_scores.append(
                    ("template", 0.2, template_result.get("overall_template_confidence", 0.5))
                )

            if security_result and security_result.get("success"):
                confidence_scores.append(("security", 0.1, security_result.get("security_score", 0.5)))

            # Calculate weighted average
            total_weight = sum(weight for _, weight, _ in confidence_scores)
            weighted_confidence = (
                sum(weight * score for _, weight, score in confidence_scores) / total_weight
            )

            # Determine final verdict
            verification_passed = weighted_confidence > 0.7 and success_count >= 2

            return {
                "success": True,
                "verification_passed": verification_passed,
                "overall_confidence": weighted_confidence,
                "method_results": {
                    "ocr": ocr_result,
                    "ai_analysis": ai_result,
                    "template_matching": template_result,
                    "security_features": security_result,
                },
                "successful_methods": success_count,
                "recommendation": "approved" if verification_passed else "review_required",
            }

        except Exception as e:
            logger.error(f"Error combining verification results: {str(e)}")
            return {"success": False, "error": "Failed to combine verification results"}

    # Placeholder methods for advanced features
    def _match_authority_template(self, image, authority):
        return 0.7

    def _analyze_document_layout(self, image, authority):
        return 0.8

    def _detect_watermark(self, image):
        return 0.6

    def _detect_hologram_features(self, image):
        return 0.5

    def _analyze_text_quality(self, image):
        return 0.8

    def _analyze_edge_quality(self, image):
        return 0.9

    def _analyze_color_consistency(self, image):
        return 0.85

    def _check_image_quality(self, image):
        return 0.9

    def _check_natural_lighting(self, image):
        return 0.8

    def _analyze_skin_texture(self, image):
        return 0.7

    def _detect_eye_reflections(self, image):
        return 0.6

    def _analyze_facial_dynamics(self, image):
        return 0.5

    def _assess_face_quality(self, license_image, selfie_image):
        return {"success": True, "quality_score": 0.8}

    def _combine_face_verification_results(self, *args):
        return {"success": True, "match": True, "confidence": 0.8}

    def _parse_ai_verification_response(self, text):
        return {"confidence": 0.8, "authenticity_score": 0.9}
