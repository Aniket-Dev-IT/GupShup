"""
GupShup Admin Panel Audit Module

This module provides comprehensive audit logging, log retention policies,
log export functionality, and compliance report generation for the admin panel.
"""

import json
import csv
import io
import zipfile
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict
from pathlib import Path

from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from django.http import HttpResponse, StreamingHttpResponse
from django.db.models import Count, Q, Avg, Sum
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator

from .models import AdminUser, AdminAction, AdminSession, UserWarning, BannedUser, ModeratedContent
from .security import encryption_manager
from accounts.models import GupShupUser
from posts.models import Post, Comment


class AuditConfig:
    """Audit configuration and constants"""
    
    # Log retention settings
    DEFAULT_RETENTION_DAYS = 365  # 1 year
    CRITICAL_RETENTION_DAYS = 2555  # 7 years for compliance
    
    # Export settings
    MAX_EXPORT_RECORDS = 50000
    EXPORT_BATCH_SIZE = 1000
    
    # Compliance settings
    COMPLIANCE_STANDARDS = [
        'GDPR',
        'SOX',
        'PCI-DSS',
        'HIPAA',
        'ISO_27001'
    ]
    
    # Action severity levels
    SEVERITY_LEVELS = {
        'info': 1,
        'warning': 2,
        'error': 3,
        'critical': 4
    }
    
    # Required audit fields for compliance
    REQUIRED_FIELDS = [
        'admin_id',
        'action_type',
        'timestamp',
        'ip_address',
        'user_agent',
        'description',
        'severity'
    ]


class AuditLogger:
    """Enhanced audit logging with structured data and compliance features"""
    
    def __init__(self):
        self.encrypted_fields = ['sensitive_data', 'personal_info', 'credentials']
    
    def log_admin_action(
        self,
        admin_user: AdminUser,
        action_type: str,
        description: str,
        severity: str = 'info',
        target_user: Optional[GupShupUser] = None,
        target_object: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: str = '',
        user_agent: str = '',
        request_path: str = '',
        before_state: Optional[Dict] = None,
        after_state: Optional[Dict] = None
    ) -> AdminAction:
        """
        Log an admin action with comprehensive details
        
        Args:
            admin_user: Admin user performing the action
            action_type: Type of action being performed
            description: Human-readable description
            severity: Severity level (info, warning, error, critical)
            target_user: User being affected (if applicable)
            target_object: Object being modified (if applicable)
            metadata: Additional structured data
            ip_address: IP address of the request
            user_agent: User agent string
            request_path: Request path/URL
            before_state: State before the action
            after_state: State after the action
            
        Returns:
            Created AdminAction instance
        """
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        # Add system metadata
        metadata.update({
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent[:500],  # Truncate to prevent overflow
            'request_path': request_path,
            'system_version': getattr(settings, 'VERSION', 'unknown'),
            'compliance_tags': self._get_compliance_tags(action_type)
        })
        
        # Add target information
        if target_user:
            metadata['target_user'] = {
                'id': target_user.id,
                'username': target_user.username,
                'email': target_user.email[:50] + '...' if len(target_user.email) > 50 else target_user.email
            }
        
        if target_object:
            metadata['target_object'] = {
                'type': target_object.__class__.__name__,
                'id': getattr(target_object, 'id', None),
                'str': str(target_object)[:200]
            }
        
        # Encrypt sensitive data in metadata
        if any(field in metadata for field in self.encrypted_fields):
            metadata = self._encrypt_sensitive_metadata(metadata)
        
        # Add state changes if provided
        if before_state or after_state:
            metadata['state_changes'] = {
                'before': before_state,
                'after': after_state,
                'diff': self._calculate_state_diff(before_state, after_state)
            }
        
        # Create the audit log entry
        admin_action = AdminAction.objects.create(
            admin=admin_user,
            action_type=action_type,
            severity=severity,
            title=self._generate_action_title(action_type),
            description=description,
            metadata=metadata,
            created_at=timezone.now()
        )
        
        # Trigger real-time alerts for critical actions
        if severity in ['error', 'critical']:
            self._trigger_security_alert(admin_action)
        
        return admin_action
    
    def log_user_action(
        self,
        admin_user: AdminUser,
        target_user: GupShupUser,
        action: str,
        reason: str = '',
        duration: Optional[timedelta] = None,
        metadata: Optional[Dict] = None
    ) -> AdminAction:
        """
        Log user-related admin actions (ban, warn, etc.)
        
        Args:
            admin_user: Admin performing the action
            target_user: User being affected
            action: Action being performed (ban, warn, activate, etc.)
            reason: Reason for the action
            duration: Duration for temporary actions
            metadata: Additional metadata
            
        Returns:
            Created AdminAction instance
        """
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'action_reason': reason,
            'user_profile': {
                'join_date': target_user.date_joined.isoformat(),
                'post_count': target_user.posts.count(),
                'last_active': target_user.last_login.isoformat() if target_user.last_login else None
            }
        })
        
        if duration:
            metadata['duration'] = {
                'days': duration.days,
                'total_seconds': duration.total_seconds()
            }
        
        return self.log_admin_action(
            admin_user=admin_user,
            action_type=f'user_{action}',
            description=f'{action.title()} user {target_user.username}: {reason}',
            severity='warning' if action in ['ban', 'warn'] else 'info',
            target_user=target_user,
            metadata=metadata
        )
    
    def log_content_action(
        self,
        admin_user: AdminUser,
        content_object: Union[Post, Comment],
        action: str,
        reason: str = '',
        metadata: Optional[Dict] = None
    ) -> AdminAction:
        """
        Log content moderation actions
        
        Args:
            admin_user: Admin performing the action
            content_object: Content being moderated
            action: Action being performed (approve, delete, flag)
            reason: Reason for the action
            metadata: Additional metadata
            
        Returns:
            Created AdminAction instance
        """
        if metadata is None:
            metadata = {}
        
        content_info = {
            'content_type': content_object.__class__.__name__.lower(),
            'content_id': content_object.id,
            'author': content_object.author.username if hasattr(content_object, 'author') else 'unknown',
            'created_at': content_object.created_at.isoformat(),
            'content_preview': str(content_object)[:200]
        }
        
        metadata.update({
            'action_reason': reason,
            'content_info': content_info
        })
        
        return self.log_admin_action(
            admin_user=admin_user,
            action_type=f'content_{action}',
            description=f'{action.title()} {content_info["content_type"]}: {reason}',
            severity='warning' if action == 'delete' else 'info',
            target_object=content_object,
            metadata=metadata
        )
    
    def log_system_event(
        self,
        event_type: str,
        description: str,
        severity: str = 'info',
        metadata: Optional[Dict] = None
    ) -> AdminAction:
        """
        Log system events (not tied to specific admin user)
        
        Args:
            event_type: Type of system event
            description: Description of the event
            severity: Severity level
            metadata: Additional metadata
            
        Returns:
            Created AdminAction instance
        """
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'system_event': True,
            'server_info': {
                'timestamp': timezone.now().isoformat(),
                'environment': getattr(settings, 'ENVIRONMENT', 'unknown')
            }
        })
        
        return AdminAction.objects.create(
            admin=None,  # System event
            action_type=event_type,
            severity=severity,
            title=self._generate_action_title(event_type),
            description=description,
            metadata=metadata,
            created_at=timezone.now()
        )
    
    def _get_compliance_tags(self, action_type: str) -> List[str]:
        """Get compliance tags for action type"""
        compliance_mapping = {
            'user_ban': ['GDPR', 'SOX'],
            'user_data_export': ['GDPR'],
            'user_data_delete': ['GDPR'],
            'financial_data_access': ['SOX', 'PCI-DSS'],
            'medical_data_access': ['HIPAA'],
            'security_incident': ['ISO_27001'],
            'data_breach': ['GDPR', 'ISO_27001'],
        }
        
        return compliance_mapping.get(action_type, [])
    
    def _encrypt_sensitive_metadata(self, metadata: Dict) -> Dict:
        """Encrypt sensitive fields in metadata"""
        encrypted_metadata = metadata.copy()
        
        for field in self.encrypted_fields:
            if field in encrypted_metadata:
                try:
                    encrypted_data = encryption_manager.encrypt_data(
                        json.dumps(encrypted_metadata[field])
                    )
                    encrypted_metadata[field] = {
                        'encrypted': True,
                        'data': encrypted_data
                    }
                except Exception as e:
                    # Log encryption failure but don't fail the audit
                    encrypted_metadata[field] = {
                        'encryption_failed': True,
                        'error': str(e)
                    }
        
        return encrypted_metadata
    
    def _calculate_state_diff(
        self, 
        before: Optional[Dict], 
        after: Optional[Dict]
    ) -> Dict[str, Any]:
        """Calculate differences between before and after states"""
        if not before or not after:
            return {}
        
        diff = {
            'added': {},
            'removed': {},
            'changed': {}
        }
        
        # Find added fields
        for key in after:
            if key not in before:
                diff['added'][key] = after[key]
        
        # Find removed fields
        for key in before:
            if key not in after:
                diff['removed'][key] = before[key]
        
        # Find changed fields
        for key in before:
            if key in after and before[key] != after[key]:
                diff['changed'][key] = {
                    'from': before[key],
                    'to': after[key]
                }
        
        return diff
    
    def _generate_action_title(self, action_type: str) -> str:
        """Generate human-readable title from action type"""
        return action_type.replace('_', ' ').title()
    
    def _trigger_security_alert(self, admin_action: AdminAction):
        """Trigger real-time security alerts for critical actions"""
        # This would integrate with your notification system
        # For now, we'll just cache the alert for dashboard display
        from django.core.cache import cache
        
        alert_data = {
            'id': admin_action.id,
            'admin': admin_action.admin.username if admin_action.admin else 'System',
            'action_type': admin_action.action_type,
            'description': admin_action.description,
            'severity': admin_action.severity,
            'timestamp': admin_action.created_at.isoformat()
        }
        
        # Store in cache for real-time alerts
        cache_key = f'security_alert_{admin_action.id}'
        cache.set(cache_key, alert_data, 3600)  # 1 hour
        
        # Add to global alerts list
        alerts_key = 'security_alerts_list'
        current_alerts = cache.get(alerts_key, [])
        current_alerts.insert(0, alert_data)
        
        # Keep only last 50 alerts
        if len(current_alerts) > 50:
            current_alerts = current_alerts[:50]
        
        cache.set(alerts_key, current_alerts, 3600)


class AuditQueryEngine:
    """Advanced querying engine for audit logs"""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
    
    def search_logs(
        self,
        admin_user: Optional[AdminUser] = None,
        action_types: Optional[List[str]] = None,
        severity_levels: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        target_user: Optional[GupShupUser] = None,
        ip_address: Optional[str] = None,
        search_text: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Advanced search in audit logs
        
        Args:
            admin_user: Filter by admin user
            action_types: List of action types to include
            severity_levels: List of severity levels to include
            date_from: Start date for filtering
            date_to: End date for filtering
            target_user: Filter by target user
            ip_address: Filter by IP address
            search_text: Text search in description/metadata
            compliance_tags: Filter by compliance requirements
            page: Page number for pagination
            per_page: Records per page
            
        Returns:
            Dictionary with results and metadata
        """
        # Build base queryset
        queryset = AdminAction.objects.select_related('admin').all()
        
        # Apply filters
        if admin_user:
            queryset = queryset.filter(admin=admin_user)
        
        if action_types:
            queryset = queryset.filter(action_type__in=action_types)
        
        if severity_levels:
            queryset = queryset.filter(severity__in=severity_levels)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        if target_user:
            queryset = queryset.filter(
                metadata__target_user__id=target_user.id
            )
        
        if ip_address:
            queryset = queryset.filter(
                metadata__ip_address__icontains=ip_address
            )
        
        if search_text:
            queryset = queryset.filter(
                Q(description__icontains=search_text) |
                Q(title__icontains=search_text) |
                Q(metadata__icontains=search_text)
            )
        
        if compliance_tags:
            for tag in compliance_tags:
                queryset = queryset.filter(
                    metadata__compliance_tags__contains=tag
                )
        
        # Order by most recent first
        queryset = queryset.order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        # Serialize results
        results = []
        for action in page_obj:
            action_data = {
                'id': action.id,
                'admin': action.admin.username if action.admin else 'System',
                'admin_id': action.admin.id if action.admin else None,
                'action_type': action.action_type,
                'title': action.title,
                'description': action.description,
                'severity': action.severity,
                'created_at': action.created_at.isoformat(),
                'metadata': action.metadata
            }
            
            # Decrypt sensitive metadata if needed
            if self._has_encrypted_metadata(action.metadata):
                action_data['metadata'] = self._decrypt_metadata(action.metadata)
            
            results.append(action_data)
        
        return {
            'results': results,
            'pagination': {
                'page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_records': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'query_metadata': {
                'filters_applied': {
                    'admin_user': admin_user.username if admin_user else None,
                    'action_types': action_types,
                    'severity_levels': severity_levels,
                    'date_range': {
                        'from': date_from.isoformat() if date_from else None,
                        'to': date_to.isoformat() if date_to else None
                    },
                    'search_text': search_text,
                    'compliance_tags': compliance_tags
                },
                'query_timestamp': timezone.now().isoformat()
            }
        }
    
    def get_activity_timeline(
        self,
        target_user: GupShupUser,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get activity timeline for a specific user
        
        Args:
            target_user: User to get timeline for
            days_back: Number of days to look back
            
        Returns:
            List of activity events
        """
        start_date = timezone.now() - timedelta(days=days_back)
        
        # Get admin actions involving this user
        admin_actions = AdminAction.objects.filter(
            created_at__gte=start_date,
            metadata__target_user__id=target_user.id
        ).order_by('-created_at')
        
        timeline = []
        for action in admin_actions:
            timeline.append({
                'timestamp': action.created_at.isoformat(),
                'type': 'admin_action',
                'action': action.action_type,
                'description': action.description,
                'admin': action.admin.username if action.admin else 'System',
                'severity': action.severity,
                'metadata': action.metadata
            })
        
        return timeline
    
    def get_admin_activity_summary(
        self,
        admin_user: AdminUser,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get activity summary for an admin user
        
        Args:
            admin_user: Admin user to analyze
            date_from: Start date (default: 30 days ago)
            date_to: End date (default: now)
            
        Returns:
            Activity summary
        """
        if not date_from:
            date_from = timezone.now() - timedelta(days=30)
        if not date_to:
            date_to = timezone.now()
        
        actions = AdminAction.objects.filter(
            admin=admin_user,
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        # Calculate statistics
        total_actions = actions.count()
        actions_by_type = dict(actions.values('action_type').annotate(count=Count('id')).values_list('action_type', 'count'))
        actions_by_severity = dict(actions.values('severity').annotate(count=Count('id')).values_list('severity', 'count'))
        
        # Get daily activity
        daily_activity = defaultdict(int)
        for action in actions.values('created_at__date').annotate(count=Count('id')):
            daily_activity[action['created_at__date'].isoformat()] = action['count']
        
        return {
            'admin_user': admin_user.username,
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'summary': {
                'total_actions': total_actions,
                'actions_by_type': actions_by_type,
                'actions_by_severity': actions_by_severity,
                'daily_activity': dict(daily_activity)
            },
            'report_timestamp': timezone.now().isoformat()
        }
    
    def _has_encrypted_metadata(self, metadata: Dict) -> bool:
        """Check if metadata contains encrypted fields"""
        for field in metadata:
            if isinstance(metadata[field], dict) and metadata[field].get('encrypted'):
                return True
        return False
    
    def _decrypt_metadata(self, metadata: Dict) -> Dict:
        """Decrypt encrypted metadata fields"""
        decrypted = metadata.copy()
        
        for field, value in metadata.items():
            if isinstance(value, dict) and value.get('encrypted'):
                try:
                    decrypted_data = encryption_manager.decrypt_data(value['data'])
                    decrypted[field] = json.loads(decrypted_data)
                except Exception:
                    decrypted[field] = {'decryption_failed': True}
        
        return decrypted


class AuditRetentionManager:
    """Manages audit log retention policies"""
    
    def __init__(self):
        self.config = AuditConfig()
    
    def apply_retention_policy(self) -> Dict[str, int]:
        """
        Apply retention policies to audit logs
        
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'archived': 0,
            'deleted': 0,
            'retained': 0
        }
        
        current_time = timezone.now()
        
        # Archive old logs (move to long-term storage)
        archive_threshold = current_time - timedelta(days=self.config.DEFAULT_RETENTION_DAYS // 2)
        old_logs = AdminAction.objects.filter(
            created_at__lt=archive_threshold,
            archived=False
        )
        
        archived_count = 0
        for log in old_logs.iterator():
            if self._archive_log(log):
                archived_count += 1
        
        stats['archived'] = archived_count
        
        # Delete very old logs (except critical ones)
        delete_threshold = current_time - timedelta(days=self.config.DEFAULT_RETENTION_DAYS)
        deletable_logs = AdminAction.objects.filter(
            created_at__lt=delete_threshold,
            severity__in=['info', 'warning']
        )
        
        stats['deleted'] = deletable_logs.count()
        deletable_logs.delete()
        
        # Keep critical logs longer
        critical_delete_threshold = current_time - timedelta(days=self.config.CRITICAL_RETENTION_DAYS)
        critical_deletable = AdminAction.objects.filter(
            created_at__lt=critical_delete_threshold,
            severity__in=['error', 'critical']
        )
        
        critical_deleted = critical_deletable.count()
        critical_deletable.delete()
        stats['deleted'] += critical_deleted
        
        # Count retained logs
        stats['retained'] = AdminAction.objects.count()
        
        # Log the retention activity
        AuditLogger().log_system_event(
            event_type='retention_policy_applied',
            description=f'Applied retention policy: archived {stats["archived"]}, deleted {stats["deleted"]}, retained {stats["retained"]}',
            severity='info',
            metadata={'retention_stats': stats}
        )
        
        return stats
    
    def _archive_log(self, log: AdminAction) -> bool:
        """
        Archive a log entry to long-term storage
        
        Args:
            log: AdminAction to archive
            
        Returns:
            True if successfully archived
        """
        try:
            # Move log to archived status for long-term retention
            log.archived = True
            log.archived_at = timezone.now()
            log.save()
            
            return True
            
        except Exception:
            return False
    
    def get_retention_status(self) -> Dict[str, Any]:
        """Get current retention status"""
        current_time = timezone.now()
        
        # Calculate various time thresholds
        archive_threshold = current_time - timedelta(days=self.config.DEFAULT_RETENTION_DAYS // 2)
        delete_threshold = current_time - timedelta(days=self.config.DEFAULT_RETENTION_DAYS)
        critical_threshold = current_time - timedelta(days=self.config.CRITICAL_RETENTION_DAYS)
        
        # Count logs in each category
        total_logs = AdminAction.objects.count()
        archived_logs = AdminAction.objects.filter(archived=True).count()
        
        logs_to_archive = AdminAction.objects.filter(
            created_at__lt=archive_threshold,
            archived=False
        ).count()
        
        logs_to_delete = AdminAction.objects.filter(
            created_at__lt=delete_threshold,
            severity__in=['info', 'warning']
        ).count()
        
        critical_logs = AdminAction.objects.filter(
            severity__in=['error', 'critical']
        ).count()
        
        return {
            'total_logs': total_logs,
            'archived_logs': archived_logs,
            'logs_to_archive': logs_to_archive,
            'logs_to_delete': logs_to_delete,
            'critical_logs': critical_logs,
            'retention_policies': {
                'default_retention_days': self.config.DEFAULT_RETENTION_DAYS,
                'critical_retention_days': self.config.CRITICAL_RETENTION_DAYS
            },
            'next_cleanup_recommended': logs_to_archive > 0 or logs_to_delete > 0,
            'status_generated_at': current_time.isoformat()
        }


class AuditExporter:
    """Handles audit log export functionality"""
    
    def __init__(self):
        self.config = AuditConfig()
        self.query_engine = AuditQueryEngine()
    
    def export_to_csv(
        self,
        queryset,
        filename: str = None,
        include_metadata: bool = False
    ) -> HttpResponse:
        """
        Export audit logs to CSV format
        
        Args:
            queryset: QuerySet of AdminAction objects
            filename: Custom filename for export
            include_metadata: Whether to include metadata column
            
        Returns:
            HTTP response with CSV file
        """
        if not filename:
            filename = f'audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header
        headers = [
            'ID', 'Admin User', 'Action Type', 'Title', 'Description',
            'Severity', 'Created At', 'IP Address'
        ]
        
        if include_metadata:
            headers.append('Metadata')
        
        writer.writerow(headers)
        
        # Write data
        for action in queryset.iterator():
            row = [
                action.id,
                action.admin.username if action.admin else 'System',
                action.action_type,
                action.title,
                action.description,
                action.severity,
                action.created_at.isoformat(),
                action.metadata.get('ip_address', '') if action.metadata else ''
            ]
            
            if include_metadata:
                row.append(json.dumps(action.metadata) if action.metadata else '')
            
            writer.writerow(row)
        
        return response
    
    def export_to_json(
        self,
        queryset,
        filename: str = None,
        pretty_print: bool = True
    ) -> HttpResponse:
        """
        Export audit logs to JSON format
        
        Args:
            queryset: QuerySet of AdminAction objects
            filename: Custom filename for export
            pretty_print: Whether to format JSON nicely
            
        Returns:
            HTTP response with JSON file
        """
        if not filename:
            filename = f'audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        # Serialize data
        data = {
            'export_info': {
                'export_timestamp': timezone.now().isoformat(),
                'total_records': queryset.count(),
                'exported_by': 'audit_system'
            },
            'records': []
        }
        
        for action in queryset.iterator():
            record = {
                'id': action.id,
                'admin_user': action.admin.username if action.admin else 'System',
                'admin_id': action.admin.id if action.admin else None,
                'action_type': action.action_type,
                'title': action.title,
                'description': action.description,
                'severity': action.severity,
                'created_at': action.created_at.isoformat(),
                'metadata': action.metadata
            }
            
            data['records'].append(record)
        
        # Create response
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        if pretty_print:
            json.dump(data, response, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)
        else:
            json.dump(data, response, cls=DjangoJSONEncoder, ensure_ascii=False)
        
        return response
    
    def export_compliance_report(
        self,
        compliance_standard: str,
        date_from: datetime,
        date_to: datetime,
        format_type: str = 'json'
    ) -> HttpResponse:
        """
        Export compliance-specific report
        
        Args:
            compliance_standard: Standard to comply with (GDPR, SOX, etc.)
            date_from: Start date for report
            date_to: End date for report
            format_type: Export format (json, csv)
            
        Returns:
            HTTP response with compliance report
        """
        # Filter logs by compliance requirements
        queryset = AdminAction.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
            metadata__compliance_tags__contains=compliance_standard
        ).order_by('-created_at')
        
        filename = f'{compliance_standard.lower()}_compliance_report_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}'
        
        if format_type == 'csv':
            return self.export_to_csv(queryset, f'{filename}.csv', include_metadata=True)
        else:
            # Enhanced JSON report with compliance metadata
            compliance_data = {
                'compliance_report': {
                    'standard': compliance_standard,
                    'period': {
                        'from': date_from.isoformat(),
                        'to': date_to.isoformat()
                    },
                    'report_timestamp': timezone.now().isoformat(),
                    'total_relevant_actions': queryset.count(),
                    'report_hash': self._calculate_report_hash(queryset)
                },
                'summary': {
                    'actions_by_type': dict(
                        queryset.values('action_type').annotate(count=Count('id')).values_list('action_type', 'count')
                    ),
                    'actions_by_severity': dict(
                        queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count')
                    )
                },
                'detailed_records': []
            }
            
            # Add detailed records
            for action in queryset.iterator():
                record = {
                    'id': action.id,
                    'timestamp': action.created_at.isoformat(),
                    'admin_user': action.admin.username if action.admin else 'System',
                    'action_type': action.action_type,
                    'description': action.description,
                    'severity': action.severity,
                    'compliance_tags': action.metadata.get('compliance_tags', []) if action.metadata else [],
                    'metadata': action.metadata
                }
                
                compliance_data['detailed_records'].append(record)
            
            response = HttpResponse(content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
            json.dump(compliance_data, response, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)
            
            return response
    
    def _calculate_report_hash(self, queryset) -> str:
        """Calculate integrity hash for compliance report"""
        # Create a hash of all record IDs and timestamps for integrity verification
        hash_data = []
        for action in queryset.values('id', 'created_at').iterator():
            hash_data.append(f"{action['id']}:{action['created_at'].isoformat()}")
        
        combined_data = '|'.join(sorted(hash_data))
        return hashlib.sha256(combined_data.encode()).hexdigest()


class ComplianceReporter:
    """Generates compliance reports for various standards"""
    
    def __init__(self):
        self.exporter = AuditExporter()
        self.query_engine = AuditQueryEngine()
    
    def generate_gdpr_report(
        self,
        date_from: datetime,
        date_to: datetime
    ) -> Dict[str, Any]:
        """Generate GDPR compliance report"""
        # GDPR-relevant actions
        gdpr_actions = AdminAction.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
            action_type__in=[
                'user_data_export',
                'user_data_delete',
                'user_consent_update',
                'data_breach_response',
                'privacy_policy_update'
            ]
        )
        
        return {
            'standard': 'GDPR',
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'metrics': {
                'data_subject_requests': gdpr_actions.filter(
                    action_type__in=['user_data_export', 'user_data_delete']
                ).count(),
                'data_breaches': gdpr_actions.filter(
                    action_type='data_breach_response'
                ).count(),
                'consent_updates': gdpr_actions.filter(
                    action_type='user_consent_update'
                ).count(),
            },
            'compliance_score': self._calculate_gdpr_compliance_score(gdpr_actions),
            'recommendations': self._get_gdpr_recommendations(gdpr_actions)
        }
    
    def generate_audit_dashboard_data(self) -> Dict[str, Any]:
        """Generate data for audit dashboard"""
        current_time = timezone.now()
        last_24h = current_time - timedelta(hours=24)
        last_week = current_time - timedelta(days=7)
        last_month = current_time - timedelta(days=30)
        
        return {
            'recent_activity': {
                'last_24h': AdminAction.objects.filter(created_at__gte=last_24h).count(),
                'last_week': AdminAction.objects.filter(created_at__gte=last_week).count(),
                'last_month': AdminAction.objects.filter(created_at__gte=last_month).count(),
            },
            'severity_distribution': dict(
                AdminAction.objects.filter(created_at__gte=last_month)
                .values('severity')
                .annotate(count=Count('id'))
                .values_list('severity', 'count')
            ),
            'top_actions': list(
                AdminAction.objects.filter(created_at__gte=last_month)
                .values('action_type')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .values_list('action_type', 'count')
            ),
            'most_active_admins': list(
                AdminAction.objects.filter(created_at__gte=last_month)
                .exclude(admin=None)
                .values('admin__username')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .values_list('admin__username', 'count')
            ),
            'security_events': AdminAction.objects.filter(
                created_at__gte=last_week,
                severity__in=['error', 'critical']
            ).count(),
            'generated_at': current_time.isoformat()
        }
    
    def _calculate_gdpr_compliance_score(self, actions) -> float:
        """Calculate GDPR compliance score (0-100)"""
        # This is a simplified scoring mechanism
        # In reality, this would be much more complex
        
        base_score = 85.0  # Assume good baseline compliance
        
        # Deduct points for delayed responses
        # Add points for proactive measures
        
        return min(100.0, max(0.0, base_score))
    
    def _get_gdpr_recommendations(self, actions) -> List[str]:
        """Get GDPR compliance recommendations"""
        recommendations = []
        
        # Analyze actions and provide recommendations
        if actions.filter(action_type='data_breach_response').exists():
            recommendations.append("Review data breach response procedures")
        
        if actions.filter(created_at__gte=timezone.now() - timedelta(days=30)).count() == 0:
            recommendations.append("Increase frequency of privacy audits")
        
        return recommendations


# Initialize audit components
audit_logger = AuditLogger()
audit_query_engine = AuditQueryEngine()
audit_retention_manager = AuditRetentionManager()
audit_exporter = AuditExporter()
compliance_reporter = ComplianceReporter()