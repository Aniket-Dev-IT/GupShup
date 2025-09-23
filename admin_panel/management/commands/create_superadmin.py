"""
Management command to create the first super admin user

Usage: python manage.py create_superadmin
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from admin_panel.models import AdminUser
from admin_panel.auth import create_admin_user
import getpass
import re


class Command(BaseCommand):
    help = 'Create a super admin user for the GupShup admin panel'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the super admin',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the super admin',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the super admin (not recommended for security)',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            help='First name of the super admin',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            help='Last name of the super admin',
        )
        parser.add_argument(
            '--phone',
            type=str,
            help='Phone number (Indian format: +919876543210)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force creation even if a super admin already exists',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '\n🚀 GupShup Admin Panel - Super Admin Setup\n'
                '==========================================\n'
            )
        )
        
        # Check if super admin already exists
        existing_super_admins = AdminUser.objects.filter(role='super_admin', is_active=True)
        if existing_super_admins.exists() and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  Super admin already exists: {existing_super_admins.first().username}\n'
                    'Use --force flag to create another super admin.\n'
                )
            )
            return
        
        # Collect user information
        username = self.get_username(options['username'])
        email = self.get_email(options['email'])
        first_name = self.get_first_name(options['first_name'])
        last_name = self.get_last_name(options['last_name'])
        phone = self.get_phone(options['phone'])
        password = self.get_password(options['password'])
        
        try:
            # Create super admin
            self.stdout.write('\n🔧 Creating super admin...\n')
            
            admin_user = AdminUser.objects.create_superadmin(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                # Super admin gets all permissions
                can_manage_users=True,
                can_manage_posts=True,
                can_view_analytics=True,
                can_send_warnings=True,
                can_ban_users=True,
                can_delete_posts=True,
                can_manage_system=True,
                can_access_reports=True,
                can_manage_admins=True,
                can_export_data=True,
                can_moderate_content=True,
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Super admin created successfully!\n\n'
                    f'📋 Admin Details:\n'
                    f'   Username: {admin_user.username}\n'
                    f'   Email: {admin_user.email}\n'
                    f'   Name: {admin_user.get_full_name()}\n'
                    f'   Role: {admin_user.get_role_display()}\n'
                    f'   Phone: {admin_user.phone_number or "Not provided"}\n'
                    f'   Created: {admin_user.created_at.strftime("%Y-%m-%d %H:%M:%S")}\n\n'
                    f'🌐 Admin Panel Access:\n'
                    f'   URL: http://localhost:8000/admin-panel/\n'
                    f'   Login: {admin_user.username}\n'
                    f'   Password: [Your chosen password]\n\n'
                    f'🔐 Security Features Enabled:\n'
                    f'   • Rate limiting on login attempts\n'
                    f'   • Session timeout (8 hours default)\n'
                    f'   • Comprehensive audit logging\n'
                    f'   • IP-based access control\n\n'
                    f'🚨 Important Security Notes:\n'
                    f'   • Change your password after first login\n'
                    f'   • Configure IP restrictions if needed\n'
                    f'   • Review admin permissions regularly\n'
                    f'   • Monitor the audit logs\n\n'
                    f'Happy administrating! 🎉\n'
                )
            )
            
        except Exception as e:
            raise CommandError(f'❌ Failed to create super admin: {str(e)}')
    
    def get_username(self, provided_username):
        """Get and validate username"""
        if provided_username:
            username = provided_username
        else:
            username = input('👤 Enter username for super admin: ').strip()
        
        if not username:
            raise CommandError('Username cannot be empty')
        
        if len(username) < 3:
            raise CommandError('Username must be at least 3 characters long')
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise CommandError('Username can only contain letters, numbers, and underscores')
        
        # Check if username already exists
        if AdminUser.objects.filter(username=username).exists():
            raise CommandError(f'Username "{username}" already exists')
        
        return username
    
    def get_email(self, provided_email):
        """Get and validate email"""
        if provided_email:
            email = provided_email
        else:
            email = input('📧 Enter email for super admin: ').strip()
        
        if not email:
            raise CommandError('Email cannot be empty')
        
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError('Please enter a valid email address')
        
        # Check if email already exists
        if AdminUser.objects.filter(email=email).exists():
            raise CommandError(f'Email "{email}" already exists')
        
        return email
    
    def get_first_name(self, provided_name):
        """Get first name"""
        if provided_name:
            return provided_name
        
        first_name = input('👨 Enter first name (optional): ').strip()
        return first_name or 'Admin'
    
    def get_last_name(self, provided_name):
        """Get last name"""
        if provided_name:
            return provided_name
        
        last_name = input('👨 Enter last name (optional): ').strip()
        return last_name or 'User'
    
    def get_phone(self, provided_phone):
        """Get and validate phone number"""
        if provided_phone:
            phone = provided_phone
        else:
            phone = input('📱 Enter phone number (Indian format +919876543210, optional): ').strip()
        
        if not phone:
            return None
        
        # Validate Indian phone number format
        if not phone.startswith('+91'):
            raise CommandError('Phone number must start with +91 for Indian numbers')
        
        digits = phone[3:]
        if not digits.isdigit() or len(digits) != 10:
            raise CommandError('Invalid Indian phone number format. Use +91XXXXXXXXXX')
        
        return phone
    
    def get_password(self, provided_password):
        """Get and validate password"""
        if provided_password:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  WARNING: Providing password via command line is not secure!'
                )
            )
            password = provided_password
        else:
            password = getpass.getpass('🔐 Enter password for super admin: ')
        
        if not password:
            raise CommandError('Password cannot be empty')
        
        if len(password) < 8:
            raise CommandError('Password must be at least 8 characters long')
        
        # Check password strength
        if not re.search(r'[A-Z]', password):
            self.stdout.write(
                self.style.WARNING('⚠️  Password should contain at least one uppercase letter')
            )
        
        if not re.search(r'[0-9]', password):
            self.stdout.write(
                self.style.WARNING('⚠️  Password should contain at least one number')
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            self.stdout.write(
                self.style.WARNING('⚠️  Password should contain at least one special character')
            )
        
        # Confirm password if entered interactively
        if not provided_password:
            confirm_password = getpass.getpass('🔐 Confirm password: ')
            if password != confirm_password:
                raise CommandError('Passwords do not match')
        
        return password