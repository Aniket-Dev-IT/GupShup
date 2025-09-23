"""
URL Configuration for Pages App (Static Pages)
"""
from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    # Homepage
    path('', views.home_view, name='home'),
    
    # Main pages
    path('features/', views.features_view, name='features'),
    path('community/', views.community_view, name='community'),
    
    # Support pages
    path('help/', views.help_center_view, name='help_center'),
    path('contact/', views.contact_us_view, name='contact'),
    path('community-guidelines/', views.community_guidelines_view, name='community_guidelines'),
    
    # Legal pages
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service_view, name='terms_of_service'),
    path('cookie-policy/', views.cookie_policy_view, name='cookie_policy'),
    path('data-protection/', views.data_protection_view, name='data_protection'),
]
