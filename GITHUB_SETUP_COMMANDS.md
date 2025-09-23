# GitHub Repository Setup Commands

## Automated Repository Configuration

Use the GitHub CLI to set up repository metadata:

```bash
# Install GitHub CLI first: https://cli.github.com/

# Set repository description
gh repo edit Aniket-Dev-IT/GupShup --description "GupShup - Professional Global Social Media Platform | Django-based social network with multilingual support (Hindi/English), cultural diversity features, real-time messaging, and comprehensive admin panel designed for users worldwide"

# Add topics/tags to repository
gh repo edit Aniket-Dev-IT/GupShup --add-topic django
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-media
gh repo edit Aniket-Dev-IT/GupShup --add-topic global-social-network
gh repo edit Aniket-Dev-IT/GupShup --add-topic multilingual-support
gh repo edit Aniket-Dev-IT/GupShup --add-topic bilingual-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic python
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-networking
gh repo edit Aniket-Dev-IT/GupShup --add-topic cultural-diversity
gh repo edit Aniket-Dev-IT/GupShup --add-topic real-time-messaging
gh repo edit Aniket-Dev-IT/GupShup --add-topic admin-panel
gh repo edit Aniket-Dev-IT/GupShup --add-topic bootstrap
gh repo edit Aniket-Dev-IT/GupShup --add-topic cultural-inclusivity
gh repo edit Aniket-Dev-IT/GupShup --add-topic community-platform
gh repo edit Aniket-Dev-IT/GupShup --add-topic global-community
gh repo edit Aniket-Dev-IT/GupShup --add-topic social-connections
gh repo edit Aniket-Dev-IT/GupShup --add-topic django-web-app
gh repo edit Aniket-Dev-IT/GupShup --add-topic responsive-design
gh repo edit Aniket-Dev-IT/GupShup --add-topic user-profiles
gh repo edit Aniket-Dev-IT/GupShup --add-topic content-sharing
gh repo edit Aniket-Dev-IT/GupShup --add-topic international
gh repo edit Aniket-Dev-IT/GupShup --add-topic worldwide-platform

# Set homepage URL (if you have a live deployment)
gh repo edit Aniket-Dev-IT/GupShup --homepage "https://your-deployment-url.com"
```

## Manual Setup (GitHub Web Interface)

1. **Go to your repository**: https://github.com/Aniket-Dev-IT/GupShup
2. **Click the gear ⚙️ icon** next to "About" section
3. **Add Description**:
   ```
   GupShup - Professional Global Social Media Platform | Django-based social network with multilingual support (Hindi/English), cultural diversity features, real-time messaging, and comprehensive admin panel designed for users worldwide
   ```
4. **Add Topics** (copy and paste these, separated by commas):
   ```
   django, social-media, global-social-network, multilingual-support, bilingual-platform, social-platform, python, social-networking, cultural-diversity, real-time-messaging, admin-panel, bootstrap, cultural-inclusivity, community-platform, global-community, social-connections, django-web-app, responsive-design, user-profiles, content-sharing, international, worldwide-platform
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