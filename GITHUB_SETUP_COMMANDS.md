# GitHub Repository Setup Commands

## Automated Repository Configuration

Use the GitHub CLI to set up repository metadata:

```bash
# Install GitHub CLI first: https://cli.github.com/

# Set repository description
gh repo edit Aniket-Dev-IT/GupShup --description "GupShup - Professional Indian Social Media Platform | Django-based social network with Hindi/English bilingual support, cultural authentication, real-time messaging, and comprehensive admin panel designed specifically for Indian community worldwide"

# Add topics/tags to repository
gh repo edit Aniket-Dev-IT/GupShup --add-topic django
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-media
gh repo edit Aniket-Dev-IT/GupShup --add-topic indian-social-network
gh repo edit Aniket-Dev-IT/GupShup --add-topic hindi-support
gh repo edit Aniket-Dev-IT/GupShup --add-topic bilingual-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic python
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-networking
gh repo edit Aniket-Dev-IT/GupShup --add-topic indian-culture
gh repo edit Aniket-Dev-IT/GupShup --add-topic real-time-messaging
gh repo edit Aniket-Dev-IT/GupShup --add-topic admin-panel
gh repo edit Aniket-Dev-IT/GupShup --add-topic bootstrap
gh repo edit Aniket-Dev-IT/GupShup --add-topic cultural-authenticity
gh repo edit Aniket-Dev-IT/GupShup --add-topic community-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic indian-community
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-connections
gh repo edit Aniket-Dev-IT/GupShup --add-topic django-web-app
gh repo edit Aniket-Dev-IT/GupShup --add-topic responsive-design
gh repo edit Aniket-Dev-IT/GupShup --add-topic user-profiles
gh repo edit Aniket-Dev-IT/GupShup --add-topic content-sharing

# Set homepage URL (if you have a live deployment)
gh repo edit Aniket-Dev-IT/GupShup --homepage "https://your-deployment-url.com"
```

## Manual Setup (GitHub Web Interface)

1. **Go to your repository**: https://github.com/Aniket-Dev-IT/GupShup
2. **Click the gear ⚙️ icon** next to "About" section
3. **Add Description**:
   ```
   GupShup - Professional Indian Social Media Platform | Django-based social network with Hindi/English bilingual support, cultural authentication, real-time messaging, and comprehensive admin panel designed specifically for Indian community worldwide
   ```
4. **Add Topics** (copy and paste these, separated by commas):
   ```
   django, social-media, indian-social-network, hindi-support, bilingual-platform, social-platform, python, social-networking, indian-culture, real-time-messaging, admin-panel, bootstrap, cultural-authenticity, community-platform, indian-community, social-connections, django-web-app, responsive-design, user-profiles, content-sharing
   ```
5. **Website**: Add your live deployment URL when available

## Repository Settings Optimization

### Enable Discussions
```bash
gh repo edit Aniket-Dev-IT/GupShup --enable-discussions
```

### Enable Issues (if not already enabled)
```bash
gh repo edit Aniket-Dev-IT/GupShup --enable-issues
```

### Set Repository Visibility (if needed)
```bash
gh repo edit Aniket-Dev-IT/GupShup --visibility public
```

This will make your repository much more discoverable and professional!