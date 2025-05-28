import requests
import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.cache import cache
import hashlib

logger = logging.getLogger(__name__)


class LicenseVerificationService:
    """Service for real-time license verification with external databases"""

    def __init__(self):
        self.cache_timeout = 3600  # 1 hour cache
        
        # External API configurations
        self.verification_apis = {
            "State Medical Board": {
                "base_url": "https://api.state-medical-board.gov",
                "api_key": settings.MEDICAL_BOARD_API_KEY if hasattr(settings, 'MEDICAL_BOARD_API_KEY') else None,
                "verify_endpoint": "/v1/verify-license"
            },
            "State Board of Psychology": {
                "base_url": "https://api.psychology-board.gov", 
                "api_key": settings.PSYCHOLOGY_BOARD_API_KEY if hasattr(settings, 'PSYCHOLOGY_BOARD_API_KEY') else None,
                "verify_endpoint": "/v1/verify-license"
            },
            # Add more boards as needed
        }

    def verify_license_with_external_database(
        self, license_number: str, issuing_authority: str, therapist_name: str = None
    ) -> Dict[str, Any]:
        """Verify license with external database"""
        
        # Check cache first
        cache_key = self._generate_cache_key(license_number, issuing_authority)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"License verification cache hit for {license_number}")
            return cached_result

        try:
            # Get API configuration for this authority
            api_config = self.verification_apis.get(issuing_authority)
            if not api_config or not api_config.get("api_key"):
                logger.warning(f"No API configuration for authority: {issuing_authority}")
                return self._create_manual_verification_result(license_number, issuing_authority)

            # Make API request
            verification_result = self._query_external_api(
                api_config, license_number, therapist_name
            )

            # Cache successful results
            if verification_result.get("success"):
                cache.set(cache_key, verification_result, self.cache_timeout)

            return verification_result

        except Exception as e:
            logger.error(f"External license verification error: {str(e)}")
            return {
                "success": False,
                "error": "External verification failed",
                "fallback_required": True
            }

    def _query_external_api(
        self, api_config: Dict, license_number: str, therapist_name: str = None
    ) -> Dict[str, Any]:
        """Query external API for license verification"""
        try:
            url = f"{api_config['base_url']}{api_config['verify_endpoint']}"
            
            headers = {
                "Authorization": f"Bearer {api_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "license_number": license_number,
                "verification_type": "full"
            }
            
            if therapist_name:
                payload["practitioner_name"] = therapist_name

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self._process_api_response(data, license_number)
            elif response.status_code == 404:
                return {
                    "success": True,
                    "verified": False,
                    "status": "not_found",
                    "message": "License not found in database"
                }
            else:
                logger.error(f"API returned status {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }

        except requests.RequestException as e:
            logger.error(f"Request error in external API query: {str(e)}")
            return {
                "success": False,
                "error": "Network error during verification"
            }

    def _process_api_response(self, data: Dict, license_number: str) -> Dict[str, Any]:
        """Process and standardize API response"""
        try:
            # Standardize response format across different APIs
            return {
                "success": True,
                "verified": data.get("is_valid", False),
                "status": data.get("status", "unknown"),
                "license_details": {
                    "number": data.get("license_number", license_number),
                    "status": data.get("license_status", "unknown"),
                    "issue_date": data.get("issue_date"),
                    "expiry_date": data.get("expiry_date"),
                    "practitioner_name": data.get("practitioner_name"),
                    "specializations": data.get("specializations", []),
                    "restrictions": data.get("restrictions", []),
                    "disciplinary_actions": data.get("disciplinary_actions", [])
                },
                "verification_timestamp": data.get("verification_timestamp"),
                "data_source": data.get("source", "external_api"),
                "confidence": 0.95  # High confidence for official database
            }

        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            return {
                "success": False,
                "error": "Failed to process verification response"
            }

    def verify_multiple_databases(
        self, license_number: str, issuing_authority: str, therapist_name: str = None
    ) -> Dict[str, Any]:
        """Verify license across multiple available databases"""
        results = {}
        overall_verified = False
        highest_confidence = 0.0

        # Try primary database first
        primary_result = self.verify_license_with_external_database(
            license_number, issuing_authority, therapist_name
        )
        results["primary"] = primary_result

        if primary_result.get("verified"):
            overall_verified = True
            highest_confidence = primary_result.get("confidence", 0.8)

        # Try secondary verification sources
        secondary_results = self._verify_secondary_sources(license_number, issuing_authority)
        results["secondary"] = secondary_results

        # Cross-reference with professional directories
        directory_results = self._verify_professional_directories(license_number, therapist_name)
        results["directories"] = directory_results

        return {
            "overall_verified": overall_verified,
            "confidence": highest_confidence,
            "verification_sources": results,
            "recommendations": self._generate_verification_recommendations(results)
        }

    def _verify_secondary_sources(self, license_number: str, issuing_authority: str) -> Dict[str, Any]:
        """Verify with secondary sources like professional organizations"""
        # Placeholder for secondary verification
        return {
            "apa_verified": False,  # American Psychological Association
            "nasp_verified": False,  # National Association of School Psychologists
            "other_professional_orgs": []
        }

    def _verify_professional_directories(self, license_number: str, therapist_name: str) -> Dict[str, Any]:
        """Verify with professional directories and listings"""
        # Placeholder for directory verification
        return {
            "psychology_today": False,
            "professional_directories": [],
            "academic_affiliations": []
        }

    def _create_manual_verification_result(self, license_number: str, issuing_authority: str) -> Dict[str, Any]:
        """Create result for manual verification when APIs are unavailable"""
        return {
            "success": True,
            "verified": False,
            "requires_manual_verification": True,
            "authority": issuing_authority,
            "license_number": license_number,
            "message": "Manual verification required - external API not available",
            "confidence": 0.0
        }

    def _generate_cache_key(self, license_number: str, issuing_authority: str) -> str:
        """Generate cache key for verification results"""
        combined = f"{license_number}:{issuing_authority}"
        return f"license_verification:{hashlib.md5(combined.encode()).hexdigest()}"

    def _generate_verification_recommendations(self, results: Dict) -> List[str]:
        """Generate recommendations based on verification results"""
        recommendations = []
        
        primary = results.get("primary", {})
        if primary.get("verified"):
            recommendations.append("License verified through official database")
        elif primary.get("requires_manual_verification"):
            recommendations.append("Manual verification recommended due to API unavailability")
        
        if not results.get("overall_verified"):
            recommendations.extend([
                "Consider requesting additional documentation",
                "Verify therapist credentials through alternative means",
                "Contact issuing authority directly for verification"
            ])
        
        return recommendations


# Create singleton instance
license_verification_service = LicenseVerificationService()
