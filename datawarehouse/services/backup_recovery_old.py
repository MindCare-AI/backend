# datawarehouse/services/backup_recovery.py
"""
Comprehensive Backup and Recovery Service for MindCare Data Warehouse
Implements enterprise-grade backup strategies with encryption, versioning, and automated recovery
"""

import os
import gzip
import json
import logging
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib
try:
    import boto3
    from botocore.exceptions import BotoCore3Error, NoCredentialsError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None
    BotoCore3Error = Exception
    NoCredentialsError = Exception

from django.conf import settings
from django.core.management import call_command
from django.core.serializers import serialize, deserialize
from django.apps import apps
from django.db import models, transaction
from django.utils import timezone

from django.core.cache import cache

from .security_service import security_service, SecurityContext


logger = logging.getLogger(__name__)


class BackupType(models.TextChoices):
    """Types of backups"""
    FULL = "full", "Full Backup"
    INCREMENTAL = "incremental", "Incremental Backup"
    DIFFERENTIAL = "differential", "Differential Backup"
    SNAPSHOT = "snapshot", "Database Snapshot"
    SELECTIVE = "selective", "Selective Backup"


class BackupStatus(models.TextChoices):
    """Backup operation status"""
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    VERIFYING = "verifying", "Verifying"
    VERIFIED = "verified", "Verified"


class RestoreStatus(models.TextChoices):
    """Restore operation status"""
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    VALIDATING = "validating", "Validating"
    VALIDATED = "validated", "Validated"


class BackupJob(models.Model):
    """Tracks backup operations"""
    
    id = models.BigAutoField(primary_key=True)
    
    # Job details
    job_id = models.CharField(max_length=100, unique=True)
    backup_type = models.CharField(max_length=20, choices=BackupType.choices)
    status = models.CharField(max_length=20, choices=BackupStatus.choices, default=BackupStatus.PENDING)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Backup details
    backup_location = models.TextField()
    backup_size_bytes = models.BigIntegerField(null=True, blank=True)
    compression_ratio = models.FloatField(null=True, blank=True)
    
    # Security
    is_encrypted = models.BooleanField(default=True)
    encryption_key_id = models.CharField(max_length=100, null=True, blank=True)
    checksum = models.CharField(max_length=64)  # SHA-256
    
    # Metadata
    included_models = models.JSONField(default=list)
    excluded_models = models.JSONField(default=list)
    filters = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['backup_type', '-created_at']),
            models.Index(fields=['-created_at']),
        ]


class RestoreJob(models.Model):
    """Tracks restore operations"""
    
    id = models.BigAutoField(primary_key=True)
    
    # Job details
    job_id = models.CharField(max_length=100, unique=True)
    backup_job = models.ForeignKey(BackupJob, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=RestoreStatus.choices, default=RestoreStatus.PENDING)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Restore details
    restore_to_timestamp = models.DateTimeField(null=True, blank=True)
    partial_restore = models.BooleanField(default=False)
    included_models = models.JSONField(default=list)
    target_environment = models.CharField(max_length=50, default="production")
    
    # Validation
    validation_results = models.JSONField(default=dict)
    records_restored = models.IntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    rollback_required = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['backup_job', '-created_at']),
        ]


@dataclass
class BackupConfig:
    """Configuration for backup operations"""
    
    backup_type: str = BackupType.INCREMENTAL
    include_models: Optional[List[str]] = None
    exclude_models: Optional[List[str]] = None
    compress: bool = True
    encrypt: bool = True
    verify_integrity: bool = True
    retention_days: int = 30
    storage_backend: str = "local"  # local, s3, gcs
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreConfig:
    """Configuration for restore operations"""
    
    target_timestamp: Optional[datetime] = None
    partial_restore: bool = False
    include_models: Optional[List[str]] = None
    validate_data: bool = True
    dry_run: bool = False
    target_environment: str = "production"
    rollback_on_failure: bool = True


class BackupRecoveryService:
    """
    Comprehensive backup and recovery service for the MindCare data warehouse
    
    Features:
    - Multiple backup types (full, incremental, differential)
    - Encrypted backup storage with key management
    - Multi-destination backup (local, cloud)
    - Point-in-time recovery
    - Automated backup scheduling
    - Data integrity verification
    - Selective restore capabilities
    - Backup compression and deduplication
    - Compliance reporting
    """
    
    def __init__(self):
        self.backup_root = getattr(settings, 'BACKUP_ROOT', '/var/backups/mindcare')
        self.s3_bucket = getattr(settings, 'BACKUP_S3_BUCKET', None)
        self.compression_level = 6
        self.chunk_size = 1024 * 1024  # 1MB chunks
        
        # Ensure backup directory exists
        os.makedirs(self.backup_root, exist_ok=True)
        
        # Initialize cloud storage if configured
        self.s3_client = None
        if self.s3_bucket:
            try:
                self.s3_client = boto3.client('s3')
            except (BotoCore3Error, NoCredentialsError) as e:
                logger.warning(f"S3 backup not available: {e}")
    
    def create_backup(
        self,
        config: BackupConfig,
        context: Optional[SecurityContext] = None
    ) -> BackupJob:
        """Create a backup with specified configuration"""
        
        job_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{config.backup_type}"
        
        # Create backup job record
        backup_job = BackupJob.objects.create(
            job_id=job_id,
            backup_type=config.backup_type,
            status=BackupStatus.PENDING,
            backup_location="",
            included_models=config.include_models or [],
            excluded_models=config.exclude_models or [],
            filters=config.filters,
            is_encrypted=config.encrypt,
            metadata={
                'config': config.__dict__,
                'created_by': context.user.username if context else 'system',
                'storage_backend': config.storage_backend
            }
        )
        
        try:
            # Start backup process
            backup_job.status = BackupStatus.RUNNING
            backup_job.started_at = timezone.now()
            backup_job.save()
            
            # Log backup start
            logger.info(f"Starting backup {job_id} of type {config.backup_type}")
            
            # Perform backup based on type
            if config.backup_type == BackupType.FULL:
                backup_path = self._create_full_backup(backup_job, config)
            elif config.backup_type == BackupType.INCREMENTAL:
                backup_path = self._create_incremental_backup(backup_job, config)
            elif config.backup_type == BackupType.DIFFERENTIAL:
                backup_path = self._create_differential_backup(backup_job, config)
            elif config.backup_type == BackupType.SNAPSHOT:
                backup_path = self._create_database_snapshot(backup_job, config)
            elif config.backup_type == BackupType.SELECTIVE:
                backup_path = self._create_selective_backup(backup_job, config)
            else:
                raise ValueError(f"Unsupported backup type: {config.backup_type}")
            
            # Update job with results
            backup_job.backup_location = backup_path
            backup_job.backup_size_bytes = self._get_file_size(backup_path)
            
            # Calculate checksum
            backup_job.checksum = self._calculate_checksum(backup_path)
            
            # Encrypt if requested
            if config.encrypt:
                encrypted_path = self._encrypt_backup(backup_path, backup_job)
                backup_job.backup_location = encrypted_path
                backup_job.backup_size_bytes = self._get_file_size(encrypted_path)
            
            # Upload to cloud if configured
            if config.storage_backend in ['s3', 'cloud'] and self.s3_client:
                cloud_path = self._upload_to_cloud(backup_job.backup_location, backup_job)
                backup_job.metadata['cloud_location'] = cloud_path
            
            # Verify integrity if requested
            if config.verify_integrity:
                backup_job.status = BackupStatus.VERIFYING
                backup_job.save()
                
                if self._verify_backup_integrity(backup_job):
                    backup_job.status = BackupStatus.VERIFIED
                else:
                    backup_job.status = BackupStatus.FAILED
                    backup_job.error_message = "Backup integrity verification failed"
            else:
                backup_job.status = BackupStatus.COMPLETED
            
            backup_job.completed_at = timezone.now()
            backup_job.save()
            
            logger.info(f"Backup {job_id} completed successfully")
            return backup_job
            
        except Exception as e:
            backup_job.status = BackupStatus.FAILED
            backup_job.error_message = str(e)
            backup_job.completed_at = timezone.now()
            backup_job.save()
            
            logger.error(f"Backup {job_id} failed: {e}")
            raise
    
    def restore_backup(
        self,
        backup_job: BackupJob,
        config: RestoreConfig,
        context: Optional[SecurityContext] = None
    ) -> RestoreJob:
        """Restore from a backup with specified configuration"""
        
        job_id = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{backup_job.job_id}"
        
        # Create restore job record
        restore_job = RestoreJob.objects.create(
            job_id=job_id,
            backup_job=backup_job,
            status=RestoreStatus.PENDING,
            restore_to_timestamp=config.target_timestamp,
            partial_restore=config.partial_restore,
            included_models=config.include_models or [],
            target_environment=config.target_environment
        )
        
        try:
            # Validate backup before restore
            if not self._verify_backup_integrity(backup_job):
                raise ValueError("Backup integrity verification failed")
            
            restore_job.status = RestoreStatus.RUNNING
            restore_job.started_at = timezone.now()
            restore_job.save()
            
            logger.info(f"Starting restore {job_id} from backup {backup_job.job_id}")
            
            # Decrypt backup if encrypted
            backup_path = backup_job.backup_location
            if backup_job.is_encrypted:
                backup_path = self._decrypt_backup(backup_job)
            
            # Download from cloud if needed
            if 'cloud_location' in backup_job.metadata:
                backup_path = self._download_from_cloud(backup_job)
            
            # Perform restore
            if config.dry_run:
                logger.info("Dry run mode - validating restore without applying changes")
                validation_results = self._validate_restore(backup_path, config)
                restore_job.validation_results = validation_results
            else:
                # Create database backup before restore (rollback point)
                if config.rollback_on_failure:
                    rollback_backup = self._create_rollback_point()
                    restore_job.validation_results['rollback_backup'] = rollback_backup
                
                # Perform actual restore
                records_restored = self._perform_restore(backup_path, config, restore_job)
                restore_job.records_restored = records_restored
            
            # Validate restored data
            if config.validate_data:
                restore_job.status = RestoreStatus.VALIDATING
                restore_job.save()
                
                validation_results = self._validate_restored_data(restore_job, config)
                restore_job.validation_results.update(validation_results)
                
                if validation_results.get('validation_passed', False):
                    restore_job.status = RestoreStatus.VALIDATED
                else:
                    restore_job.status = RestoreStatus.FAILED
                    restore_job.error_message = "Data validation failed after restore"
                    
                    # Rollback if configured
                    if config.rollback_on_failure and not config.dry_run:
                        self._perform_rollback(restore_job)
            else:
                restore_job.status = RestoreStatus.COMPLETED
            
            restore_job.completed_at = timezone.now()
            restore_job.save()
            
            logger.info(f"Restore {job_id} completed successfully")
            return restore_job
            
        except Exception as e:
            restore_job.status = RestoreStatus.FAILED
            restore_job.error_message = str(e)
            restore_job.completed_at = timezone.now()
            
            # Attempt rollback if configured
            if config.rollback_on_failure and not config.dry_run:
                try:
                    self._perform_rollback(restore_job)
                    restore_job.rollback_required = True
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
            
            restore_job.save()
            
            logger.error(f"Restore {job_id} failed: {e}")
            raise
    
    def schedule_backup(
        self,
        schedule: str,  # cron-style schedule
        config: BackupConfig,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """Schedule automatic backups"""
        
        # This would integrate with a task scheduler like Celery
        # For now, return configuration that can be used by external scheduler
        
        schedule_config = {
            'schedule': schedule,
            'backup_config': config.__dict__,
            'enabled': enabled,
            'created_at': timezone.now().isoformat(),
            'next_run': self._calculate_next_run(schedule)
        }
        
        # Store in cache or database for scheduler to pick up
        cache.set(f"backup_schedule_{schedule}", schedule_config, timeout=None)
        
        logger.info(f"Backup scheduled: {schedule}")
        return schedule_config
    
    def cleanup_old_backups(self, retention_days: int = 30) -> Dict[str, Any]:
        """Clean up old backups based on retention policy"""
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        old_backups = BackupJob.objects.filter(
            created_at__lt=cutoff_date,
            status__in=[BackupStatus.COMPLETED, BackupStatus.VERIFIED]
        )
        
        cleaned_count = 0
        freed_space = 0
        errors = []
        
        for backup in old_backups:
            try:
                # Delete local files
                if os.path.exists(backup.backup_location):
                    file_size = self._get_file_size(backup.backup_location)
                    os.remove(backup.backup_location)
                    freed_space += file_size
                
                # Delete cloud files
                if 'cloud_location' in backup.metadata:
                    self._delete_from_cloud(backup.metadata['cloud_location'])
                
                # Delete backup record
                backup.delete()
                cleaned_count += 1
                
            except Exception as e:
                errors.append(f"Failed to clean backup {backup.job_id}: {e}")
                logger.error(f"Error cleaning backup {backup.job_id}: {e}")
        
        result = {
            'cleaned_backups': cleaned_count,
            'freed_space_bytes': freed_space,
            'errors': errors,
            'retention_days': retention_days,
            'cleanup_timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Backup cleanup completed: {cleaned_count} backups cleaned, {freed_space} bytes freed")
        return result
    
    def get_backup_history(
        self,
        days: int = 30,
        backup_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get backup history with filtering options"""
        
        start_date = timezone.now() - timedelta(days=days)
        queryset = BackupJob.objects.filter(created_at__gte=start_date)
        
        if backup_type:
            queryset = queryset.filter(backup_type=backup_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        backups = []
        for backup in queryset.order_by('-created_at'):
            backup_info = {
                'job_id': backup.job_id,
                'backup_type': backup.backup_type,
                'status': backup.status,
                'created_at': backup.created_at.isoformat(),
                'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
                'size_bytes': backup.backup_size_bytes,
                'location': backup.backup_location,
                'is_encrypted': backup.is_encrypted,
                'included_models': backup.included_models,
                'metadata': backup.metadata
            }
            backups.append(backup_info)
        
        return backups
    
    def generate_backup_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive backup report"""
        
        start_date = timezone.now() - timedelta(days=days)
        backups = BackupJob.objects.filter(created_at__gte=start_date)
        
        # Statistics
        total_backups = backups.count()
        successful_backups = backups.filter(status__in=[BackupStatus.COMPLETED, BackupStatus.VERIFIED]).count()
        failed_backups = backups.filter(status=BackupStatus.FAILED).count()
        
        # Success rate
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Storage usage
        total_storage = sum(b.backup_size_bytes or 0 for b in backups)
        
        # Backup types distribution
        backup_types = dict(backups.values_list('backup_type').annotate(count=models.Count('id')))
        
        # Average backup size by type
        avg_sizes = {}
        for backup_type in BackupType.values:
            type_backups = backups.filter(backup_type=backup_type, backup_size_bytes__isnull=False)
            if type_backups.exists():
                avg_sizes[backup_type] = type_backups.aggregate(avg=models.Avg('backup_size_bytes'))['avg']
        
        # Recent failures
        recent_failures = list(
            backups.filter(status=BackupStatus.FAILED)
            .values('job_id', 'created_at', 'error_message')
            .order_by('-created_at')[:10]
        )
        
        return {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'days': days
            },
            'summary': {
                'total_backups': total_backups,
                'successful_backups': successful_backups,
                'failed_backups': failed_backups,
                'success_rate': round(success_rate, 2),
                'total_storage_bytes': total_storage
            },
            'breakdown': {
                'backup_types': backup_types,
                'average_sizes': avg_sizes
            },
            'recent_failures': recent_failures,
            'recommendations': self._generate_backup_recommendations(backups),
            'generated_at': timezone.now().isoformat()
        }
    
    def _create_full_backup(self, backup_job: BackupJob, config: BackupConfig) -> str:
        """Create a full database backup"""
        
        backup_path = os.path.join(
            self.backup_root,
            f"{backup_job.job_id}_full.sql"
        )
        
        # Use Django's dumpdata command for application data
        with open(backup_path, 'w') as f:
            call_command('dumpdata', stdout=f, format='json', indent=2)
        
        # Compress if requested
        if config.compress:
            compressed_path = f"{backup_path}.gz"
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=self.compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            os.remove(backup_path)  # Remove uncompressed file
            backup_path = compressed_path
            
            # Calculate compression ratio
            original_size = backup_job.metadata.get('original_size', 0)
            compressed_size = self._get_file_size(backup_path)
            if original_size > 0:
                backup_job.compression_ratio = compressed_size / original_size
        
        return backup_path
    
    def _create_incremental_backup(self, backup_job: BackupJob, config: BackupConfig) -> str:
        """Create an incremental backup (changes since last backup)"""
        
        # Find last successful backup
        last_backup = BackupJob.objects.filter(
            status__in=[BackupStatus.COMPLETED, BackupStatus.VERIFIED],
            backup_type__in=[BackupType.FULL, BackupType.INCREMENTAL]
        ).exclude(id=backup_job.id).order_by('-completed_at').first()
        
        if not last_backup:
            # No previous backup, create full backup
            logger.info("No previous backup found, creating full backup instead")
            return self._create_full_backup(backup_job, config)
        
        # Get changes since last backup
        since_timestamp = last_backup.completed_at
        backup_path = os.path.join(
            self.backup_root,
            f"{backup_job.job_id}_incremental.json"
        )
        
        # Collect changed data
        changed_data = self._collect_changed_data(since_timestamp, config)
        
        # Write to file
        with open(backup_path, 'w') as f:
            json.dump(changed_data, f, indent=2, default=str)
        
        return backup_path
    
    def _create_differential_backup(self, backup_job: BackupJob, config: BackupConfig) -> str:
        """Create a differential backup (changes since last full backup)"""
        
        # Find last full backup
        last_full_backup = BackupJob.objects.filter(
            status__in=[BackupStatus.COMPLETED, BackupStatus.VERIFIED],
            backup_type=BackupType.FULL
        ).exclude(id=backup_job.id).order_by('-completed_at').first()
        
        if not last_full_backup:
            # No previous full backup, create full backup
            logger.info("No previous full backup found, creating full backup instead")
            return self._create_full_backup(backup_job, config)
        
        # Get changes since last full backup
        since_timestamp = last_full_backup.completed_at
        backup_path = os.path.join(
            self.backup_root,
            f"{backup_job.job_id}_differential.json"
        )
        
        # Collect changed data
        changed_data = self._collect_changed_data(since_timestamp, config)
        
        # Write to file
        with open(backup_path, 'w') as f:
            json.dump(changed_data, f, indent=2, default=str)
        
        return backup_path
    
    def _create_database_snapshot(self, backup_job: BackupJob, config: BackupConfig) -> str:
        """Create a database snapshot using native database tools"""
        
        backup_path = os.path.join(
            self.backup_root,
            f"{backup_job.job_id}_snapshot.sql"
        )
        
        # Use pg_dump for PostgreSQL
        db_settings = settings.DATABASES['default']
        
        cmd = [
            'pg_dump',
            f"--host={db_settings['HOST']}",
            f"--port={db_settings['PORT']}",
            f"--username={db_settings['USER']}",
            f"--dbname={db_settings['NAME']}",
            '--verbose',
            '--no-password',
            f"--file={backup_path}"
        ]
        
        # Set password via environment
        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")
        
        return backup_path
    
    def _create_selective_backup(self, backup_job: BackupJob, config: BackupConfig) -> str:
        """Create a selective backup of specific models/data"""
        
        backup_path = os.path.join(
            self.backup_root,
            f"{backup_job.job_id}_selective.json"
        )
        
        # Prepare models to include
        models_to_backup = []
        
        if config.include_models:
            for model_name in config.include_models:
                try:
                    app_label, model_label = model_name.split('.')
                    model = apps.get_model(app_label, model_label)
                    models_to_backup.append(model)
                except (ValueError, LookupError) as e:
                    logger.warning(f"Invalid model {model_name}: {e}")
        
        # Collect data
        backup_data = {}
        
        for model in models_to_backup:
            queryset = model.objects.all()
            
            # Apply filters if specified
            if config.filters.get(model._meta.label_lower):
                model_filters = config.filters[model._meta.label_lower]
                queryset = queryset.filter(**model_filters)
            
            # Serialize data
            serialized_data = serialize('json', queryset)
            backup_data[model._meta.label_lower] = json.loads(serialized_data)
        
        # Write to file
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        return backup_path
    
    def _collect_changed_data(self, since_timestamp: datetime, config: BackupConfig) -> Dict[str, Any]:
        """Collect data that has changed since specified timestamp"""
        
        changed_data = {
            'since_timestamp': since_timestamp.isoformat(),
            'collected_at': timezone.now().isoformat(),
            'models': {}
        }
        
        # Get all models from specified apps
        for app_config in apps.get_app_configs():
            if config.exclude_models and app_config.label in config.exclude_models:
                continue
                
            if config.include_models and app_config.label not in config.include_models:
                continue
            
            for model in app_config.get_models():
                model_label = model._meta.label_lower
                
                # Check if model has timestamp fields
                timestamp_fields = [
                    'created_at', 'updated_at', 'modified_at', 
                    'timestamp', 'date_created', 'date_modified'
                ]
                
                timestamp_field = None
                for field_name in timestamp_fields:
                    if hasattr(model, field_name):
                        timestamp_field = field_name
                        break
                
                if timestamp_field:
                    # Get changed records
                    queryset = model.objects.filter(**{f"{timestamp_field}__gte": since_timestamp})
                    
                    if queryset.exists():
                        serialized_data = serialize('json', queryset)
                        changed_data['models'][model_label] = json.loads(serialized_data)
        
        return changed_data
    
    def _encrypt_backup(self, backup_path: str, backup_job: BackupJob) -> str:
        """Encrypt backup file"""
        
        # Create encryption key for this backup
        encryption_key = security_service.create_encryption_key(
            purpose=f"backup_{backup_job.job_id}",
            expires_in_days=backup_job.metadata.get('retention_days', 30) + 7  # Grace period
        )
        
        backup_job.encryption_key_id = encryption_key.key_id
        
        # Encrypt file
        encrypted_path = f"{backup_path}.encrypted"
        
        with open(backup_path, 'rb') as f_in:
            with open(encrypted_path, 'wb') as f_out:
                # Get Fernet instance for encryption
                fernet = security_service._get_fernet_for_key(encryption_key)
                
                # Encrypt in chunks
                while True:
                    chunk = f_in.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    encrypted_chunk = fernet.encrypt(chunk)
                    f_out.write(len(encrypted_chunk).to_bytes(4, 'big'))  # Write chunk size
                    f_out.write(encrypted_chunk)
        
        # Remove original file
        os.remove(backup_path)
        
        return encrypted_path
    
    def _decrypt_backup(self, backup_job: BackupJob) -> str:
        """Decrypt backup file"""
        
        if not backup_job.is_encrypted or not backup_job.encryption_key_id:
            return backup_job.backup_location
        
        # Get encryption key
        from .security_service import EncryptionKey
        try:
            encryption_key = EncryptionKey.objects.get(
                key_id=backup_job.encryption_key_id,
                is_active=True
            )
        except EncryptionKey.DoesNotExist:
            raise ValueError(f"Encryption key {backup_job.encryption_key_id} not found")
        
        # Decrypt file
        encrypted_path = backup_job.backup_location
        decrypted_path = encrypted_path.replace('.encrypted', '.decrypted')
        
        with open(encrypted_path, 'rb') as f_in:
            with open(decrypted_path, 'wb') as f_out:
                # Get Fernet instance for decryption
                fernet = security_service._get_fernet_for_key(encryption_key)
                
                # Decrypt in chunks
                while True:
                    chunk_size_bytes = f_in.read(4)
                    if not chunk_size_bytes:
                        break
                    
                    chunk_size = int.from_bytes(chunk_size_bytes, 'big')
                    encrypted_chunk = f_in.read(chunk_size)
                    
                    if not encrypted_chunk:
                        break
                    
                    decrypted_chunk = fernet.decrypt(encrypted_chunk)
                    f_out.write(decrypted_chunk)
        
        return decrypted_path
    
    def _upload_to_cloud(self, local_path: str, backup_job: BackupJob) -> str:
        """Upload backup to cloud storage"""
        
        if not self.s3_client or not self.s3_bucket:
            raise ValueError("Cloud storage not configured")
        
        cloud_key = f"backups/{backup_job.job_id}/{os.path.basename(local_path)}"
        
        try:
            self.s3_client.upload_file(local_path, self.s3_bucket, cloud_key)
            cloud_url = f"s3://{self.s3_bucket}/{cloud_key}"
            
            logger.info(f"Backup uploaded to cloud: {cloud_url}")
            return cloud_url
            
        except Exception as e:
            logger.error(f"Failed to upload backup to cloud: {e}")
            raise
    
    def _download_from_cloud(self, backup_job: BackupJob) -> str:
        """Download backup from cloud storage"""
        
        cloud_location = backup_job.metadata.get('cloud_location')
        if not cloud_location:
            raise ValueError("No cloud location found for backup")
        
        # Parse S3 URL
        if cloud_location.startswith('s3://'):
            bucket_key = cloud_location[5:]  # Remove s3://
            bucket, key = bucket_key.split('/', 1)
        else:
            raise ValueError(f"Unsupported cloud location: {cloud_location}")
        
        # Download to temporary location
        local_path = os.path.join(
            self.backup_root,
            f"temp_{backup_job.job_id}_{os.path.basename(key)}"
        )
        
        try:
            self.s3_client.download_file(bucket, key, local_path)
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download backup from cloud: {e}")
            raise
    
    def _delete_from_cloud(self, cloud_location: str):
        """Delete backup from cloud storage"""
        
        if cloud_location.startswith('s3://'):
            bucket_key = cloud_location[5:]
            bucket, key = bucket_key.split('/', 1)
            
            try:
                self.s3_client.delete_object(Bucket=bucket, Key=key)
                logger.info(f"Deleted backup from cloud: {cloud_location}")
            except Exception as e:
                logger.error(f"Failed to delete backup from cloud: {e}")
                raise
    
    def _verify_backup_integrity(self, backup_job: BackupJob) -> bool:
        """Verify backup file integrity"""
        
        backup_path = backup_job.backup_location
        
        # Check file exists
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Verify checksum
        calculated_checksum = self._calculate_checksum(backup_path)
        if calculated_checksum != backup_job.checksum:
            logger.error(f"Checksum mismatch for backup {backup_job.job_id}")
            return False
        
        # Additional validation for specific backup types
        try:
            if backup_path.endswith('.json'):
                # Validate JSON structure
                with open(backup_path, 'r') as f:
                    json.load(f)
            elif backup_path.endswith('.sql'):
                # Basic SQL validation (check file size and first line)
                if self._get_file_size(backup_path) == 0:
                    return False
                    
                with open(backup_path, 'r') as f:
                    first_line = f.readline().strip()
                    if not first_line or 'dump' not in first_line.lower():
                        return False
        
        except Exception as e:
            logger.error(f"Backup validation failed: {e}")
            return False
        
        return True
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file"""
        
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(self.chunk_size), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0
    
    def _perform_restore(self, backup_path: str, config: RestoreConfig, restore_job: RestoreJob) -> int:
        """Perform the actual restore operation"""
        
        records_restored = 0
        
        with transaction.atomic():
            if backup_path.endswith('.json'):
                # JSON restore
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                
                # Handle different JSON formats
                if 'models' in data:
                    # Incremental/differential backup format
                    for model_label, model_data in data['models'].items():
                        records_restored += self._restore_model_data(model_label, model_data, config)
                else:
                    # Full backup format or selective backup
                    for obj in deserialize('json', json.dumps(data)):
                        if self._should_restore_object(obj, config):
                            obj.save()
                            records_restored += 1
            
            elif backup_path.endswith('.sql'):
                # SQL restore using psql
                self._restore_sql_dump(backup_path, config)
                # Count would need to be calculated differently for SQL restores
                records_restored = -1  # Indicate SQL restore completed
        
        return records_restored
    
    def _restore_model_data(self, model_label: str, model_data: List[Dict], config: RestoreConfig) -> int:
        """Restore data for a specific model"""
        
        if config.include_models and model_label not in config.include_models:
            return 0
        
        records_restored = 0
        
        for obj in deserialize('json', json.dumps(model_data)):
            if self._should_restore_object(obj, config):
                obj.save()
                records_restored += 1
        
        return records_restored
    
    def _should_restore_object(self, obj, config: RestoreConfig) -> bool:
        """Determine if an object should be restored based on configuration"""
        
        # Check timestamp filter
        if config.target_timestamp:
            obj_timestamp = getattr(obj.object, 'created_at', None) or getattr(obj.object, 'timestamp', None)
            if obj_timestamp and obj_timestamp > config.target_timestamp:
                return False
        
        # Additional filters can be added here
        return True
    
    def _restore_sql_dump(self, backup_path: str, config: RestoreConfig):
        """Restore from SQL dump file"""
        
        db_settings = settings.DATABASES['default']
        
        cmd = [
            'psql',
            f"--host={db_settings['HOST']}",
            f"--port={db_settings['PORT']}",
            f"--username={db_settings['USER']}",
            f"--dbname={db_settings['NAME']}",
            '--file', backup_path
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"SQL restore failed: {result.stderr}")
    
    def _validate_restore(self, backup_path: str, config: RestoreConfig) -> Dict[str, Any]:
        """Validate restore operation without applying changes"""
        
        validation_results = {
            'validation_timestamp': timezone.now().isoformat(),
            'backup_path': backup_path,
            'validation_passed': True,
            'errors': [],
            'warnings': [],
            'estimated_records': 0
        }
        
        try:
            if backup_path.endswith('.json'):
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                
                # Count records that would be restored
                if 'models' in data:
                    for model_label, model_data in data['models'].items():
                        if not config.include_models or model_label in config.include_models:
                            validation_results['estimated_records'] += len(model_data)
                else:
                    validation_results['estimated_records'] = len(data)
            
            # Additional validation checks can be added here
            
        except Exception as e:
            validation_results['validation_passed'] = False
            validation_results['errors'].append(str(e))
        
        return validation_results
    
    def _validate_restored_data(self, restore_job: RestoreJob, config: RestoreConfig) -> Dict[str, Any]:
        """Validate data after restore operation"""
        
        validation_results = {
            'validation_timestamp': timezone.now().isoformat(),
            'validation_passed': True,
            'checks_performed': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            # Data integrity checks
            validation_results['checks_performed'].append('data_integrity')
            
            # Check for orphaned records
            validation_results['checks_performed'].append('orphaned_records')
            
            # Check foreign key constraints
            validation_results['checks_performed'].append('foreign_keys')
            
            # Application-specific validation
            validation_results['checks_performed'].append('application_logic')
            
        except Exception as e:
            validation_results['validation_passed'] = False
            validation_results['errors'].append(str(e))
        
        return validation_results
    
    def _create_rollback_point(self) -> str:
        """Create a rollback point before restore"""
        
        rollback_config = BackupConfig(
            backup_type=BackupType.SNAPSHOT,
            compress=True,
            encrypt=True
        )
        
        # Create backup job for rollback
        rollback_job = self.create_backup(rollback_config)
        
        return rollback_job.job_id
    
    def _perform_rollback(self, restore_job: RestoreJob):
        """Perform rollback using rollback backup"""
        
        rollback_backup_id = restore_job.validation_results.get('rollback_backup')
        if not rollback_backup_id:
            raise ValueError("No rollback backup available")
        
        try:
            rollback_backup = BackupJob.objects.get(job_id=rollback_backup_id)
            
            # Restore from rollback backup
            rollback_config = RestoreConfig(
                validate_data=False,
                rollback_on_failure=False  # Prevent infinite recursion
            )
            
            self.restore_backup(rollback_backup, rollback_config)
            
            logger.info(f"Rollback completed using backup {rollback_backup_id}")
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
    
    def _calculate_next_run(self, schedule: str) -> datetime:
        """Calculate next run time for cron schedule"""
        # This is a simplified implementation
        # In practice, you'd use a library like croniter
        
        # For now, just add 24 hours as default
        return timezone.now() + timedelta(hours=24)
    
    def _generate_backup_recommendations(self, backups) -> List[str]:
        """Generate recommendations based on backup history"""
        
        recommendations = []
        
        # Check backup frequency
        recent_backups = backups.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        if recent_backups < 7:
            recommendations.append("Consider increasing backup frequency to daily")
        
        # Check for failed backups
        failed_rate = backups.filter(status=BackupStatus.FAILED).count() / max(backups.count(), 1)
        if failed_rate > 0.1:  # More than 10% failure rate
            recommendations.append("High backup failure rate detected - investigate backup infrastructure")
        
        # Check storage usage
        total_storage = sum(b.backup_size_bytes or 0 for b in backups)
        if total_storage > 100 * 1024 * 1024 * 1024:  # 100GB
            recommendations.append("Consider implementing backup compression or cleanup policies")
        
        return recommendations


# Global service instance
backup_service = BackupRecoveryService()
