# datawarehouse/services/audit_trail.py
"""
Comprehensive Audit Trail Service for Data Changes
Tracks all data modifications, access patterns, and system events with detailed logging
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

# Import models from the main models module to avoid conflicts
from ..models import AuditLog, DataChangeHistory, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditTrailService:
    """
    Comprehensive audit trail service for tracking all data changes and system events
    
    Features:
    - Automatic change tracking for all models
    - User action logging
    - Security event monitoring
    - Data integrity verification
    - Compliance reporting
    - Real-time audit alerts
    - Historical data analysis
    """
    
    def __init__(self):
        self.excluded_fields = {'password', 'last_login', 'date_joined'}
        self.sensitive_fields = {'ssn', 'medical_record', 'diagnosis', 'prescription'}
        
    def log_event(
        self,
        event_type: str,
        event_name: str,
        user=None,
        obj=None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        severity: str = AuditSeverity.LOW,
        action_details: Optional[Dict] = None,
        request_data: Optional[Dict] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_module: Optional[str] = None
    ) -> AuditLog:
        """
        Log an audit event with comprehensive details
        """
        try:
            # Prepare object information
            content_type = None
            object_id = None
            object_repr = None
            
            if obj:
                content_type = ContentType.objects.get_for_model(obj)
                object_id = str(obj.pk)
                object_repr = str(obj)[:200]
            
            # Create audit log entry
            audit_log = AuditLog.objects.create(
                event_type=event_type,
                event_name=event_name,
                severity=severity,
                user=user,
                session_id=session_id,
                user_agent=user_agent,
                ip_address=ip_address,
                content_type=content_type,
                object_id=object_id,
                object_repr=object_repr,
                old_values=self._sanitize_values(old_values),
                new_values=self._sanitize_values(new_values),
                changed_fields=self._get_changed_fields(old_values, new_values),
                action_details=action_details or {},
                request_data=self._sanitize_request_data(request_data),
                correlation_id=correlation_id,
                source_module=source_module,
                tags=tags or []
            )
            
            # Log detailed field changes for sensitive data
            if old_values and new_values:
                self._log_field_changes(audit_log, old_values, new_values)
            
            # Trigger alerts for high-severity events
            if severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
                self._trigger_audit_alert(audit_log)
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            # Create minimal audit log for the error itself
            try:
                return AuditLog.objects.create(
                    event_type=AuditEventType.ERROR,
                    event_name="audit_logging_error",
                    severity=AuditSeverity.HIGH,
                    error_message=str(e),
                    action_details={"original_event": event_name}
                )
            except Exception:
                # If even error logging fails, just log to system logger
                logger.critical(f"Critical error in audit logging: {e}")
                return None
    
    def log_model_change(
        self,
        action: str,
        obj,
        user=None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        **kwargs
    ) -> AuditLog:
        """Log model-specific changes"""
        
        event_name = f"{obj._meta.model_name}_{action}"
        severity = self._determine_severity(obj, action)
        
        return self.log_event(
            event_type=action,
            event_name=event_name,
            user=user,
            obj=obj,
            old_values=old_values,
            new_values=new_values,
            severity=severity,
            source_module=obj._meta.app_label,
            **kwargs
        )
    
    def log_user_action(
        self,
        action: str,
        user,
        details: Optional[Dict] = None,
        severity: str = AuditSeverity.LOW,
        **kwargs
    ) -> AuditLog:
        """Log user-specific actions"""
        
        return self.log_event(
            event_type=AuditEventType.ACCESS,
            event_name=f"user_{action}",
            user=user,
            severity=severity,
            action_details=details,
            source_module="user_actions",
            **kwargs
        )
    
    def log_security_event(
        self,
        event_name: str,
        details: Dict[str, Any],
        user=None,
        severity: str = AuditSeverity.HIGH,
        **kwargs
    ) -> AuditLog:
        """Log security-related events"""
        
        return self.log_event(
            event_type=AuditEventType.SECURITY,
            event_name=event_name,
            user=user,
            severity=severity,
            action_details=details,
            source_module="security",
            tags=["security"],
            **kwargs
        )
    
    def log_api_call(
        self,
        endpoint: str,
        method: str,
        user=None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        **kwargs
    ) -> AuditLog:
        """Log API calls for monitoring and debugging"""
        
        severity = AuditSeverity.MEDIUM if status_code and status_code >= 400 else AuditSeverity.LOW
        success = status_code is None or status_code < 400
        
        return self.log_event(
            event_type=AuditEventType.API_CALL,
            event_name=f"{method}_{endpoint}",
            user=user,
            severity=severity,
            request_data=request_data,
            response_data=response_data,
            action_details={
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code
            },
            duration_ms=duration_ms,
            success=success,
            source_module="api",
            **kwargs
        )
    
    def get_audit_trail(
        self,
        obj=None,
        user=None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        severity: Optional[str] = None
    ) -> List:
        """Retrieve audit trail with filtering options"""
        
        queryset = AuditLog.objects.all()
        
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            queryset = queryset.filter(
                content_type=content_type,
                object_id=str(obj.pk)
            )
        
        if user:
            queryset = queryset.filter(user=user)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        if event_types:
            queryset = queryset.filter(event_type__in=event_types)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return list(queryset.select_related('user', 'content_type'))
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        include_user_actions: bool = True,
        include_data_changes: bool = True,
        include_security_events: bool = True
    ) -> Dict[str, Any]:
        """Generate compliance report for audit requirements"""
        
        queryset = AuditLog.objects.filter(
            timestamp__range=[start_date, end_date]
        )
        
        # Filter by event types if specified
        event_types = []
        if include_user_actions:
            event_types.extend([AuditEventType.LOGIN, AuditEventType.LOGOUT, AuditEventType.ACCESS])
        if include_data_changes:
            event_types.extend([AuditEventType.CREATE, AuditEventType.UPDATE, AuditEventType.DELETE])
        if include_security_events:
            event_types.append(AuditEventType.SECURITY)
        
        if event_types:
            queryset = queryset.filter(event_type__in=event_types)
        
        # Aggregate statistics
        total_events = queryset.count()
        events_by_type = dict(queryset.values_list('event_type').annotate(count=models.Count('id')))
        events_by_severity = dict(queryset.values_list('severity').annotate(count=models.Count('id')))
        events_by_user = dict(
            queryset.exclude(user=None)
            .values_list('user__username')
            .annotate(count=models.Count('id'))
        )
        
        # Security incidents
        security_incidents = queryset.filter(
            severity__in=[AuditSeverity.HIGH, AuditSeverity.CRITICAL]
        ).count()
        
        # Failed operations
        failed_operations = queryset.filter(success=False).count()
        
        return {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_events': total_events,
                'security_incidents': security_incidents,
                'failed_operations': failed_operations,
                'unique_users': len(events_by_user)
            },
            'breakdown': {
                'events_by_type': events_by_type,
                'events_by_severity': events_by_severity,
                'events_by_user': events_by_user
            },
            'generated_at': timezone.now().isoformat()
        }
    
    def verify_audit_integrity(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Verify the integrity of audit log entries"""
        
        queryset = AuditLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        total_entries = queryset.count()
        corrupted_entries = []
        
        for audit_log in queryset.iterator():
            if not audit_log.verify_integrity():
                corrupted_entries.append({
                    'id': audit_log.id,
                    'timestamp': audit_log.timestamp.isoformat(),
                    'event_name': audit_log.event_name,
                    'stored_checksum': audit_log.checksum,
                    'calculated_checksum': audit_log._generate_checksum()
                })
        
        integrity_percentage = ((total_entries - len(corrupted_entries)) / total_entries * 100) if total_entries > 0 else 100
        
        return {
            'total_entries': total_entries,
            'corrupted_entries': len(corrupted_entries),
            'integrity_percentage': round(integrity_percentage, 2),
            'corrupted_details': corrupted_entries,
            'verification_timestamp': timezone.now().isoformat()
        }
    
    def _sanitize_values(self, values: Optional[Dict]) -> Optional[Dict]:
        """Sanitize sensitive values before storage"""
        if not values:
            return values
        
        sanitized = {}
        for key, value in values.items():
            if key.lower() in self.excluded_fields:
                continue
            elif key.lower() in self.sensitive_fields:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_request_data(self, request_data: Optional[Dict]) -> Optional[Dict]:
        """Sanitize request data before storage"""
        if not request_data:
            return request_data
        
        # Remove sensitive fields from request data
        sanitized = dict(request_data)
        for field_name in self.excluded_fields:
            sanitized.pop(field_name, None)
        
        return sanitized
    
    def _get_changed_fields(self, old_values: Optional[Dict], new_values: Optional[Dict]) -> List[str]:
        """Get list of fields that changed"""
        if not old_values or not new_values:
            return []
        
        changed = []
        all_fields = set(old_values.keys()) | set(new_values.keys())
        
        for field_name in all_fields:
            old_val = old_values.get(field_name)
            new_val = new_values.get(field_name)
            if old_val != new_val:
                changed.append(field_name)
        
        return changed
    
    def _determine_severity(self, obj: models.Model, action: str) -> str:
        """Determine severity based on object type and action"""
        
        # High sensitivity models
        sensitive_models = {'patientprofile', 'medicalhistory', 'prescription', 'diagnosis'}
        
        if obj._meta.model_name.lower() in sensitive_models:
            return AuditSeverity.HIGH if action == AuditEventType.DELETE else AuditSeverity.MEDIUM
        
        return AuditSeverity.LOW
    
    def _log_field_changes(self, audit_log: AuditLog, old_values: Dict, new_values: Dict):
        """Log detailed field-level changes"""
        
        changed_fields = self._get_changed_fields(old_values, new_values)
        
        for field_name in changed_fields:
            old_value = old_values.get(field_name)
            new_value = new_values.get(field_name)
            
            # Determine if field is sensitive
            is_sensitive = field_name.lower() in self.sensitive_fields
            
            DataChangeHistory.objects.create(
                audit_log=audit_log,
                field_name=field_name,
                old_value=str(old_value) if not is_sensitive else "[REDACTED]",
                new_value=str(new_value) if not is_sensitive else "[REDACTED]",
                field_type=type(old_value).__name__ if old_value else type(new_value).__name__,
                is_encrypted=is_sensitive
            )
    
    def _trigger_audit_alert(self, audit_log: AuditLog):
        """Trigger alerts for high-severity audit events"""
        try:
            # Send alert to administrators
            logger.warning(
                f"High-severity audit event: {audit_log.event_name} "
                f"by user {audit_log.user} at {audit_log.timestamp}"
            )
            
            # Could integrate with notification system here
            # notifications.send_audit_alert(audit_log)
            
        except Exception as e:
            logger.error(f"Error triggering audit alert: {e}")


# Global service instance
audit_service = AuditTrailService()


# Django signal receivers for automatic audit logging
@receiver(pre_save)
def capture_old_values(sender, instance, **kwargs):
    """Capture old values before save for audit trail"""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = {
                field.name: getattr(old_instance, field.name)
                for field in sender._meta.fields
                if hasattr(old_instance, field.name)
            }
        except sender.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """Automatically log model saves"""
    
    # Skip audit logs to prevent recursion
    if sender == AuditLog or sender == DataChangeHistory:
        return
    
    try:
        action = AuditEventType.CREATE if created else AuditEventType.UPDATE
        old_values = getattr(instance, '_old_values', {}) if not created else None
        new_values = {
            field.name: getattr(instance, field.name)
            for field in sender._meta.fields
            if hasattr(instance, field.name)
        } if not created else None
        
        # Get user from request context if available
        user = getattr(instance, '_audit_user', None)
        
        audit_service.log_model_change(
            action=action,
            obj=instance,
            user=user,
            old_values=old_values,
            new_values=new_values
        )
        
    except Exception as e:
        logger.error(f"Error in automatic audit logging: {e}")


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """Automatically log model deletions"""
    
    # Skip audit logs to prevent recursion
    if sender == AuditLog or sender == DataChangeHistory:
        return
    
    try:
        old_values = {
            field.name: getattr(instance, field.name)
            for field in sender._meta.fields
            if hasattr(instance, field.name)
        }
        
        # Get user from request context if available
        user = getattr(instance, '_audit_user', None)
        
        audit_service.log_model_change(
            action=AuditEventType.DELETE,
            obj=instance,
            user=user,
            old_values=old_values
        )
        
    except Exception as e:
        logger.error(f"Error in automatic audit logging: {e}")
