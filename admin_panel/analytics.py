"""
GupShup Admin Panel Analytics System

This module provides comprehensive analytics and reporting capabilities
for the admin panel, including user growth metrics, content engagement
tracking, geographic analytics, and real-time data aggregation.
"""

import json
import csv
import io
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Union

from django.db import models
from django.db.models import Count, Sum, Avg, Max, Min, Q, F, Case, When
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Extract
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from accounts.models import GupShupUser
from posts.models import Post
from social.models import Follow, Comment, Like
from .models import AdminAction, UserWarning, BannedUser, ModeratedContent


class BaseAnalytics:
    """Base class for all analytics modules"""
    
    def __init__(self, cache_timeout: int = 300):
        self.cache_timeout = cache_timeout
        self.timezone = timezone.get_current_timezone()
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key for analytics data"""
        key_parts = [prefix]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}_{v}")
        return "_".join(key_parts)
    
    def _get_date_range(self, days: int) -> Tuple[datetime, datetime]:
        """Get date range for analytics queries"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date
    
    def _cache_result(self, cache_key: str, data: any) -> any:
        """Cache analytics result"""
        cache.set(cache_key, data, self.cache_timeout)
        return data
    
    def _get_cached_or_calculate(self, cache_key: str, calculation_func) -> any:
        """Get cached result or calculate and cache it"""
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        result = calculation_func()
        return self._cache_result(cache_key, result)


class UserAnalytics(BaseAnalytics):
    """Analytics for user growth and behavior metrics"""
    
    def get_user_growth_data(self, days: int = 30) -> Dict:
        """Get user growth data over specified period"""
        cache_key = self._generate_cache_key("user_growth", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Daily user registrations
            daily_registrations = list(
                GupShupUser.objects.filter(
                    date_joined__gte=start_date,
                    date_joined__lte=end_date
                ).extra({'date': 'DATE(date_joined)'})
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            
            # Fill in missing dates with zero counts
            date_counts = {item['date']: item['count'] for item in daily_registrations}
            
            growth_data = []
            current_date = start_date.date()
            total_users = 0
            
            while current_date <= end_date.date():
                daily_count = date_counts.get(current_date, 0)
                total_users += daily_count
                
                growth_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'new_users': daily_count,
                    'cumulative_users': total_users,
                    'growth_rate': (daily_count / max(total_users - daily_count, 1)) * 100
                })
                
                current_date += timedelta(days=1)
            
            # Calculate summary statistics
            total_new_users = sum(item['new_users'] for item in growth_data)
            avg_daily_growth = total_new_users / days if days > 0 else 0
            
            return {
                'growth_data': growth_data,
                'summary': {
                    'total_new_users': total_new_users,
                    'avg_daily_growth': round(avg_daily_growth, 2),
                    'peak_day': max(growth_data, key=lambda x: x['new_users']) if growth_data else None,
                    'growth_trend': self._calculate_trend([item['new_users'] for item in growth_data])
                }
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def get_user_demographics(self) -> Dict:
        """Get comprehensive user demographic data"""
        cache_key = self._generate_cache_key("user_demographics")
        
        def calculate():
            # State distribution
            state_distribution = list(
                GupShupUser.objects.exclude(state='')
                .values('state')
                .annotate(count=Count('id'))
                .order_by('-count')[:20]
            )
            
            # City distribution
            city_distribution = list(
                GupShupUser.objects.exclude(city='')
                .values('city', 'state')
                .annotate(count=Count('id'))
                .order_by('-count')[:15]
            )
            
            # Age distribution (if birth_date available)
            age_groups = []
            if hasattr(GupShupUser, 'birth_date'):
                today = timezone.now().date()
                age_groups = list(
                    GupShupUser.objects.exclude(birth_date__isnull=True)
                    .extra({
                        'age_group': """
                        CASE 
                            WHEN TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) < 18 THEN 'Under 18'
                            WHEN TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) BETWEEN 18 AND 24 THEN '18-24'
                            WHEN TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) BETWEEN 25 AND 34 THEN '25-34'
                            WHEN TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) BETWEEN 35 AND 44 THEN '35-44'
                            WHEN TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) BETWEEN 45 AND 54 THEN '45-54'
                            ELSE '55+'
                        END
                        """
                    })
                    .values('age_group')
                    .annotate(count=Count('id'))
                    .order_by('age_group')
                )
            
            # Verification status
            verification_stats = {
                'verified': GupShupUser.objects.filter(is_verified=True).count(),
                'unverified': GupShupUser.objects.filter(is_verified=False).count(),
                'verification_rate': 0
            }
            
            total_users = verification_stats['verified'] + verification_stats['unverified']
            if total_users > 0:
                verification_stats['verification_rate'] = (
                    verification_stats['verified'] / total_users
                ) * 100
            
            # Account status
            account_status = {
                'active': GupShupUser.objects.filter(is_active=True).count(),
                'inactive': GupShupUser.objects.filter(is_active=False).count(),
                'banned': BannedUser.objects.filter(is_active=True).count()
            }
            
            return {
                'state_distribution': state_distribution,
                'city_distribution': city_distribution,
                'age_groups': age_groups,
                'verification_stats': verification_stats,
                'account_status': account_status,
                'total_users': GupShupUser.objects.count()
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def get_user_activity_metrics(self, days: int = 30) -> Dict:
        """Get user activity and engagement metrics"""
        cache_key = self._generate_cache_key("user_activity", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Active users (users who posted, commented, or liked)
            active_users = GupShupUser.objects.filter(
                Q(posts__created_at__gte=start_date) |
                Q(comment_set__created_at__gte=start_date) |
                Q(likes__created_at__gte=start_date)
            ).distinct().count()
            
            # Most active users
            most_active_users = list(
                GupShupUser.objects.annotate(
                    activity_score=Count('posts', filter=Q(posts__created_at__gte=start_date)) +
                                  Count('comment_set', filter=Q(comment_set__created_at__gte=start_date)) +
                                  Count('likes', filter=Q(likes__created_at__gte=start_date))
                ).filter(activity_score__gt=0)
                .order_by('-activity_score')[:10]
                .values('username', 'first_name', 'last_name', 'activity_score')
            )
            
            # User retention (users who were active in multiple weeks)
            retention_data = self._calculate_user_retention(start_date, end_date)
            
            # Login activity
            login_activity = list(
                GupShupUser.objects.filter(last_login__gte=start_date)
                .extra({'date': 'DATE(last_login)'})
                .values('date')
                .annotate(unique_logins=Count('id'))
                .order_by('date')
            )
            
            return {
                'active_users': active_users,
                'most_active_users': most_active_users,
                'retention_data': retention_data,
                'login_activity': login_activity,
                'activity_rate': (active_users / max(GupShupUser.objects.count(), 1)) * 100
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def _calculate_user_retention(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate user retention rates"""
        # Weekly cohort analysis
        weeks = []
        current_week = start_date
        
        while current_week < end_date:
            week_end = current_week + timedelta(days=7)
            
            # New users this week
            new_users = list(
                GupShupUser.objects.filter(
                    date_joined__gte=current_week,
                    date_joined__lt=week_end
                ).values_list('id', flat=True)
            )
            
            if new_users:
                # Check retention in following weeks
                retention_rates = []
                for i in range(1, 5):  # Check 4 weeks after
                    retention_start = week_end + timedelta(weeks=i-1)
                    retention_end = retention_start + timedelta(days=7)
                    
                    if retention_end <= timezone.now():
                        retained_users = GupShupUser.objects.filter(
                            id__in=new_users,
                            last_login__gte=retention_start,
                            last_login__lt=retention_end
                        ).count()
                        
                        retention_rate = (retained_users / len(new_users)) * 100
                        retention_rates.append(retention_rate)
                
                weeks.append({
                    'week_start': current_week.strftime('%Y-%m-%d'),
                    'new_users': len(new_users),
                    'retention_rates': retention_rates
                })
            
            current_week = week_end
        
        return {'weekly_cohorts': weeks}
    
    def _calculate_trend(self, data_points: List[Union[int, float]]) -> str:
        """Calculate trend direction from data points"""
        if len(data_points) < 2:
            return 'neutral'
        
        # Simple linear trend calculation
        n = len(data_points)
        x_sum = sum(range(n))
        y_sum = sum(data_points)
        xy_sum = sum(i * data_points[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        if n * x2_sum - x_sum * x_sum == 0:
            return 'neutral'
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        if slope > 0.1:
            return 'increasing'
        elif slope < -0.1:
            return 'decreasing'
        else:
            return 'stable'


class PostAnalytics(BaseAnalytics):
    """Analytics for content engagement and post metrics"""
    
    def get_content_metrics(self, days: int = 30) -> Dict:
        """Get comprehensive content engagement metrics"""
        cache_key = self._generate_cache_key("content_metrics", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Basic content stats
            total_posts = Post.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).count()
            
            total_comments = Comment.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).count()
            
            total_likes = Like.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).count()
            
            # Daily content creation
            daily_posts = list(
                Post.objects.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date
                ).extra({'date': 'DATE(created_at)'})
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            
            # Engagement rates
            posts_with_engagement = Post.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).annotate(
                total_engagement=Count('likes') + Count('comments')
            ).filter(total_engagement__gt=0).count()
            
            engagement_rate = (posts_with_engagement / max(total_posts, 1)) * 100
            
            # Top performing posts
            top_posts = list(
                Post.objects.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date
                ).annotate(
                    engagement_score=Count('likes') + Count('comments') * 2
                ).order_by('-engagement_score')[:10]
                .values(
                    'id', 'content', 'author__username', 
                    'engagement_score', 'created_at'
                )
            )
            
            # Content type analysis
            content_types = {
                'text_only': Post.objects.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date,
                    image__isnull=True
                ).count(),
                'with_image': Post.objects.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date,
                    image__isnull=False
                ).count()
            }
            
            # Average engagement per post type
            avg_engagement = Post.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).aggregate(
                avg_likes=Avg('likes_count'),
                avg_comments=Avg('comments_count')
            )
            
            return {
                'total_posts': total_posts,
                'total_comments': total_comments,
                'total_likes': total_likes,
                'daily_posts': daily_posts,
                'engagement_rate': round(engagement_rate, 2),
                'top_posts': top_posts,
                'content_types': content_types,
                'avg_engagement': {
                    'likes': round(avg_engagement['avg_likes'] or 0, 2),
                    'comments': round(avg_engagement['avg_comments'] or 0, 2)
                },
                'posts_per_day': round(total_posts / days, 2)
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def get_hashtag_analytics(self, days: int = 30) -> Dict:
        """Analyze hashtag usage and trends"""
        cache_key = self._generate_cache_key("hashtag_analytics", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Get posts with hashtags
            posts_with_hashtags = Post.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date,
                hashtags__isnull=False
            ).exclude(hashtags='')
            
            # Extract and count hashtags
            hashtag_counts = Counter()
            hashtag_engagement = defaultdict(list)
            
            for post in posts_with_hashtags:
                if post.hashtags:
                    hashtags = [tag.strip().lower() for tag in post.hashtags.split(',')]
                    for hashtag in hashtags:
                        if hashtag:
                            hashtag_counts[hashtag] += 1
                            # Track engagement for this hashtag
                            engagement = post.likes_count + post.comments_count
                            hashtag_engagement[hashtag].append(engagement)
            
            # Calculate trending hashtags
            trending_hashtags = []
            for hashtag, count in hashtag_counts.most_common(20):
                avg_engagement = sum(hashtag_engagement[hashtag]) / len(hashtag_engagement[hashtag])
                trending_hashtags.append({
                    'hashtag': hashtag,
                    'usage_count': count,
                    'avg_engagement': round(avg_engagement, 2),
                    'trend_score': count * avg_engagement
                })
            
            # Sort by trend score
            trending_hashtags.sort(key=lambda x: x['trend_score'], reverse=True)
            
            return {
                'total_hashtags': len(hashtag_counts),
                'trending_hashtags': trending_hashtags[:15],
                'hashtag_usage_rate': (posts_with_hashtags.count() / max(
                    Post.objects.filter(
                        created_at__gte=start_date,
                        created_at__lte=end_date
                    ).count(), 1
                )) * 100
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def get_viral_content_analysis(self, days: int = 7) -> Dict:
        """Analyze viral content patterns"""
        cache_key = self._generate_cache_key("viral_content", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Define viral threshold (top 1% of posts by engagement)
            all_posts = Post.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            ).annotate(
                engagement_score=F('likes_count') + F('comments_count')
            )
            
            if not all_posts.exists():
                return {'viral_posts': [], 'viral_patterns': {}}
            
            # Calculate 95th percentile threshold for viral content
            engagement_scores = list(all_posts.values_list('engagement_score', flat=True))
            engagement_scores.sort()
            viral_threshold = engagement_scores[int(len(engagement_scores) * 0.95)] if engagement_scores else 0
            
            viral_posts = list(
                all_posts.filter(engagement_score__gte=viral_threshold)
                .order_by('-engagement_score')[:20]
                .values(
                    'id', 'content', 'author__username', 'engagement_score',
                    'likes_count', 'comments_count', 'created_at', 'hashtags'
                )
            )
            
            # Analyze viral patterns
            viral_patterns = self._analyze_viral_patterns(viral_posts)
            
            return {
                'viral_posts': viral_posts,
                'viral_patterns': viral_patterns,
                'viral_threshold': viral_threshold
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def _analyze_viral_patterns(self, viral_posts: List[Dict]) -> Dict:
        """Analyze patterns in viral content"""
        if not viral_posts:
            return {}
        
        # Time patterns
        hours = [datetime.fromisoformat(str(post['created_at'])).hour for post in viral_posts]
        peak_hours = Counter(hours).most_common(5)
        
        # Content length patterns
        content_lengths = [len(post['content']) for post in viral_posts]
        avg_length = sum(content_lengths) / len(content_lengths)
        
        # Hashtag patterns
        hashtags_used = []
        for post in viral_posts:
            if post['hashtags']:
                hashtags_used.extend([tag.strip().lower() for tag in post['hashtags'].split(',')])
        
        common_hashtags = Counter(hashtags_used).most_common(10)
        
        return {
            'peak_posting_hours': peak_hours,
            'avg_content_length': round(avg_length, 0),
            'common_hashtags_in_viral': common_hashtags,
            'avg_likes': sum(post['likes_count'] for post in viral_posts) / len(viral_posts),
            'avg_comments': sum(post['comments_count'] for post in viral_posts) / len(viral_posts)
        }


class GeographicAnalytics(BaseAnalytics):
    """Analytics for Indian state/city distribution and regional trends"""
    
    # Indian states for validation and analysis
    INDIAN_STATES = [
        'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
        'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
        'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
        'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
        'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
        'Andaman and Nicobar Islands', 'Chandigarh', 'Delhi', 'Jammu and Kashmir',
        'Ladakh', 'Lakshadweep', 'Puducherry'
    ]
    
    def get_geographic_distribution(self) -> Dict:
        """Get comprehensive geographic distribution of users"""
        cache_key = self._generate_cache_key("geographic_distribution")
        
        def calculate():
            # State-wise distribution
            state_data = list(
                GupShupUser.objects.exclude(state='')
                .values('state')
                .annotate(user_count=Count('id'))
                .order_by('-user_count')
            )
            
            # Validate and normalize state names
            normalized_states = []
            for item in state_data:
                state_name = item['state'].title()
                if state_name in self.INDIAN_STATES:
                    normalized_states.append({
                        'state': state_name,
                        'user_count': item['user_count'],
                        'percentage': 0  # Will be calculated below
                    })
            
            # Calculate percentages
            total_users_with_state = sum(item['user_count'] for item in normalized_states)
            for item in normalized_states:
                item['percentage'] = (item['user_count'] / max(total_users_with_state, 1)) * 100
            
            # Top cities
            city_data = list(
                GupShupUser.objects.exclude(city='')
                .values('city', 'state')
                .annotate(user_count=Count('id'))
                .order_by('-user_count')[:20]
            )
            
            # Metro vs non-metro classification
            metro_cities = [
                'Mumbai', 'Delhi', 'Bengaluru', 'Bangalore', 'Hyderabad', 'Chennai',
                'Kolkata', 'Pune', 'Ahmedabad', 'Surat', 'Jaipur', 'Lucknow',
                'Kanpur', 'Nagpur', 'Indore', 'Thane', 'Bhopal', 'Visakhapatnam',
                'Pimpri-Chinchwad', 'Patna', 'Vadodara', 'Ghaziabad', 'Ludhiana',
                'Agra', 'Nashik', 'Faridabad', 'Meerut', 'Rajkot', 'Kalyan-Dombivli',
                'Vasai-Virar', 'Varanasi', 'Srinagar', 'Aurangabad', 'Dhanbad',
                'Amritsar', 'Navi Mumbai', 'Allahabad', 'Ranchi', 'Howrah', 'Coimbatore'
            ]
            
            metro_users = GupShupUser.objects.filter(
                city__in=metro_cities
            ).count()
            
            non_metro_users = GupShupUser.objects.exclude(city='').exclude(
                city__in=metro_cities
            ).count()
            
            return {
                'state_distribution': normalized_states[:15],  # Top 15 states
                'city_distribution': city_data,
                'metro_vs_nonmetro': {
                    'metro': metro_users,
                    'non_metro': non_metro_users,
                    'metro_percentage': (metro_users / max(metro_users + non_metro_users, 1)) * 100
                },
                'coverage_stats': {
                    'total_states': len(normalized_states),
                    'total_cities': len(city_data),
                    'users_with_location': total_users_with_state
                }
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def get_regional_activity_patterns(self, days: int = 30) -> Dict:
        """Analyze activity patterns by region"""
        cache_key = self._generate_cache_key("regional_activity", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Activity by state
            state_activity = list(
                GupShupUser.objects.exclude(state='')
                .annotate(
                    posts_count=Count('posts', filter=Q(posts__created_at__gte=start_date)),
                    comments_count=Count('comment_set', filter=Q(comment_set__created_at__gte=start_date)),
                    likes_count=Count('likes', filter=Q(likes__created_at__gte=start_date))
                )
                .values('state')
                .annotate(
                    total_posts=Sum('posts_count'),
                    total_comments=Sum('comments_count'),
                    total_likes=Sum('likes_count'),
                    user_count=Count('id')
                )
                .filter(total_posts__gt=0)
                .order_by('-total_posts')[:10]
            )
            
            # Calculate activity rates per user by state
            for item in state_activity:
                if item['user_count'] > 0:
                    item['posts_per_user'] = round(item['total_posts'] / item['user_count'], 2)
                    item['engagement_per_user'] = round(
                        (item['total_comments'] + item['total_likes']) / item['user_count'], 2
                    )
                else:
                    item['posts_per_user'] = 0
                    item['engagement_per_user'] = 0
            
            # Most active cities
            city_activity = list(
                GupShupUser.objects.exclude(city='')
                .annotate(
                    posts_count=Count('posts', filter=Q(posts__created_at__gte=start_date))
                )
                .values('city', 'state')
                .annotate(
                    total_posts=Sum('posts_count'),
                    user_count=Count('id')
                )
                .filter(total_posts__gt=0)
                .order_by('-total_posts')[:15]
            )
            
            return {
                'state_activity': state_activity,
                'city_activity': city_activity,
                'regional_insights': self._generate_regional_insights(state_activity)
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def _generate_regional_insights(self, state_activity: List[Dict]) -> Dict:
        """Generate insights from regional activity data"""
        if not state_activity:
            return {}
        
        # Most active state
        most_active_state = state_activity[0] if state_activity else None
        
        # Highest engagement per user
        highest_engagement_state = max(
            state_activity, 
            key=lambda x: x.get('engagement_per_user', 0)
        )
        
        # Most posts per user
        highest_posting_state = max(
            state_activity,
            key=lambda x: x.get('posts_per_user', 0)
        )
        
        return {
            'most_active_state': most_active_state,
            'highest_engagement_state': highest_engagement_state,
            'highest_posting_state': highest_posting_state,
            'total_active_states': len(state_activity)
        }


class EngagementMetrics(BaseAnalytics):
    """Platform-wide engagement and activity metrics"""
    
    def get_platform_engagement_summary(self, days: int = 30) -> Dict:
        """Get comprehensive platform engagement summary"""
        cache_key = self._generate_cache_key("platform_engagement", days=days)
        
        def calculate():
            start_date, end_date = self._get_date_range(days)
            
            # Basic engagement metrics
            total_interactions = (
                Post.objects.filter(created_at__gte=start_date).count() +
                Comment.objects.filter(created_at__gte=start_date).count() +
                Like.objects.filter(created_at__gte=start_date).count()
            )
            
            # Daily engagement
            daily_engagement = []
            current_date = start_date.date()
            
            while current_date <= end_date.date():
                day_posts = Post.objects.filter(created_at__date=current_date).count()
                day_comments = Comment.objects.filter(created_at__date=current_date).count()
                day_likes = Like.objects.filter(created_at__date=current_date).count()
                
                daily_engagement.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'posts': day_posts,
                    'comments': day_comments,
                    'likes': day_likes,
                    'total_interactions': day_posts + day_comments + day_likes
                })
                
                current_date += timedelta(days=1)
            
            # Engagement rates
            active_users = GupShupUser.objects.filter(
                Q(posts__created_at__gte=start_date) |
                Q(comment_set__created_at__gte=start_date) |
                Q(likes__created_at__gte=start_date)
            ).distinct().count()
            
            total_users = GupShupUser.objects.count()
            
            # Peak activity hours
            peak_hours = self._calculate_peak_activity_hours(start_date, end_date)
            
            # Engagement quality metrics
            quality_metrics = self._calculate_engagement_quality(start_date, end_date)
            
            return {
                'total_interactions': total_interactions,
                'daily_engagement': daily_engagement,
                'active_users': active_users,
                'user_engagement_rate': (active_users / max(total_users, 1)) * 100,
                'interactions_per_active_user': total_interactions / max(active_users, 1),
                'peak_activity_hours': peak_hours,
                'quality_metrics': quality_metrics,
                'avg_daily_interactions': total_interactions / days
            }
        
        return self._get_cached_or_calculate(cache_key, calculate)
    
    def _calculate_peak_activity_hours(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Calculate peak activity hours"""
        hourly_activity = defaultdict(int)
        
        # Posts by hour
        posts_by_hour = Post.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).extra({'hour': 'EXTRACT(hour FROM created_at)'}).values('hour').annotate(count=Count('id'))
        
        for item in posts_by_hour:
            hourly_activity[item['hour']] += item['count']
        
        # Comments by hour
        comments_by_hour = Comment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).extra({'hour': 'EXTRACT(hour FROM created_at)'}).values('hour').annotate(count=Count('id'))
        
        for item in comments_by_hour:
            hourly_activity[item['hour']] += item['count']
        
        # Convert to sorted list
        peak_hours = [
            {'hour': hour, 'activity_count': count, 'time_label': f"{hour:02d}:00"}
            for hour, count in sorted(hourly_activity.items())
        ]
        
        return sorted(peak_hours, key=lambda x: x['activity_count'], reverse=True)[:5]
    
    def _calculate_engagement_quality(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate engagement quality metrics"""
        # Posts with meaningful engagement (comments)
        posts_with_comments = Post.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            comments_count__gt=0
        ).count()
        
        total_posts = Post.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        # Average comment length (indicator of quality)
        avg_comment_length = Comment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).aggregate(avg_length=Avg(models.functions.Length('text')))['avg_length'] or 0
        
        # Repeat engagement rate (users who engage multiple times)
        repeat_engagers = GupShupUser.objects.annotate(
            engagement_count=Count('comment_set', filter=Q(comment_set__created_at__gte=start_date)) +
                           Count('likes', filter=Q(likes__created_at__gte=start_date))
        ).filter(engagement_count__gt=1).count()
        
        total_engagers = GupShupUser.objects.filter(
            Q(comment_set__created_at__gte=start_date) |
            Q(likes__created_at__gte=start_date)
        ).distinct().count()
        
        return {
            'comment_rate': (posts_with_comments / max(total_posts, 1)) * 100,
            'avg_comment_length': round(avg_comment_length, 1),
            'repeat_engagement_rate': (repeat_engagers / max(total_engagers, 1)) * 100,
            'quality_score': self._calculate_quality_score(
                posts_with_comments / max(total_posts, 1),
                avg_comment_length,
                repeat_engagers / max(total_engagers, 1)
            )
        }
    
    def _calculate_quality_score(self, comment_rate: float, avg_length: float, repeat_rate: float) -> float:
        """Calculate overall engagement quality score"""
        # Weighted average of quality indicators (0-100 scale)
        normalized_length = min(avg_length / 100, 1.0)  # Normalize to 0-1
        
        quality_score = (
            comment_rate * 0.4 +          # 40% weight on comment rate
            normalized_length * 0.3 +      # 30% weight on comment length
            repeat_rate * 0.3              # 30% weight on repeat engagement
        ) * 100
        
        return round(quality_score, 2)


class ReportGenerator(BaseAnalytics):
    """Generate various types of reports and exports"""
    
    def __init__(self, cache_timeout: int = 300):
        super().__init__(cache_timeout)
        self.user_analytics = UserAnalytics(cache_timeout)
        self.post_analytics = PostAnalytics(cache_timeout)
        self.geo_analytics = GeographicAnalytics(cache_timeout)
        self.engagement_metrics = EngagementMetrics(cache_timeout)
    
    def generate_comprehensive_report(self, days: int = 30) -> Dict:
        """Generate comprehensive platform report"""
        return {
            'report_meta': {
                'generated_at': timezone.now().isoformat(),
                'period_days': days,
                'start_date': (timezone.now() - timedelta(days=days)).isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'user_analytics': self.user_analytics.get_user_growth_data(days),
            'content_metrics': self.post_analytics.get_content_metrics(days),
            'engagement_metrics': self.engagement_metrics.get_platform_engagement_summary(days),
            'geographic_data': self.geo_analytics.get_geographic_distribution(),
            'hashtag_trends': self.post_analytics.get_hashtag_analytics(days),
            'viral_content': self.post_analytics.get_viral_content_analysis(min(days, 7))
        }
    
    def export_to_csv(self, data: Dict, filename: str = None) -> HttpResponse:
        """Export analytics data to CSV format"""
        if not filename:
            filename = f"gupshup_analytics_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(['Metric', 'Value', 'Category'])
        
        # Flatten data for CSV export
        self._flatten_dict_to_csv(data, writer)
        
        return response
    
    def export_to_json(self, data: Dict, filename: str = None) -> HttpResponse:
        """Export analytics data to JSON format"""
        if not filename:
            filename = f"gupshup_analytics_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def _flatten_dict_to_csv(self, data: Dict, writer, prefix: str = ''):
        """Recursively flatten dictionary for CSV export"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                self._flatten_dict_to_csv(value, writer, full_key)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._flatten_dict_to_csv(item, writer, f"{full_key}[{i}]")
                    else:
                        writer.writerow([f"{full_key}[{i}]", str(item), prefix.split('.')[0] if prefix else 'general'])
            else:
                writer.writerow([full_key, str(value), prefix.split('.')[0] if prefix else 'general'])


# Convenience function to get all analytics in one call
def get_dashboard_analytics(days: int = 30) -> Dict:
    """Get all analytics data needed for dashboard"""
    report_gen = ReportGenerator()
    return report_gen.generate_comprehensive_report(days)