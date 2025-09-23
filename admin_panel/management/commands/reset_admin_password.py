"""
Management command to reset admin user passwords

Usage: python manage.py reset_admin_password --username=admin_user
"""

import getpass
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.utils import timezone
from admin_panel.models import AdminUser, AdminAction
from admin_panel.auth import hash_password


class Command(BaseCommand):
    help = 'Reset password for an admin user'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Username of the admin to reset password for',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='New password (not recommended for security)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force password reset without confirmation',
        )
        parser.add_argument(
            '--deactivate',
            action='store_true',
            help='Deactivate the admin account after password reset',
        )
        parser.add_argument(
            '--expire-sessions',
            action='store_true',
            help='Expire all existing sessions for this admin',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '\n🔐 GupShup Admin Panel - Password Reset\n'
                '======================================\n'
            )
        )
        
        username = options['username']
        new_password = options['password']
        force = options['force']
        deactivate = options['deactivate']
        expire_sessions = options['expire_sessions']
        
        # Find admin user
        try:
            admin_user = AdminUser.objects.get(username=username)
        except AdminUser.DoesNotExist:
            raise CommandError(f'❌ Admin user "{username}" not found')
        
        # Show admin info
        self.stdout.write(f'👤 Admin User Information:')
        self.stdout.write(f'   • Username: {admin_user.username}')
        self.stdout.write(f'   • Email: {admin_user.email}')
        self.stdout.write(f'   • Role: {admin_user.role}')
        self.stdout.write(f'   • Full Name: {admin_user.full_name or "Not set"}')
        self.stdout.write(f'   • Is Active: {admin_user.is_active}')
        self.stdout.write(f'   • Last Login: {admin_user.last_login or "Never"}')
        self.stdout.write(f'   • Created: {admin_user.created_at}')
        
        # Security warning for inactive admin
        if not admin_user.is_active:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  WARNING: This admin account is currently deactivated!\n'
                )
            )
        
        # Confirm reset
        if not force:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  You are about to reset the password for admin "{username}".\n'
                    'This action will:\n'
                    '   • Change the admin\'s password\n'
                    '   • Log the password reset action\n'
                )
            )
            
            if expire_sessions:
                self.stdout.write('   • Expire all existing sessions for this admin')
            
            if deactivate:
                self.stdout.write('   • Deactivate the admin account')
            
            self.stdout.write('\nThis action cannot be undone!\n')
            
            confirm = input('Are you sure you want to proceed? (yes/no): ').lower().strip()
            if confirm != 'yes':
                self.stdout.write(self.style.ERROR('❌ Password reset cancelled.\n'))
                return
        
        # Get new password
        if new_password:
            if not force:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️  Password provided via command line. This is not secure!\n'
                    )
                )
        else:
            # Get password interactively
            while True:
                new_password = getpass.getpass('🔒 Enter new admin password: ')
                password_confirm = getpass.getpass('🔒 Confirm new admin password: ')
                
                if new_password == password_confirm:
                    break
                else:
                    self.stdout.write(self.style.ERROR('❌ Passwords do not match. Try again.\n'))
        
        # Validate password
        try:
            self._validate_password(new_password)
        except ValidationError as e:
            raise CommandError(f'❌ Password validation error: {e}')
        
        # Reset password
        try:
            old_password_hash = admin_user.password_hash
            
            # Hash new password
            admin_user.password_hash = hash_password(new_password)
            admin_user.password_changed_at = timezone.now()
            admin_user.save()
            
            # Deactivate if requested
            if deactivate:
                admin_user.is_active = False
                admin_user.deactivated_at = timezone.now()
                admin_user.save()
            
            # Expire sessions if requested
            if expire_sessions:
                expired_count = self._expire_admin_sessions(admin_user)
                self.stdout.write(f'📱 Expired {expired_count} existing sessions')
            
            # Log the password reset
            self._log_password_reset(admin_user, deactivate, expire_sessions)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎉 Password reset successful!\n\n'
                    f'Details:\n'
                    f'   • Admin: {admin_user.username}\n'
                    f'   • Password changed: {admin_user.password_changed_at}\n'
                    f'   • Account active: {admin_user.is_active}\n'
                )
            )
            
            if deactivate:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️  Admin account has been deactivated. '
                        'It will need to be reactivated before login.\n'
                    )
                )
            
            # Security recommendations
            self.stdout.write(
                self.style.SUCCESS(
                    '🛡️  Security Recommendations:\n'
                    '   • Admin should change password on first login\n'
                    '   • Consider enabling 2FA for this account\n'
                    '   • Monitor admin activity logs\n'
                    '   • Ensure password meets security requirements\n'
                )
            )
            
        except Exception as e:
            raise CommandError(f'❌ Error resetting password: {e}')
    
    def _validate_password(self, password):
        """Validate password strength"""
        if not password:
            raise ValidationError('Password is required')
        
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        
        # Check password complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValidationError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one digit, and one special character'
            )
        
        # Check for common weak passwords
        weak_passwords = [
            'password', '12345678', 'admin123', 'qwerty123',
            'password123', 'admin@123', 'welcome123'
        ]
        
        if password.lower() in weak_passwords:
            raise ValidationError('Password is too common. Please choose a stronger password.')
    
    def _expire_admin_sessions(self, admin_user):
        """Expire all sessions for the admin user"""
        from admin_panel.models import AdminSession
        
        active_sessions = AdminSession.objects.filter(
            admin=admin_user,
            is_active=True
        )
        
        count = active_sessions.count()
        
        active_sessions.update(
            is_active=False,
            ended_at=timezone.now(),
            end_reason='password_reset'
        )
        
        return count
    
    def _log_password_reset(self, admin_user, deactivated, sessions_expired):
        """Log the password reset action"""
        try:
            AdminAction.objects.create(
                admin=None,  # System action
                action_type='password_reset',
                severity='warning',
                title='Admin Password Reset',
                description=f'Password was reset for admin "{admin_user.username}"',
                metadata={
                    'target_admin_id': admin_user.id,
                    'target_admin_username': admin_user.username,
                    'target_admin_role': admin_user.role,
                    'deactivated': deactivated,
                    'sessions_expired': sessions_expired,
                    'reset_method': 'management_command',
                    'reset_timestamp': timezone.now().isoformat()
                }
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not log password reset: {e}')
            )
    
    def _show_admin_sessions(self, admin_user):
        """Show current admin sessions"""
        from admin_panel.models import AdminSession
        
        active_sessions = AdminSession.objects.filter(
            admin=admin_user,
            is_active=True
        ).order_by('-last_activity')
        
        if active_sessions.exists():
            self.stdout.write(f'\n📱 Active Sessions ({active_sessions.count()}):')
            for session in active_sessions[:5]:  # Show top 5
                self.stdout.write(
                    f'   • {session.ip_address} - '
                    f'Last active: {session.last_activity} - '
                    f'User Agent: {session.user_agent[:50]}...'
                )
            
            if active_sessions.count() > 5:
                self.stdout.write(f'   ... and {active_sessions.count() - 5} more sessions')
        else:
            self.stdout.write('\n📱 No active sessions found')