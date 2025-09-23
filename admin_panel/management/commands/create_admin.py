"""
Management command to create admin users for the GupShup admin panel

Usage: python manage.py create_admin
"""

import getpass
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from admin_panel.models import AdminUser, AdminAction
from admin_panel.auth import hash_password
from accounts.models import GupShupUser


class Command(BaseCommand):
    help = 'Create a new admin user for the GupShup admin panel'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Admin username',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Admin email address',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Admin password (not recommended for security)',
        )
        parser.add_argument(
            '--role',
            type=str,
            default='moderator',
            choices=['super_admin', 'admin', 'moderator', 'support'],
            help='Admin role (default: moderator)',
        )
        parser.add_argument(
            '--full-name',
            type=str,
            help='Admin full name',
        )
        parser.add_argument(
            '--department',
            type=str,
            help='Admin department',
        )
        parser.add_argument(
            '--phone',
            type=str,
            help='Admin phone number',
        )
        parser.add_argument(
            '--non-interactive',
            action='store_true',
            help='Run in non-interactive mode (all details must be provided via arguments)',
        )
        parser.add_argument(
            '--super-admin',
            action='store_true',
            help='Create a super admin with all permissions',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '\n👑 GupShup Admin Panel - Create Admin User\n'
                '==========================================\n'
            )
        )
        
        # Set role to super_admin if --super-admin flag is used
        if options['super_admin']:
            options['role'] = 'super_admin'
            self.stdout.write(
                self.style.WARNING('🔐 Creating Super Admin user with full permissions\n')
            )
        
        # Get admin details
        admin_data = self._get_admin_details(options)
        
        # Validate data
        try:
            self._validate_admin_data(admin_data)
        except ValidationError as e:
            raise CommandError(f'❌ Validation error: {e}')
        
        # Check if admin already exists
        if AdminUser.objects.filter(username=admin_data['username']).exists():
            raise CommandError(f'❌ Admin user "{admin_data["username"]}" already exists')
        
        if AdminUser.objects.filter(email=admin_data['email']).exists():
            raise CommandError(f'❌ Admin user with email "{admin_data["email"]}" already exists')
        
        # Show summary and confirm
        if not options['non_interactive']:
            self._show_summary(admin_data)
            confirm = input('\nProceed with admin creation? (yes/no): ').lower().strip()
            if confirm != 'yes':
                self.stdout.write(self.style.ERROR('❌ Admin creation cancelled.\n'))
                return
        
        # Create admin user
        try:
            admin_user = self._create_admin_user(admin_data)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎉 Admin user created successfully!\n\n'
                    f'Details:\n'
                    f'   • Username: {admin_user.username}\n'
                    f'   • Email: {admin_user.email}\n'
                    f'   • Role: {admin_user.role}\n'
                    f'   • Full Name: {admin_user.full_name or "Not provided"}\n'
                    f'   • Department: {admin_user.department or "Not provided"}\n'
                    f'   • Created: {admin_user.created_at}\n\n'
                    f'The admin can now log in to the admin panel at /admin-panel/\n'
                )
            )
            
            # Log the admin creation
            self._log_admin_creation(admin_user)
            
        except Exception as e:
            raise CommandError(f'❌ Error creating admin user: {e}')
    
    def _get_admin_details(self, options):
        """Get admin details from options or interactive input"""
        admin_data = {}
        
        # Username
        if options['username']:
            admin_data['username'] = options['username']
        elif not options['non_interactive']:
            admin_data['username'] = input('👤 Enter admin username: ').strip()
        else:
            raise CommandError('❌ Username is required in non-interactive mode')
        
        # Email
        if options['email']:
            admin_data['email'] = options['email']
        elif not options['non_interactive']:
            admin_data['email'] = input('📧 Enter admin email: ').strip()
        else:
            raise CommandError('❌ Email is required in non-interactive mode')
        
        # Password
        if options['password']:
            admin_data['password'] = options['password']
            if not options['non_interactive']:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️  Password provided via command line. This is not secure!\n'
                    )
                )
        elif not options['non_interactive']:
            while True:
                password = getpass.getpass('🔒 Enter admin password: ')
                password_confirm = getpass.getpass('🔒 Confirm admin password: ')
                
                if password == password_confirm:
                    admin_data['password'] = password
                    break
                else:
                    self.stdout.write(self.style.ERROR('❌ Passwords do not match. Try again.\n'))
        else:
            raise CommandError('❌ Password is required in non-interactive mode')
        
        # Role
        admin_data['role'] = options['role']
        
        # Optional fields
        admin_data['full_name'] = options['full_name']
        admin_data['department'] = options['department']
        admin_data['phone'] = options['phone']
        
        # Get optional fields interactively if not provided
        if not options['non_interactive']:
            if not admin_data['full_name']:
                admin_data['full_name'] = input('👨‍💼 Enter full name (optional): ').strip() or None
            
            if not admin_data['department']:
                admin_data['department'] = input('🏢 Enter department (optional): ').strip() or None
            
            if not admin_data['phone']:
                admin_data['phone'] = input('📱 Enter phone number (optional): ').strip() or None
        
        return admin_data
    
    def _validate_admin_data(self, admin_data):
        """Validate admin user data"""
        # Validate username
        if not admin_data['username']:
            raise ValidationError('Username is required')
        
        if len(admin_data['username']) < 3:
            raise ValidationError('Username must be at least 3 characters long')
        
        if not admin_data['username'].replace('_', '').replace('-', '').isalnum():
            raise ValidationError('Username can only contain letters, numbers, underscores, and hyphens')
        
        # Validate email
        if not admin_data['email']:
            raise ValidationError('Email is required')
        
        try:
            validate_email(admin_data['email'])
        except ValidationError:
            raise ValidationError('Invalid email address')
        
        # Validate password
        if not admin_data['password']:
            raise ValidationError('Password is required')
        
        if len(admin_data['password']) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        
        # Check password strength
        password = admin_data['password']
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValidationError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one digit, and one special character'
            )
        
        # Validate phone (if provided)
        if admin_data['phone']:
            # Simple Indian phone number validation
            phone = admin_data['phone'].replace('+91', '').replace('-', '').replace(' ', '')
            if not (phone.isdigit() and len(phone) == 10):
                raise ValidationError('Phone number must be a valid 10-digit Indian mobile number')
    
    def _show_summary(self, admin_data):
        """Show summary of admin user to be created"""
        self.stdout.write('\n📋 Admin User Summary:')
        self.stdout.write(f'   • Username: {admin_data["username"]}')
        self.stdout.write(f'   • Email: {admin_data["email"]}')
        self.stdout.write(f'   • Role: {admin_data["role"]}')
        self.stdout.write(f'   • Full Name: {admin_data["full_name"] or "Not provided"}')
        self.stdout.write(f'   • Department: {admin_data["department"] or "Not provided"}')
        self.stdout.write(f'   • Phone: {admin_data["phone"] or "Not provided"}')
        
        # Show role permissions
        role_permissions = self._get_role_permissions(admin_data['role'])
        self.stdout.write(f'\n🔑 Role Permissions ({admin_data["role"]}):')
        for permission in role_permissions:
            self.stdout.write(f'   ✅ {permission}')
    
    def _get_role_permissions(self, role):
        """Get list of permissions for a role"""
        permissions = {
            'super_admin': [
                'Full system access',
                'Manage all admins',
                'System configuration',
                'Advanced analytics',
                'Database management'
            ],
            'admin': [
                'Manage users and content',
                'View analytics',
                'Moderate content',
                'Manage warnings and bans',
                'Create announcements'
            ],
            'moderator': [
                'Moderate content',
                'Manage user warnings',
                'View basic analytics',
                'Handle user reports'
            ],
            'support': [
                'View user information',
                'Handle support tickets',
                'View basic reports'
            ]
        }
        return permissions.get(role, [])
    
    def _create_admin_user(self, admin_data):
        """Create the admin user"""
        # Hash password
        password_hash = hash_password(admin_data['password'])
        
        # Set permissions based on role
        permissions = self._get_role_permissions_dict(admin_data['role'])
        
        # Create admin user
        admin_user = AdminUser.objects.create(
            username=admin_data['username'],
            email=admin_data['email'],
            password_hash=password_hash,
            role=admin_data['role'],
            full_name=admin_data['full_name'],
            department=admin_data['department'],
            phone_number=admin_data['phone'],
            is_active=True,
            permissions=permissions
        )
        
        return admin_user
    
    def _get_role_permissions_dict(self, role):
        """Get permissions dictionary for a role"""
        base_permissions = {
            'can_view_dashboard': True,
            'can_view_users': False,
            'can_edit_users': False,
            'can_ban_users': False,
            'can_delete_users': False,
            'can_view_posts': False,
            'can_edit_posts': False,
            'can_delete_posts': False,
            'can_moderate_content': False,
            'can_manage_warnings': False,
            'can_view_analytics': False,
            'can_view_audit_logs': False,
            'can_manage_admins': False,
            'can_create_announcements': False,
            'can_manage_settings': False
        }
        
        if role == 'super_admin':
            # Super admin has all permissions
            return {key: True for key in base_permissions}
        
        elif role == 'admin':
            base_permissions.update({
                'can_view_users': True,
                'can_edit_users': True,
                'can_ban_users': True,
                'can_view_posts': True,
                'can_edit_posts': True,
                'can_delete_posts': True,
                'can_moderate_content': True,
                'can_manage_warnings': True,
                'can_view_analytics': True,
                'can_view_audit_logs': True,
                'can_create_announcements': True
            })
        
        elif role == 'moderator':
            base_permissions.update({
                'can_view_users': True,
                'can_view_posts': True,
                'can_edit_posts': True,
                'can_moderate_content': True,
                'can_manage_warnings': True,
                'can_view_analytics': True
            })
        
        elif role == 'support':
            base_permissions.update({
                'can_view_users': True,
                'can_view_posts': True,
                'can_view_analytics': True
            })
        
        return base_permissions
    
    def _log_admin_creation(self, admin_user):
        """Log the admin creation action"""
        try:
            AdminAction.objects.create(
                admin=None,  # System action
                action_type='admin_created',
                severity='info',
                title='New Admin User Created',
                description=f'Admin user "{admin_user.username}" was created with role "{admin_user.role}"',
                metadata={
                    'created_admin_id': admin_user.id,
                    'created_admin_username': admin_user.username,
                    'created_admin_role': admin_user.role,
                    'creation_method': 'management_command'
                }
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not log admin creation: {e}')
            )