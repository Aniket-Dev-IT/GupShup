"""
Management command to generate various admin reports

Usage: python manage.py generate_reports --type=daily --format=pdf
"""

import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Count, Q, Avg
from accounts.models import GupShupUser
from posts.models import Post, Comment, Like
from admin_panel.models import AdminAction, UserWarning, BannedUser, AdminUser


class Command(BaseCommand):
    help = 'Generate administrative reports for GupShup platform'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='daily',
            choices=['daily', 'weekly', 'monthly', 'user-summary', 'content-summary', 'moderation-summary'],
            help='Type of report to generate (default: daily)',
        )
        parser.add_argument(
            '--format',
            type=str,
            default='html',
            choices=['html', 'json', 'csv'],
            help='Output format (default: html)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (optional)',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for report (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for report (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send report to',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress console output',
        )
    
    def handle(self, *args, **options):
        if not options['quiet']:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n📊 GupShup Admin Panel - Report Generator\n'
                    '=========================================\n'
                )
            )
        
        report_type = options['type']
        output_format = options['format']
        output_path = options['output']
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        email = options['email']
        quiet = options['quiet']
        
        # Parse dates
        try:
            start_date, end_date = self._parse_dates(report_type, start_date_str, end_date_str)
        except ValueError as e:
            raise CommandError(f'❌ Date parsing error: {e}')
        
        if not quiet:
            self.stdout.write(f'🗓️  Generating {report_type} report for period: {start_date.date()} to {end_date.date()}')
        
        # Generate report data
        try:
            report_data = self._generate_report_data(report_type, start_date, end_date)
            
            if not quiet:
                self.stdout.write(f'✅ Report data compiled: {len(report_data)} sections')
            
        except Exception as e:
            raise CommandError(f'❌ Error generating report data: {e}')
        
        # Format and output report
        try:
            report_content = self._format_report(report_data, output_format, report_type)
            
            if output_path:
                self._save_report(report_content, output_path, output_format)
                if not quiet:
                    self.stdout.write(f'💾 Report saved to: {output_path}')
            else:
                if not quiet:
                    self.stdout.write('\n' + '='*60)
                    self.stdout.write(report_content)
                    self.stdout.write('='*60 + '\n')
            
        except Exception as e:
            raise CommandError(f'❌ Error formatting report: {e}')
        
        # Email report if requested
        if email:
            try:
                self._email_report(report_content, email, report_type, output_format)
                if not quiet:
                    self.stdout.write(f'📧 Report emailed to: {email}')
            except Exception as e:
                if not quiet:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Could not email report: {e}')
                    )
        
        # Log report generation
        try:
            AdminAction.objects.create(
                admin=None,
                action_type='report_generated',
                severity='info',
                title=f'{report_type.title()} Report Generated',
                description=f'Generated {report_type} report for {start_date.date()} to {end_date.date()}',
                metadata={
                    'report_type': report_type,
                    'output_format': output_format,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'sections_count': len(report_data),
                    'emailed': bool(email)
                }
            )
        except Exception as e:
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Could not log report generation: {e}')
                )
        
        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(f'\n🎉 {report_type.title()} report generated successfully!\n')
            )
    
    def _parse_dates(self, report_type, start_date_str, end_date_str):
        """Parse and validate date parameters"""
        now = timezone.now()
        
        if start_date_str and end_date_str:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone()) + timedelta(days=1)
        else:
            # Default date ranges based on report type
            if report_type == 'daily':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif report_type == 'weekly':
                start_date = now - timedelta(days=7)
                end_date = now
            elif report_type == 'monthly':
                start_date = now - timedelta(days=30)
                end_date = now
            else:
                # For summary reports, use last 30 days
                start_date = now - timedelta(days=30)
                end_date = now
        
        if start_date >= end_date:
            raise ValueError('Start date must be before end date')
        
        return start_date, end_date
    
    def _generate_report_data(self, report_type, start_date, end_date):
        """Generate report data based on type"""
        data = {
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
                    'report_timestamp': timezone.now(),
            'sections': {}
        }
        
        if report_type in ['daily', 'weekly', 'monthly']:
            data['sections'] = self._generate_activity_report(start_date, end_date)
        elif report_type == 'user-summary':
            data['sections'] = self._generate_user_summary(start_date, end_date)
        elif report_type == 'content-summary':
            data['sections'] = self._generate_content_summary(start_date, end_date)
        elif report_type == 'moderation-summary':
            data['sections'] = self._generate_moderation_summary(start_date, end_date)
        
        return data
    
    def _generate_activity_report(self, start_date, end_date):
        """Generate general activity report"""
        sections = {}
        
        # User statistics
        total_users = GupShupUser.objects.count()
        new_users = GupShupUser.objects.filter(
            date_joined__range=[start_date, end_date]
        ).count()
        active_users = GupShupUser.objects.filter(
            last_login__range=[start_date, end_date]
        ).count()
        
        sections['user_stats'] = {
            'title': 'User Statistics',
            'total_users': total_users,
            'new_users': new_users,
            'active_users': active_users,
            'growth_rate': (new_users / max(total_users - new_users, 1)) * 100
        }
        
        # Post statistics
        total_posts = Post.objects.count()
        new_posts = Post.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        sections['post_stats'] = {
            'title': 'Content Statistics',
            'total_posts': total_posts,
            'new_posts': new_posts,
            'posts_per_user': new_posts / max(active_users, 1)
        }
        
        # Engagement statistics
        new_comments = Comment.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        new_likes = Like.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        sections['engagement_stats'] = {
            'title': 'Engagement Statistics',
            'new_comments': new_comments,
            'new_likes': new_likes,
            'engagement_rate': (new_comments + new_likes) / max(new_posts, 1)
        }
        
        # Admin activity
        admin_actions = AdminAction.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        sections['admin_activity'] = {
            'title': 'Admin Activity',
            'total_actions': admin_actions.count(),
            'unique_admins': admin_actions.values('admin').distinct().count(),
            'top_actions': list(
                admin_actions.values('action_type')
                .annotate(count=Count('action_type'))
                .order_by('-count')[:5]
            )
        }
        
        return sections
    
    def _generate_user_summary(self, start_date, end_date):
        """Generate user-focused summary"""
        sections = {}
        
        # User demographics
        users_by_state = list(
            GupShupUser.objects.values('state')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        sections['demographics'] = {
            'title': 'User Demographics',
            'users_by_state': users_by_state,
            'total_states': len(users_by_state)
        }
        
        # User behavior
        most_active_users = list(
            Post.objects.filter(created_at__range=[start_date, end_date])
            .values('author__username', 'author__full_name')
            .annotate(post_count=Count('id'))
            .order_by('-post_count')[:10]
        )
        
        sections['user_behavior'] = {
            'title': 'Most Active Users',
            'top_posters': most_active_users
        }
        
        # Warnings and bans
        warnings_issued = UserWarning.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        bans_issued = BannedUser.objects.filter(
            banned_at__range=[start_date, end_date]
        ).count()
        
        sections['moderation_stats'] = {
            'title': 'User Moderation',
            'warnings_issued': warnings_issued,
            'bans_issued': bans_issued
        }
        
        return sections
    
    def _generate_content_summary(self, start_date, end_date):
        """Generate content-focused summary"""
        sections = {}
        
        # Content creation trends
        posts_by_day = list(
            Post.objects.filter(created_at__range=[start_date, end_date])
            .extra({'date': 'DATE(created_at)'})
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        sections['content_trends'] = {
            'title': 'Content Creation Trends',
            'posts_by_day': posts_by_day
        }
        
        # Popular content
        top_posts = list(
            Post.objects.filter(created_at__range=[start_date, end_date])
            .annotate(like_count=Count('likes'))
            .order_by('-like_count')[:10]
            .values('id', 'content', 'author__username', 'like_count', 'created_at')
        )
        
        sections['popular_content'] = {
            'title': 'Most Popular Posts',
            'top_posts': top_posts
        }
        
        # Content types
        posts_with_images = Post.objects.filter(
            created_at__range=[start_date, end_date],
            image__isnull=False
        ).count()
        
        posts_without_images = Post.objects.filter(
            created_at__range=[start_date, end_date],
            image__isnull=True
        ).count()
        
        sections['content_types'] = {
            'title': 'Content Types',
            'posts_with_images': posts_with_images,
            'posts_without_images': posts_without_images
        }
        
        return sections
    
    def _generate_moderation_summary(self, start_date, end_date):
        """Generate moderation-focused summary"""
        sections = {}
        
        # Moderation actions
        moderation_actions = AdminAction.objects.filter(
            created_at__range=[start_date, end_date],
            action_type__in=['user_banned', 'user_warned', 'post_deleted', 'post_edited']
        )
        
        actions_by_type = list(
            moderation_actions.values('action_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        sections['moderation_actions'] = {
            'title': 'Moderation Actions',
            'actions_by_type': actions_by_type,
            'total_actions': moderation_actions.count()
        }
        
        # Active moderators
        active_moderators = list(
            moderation_actions.values('admin__username', 'admin__role')
            .annotate(action_count=Count('id'))
            .order_by('-action_count')
        )
        
        sections['active_moderators'] = {
            'title': 'Active Moderators',
            'moderators': active_moderators
        }
        
        # Warning and ban details
        warnings_by_type = list(
            UserWarning.objects.filter(created_at__range=[start_date, end_date])
            .values('warning_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        bans_by_type = list(
            BannedUser.objects.filter(banned_at__range=[start_date, end_date])
            .values('ban_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        sections['disciplinary_actions'] = {
            'title': 'Disciplinary Actions',
            'warnings_by_type': warnings_by_type,
            'bans_by_type': bans_by_type
        }
        
        return sections
    
    def _format_report(self, data, output_format, report_type):
        """Format report based on output format"""
        if output_format == 'json':
            import json
            return json.dumps(data, indent=2, default=str)
        
        elif output_format == 'csv':
            return self._format_as_csv(data)
        
        else:  # HTML format
            return self._format_as_html(data, report_type)
    
    def _format_as_csv(self, data):
        """Format report as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Section', 'Metric', 'Value'])
        
        # Write data
        for section_key, section_data in data['sections'].items():
            if isinstance(section_data, dict):
                section_title = section_data.get('title', section_key)
                for key, value in section_data.items():
                    if key != 'title' and not isinstance(value, (list, dict)):
                        writer.writerow([section_title, key, value])
        
        return output.getvalue()
    
    def _format_as_html(self, data, report_type):
        """Format report as HTML"""
        html = f"""
        <h1>GupShup Admin Report - {report_type.replace('_', ' ').title()}</h1>
        <p><strong>Period:</strong> {data['start_date'].date()} to {data['end_date'].date()}</p>
        <p><strong>Generated:</strong> {data['report_timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
        """
        
        for section_key, section_data in data['sections'].items():
            if isinstance(section_data, dict):
                html += f"\n<h2>{section_data.get('title', section_key.title())}</h2>\n<ul>"
                
                for key, value in section_data.items():
                    if key != 'title':
                        if isinstance(value, list):
                            html += f"\n<li><strong>{key.replace('_', ' ').title()}:</strong><ul>"
                            for item in value[:5]:  # Show top 5
                                if isinstance(item, dict):
                                    html += f"<li>{item}</li>"
                                else:
                                    html += f"<li>{item}</li>"
                            html += "</ul></li>"
                        elif not isinstance(value, dict):
                            html += f"\n<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
                
                html += "\n</ul>\n"
        
        return html
    
    def _save_report(self, content, output_path, output_format):
        """Save report to file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _email_report(self, content, email, report_type, output_format):
        """Email report to specified address"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = f'GupShup Admin Report - {report_type.replace("_", " ").title()}'
        
        if output_format == 'html':
            send_mail(
                subject=subject,
                message='Please see attached HTML report.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=content
            )
        else:
            send_mail(
                subject=subject,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email]
            )