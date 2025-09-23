"""
Management command for batch content moderation

Usage: python manage.py moderate_content --action=review --filter=flagged
"""

import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction
from posts.models import Post, Comment
from admin_panel.models import AdminAction, ModeratedContent, AdminUser


class Command(BaseCommand):
    help = 'Batch content moderation for GupShup platform'
    
    # Predefined content filters
    INAPPROPRIATE_KEYWORDS = [
        'spam', 'fake', 'scam', 'fraud', 'hate', 'abuse',
        'violence', 'harassment', 'threat', 'illegal'
    ]
    
    INDIAN_INAPPROPRIATE_TERMS = [
        'bhakchod', 'gandu', 'chutiya', 'madarchod', 'bhenchod',
        'randi', 'saala', 'kamina', 'harami'
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            default='review',
            choices=['review', 'flag', 'approve', 'delete', 'analyze'],
            help='Moderation action to perform (default: review)',
        )
        parser.add_argument(
            '--filter',
            type=str,
            default='recent',
            choices=['recent', 'flagged', 'reported', 'suspicious', 'all'],
            help='Content filter to apply (default: recent)',
        )
        parser.add_argument(
            '--content-type',
            type=str,
            default='posts',
            choices=['posts', 'comments', 'both'],
            help='Type of content to moderate (default: posts)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back (default: 7)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of items to process (default: 100)',
        )
        parser.add_argument(
            '--admin',
            type=str,
            help='Admin username performing the moderation',
        )
        parser.add_argument(
            '--reason',
            type=str,
            help='Reason for bulk moderation action',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--auto-approve',
            action='store_true',
            help='Auto-approve content that passes all filters',
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to file (JSON/CSV format)',
        )
        parser.add_argument(
            '--severity',
            type=str,
            default='medium',
            choices=['low', 'medium', 'high', 'critical'],
            help='Severity level for flagged content (default: medium)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '\n🛡️  GupShup Admin Panel - Content Moderation\n'
                '=============================================\n'
            )
        )
        
        action = options['action']
        content_filter = options['filter']
        content_type = options['content_type']
        days = options['days']
        limit = options['limit']
        admin_username = options['admin']
        reason = options['reason']
        dry_run = options['dry_run']
        auto_approve = options['auto_approve']
        export_path = options['export']
        severity = options['severity']
        
        # Get admin user
        admin_user = None
        if admin_username:
            try:
                admin_user = AdminUser.objects.get(username=admin_username)
            except AdminUser.DoesNotExist:
                raise CommandError(f'❌ Admin user "{admin_username}" not found')
        
        # Get content to moderate
        content_items = self._get_content_to_moderate(
            content_filter, content_type, days, limit
        )
        
        self.stdout.write(f'📋 Found {len(content_items)} items to moderate')
        
        if not content_items:
            self.stdout.write(
                self.style.SUCCESS('✅ No content found matching the criteria\n')
            )
            return
        
        # Show summary
        self._show_moderation_summary(content_items, action, dry_run)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - No changes will be made\n')
            )
            if export_path:
                self._export_results(content_items, export_path, 'dry_run')
            return
        
        # Confirm action
        if action in ['delete', 'flag'] and not dry_run:
            confirm = input(f'\nProceed with {action} action on {len(content_items)} items? (yes/no): ')
            if confirm.lower().strip() != 'yes':
                self.stdout.write(self.style.ERROR('❌ Moderation cancelled.\n'))
                return
        
        # Perform moderation action
        try:
            results = self._perform_moderation_action(
                content_items, action, admin_user, reason, severity, auto_approve
            )
            
            self._show_results(results)
            
            # Export results if requested
            if export_path:
                self._export_results(results, export_path, action)
            
            # Log bulk moderation
            self._log_bulk_moderation(results, action, admin_user)
            
        except Exception as e:
            raise CommandError(f'❌ Error performing moderation: {e}')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Batch moderation completed successfully!\n')
        )
    
    def _get_content_to_moderate(self, content_filter, content_type, days, limit):
        """Get content items based on filter criteria"""
        cutoff_date = timezone.now() - timedelta(days=days)
        content_items = []
        
        # Get posts
        if content_type in ['posts', 'both']:
            posts_query = Post.objects.all()
            
            if content_filter == 'recent':
                posts_query = posts_query.filter(created_at__gte=cutoff_date)
            elif content_filter == 'flagged':
                posts_query = posts_query.filter(
                    moderated_content__status='flagged'
                )
            elif content_filter == 'reported':
                # Assuming there's a report system
                posts_query = posts_query.filter(
                    # Add report filtering logic here
                    created_at__gte=cutoff_date
                )
            elif content_filter == 'suspicious':
                posts_query = self._get_suspicious_posts(posts_query, cutoff_date)
            
            posts = list(posts_query.order_by('-created_at')[:limit // 2 if content_type == 'both' else limit])
            content_items.extend([{'type': 'post', 'item': post} for post in posts])
        
        # Get comments
        if content_type in ['comments', 'both']:
            comments_query = Comment.objects.all()
            
            if content_filter == 'recent':
                comments_query = comments_query.filter(created_at__gte=cutoff_date)
            elif content_filter == 'flagged':
                comments_query = comments_query.filter(
                    moderated_content__status='flagged'
                )
            elif content_filter == 'suspicious':
                comments_query = self._get_suspicious_comments(comments_query, cutoff_date)
            
            remaining_limit = limit - len(content_items)
            comments = list(comments_query.order_by('-created_at')[:remaining_limit])
            content_items.extend([{'type': 'comment', 'item': comment} for comment in comments])
        
        return content_items
    
    def _get_suspicious_posts(self, posts_query, cutoff_date):
        """Filter posts that might be suspicious"""
        suspicious_conditions = Q()
        
        # Posts with inappropriate keywords
        for keyword in self.INAPPROPRIATE_KEYWORDS + self.INDIAN_INAPPROPRIATE_TERMS:
            suspicious_conditions |= Q(content__icontains=keyword)
        
        # Posts with excessive capitalization
        suspicious_conditions |= Q(content__regex=r'[A-Z]{10,}')
        
        # Posts with excessive special characters
        suspicious_conditions |= Q(content__regex=r'[!@#$%^&*]{5,}')
        
        # Very short posts with links
        suspicious_conditions |= Q(
            content__icontains='http',
            content__length__lt=50
        )
        
        # Posts from recently created accounts (potential spam)
        recent_user_cutoff = timezone.now() - timedelta(days=7)
        suspicious_conditions |= Q(author__date_joined__gte=recent_user_cutoff)
        
        return posts_query.filter(suspicious_conditions, created_at__gte=cutoff_date)
    
    def _get_suspicious_comments(self, comments_query, cutoff_date):
        """Filter comments that might be suspicious"""
        suspicious_conditions = Q()
        
        # Comments with inappropriate keywords
        for keyword in self.INAPPROPRIATE_KEYWORDS + self.INDIAN_INAPPROPRIATE_TERMS:
            suspicious_conditions |= Q(text__icontains=keyword)
        
        # Very short comments (potential spam)
        suspicious_conditions |= Q(text__length__lt=10)
        
        # Comments with excessive repetition
        suspicious_conditions |= Q(text__regex=r'(.)\1{5,}')
        
        return comments_query.filter(suspicious_conditions, created_at__gte=cutoff_date)
    
    def _show_moderation_summary(self, content_items, action, dry_run):
        """Show summary of items to be moderated"""
        posts_count = sum(1 for item in content_items if item['type'] == 'post')
        comments_count = sum(1 for item in content_items if item['type'] == 'comment')
        
        self.stdout.write(f'\n📊 Moderation Summary:')
        self.stdout.write(f'   • Action: {action}')
        self.stdout.write(f'   • Posts: {posts_count}')
        self.stdout.write(f'   • Comments: {comments_count}')
        self.stdout.write(f'   • Total Items: {len(content_items)}')
        
        if dry_run:
            self.stdout.write(f'   • Mode: DRY RUN (no changes will be made)')
        
        # Show sample content
        if content_items:
            self.stdout.write(f'\n📝 Sample Content:')
            for i, item in enumerate(content_items[:3]):
                content_text = item['item'].content if item['type'] == 'post' else item['item'].text
                preview = content_text[:100] + '...' if len(content_text) > 100 else content_text
                self.stdout.write(f'   {i+1}. [{item["type"].upper()}] {preview}')
            
            if len(content_items) > 3:
                self.stdout.write(f'   ... and {len(content_items) - 3} more items')
    
    def _perform_moderation_action(self, content_items, action, admin_user, reason, severity, auto_approve):
        """Perform the actual moderation action"""
        results = {
            'processed': 0,
            'flagged': 0,
            'approved': 0,
            'deleted': 0,
            'errors': 0,
            'details': []
        }
        
        with transaction.atomic():
            for item_data in content_items:
                try:
                    item = item_data['item']
                    item_type = item_data['type']
                    
                    if action == 'flag':
                        self._flag_content(item, item_type, admin_user, reason, severity)
                        results['flagged'] += 1
                    
                    elif action == 'approve':
                        self._approve_content(item, item_type, admin_user, reason)
                        results['approved'] += 1
                    
                    elif action == 'delete':
                        self._delete_content(item, item_type, admin_user, reason)
                        results['deleted'] += 1
                    
                    elif action == 'analyze':
                        analysis = self._analyze_content(item, item_type)
                        results['details'].append({
                            'item_id': item.id,
                            'type': item_type,
                            'analysis': analysis
                        })
                        
                        # Auto-approve if enabled and content is clean
                        if auto_approve and analysis['risk_score'] < 0.3:
                            self._approve_content(item, item_type, admin_user, 'Auto-approved based on analysis')
                            results['approved'] += 1
                    
                    elif action == 'review':
                        self._add_to_moderation_queue(item, item_type, admin_user, severity)
                    
                    results['processed'] += 1
                    
                except Exception as e:
                    results['errors'] += 1
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Error processing {item_type} {item.id}: {e}')
                    )
        
        return results
    
    def _flag_content(self, item, item_type, admin_user, reason, severity):
        """Flag content for review"""
        ModeratedContent.objects.update_or_create(
            content_type=item_type,
            object_id=item.id,
            defaults={
                'status': 'flagged',
                'flagged_by': admin_user,
                'flagged_at': timezone.now(),
                'flag_reason': reason or 'Bulk moderation',
                'severity': severity,
                'notes': f'Flagged via bulk moderation command'
            }
        )
    
    def _approve_content(self, item, item_type, admin_user, reason):
        """Approve content"""
        ModeratedContent.objects.update_or_create(
            content_type=item_type,
            object_id=item.id,
            defaults={
                'status': 'approved',
                'reviewed_by': admin_user,
                'reviewed_at': timezone.now(),
                'review_notes': reason or 'Bulk approved',
                'auto_flagged': False
            }
        )
    
    def _delete_content(self, item, item_type, admin_user, reason):
        """Delete content"""
        # Mark as deleted in moderation system first
        ModeratedContent.objects.update_or_create(
            content_type=item_type,
            object_id=item.id,
            defaults={
                'status': 'deleted',
                'reviewed_by': admin_user,
                'reviewed_at': timezone.now(),
                'review_notes': reason or 'Bulk deleted',
                'severity': 'high'
            }
        )
        
        # Actually delete the content
        item.delete()
    
    def _add_to_moderation_queue(self, item, item_type, admin_user, severity):
        """Add content to moderation queue"""
        ModeratedContent.objects.update_or_create(
            content_type=item_type,
            object_id=item.id,
            defaults={
                'status': 'pending',
                'flagged_by': admin_user,
                'flagged_at': timezone.now(),
                'severity': severity,
                'notes': 'Added to queue via bulk moderation'
            }
        )
    
    def _analyze_content(self, item, item_type):
        """Analyze content for potential issues"""
        content_text = item.content if item_type == 'post' else item.text
        
        analysis = {
            'length': len(content_text),
            'word_count': len(content_text.split()),
            'inappropriate_keywords': 0,
            'caps_ratio': 0,
            'special_chars_ratio': 0,
            'risk_score': 0,
            'issues': []
        }
        
        # Check for inappropriate keywords
        text_lower = content_text.lower()
        for keyword in self.INAPPROPRIATE_KEYWORDS + self.INDIAN_INAPPROPRIATE_TERMS:
            if keyword in text_lower:
                analysis['inappropriate_keywords'] += 1
                analysis['issues'].append(f'Contains keyword: {keyword}')
        
        # Check capitalization
        if content_text:
            caps_count = sum(1 for c in content_text if c.isupper())
            analysis['caps_ratio'] = caps_count / len(content_text)
            if analysis['caps_ratio'] > 0.5:
                analysis['issues'].append('Excessive capitalization')
        
        # Check special characters
        special_chars = sum(1 for c in content_text if not c.isalnum() and not c.isspace())
        if content_text:
            analysis['special_chars_ratio'] = special_chars / len(content_text)
            if analysis['special_chars_ratio'] > 0.2:
                analysis['issues'].append('Excessive special characters')
        
        # Calculate risk score
        risk_score = 0
        risk_score += analysis['inappropriate_keywords'] * 0.3
        risk_score += analysis['caps_ratio'] * 0.2
        risk_score += analysis['special_chars_ratio'] * 0.1
        
        # Very short content is suspicious
        if analysis['word_count'] < 3:
            risk_score += 0.2
            analysis['issues'].append('Very short content')
        
        analysis['risk_score'] = min(risk_score, 1.0)
        
        return analysis
    
    def _show_results(self, results):
        """Show moderation results"""
        self.stdout.write(f'\n📊 Moderation Results:')
        self.stdout.write(f'   • Processed: {results["processed"]}')
        self.stdout.write(f'   • Flagged: {results["flagged"]}')
        self.stdout.write(f'   • Approved: {results["approved"]}')
        self.stdout.write(f'   • Deleted: {results["deleted"]}')
        self.stdout.write(f'   • Errors: {results["errors"]}')
        
        if results.get('details'):
            self.stdout.write(f'\n📋 Content Analysis Details:')
            for detail in results['details'][:5]:  # Show first 5
                analysis = detail['analysis']
                self.stdout.write(
                    f'   • {detail["type"].upper()} {detail["item_id"]}: '
                    f'Risk Score: {analysis["risk_score"]:.2f}, '
                    f'Issues: {len(analysis["issues"])}'
                )
    
    def _export_results(self, results, export_path, action):
        """Export moderation results"""
        import json
        
        export_data = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'results': results
        }
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.stdout.write(f'📁 Results exported to: {export_path}')
    
    def _log_bulk_moderation(self, results, action, admin_user):
        """Log bulk moderation action"""
        try:
            AdminAction.objects.create(
                admin=admin_user,
                action_type='bulk_moderation',
                severity='info',
                title=f'Bulk Content {action.title()}',
                description=f'Bulk {action} performed on {results["processed"]} items',
                metadata={
                    'action': action,
                    'processed_count': results['processed'],
                    'flagged_count': results['flagged'],
                    'approved_count': results['approved'],
                    'deleted_count': results['deleted'],
                    'error_count': results['errors']
                }
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not log bulk moderation: {e}')
            )