# management/commands/run_backup.py
"""
Management command to run backup operations
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datawarehouse.services.backup_recovery import BackupRecoveryService


class Command(BaseCommand):
    help = 'Run backup operations for the datawarehouse'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'incremental', 'differential', 'snapshot', 'selective'],
            help='Type of backup to perform'
        )
        parser.add_argument(
            '--schedule',
            type=str,
            help='Schedule name for recurring backups'
        )
        parser.add_argument(
            '--models',
            type=str,
            nargs='+',
            help='Specific models to backup (for selective backup)'
        )
        parser.add_argument(
            '--storage',
            type=str,
            default='local',
            choices=['local', 's3'],
            help='Storage backend to use'
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=30,
            help='Number of days to retain the backup'
        )

    def handle(self, *args, **options):
        backup_service = BackupRecoveryService()
        
        try:
            self.stdout.write(
                self.style.SUCCESS(f'Starting {options["type"]} backup...')
            )
            
            # Prepare backup options
            backup_options = {
                'retention_days': options['retention_days'],
                'storage_type': options['storage'],
                'scheduled': bool(options.get('schedule')),
                'schedule_name': options.get('schedule', ''),
            }
            
            if options['type'] == 'selective' and options.get('models'):
                backup_options['included_models'] = options['models']
            
            # Start backup
            backup_job = backup_service.create_backup(
                backup_type=options['type'],
                **backup_options
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Backup initiated successfully. Job ID: {backup_job.id}'
                )
            )
            
            # For synchronous execution, wait for completion
            if not options.get('schedule'):
                self.stdout.write('Waiting for backup to complete...')
                # In a real implementation, you'd poll the job status
                # For now, just show the job was created
                
        except Exception as e:
            raise CommandError(f'Backup failed: {str(e)}')
