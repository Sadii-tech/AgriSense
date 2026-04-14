from django.urls import path
from . import views
from agrisense.views import CustomPasswordResetConfirmView, CustomPasswordResetView
from django.contrib.auth import views as auth_views
urlpatterns = [
    # Auth URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
     path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),  # ✅ Use this one only
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),

   path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(  
    template_name='registration/password_reset_confirm.html',
), name='password_reset_confirm'),
    
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    # Main URLs
    path('', views.dashboard_view, name='dashboard'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('diagnosis/<int:scan_id>/', views.diagnosis_view, name='diagnosis'),
    path('history/', views.history_view, name='history'),
    path('About/', views.about_view, name='about'),
    path('Setting/', views.settings_view, name='setting'),
    path('api/mark-notifications-read/', views.mark_notifications_read_api, name='mark_notifications_read'),
    
    # API URLs
    path('api/analyze-plant/', views.analyze_plant_api, name='analyze_plant'),
    path('api/dashboard-stats/', views.dashboard_stats_api, name='dashboard_stats'),
    path('api/history/recent/', views.recent_history_api, name='recent_history_api'),
    path('api/test-clip/', views.test_clip_api, name='test_clip'),  # Optional test endpoint
]