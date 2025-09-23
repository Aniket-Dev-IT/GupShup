from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from posts.models import Post, PostMedia
from social.models import Like, Comment, Follow
from datetime import datetime, timedelta
import random
from faker import Faker

User = get_user_model()
fake = Faker(['en_IN'])  # Indian locale for realistic data

class Command(BaseCommand):
    help = 'Populate database with realistic sample data for GupShup platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=25,
            help='Number of users to create'
        )
        parser.add_argument(
            '--posts',
            type=int,
            default=60,
            help='Number of posts to create'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting GupShup sample data population...')
        )
        
        with transaction.atomic():
            # Create users first
            users = self.create_sample_users(options['users'])
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created {len(users)} sample users')
            )
            
            # Create posts
            posts = self.create_sample_posts(users, options['posts'])
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created {len(posts)} sample posts')
            )
            
            # Create social interactions
            self.create_social_interactions(users, posts)
            self.stdout.write(
                self.style.SUCCESS('✅ Created social interactions (likes, follows, comments)')
            )
            
            # Update user statistics
            self.update_user_statistics(users)
            self.stdout.write(
                self.style.SUCCESS('✅ Updated user statistics')
            )

        self.stdout.write(
            self.style.SUCCESS('🎉 Sample data population completed successfully!')
        )

    def create_sample_users(self, count):
        """Create realistic Indian users"""
        
        # Indian names and usernames
        indian_names = [
            ('Aarav', 'Sharma'), ('Vivaan', 'Gupta'), ('Aditya', 'Singh'),
            ('Vihaan', 'Kumar'), ('Arjun', 'Verma'), ('Sai', 'Patel'),
            ('Reyansh', 'Shah'), ('Ayaan', 'Agarwal'), ('Krishna', 'Joshi'),
            ('Ishaan', 'Mehta'), ('Shaurya', 'Yadav'), ('Atharv', 'Mishra'),
            ('Aadhya', 'Sharma'), ('Anaya', 'Gupta'), ('Diya', 'Singh'),
            ('Pihu', 'Kumar'), ('Prisha', 'Verma'), ('Anvi', 'Patel'),
            ('Kavya', 'Shah'), ('Myra', 'Agarwal'), ('Sara', 'Joshi'),
            ('Pari', 'Mehta'), ('Avni', 'Yadav'), ('Riya', 'Mishra')
        ]
        
        indian_cities = [
            ('Mumbai', 'MH'), ('Delhi', 'DL'), ('Bangalore', 'KA'),
            ('Chennai', 'TN'), ('Kolkata', 'WB'), ('Hyderabad', 'TS'),
            ('Pune', 'MH'), ('Ahmedabad', 'GJ'), ('Jaipur', 'RJ'),
            ('Lucknow', 'UP'), ('Kanpur', 'UP'), ('Nagpur', 'MH'),
            ('Indore', 'MP'), ('Bhopal', 'MP'), ('Visakhapatnam', 'AP'),
            ('Patna', 'BR'), ('Vadodara', 'GJ'), ('Ghaziabad', 'UP')
        ]
        
        users = []
        
        for i in range(min(count, len(indian_names))):
            first_name, last_name = indian_names[i]
            city, state = random.choice(indian_cities)
            
            username = f"{first_name.lower()}.{last_name.lower()}{random.randint(10, 99)}"
            email = f"{username}@example.com"
            
            # Create user with random join date (last 6 months)
            join_date = fake.date_time_between(
                start_date='-6M',
                end_date='now',
                tzinfo=timezone.get_current_timezone()
            )
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                city=city,
                state=state,
                bio=fake.text(max_nb_chars=200),
                is_verified=random.choice([True, False, False, False]),  # 25% verified
                preferred_language=random.choice(['en', 'hi']),
                date_joined=join_date,
                last_login=fake.date_time_between(
                    start_date=join_date,
                    end_date='now',
                    tzinfo=timezone.get_current_timezone()
                )
            )
            
            users.append(user)
        
        return users

    def create_sample_posts(self, users, count):
        """Create engaging sample posts"""
        
        # Sample post content in Hindi and English
        post_templates = [
            "Just had an amazing cup of chai! ☕ Nothing beats the morning ritual #ChaiLover #MorningVibes",
            "हाल ही में एक शानदार फिल्म देखी! 🎬 Bollywood की कहानियां दिल छू जाती हैं #Bollywood #Cinema",
            "Cricket season is here! Who's excited for the upcoming matches? 🏏 #Cricket #India #Sports",
            "Weekend plans: exploring local street food! 🍛 Mumbai's vada pav is unbeatable #StreetFood #Mumbai",
            "Working on some exciting new projects. Technology is changing everything! 💻 #TechLife #Innovation",
            "Beautiful sunset today in Delhi! 🌅 Nature always inspires me #Delhi #Sunset #Photography",
            "Reading a fantastic book about Indian history. So much to learn! 📚 #Reading #History #India",
            "Celebrating Diwali with family and friends! ✨ Wishing everyone happiness and prosperity #Diwali #Festival",
            "Just finished a great workout session! 💪 Staying fit and healthy #Fitness #Health #Motivation",
            "Amazing classical music concert last night! 🎵 Indian classical music touches the soul #Music #Classical"
        ]
        
        hashtag_groups = [
            ['#India', '#Culture', '#Heritage'],
            ['#Technology', '#Innovation', '#StartUp'],
            ['#Food', '#Cooking', '#Recipes'],
            ['#Travel', '#Adventure', '#Explore'],
            ['#Fitness', '#Health', '#Wellness'],
            ['#Education', '#Learning', '#Knowledge'],
            ['#Art', '#Creativity', '#Design'],
            ['#Music', '#Dance', '#Entertainment'],
            ['#Sports', '#Cricket', '#Football'],
            ['#Nature', '#Environment', '#Conservation']
        ]
        
        posts = []
        
        for i in range(count):
            author = random.choice(users)
            
            # Create post with random timestamp (last 3 months)
            post_date = fake.date_time_between(
                start_date='-3M',
                end_date='now',
                tzinfo=timezone.get_current_timezone()
            )
            
            # Choose content
            if i < len(post_templates):
                content = post_templates[i]
            else:
                content = fake.text(max_nb_chars=200) + " " + " ".join(random.choice(hashtag_groups))
            
            post = Post.objects.create(
                author=author,
                content=content,
                privacy=random.choice(['public', 'public', 'public', 'friends']),  # Mostly public
                location=f"{author.city}, {author.state}" if author.city else '',
                created_at=post_date,
                updated_at=post_date
            )
            
            posts.append(post)
        
        return posts

    def create_social_interactions(self, users, posts):
        """Create likes, comments, and follows"""
        
        # Create follow relationships
        for user in users[:15]:  # First 15 users follow others
            # Each user follows 3-8 other users
            followers_count = random.randint(3, 8)
            potential_follows = [u for u in users if u != user]
            follows = random.sample(potential_follows, min(followers_count, len(potential_follows)))
            
            for followed_user in follows:
                Follow.objects.get_or_create(
                    follower=user,
                    following=followed_user
                )
        
        # Create likes on posts
        for post in posts:
            # Each post gets 5-25 likes
            likes_count = random.randint(5, 25)
            potential_likers = [u for u in users if u != post.author]
            likers = random.sample(potential_likers, min(likes_count, len(potential_likers)))
            
            for liker in likers:
                Like.objects.get_or_create(
                    user=liker,
                    post=post
                )
            
            # Update post likes count
            post.likes_count = len(likers)
            post.save()
        
        # Create comments
        comment_templates = [
            "Great post! 👍", "Love this! ❤️", "So inspiring!", 
            "Thanks for sharing!", "Absolutely agree!", "Well said!",
            "Amazing content!", "Keep it up! 💪", "Beautiful! 😍",
            "Totally relatable!", "Fantastic!", "So true!"
        ]
        
        for post in posts[:30]:  # First 30 posts get comments
            comments_count = random.randint(2, 8)
            potential_commenters = [u for u in users if u != post.author]
            commenters = random.sample(potential_commenters, min(comments_count, len(potential_commenters)))
            
            for commenter in commenters:
                Comment.objects.create(
                    author=commenter,
                    post=post,
                    content=random.choice(comment_templates)
                )
            
            # Update post comments count
            post.comments_count = comments_count
            post.save()

    def update_user_statistics(self, users):
        """Update user follower and post counts"""
        
        for user in users:
            # Update follower/following counts
            user.followers_count = Follow.objects.filter(following=user).count()
            user.following_count = Follow.objects.filter(follower=user).count()
            
            # Update posts count
            user.posts_count = Post.objects.filter(author=user).count()
            
            user.save()