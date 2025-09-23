"""
Django Management Command to Populate GupShup Platform with Realistic Data
This command creates users, posts, comments, likes, and follows to make the platform look like a real social media site.
"""

import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files import File
from django.utils import timezone
from accounts.models import GupShupUser
from posts.models import Post, PostMedia
from social.models import Follow, Comment, Like

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate the platform with realistic users, posts, and interactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=15,
            help='Number of users to create (default: 15)',
        )
        parser.add_argument(
            '--posts',
            type=int,
            default=25,
            help='Number of posts to create (default: 25)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting GupShup data population...'))
        
        # User profile data
        self.user_profiles = [
            {
                'username': 'aarav_sharma',
                'email': 'aarav.sharma@gmail.com',
                'first_name': 'Aarav',
                'last_name': 'Sharma',
                'bio': '🎮 Gamer | 💻 Tech Enthusiast | 🏏 Cricket Lover | Delhi, India',
                'location': 'New Delhi, India',
                'avatar_image': 'Aarav.jpeg'
            },
            {
                'username': 'ananya_gupta',
                'email': 'ananya.gupta@gmail.com',
                'first_name': 'Ananya',
                'last_name': 'Gupta',
                'bio': '📚 Student | 🎨 Art Lover | 🌸 Nature Photography | Mumbai',
                'location': 'Mumbai, Maharashtra',
                'avatar_image': 'Ananya.jpeg'
            },
            {
                'username': 'aadvik_patel',
                'email': 'aadvik.patel@gmail.com',
                'first_name': 'Aadvik',
                'last_name': 'Patel',
                'bio': '✨ Presence Changes the Room | 🎵 Music Producer | Ahmedabad',
                'location': 'Ahmedabad, Gujarat',
                'avatar_image': 'Aadvik- Presence Changes the Room.jpeg'
            },
            {
                'username': 'bhavika_singh',
                'email': 'bhavika.singh@gmail.com',
                'first_name': 'Bhavika',
                'last_name': 'Singh',
                'bio': '💃 Classical Dancer | 🌺 Cultural Enthusiast | Jaipur, Rajasthan',
                'location': 'Jaipur, Rajasthan',
                'avatar_image': 'Bhavika.jpeg'
            },
            {
                'username': 'mirha_khan',
                'email': 'mirha.khan@gmail.com',
                'first_name': 'Mirha',
                'last_name': 'Khan',
                'bio': '📱 Content Creator | 💄 Beauty Blogger | 🎬 Filmmaker | Hyderabad',
                'location': 'Hyderabad, Telangana',
                'avatar_image': 'Mirha.jpeg'
            },
            {
                'username': 'niharika_agarwal',
                'email': 'niharika.agarwal@gmail.com',
                'first_name': 'Niharika',
                'last_name': 'Agarwal',
                'bio': '🎯 Marketing Professional | 📊 Data Analyst | Bangalore Tech Hub',
                'location': 'Bangalore, Karnataka',
                'avatar_image': 'Niharika.jpeg'
            },
            {
                'username': 'yugansh_verma',
                'email': 'yugansh.verma@gmail.com',
                'first_name': 'Yugansh',
                'last_name': 'Verma',
                'bio': '🚀 Startup Founder | 💡 Innovation | 🌐 Tech for Good | Pune',
                'location': 'Pune, Maharashtra',
                'avatar_image': 'Yugansh.jpeg'
            },
            {
                'username': 'himanshu_gautam',
                'email': 'himanshu.gautam@gmail.com',
                'first_name': 'Himanshu',
                'last_name': 'Gautam',
                'bio': '🕉️ Spiritual Seeker | 📷 Documentary Photographer | Varanasi',
                'location': 'Varanasi, Uttar Pradesh',
                'avatar_image': 'Kumbh _ Mahakumbh _ Himanshu gautam.jpeg'
            },
            {
                'username': 'priya_travel',
                'email': 'priya.travel@gmail.com',
                'first_name': 'Priya',
                'last_name': 'Wanderlust',
                'bio': '✈️ Travel Enthusiast | 🗺️ Explorer | 📝 Travel Blogger | Goa',
                'location': 'Goa, India',
                'avatar_image': 'Are you an enthusiastic traveler who loves to explore new places_ But hate planning your trip because you always end up struggling_ Let me tell you about WayAway, a flight aggregator that provides travelers with t.jpeg'
            },
            {
                'username': 'arjun_foodie',
                'email': 'arjun.foodie@gmail.com',
                'first_name': 'Arjun',
                'last_name': 'Foodie',
                'bio': '🍛 Food Blogger | 👨‍🍳 Street Food Expert | 🌶️ Spice Lover | Chennai',
                'location': 'Chennai, Tamil Nadu',
                'avatar_image': 'amazing_indian_street_food_tour_thumbnail.jpeg'
            }
        ]

        # Post content data
        self.post_contents = [
            {
                'content': 'Just discovered this amazing street food place! The flavors are incredible 😍 #StreetFood #FoodLover #IndianFood',
                'image': 'amazing_indian_street_food_tour_thumbnail.jpeg'
            },
            {
                'content': 'Beautiful morning with nature! 🌅 There\'s something magical about early morning walks. The chirping birds make it even more special.',
                'image': 'Birds Chirping.jpeg'
            },
            {
                'content': 'Love is in the air! ❤️ Celebrating another beautiful day with my favorite person. #Love #Happiness #Blessed',
                'image': 'Love.jpeg'
            },
            {
                'content': 'College memories never fade! 🎓 Looking back at all the fun times and friendships that made college life amazing.',
                'image': 'College Pass.jpeg'
            },
            {
                'content': 'Friends and family are everything! 👨‍👩‍👧‍👦 Spending quality time with loved ones is the best therapy. #Family #Friends #Love',
                'image': 'friends, family.jpeg'
            },
            {
                'content': 'Attended an amazing seminar today! 📚 Learning never stops, and today was full of new insights and networking opportunities.',
                'image': 'Seminar.jpeg'
            },
            {
                'content': 'Traditional Indian art is so mesmerizing! 🎨 Every brushstroke tells a story of our rich cultural heritage.',
                'image': 'art_indian_painting_tutorial_thumbnail.jpeg'
            },
            {
                'content': 'Classical dance performance was absolutely stunning! 💃 The grace, the expressions, the storytelling through dance - pure magic!',
                'image': 'classical_dance_performance_thumbnail.jpeg'
            },
            {
                'content': 'Cricket highlights from yesterday\'s match! 🏏 What an incredible game! The last over was nail-biting.',
                'image': 'cricket_highlights_2024_thumbnail.jpeg'
            },
            {
                'content': 'Cooked traditional biryani today! 🍚 The aroma filling the house brings back childhood memories. Recipe passed down from grandma!',
                'image': 'cooking_traditional_biryani_thumbnail.jpeg'
            },
            {
                'content': 'Festival celebrations bringing communities together! 🎊 Unity in diversity - that\'s the beauty of India!',
                'image': 'culture_festival_celebrations_thumbnail.jpeg'
            },
            {
                'content': 'Working on some new Django projects! 💻 Loving how powerful this framework is for rapid development.',
                'image': 'introduction_to_django_thumbnail.jpeg'
            },
            {
                'content': 'Traditional fashion never goes out of style! 👗 Celebrating our beautiful heritage through clothing.',
                'image': 'fashion_traditional_wear_thumbnail.jpeg'
            },
            {
                'content': 'Morning yoga session complete! 🧘‍♀️ Starting the day with mindfulness and stretching. Feeling energized!',
                'image': 'fitness_yoga_for_beginners_thumbnail.jpeg'
            },
            {
                'content': 'Gaming session with friends was epic! 🎮 Tried some of the latest mobile games. Technology has come so far!',
                'image': 'gaming_popular_mobile_games_thumbnail.jpeg'
            },
            {
                'content': 'Learning about Ayurvedic medicine! 🌿 Ancient wisdom meets modern wellness. Our ancestors knew so much about natural healing.',
                'image': 'health_ayurvedic_medicine_thumbnail.jpeg'
            },
            {
                'content': 'Exploring ancient Indian civilization! 🏛️ The rich history and architectural marvels continue to amaze me.',
                'image': 'history_ancient_indian_civilization_thumbnail.jpeg'
            },
            {
                'content': 'Beautiful monsoon evening! 🌧️ The sound of rain and the fresh smell of earth - nothing beats this feeling.',
                'image': 'monsoon_rain_footage_placeholder_thumbnail.jpeg'
            },
            {
                'content': 'Folk music collection growing! 🎵 There\'s something so soulful about traditional melodies that touch the heart.',
                'image': 'music_folk_songs_collection_thumbnail.jpeg'
            },
            {
                'content': 'Tech review time! 📱 Checking out the latest smartphone features. The camera quality is absolutely stunning!',
                'image': 'tech_review_latest_smartphone_thumbnail.jpeg'
            }
        ]

        # Create superuser/admin
        self.create_admin_user()
        
        # Create regular users
        self.create_users(options['users'])
        
        # Create posts
        self.create_posts(options['posts'])
        
        # Create interactions
        self.create_interactions()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Successfully populated GupShup with realistic data!')
        )
        self.stdout.write(
            self.style.SUCCESS(f'📊 Created: {User.objects.count()} users, {Post.objects.count()} posts')
        )

    def create_admin_user(self):
        """Create admin/superuser and save credentials"""
        admin_username = 'admin'
        admin_email = 'admin@gupshup.com'
        admin_password = 'GupShup@2024'
        
        if not User.objects.filter(username=admin_username).exists():
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                first_name='Admin',
                last_name='GupShup',
                bio='🛠️ GupShup Platform Administrator | Managing the community',
                city='India',
                is_active=True,
                date_joined=timezone.now() - timedelta(days=30)
            )
            
            # Save admin credentials to file
            credentials_file = 'admin_credentials.txt'
            with open(credentials_file, 'w', encoding='utf-8') as f:
                f.write('GupShup Admin Credentials\n')
                f.write('========================\n\n')
                f.write(f'Username: {admin_username}\n')
                f.write(f'Password: {admin_password}\n')
                f.write(f'Email: {admin_email}\n\n')
                f.write('Access: http://localhost:8000/admin/\n')
                f.write('Login: http://localhost:8000/login/\n\n')
                f.write('Created: ' + str(timezone.now()) + '\n')
            
            self.stdout.write(
                self.style.SUCCESS(f'👑 Admin user created! Credentials saved to {credentials_file}')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️ Admin user already exists')
            )

    def create_users(self, num_users):
        """Create regular users with realistic profiles"""
        created_users = 0
        
        for i, profile in enumerate(self.user_profiles[:num_users]):
            if User.objects.filter(username=profile['username']).exists():
                continue
                
            # Parse location
            location_parts = profile['location'].split(', ')
            city = location_parts[0] if location_parts else ''
            
            # Create user
            user = User.objects.create_user(
                username=profile['username'],
                email=profile['email'],
                password='password123',  # Simple password for demo
                first_name=profile['first_name'],
                last_name=profile['last_name'],
                bio=profile['bio'],
                city=city,
                is_active=True,
                date_joined=timezone.now() - timedelta(days=random.randint(1, 90))
            )
            
            # Set avatar if exists
            image_path = os.path.join('static', profile['avatar_image'])
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    user.avatar.save(
                        profile['avatar_image'],
                        File(f),
                        save=True
                    )
            
            created_users += 1
            self.stdout.write(f'👤 Created user: {user.username}')
        
        # Save user credentials
        self.save_user_credentials()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Created {created_users} users')
        )

    def save_user_credentials(self):
        """Save all user login credentials to file"""
        credentials_file = 'user_credentials.txt'
        with open(credentials_file, 'w', encoding='utf-8') as f:
            f.write('GupShup User Login Credentials\n')
            f.write('==============================\n\n')
            
            for profile in self.user_profiles:
                if User.objects.filter(username=profile['username']).exists():
                    f.write(f"Username: {profile['username']}\n")
                    f.write(f"Password: password123\n")
                    f.write(f"Email: {profile['email']}\n")
                    f.write(f"Name: {profile['first_name']} {profile['last_name']}\n")
                    f.write('-' * 40 + '\n')
            
            f.write(f'\nAll users have the password: password123\n')
            f.write(f'Login at: http://localhost:8000/login/\n')
            f.write(f'Created: {timezone.now()}\n')

    def create_posts(self, num_posts):
        """Create posts with images and realistic content"""
        users = list(User.objects.all())
        if not users:
            self.stdout.write(self.style.ERROR('❌ No users found to create posts'))
            return
        
        created_posts = 0
        post_contents = self.post_contents[:num_posts]
        
        for i, post_data in enumerate(post_contents):
            # Random user creates the post
            author = random.choice(users)
            
            # Create post
            post = Post.objects.create(
                author=author,
                content=post_data['content'],
                created_at=timezone.now() - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
            )
            
            # Add image if exists
            image_path = os.path.join('static', post_data['image'])
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    post_media = PostMedia.objects.create(
                        post=post,
                        media_type='image',
                        order=0
                    )
                    post_media.file.save(
                        post_data['image'],
                        File(f),
                        save=True
                    )
            
            created_posts += 1
            self.stdout.write(f'📝 Created post by {author.username}')
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Created {created_posts} posts')
        )

    def create_interactions(self):
        """Create likes, comments, and follows to make platform feel alive"""
        users = list(User.objects.all())
        posts = list(Post.objects.all())
        
        if not users or not posts:
            return
        
        # Create comments
        comment_texts = [
            "Amazing post! 😍",
            "Love this! ❤️",
            "So beautiful!",
            "Great content 👏",
            "This made my day!",
            "Incredible! 🔥",
            "Thanks for sharing!",
            "Wow! Simply awesome",
            "Keep it up! 💪",
            "Beautiful capture 📸",
            "So inspiring!",
            "This is perfect!",
            "Amazing work 🎉",
            "Love the vibes!",
            "Fantastic! 🌟"
        ]
        
        comments_created = 0
        for post in posts:
            # Random number of comments per post
            num_comments = random.randint(0, 5)
            
            for _ in range(num_comments):
                commenter = random.choice([u for u in users if u != post.author])
                Comment.objects.create(
                    post=post,
                    author=commenter,
                    content=random.choice(comment_texts),
                    created_at=post.created_at + timedelta(
                        hours=random.randint(1, 48),
                        minutes=random.randint(0, 59)
                    )
                )
                comments_created += 1
        
        # Create likes
        likes_created = 0
        for post in posts:
            # Random number of likes per post
            num_likes = random.randint(1, min(8, len(users)))
            likers = random.sample([u for u in users if u != post.author], num_likes)
            
            for user in likers:
                Like.objects.get_or_create(
                    user=user,
                    post=post
                )
                likes_created += 1
        
        # Create follows
        follows_created = 0
        for user in users:
            # Each user follows 2-5 random other users
            num_follows = random.randint(2, min(5, len(users) - 1))
            followees = random.sample([u for u in users if u != user], num_follows)
            
            for followee in followees:
                Follow.objects.get_or_create(
                    follower=user,
                    following=followee
                )
                follows_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'💬 Created {comments_created} comments')
        )
        self.stdout.write(
            self.style.SUCCESS(f'👍 Created {likes_created} likes')
        )
        self.stdout.write(
            self.style.SUCCESS(f'👥 Created {follows_created} follows')
        )