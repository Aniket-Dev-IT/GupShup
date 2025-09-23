"""
Management command to clean up expired admin sessions

Usage: python manage.py cleanup_sessions
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from admin_panel.models import AdminSession, AdminAction
from datetime import timedelta


class Command(BaseCommand):
    help = 'Clean up expired admin sessions and old audit logs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to keep inactive sessions (default: 30)',
        )
        parser.add_argument(
            '--audit-days',
            type=int,
            default=90,
            help='Number of days to keep audit logs (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation prompt',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '\n🧹 GupShup Admin Panel - Session Cleanup\n'
                '========================================\n'
            )
        )
        
        days = options['days']
        audit_days = options['audit_days']
        dry_run = options['dry_run']
        force = options['force']
        
        # Calculate cutoff dates
        session_cutoff = timezone.now() - timedelta(days=days)
        audit_cutoff = timezone.now() - timedelta(days=audit_days)
        
        # Find expired sessions
        expired_sessions = AdminSession.objects.filter(
            expires_at__lt=timezone.now()
        )
        
        # Find old inactive sessions
        old_inactive_sessions = AdminSession.objects.filter(
            is_active=False,
            last_activity__lt=session_cutoff
        )
        
        # Find old audit logs
        old_audit_logs = AdminAction.objects.filter(
            created_at__lt=audit_cutoff
        )
        
        # Count items to be cleaned
        expired_count = expired_sessions.count()
        inactive_count = old_inactive_sessions.count()
        audit_count = old_audit_logs.count()
        
        total_sessions = expired_count + inactive_count
        
        # Display summary
        self.stdout.write(f'📊 Cleanup Summary:')
        self.stdout.write(f'   • Expired sessions: {expired_count}')
        self.stdout.write(f'   • Old inactive sessions (>{days} days): {inactive_count}')
        self.stdout.write(f'   • Old audit logs (>{audit_days} days): {audit_count}')
        self.stdout.write(f'   • Total items to clean: {total_sessions + audit_count}\n')
        
        if total_sessions == 0 and audit_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ No cleanup needed. Everything is already clean!\n')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - No actual cleanup will be performed\n')
            )
            self._show_detailed_summary(
                expired_sessions, old_inactive_sessions, old_audit_logs
            )
            return
        
        # Confirmation prompt
        if not force:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  This will permanently delete the above items.\n'
                    'This action cannot be undone!\n'
                )
            )
            
            confirm = input('Are you sure you want to proceed? (yes/no): ').lower().strip()
            if confirm != 'yes':
                self.stdout.write(self.style.ERROR('❌ Cleanup cancelled.\n'))
                return
        
        # Perform cleanup
        self.stdout.write('\n🧹 Starting cleanup...\n')
        
        deleted_counts = {'sessions': 0, 'audit_logs': 0}
        
        # Clean expired sessions
        if expired_count > 0:
            expired_deleted = expired_sessions.delete()[0]
            deleted_counts['sessions'] += expired_deleted
            self.stdout.write(f'✅ Cleaned {expired_deleted} expired sessions')
        
        # Clean old inactive sessions
        if inactive_count > 0:
            inactive_deleted = old_inactive_sessions.delete()[0]
            deleted_counts['sessions'] += inactive_deleted
            self.stdout.write(f'✅ Cleaned {inactive_deleted} old inactive sessions')
        
        # Clean old audit logs
        if audit_count > 0:
            audit_deleted = old_audit_logs.delete()[0]
            deleted_counts['audit_logs'] = audit_deleted
            self.stdout.write(f'✅ Cleaned {audit_deleted} old audit log entries')
        
        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Cleanup completed successfully!\n'
                f'   • Sessions cleaned: {deleted_counts["sessions"]}\n'
                f'   • Audit logs cleaned: {deleted_counts["audit_logs"]}\n'
                f'   • Total items cleaned: {sum(deleted_counts.values())}\n\n'
                f'💡 Tip: Run this command regularly or set up a cron job:\n'
                f'   0 2 * * 0 cd /path/to/project && python manage.py cleanup_sessions\n'
            )
        )
        
        # Log the cleanup action
        try:
            AdminAction.objects.create(
                admin=None,  # System action
                action_type='system_cleanup',
                severity='info',
                title='Session Cleanup Performed',
                description=f'Cleanup removed {sum(deleted_counts.values())} items',
                metadata={
                    'sessions_cleaned': deleted_counts['sessions'],
                    'audit_logs_cleaned': deleted_counts['audit_logs'],
                    'session_retention_days': days,
                    'audit_retention_days': audit_days
                }
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not log cleanup action: {e}')
            )
    
    def _show_detailed_summary(self, expired_sessions, old_inactive_sessions, old_audit_logs):
        """Show detailed summary of what would be cleaned"""
        
        if expired_sessions.exists():
            self.stdout.write('\n📋 Expired Sessions:')
            for session in expired_sessions[:10]:  # Show first 10
                self.stdout.write(
                    f'   • {session.admin.username if session.admin else "Unknown"} '
                    f'({session.ip_address}) - expired {session.expires_at}'
                )
            if expired_sessions.count() > 10:
                self.stdout.write(f'   ... and {expired_sessions.count() - 10} more')
        
        if old_inactive_sessions.exists():
            self.stdout.write('\n📋 Old Inactive Sessions:')
            for session in old_inactive_sessions[:10]:  # Show first 10
                self.stdout.write(
                    f'   • {session.admin.username if session.admin else "Unknown"} '
                    f'({session.ip_address}) - last active {session.last_activity}'
                )
            if old_inactive_sessions.count() > 10:
                self.stdout.write(f'   ... and {old_inactive_sessions.count() - 10} more')
        
        if old_audit_logs.exists():
            self.stdout.write('\n📋 Old Audit Logs:')
            for log in old_audit_logs[:10]:  # Show first 10
                self.stdout.write(
                    f'   • {log.admin.username if log.admin else "System"} '
                    f'- {log.action_type} ({log.created_at})'
                )
            if old_audit_logs.count() > 10:
                self.stdout.write(f'   ... and {old_audit_logs.count() - 10} more')