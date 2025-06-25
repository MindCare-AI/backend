# management/commands/generate_compliance_report.py
"""
Management command to generate compliance reports
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import json
from datawarehouse.services.security_service import security_service
from datawarehouse.services.audit_trail import audit_service


class Command(BaseCommand):
    help = 'Generate compliance reports for auditing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to include in the report'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for the report'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='json',
            choices=['json', 'csv'],
            help='Output format'
        )

    def handle(self, *args, **options):
        end_date = timezone.now()
        start_date = end_date - timedelta(days=options['days'])
        
        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Generating compliance report for {options["days"]} days...'
                )
            )
            
            # Generate security compliance report
            security_report = security_service.get_compliance_report(
                start_date=start_date,
                end_date=end_date
            )
            
            # Generate audit report
            audit_report = audit_service.generate_compliance_report(
                start_date=start_date,
                end_date=end_date
            )
            
            # Combine reports
            combined_report = {
                'report_metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat(),
                    'report_type': 'compliance_audit'
                },
                'security_report': security_report,
                'audit_report': audit_report
            }
            
            # Output report
            if options.get('output'):
                if options['format'] == 'json':
                    with open(options['output'], 'w') as f:
                        json.dump(combined_report, f, indent=2)
                    self.stdout.write(
                        self.style.SUCCESS(f'Report saved to {options["output"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('CSV format not yet implemented')
                    )
            else:
                # Print to stdout
                self.stdout.write(json.dumps(combined_report, indent=2))
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Report generation failed: {str(e)}')
            )
