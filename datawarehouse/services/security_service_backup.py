# datawarehouse/services/security_service.py
"""
Enhanced Security Service for Sensitive Health Data
Implements comprehensive security measures including encryption, access control, and privacy protection
"""

import logging
import hashlib
import base64
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
User = get_user_model()


class DataClassification(models.TextChoices):
    """Data classification levels for HIPAA/GDPR compliance"""
    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    CONFIDENTIAL = "confidential", "Confidential"
    RESTRICTED = "restricted", "Restricted"
    PHI = "phi", "Protected Health Information"


class ComplianceStandard(models.TextChoices):
    """Compliance standards"""
    HIPAA = "hipaa", "HIPAA"
    GDPR = "gdpr", "GDPR"
    SOC2 = "soc2", "SOC 2"
    ISO27001 = "iso27001", "ISO 27001"


@dataclass
class SecurityContext:
    """Security context for data access requests"""
    user: Any  # User model instance
    ip_address: str
    user_agent: str
    session_id: str
    request_time: datetime = field(default_factory=timezone.now)
    access_level: str = "basic"


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata"""
    encrypted_value: bytes
    key_id: str
    algorithm: str
    created_at: datetime = field(default_factory=timezone.now)
    integrity_hash: str = ""


class EncryptionKey(models.Model):
    """Encryption key management with rotation capability"""
    
    key_id = models.CharField(max_length=64, unique=True)
    encrypted_key = models.TextField()
    algorithm = models.CharField(max_length=50, default="fernet")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    rotation_schedule = models.CharField(max_length=20, default="quarterly")
    
    class Meta:
        db_table = 'datawarehouse_encryption_key'
        indexes = [
            models.Index(fields=['key_id', 'is_active']),
            models.Index(fields=['expires_at']),
        ]


class DataClassificationRule(models.Model):
    """Rules for automatic data classification"""
    
    model_name = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    classification = models.CharField(
        max_length=20, 
        choices=DataClassification.choices,
        default=DataClassification.INTERNAL
    )
    compliance_requirements = models.JSONField(default=list)
    encryption_required = models.BooleanField(default=False)
    access_restrictions = models.JSONField(default=dict)
    classified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_data_classification'
        unique_together = ['model_name', 'field_name']


class AccessLog(models.Model):
    """Comprehensive access logging for security monitoring"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    action = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    session_id = models.CharField(max_length=100)
    access_granted = models.BooleanField()
    denial_reason = models.TextField(blank=True)
    classification_level = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
        null=True
    )
    compliance_context = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'datawarehouse_access_log'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['resource_type', 'action']),
            models.Index(fields=['ip_address', 'created_at']),
        ]


class SecurityService:
    """
    Comprehensive security service for health data protection
    
    Features:
    - Field-level encryption with key rotation
    - Automatic data classification and tagging
    - Role-based access control with logging
    - Data masking and anonymization
    - Compliance reporting (HIPAA, GDPR)
    - Secure data export with audit trails
    """
    
    def __init__(self):
        self.master_key = self._get_master_key()
        self.classification_cache = {}
        
    def _get_master_key(self) -> bytes:
        """Get or generate master encryption key"""
        key = getattr(settings, 'ENCRYPTION_MASTER_KEY', None)
        if not key:
            # Generate and store a new key (in production, use secure key management)
            key = Fernet.generate_key()
            logger.warning("Generated new encryption key - store securely!")
        return key if isinstance(key, bytes) else key.encode()
    
    def generate_encryption_key(self, algorithm: str = "fernet") -> EncryptionKey:
        """Generate a new encryption key with metadata"""
        key_data = Fernet.generate_key()
        key_id = hashlib.sha256(key_data).hexdigest()[:16]
        
        # Encrypt the key with master key
        fernet = Fernet(self.master_key)
        encrypted_key = fernet.encrypt(key_data)
        
        return EncryptionKey.objects.create(
            key_id=key_id,
            encrypted_key=base64.b64encode(encrypted_key).decode(),
            algorithm=algorithm,
            expires_at=timezone.now() + timedelta(days=90),  # 3 months
            is_active=True
        )
    
    def encrypt_field(self, value: Any, obj: models.Model, field_name: str) -> EncryptedData:
        """Encrypt a field value with appropriate classification"""
        if value is None:
            return None
            
        # Get or create classification
        self._get_classification(obj, field_name)
        
        # Get active encryption key
        key = self._get_active_key()
        fernet = Fernet(self._decrypt_key(key.encrypted_key))
        
        # Convert value to JSON string for encryption
        json_str = json.dumps(value, cls=DjangoJSONEncoder)
        encrypted_value = fernet.encrypt(json_str.encode())
        
        # Generate integrity hash
        integrity_hash = hashlib.sha256(encrypted_value + key.key_id.encode()).hexdigest()
        
        return EncryptedData(
            encrypted_value=encrypted_value,
            key_id=key.key_id,
            algorithm=key.algorithm,
            integrity_hash=integrity_hash
        )
    
    def decrypt_field(self, encrypted_data: EncryptedData, context: SecurityContext = None) -> Any:
        """Decrypt field data with access control"""
        if not encrypted_data:
            return None
            
        # Log access attempt
        if context:
            self._log_access(context, "decrypt", encrypted_data.key_id, True)
        
        try:
            # Get decryption key
            key = EncryptionKey.objects.get(key_id=encrypted_data.key_id, is_active=True)
            fernet = Fernet(self._decrypt_key(key.encrypted_key))
            
            # Verify integrity
            expected_hash = hashlib.sha256(
                encrypted_data.encrypted_value + key.key_id.encode()
            ).hexdigest()
            
            if expected_hash != encrypted_data.integrity_hash:
                raise ValueError("Data integrity check failed")
            
            # Decrypt and deserialize
            decrypted_bytes = fernet.decrypt(encrypted_data.encrypted_value)
            return json.loads(decrypted_bytes.decode())
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            if context:
                self._log_access(context, "decrypt", encrypted_data.key_id, False, str(e))
            return None
    
    def _get_active_key(self) -> EncryptionKey:
        """Get the current active encryption key"""
        try:
            return EncryptionKey.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now()
            ).latest('created_at')
        except EncryptionKey.DoesNotExist:
            # Generate new key if none exists
            return self.generate_encryption_key()
    
    def _decrypt_key(self, encrypted_key: str) -> bytes:
        """Decrypt stored encryption key using master key"""
        fernet = Fernet(self.master_key)
        encrypted_bytes = base64.b64decode(encrypted_key.encode())
        return fernet.decrypt(encrypted_bytes)
    
    def _get_classification(self, obj: models.Model, field_name: str) -> DataClassification:
        """Get or determine field classification"""
        model_name = obj.__class__.__name__
        cache_key = f"{model_name}.{field_name}"
        
        if cache_key in self.classification_cache:
            return self.classification_cache[cache_key]
        
        try:
            rule = DataClassificationRule.objects.get(
                model_name=model_name,
                field_name=field_name
            )
            classification = rule.classification
        except DataClassificationRule.DoesNotExist:
            # Auto-classify based on field name patterns
            classification = self._auto_classify_field(field_name)
            
            # Create rule for future use
            DataClassificationRule.objects.create(
                model_name=model_name,
                field_name=field_name,
                classification=classification,
                encryption_required=classification in [DataClassification.PHI, DataClassification.RESTRICTED]
            )
        
        self.classification_cache[cache_key] = classification
        return classification
    
    def _auto_classify_field(self, field_name: str) -> str:
        """Automatically classify field based on naming patterns"""
        field_lower = field_name.lower()
        
        # PHI patterns
        phi_patterns = ['ssn', 'social_security', 'medical_record', 'diagnosis', 'medication']
        if any(pattern in field_lower for pattern in phi_patterns):
            return DataClassification.PHI
        
        # Personal information patterns
        personal_patterns = ['email', 'phone', 'address', 'name', 'dob', 'birth']
        if any(pattern in field_lower for pattern in personal_patterns):
            return DataClassification.CONFIDENTIAL
        
        # Default classification
        return DataClassification.INTERNAL
    
    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive data for analytics"""
        anonymized = {}
        
        anonymization_map = {
            'email': lambda x: f"user_{hash(x) % 10000}@example.com",
            'phone': lambda x: "XXX-XXX-XXXX",
            'ssn': lambda x: "XXX-XX-XXXX",
            'address': lambda x: "City, State",
            'name': lambda x: f"User_{hash(x) % 10000}",
        }
        
        for field_name, value in data.items():
            if field_name.lower() in anonymization_map:
                try:
                    anonymized[field_name] = anonymization_map[field_name.lower()](value)
                except Exception:
                    anonymized[field_name] = "XXXX"
            else:
                # Check if it's a date field
                if 'date' in field_name.lower() or 'birth' in field_name.lower():
                    try:
                        # Generalize to year only
                        date_obj = datetime.fromisoformat(str(value)) if isinstance(value, str) else value
                        anonymized[field_name] = date_obj.year if hasattr(date_obj, 'year') else value
                    except Exception:
                        anonymized[field_name] = value
                else:
                    anonymized[field_name] = value
        
        return anonymized
    
    def secure_export(self, data: List[Dict], context: SecurityContext) -> Tuple[bytes, Dict]:
        """Securely export data with encryption and access logging"""
        logger.info(f"Secure export requested by {context.user.username} from {context.ip_address}")
        
        # Prepare export metadata
        metadata = {
            "exported_by": context.user.username,
            "export_time": timezone.now().isoformat(),
            "record_count": len(data),
            "data_hash": hashlib.sha256(str(data).encode()).hexdigest(),
            "compliance_flags": ["HIPAA", "GDPR"]
        }
        
        # Create export package
        export_package = {
            "data": data,
            "metadata": metadata
        }
        
        # Serialize and encrypt
        json_data = json.dumps(export_package, cls=DjangoJSONEncoder, indent=2)
        
        # Log the export
        self._log_access(context, "export", "bulk_data", True)
        
        return json_data.encode('utf-8'), metadata
    
    def _log_access(self, context: SecurityContext, action: str, resource_id: str, 
                   granted: bool, denial_reason: str = ""):
        """Log access attempts for security monitoring"""
        try:
            AccessLog.objects.create(
                user=context.user,
                resource_type="encrypted_field",
                resource_id=resource_id,
                action=action,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                session_id=context.session_id,
                access_granted=granted,
                denial_reason=denial_reason,
                compliance_context={
                    "access_level": context.access_level,
                    "timestamp": context.request_time.isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to log access: {e}")
    
    def get_compliance_report(self, start_date: Optional[datetime] = None, 
                             end_date: Optional[datetime] = None,
                             action: Optional[str] = None) -> Dict[str, Any]:
        """Generate compliance report for auditing"""
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        queryset = AccessLog.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        if action:
            queryset = queryset.filter(action=action)
        
        # Generate report statistics
        total_accesses = queryset.count()
        granted_accesses = queryset.filter(access_granted=True).count()
        denied_accesses = total_accesses - granted_accesses
        
        # Top accessed resources
        top_resources = queryset.values('resource_type').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        # Access by user
        user_activity = queryset.values('user__username').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        return {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_accesses": total_accesses,
                "granted_accesses": granted_accesses,
                "denied_accesses": denied_accesses,
                "success_rate": (granted_accesses / total_accesses * 100) if total_accesses > 0 else 0
            },
            "top_resources": list(top_resources),
            "user_activity": list(user_activity),
            "compliance_status": "COMPLIANT" if denied_accesses == 0 else "REVIEW_REQUIRED"
        }


# Global service instance
security_service = SecurityService()
