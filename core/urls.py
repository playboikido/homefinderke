from django.urls import path, include
from django.contrib import admin
from . import views
from django.conf import settings
from django.conf.urls.static import static
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from django.views.generic import TemplateView
urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('search/', views.search, name='search'),
    path('residences/', views.residence_list, name='residence_list'),
   path(
        'residences/<int:pk>/',
        views.residence_detail,
        name='residence_detail'
    ),
    path('control-panel-2947/vendors/', views.vendor_dashboard, name='vendor_dashboard'),
    path('residence/<int:pk>/edit/', views.edit_residence, name='edit_residence'),
    path(
        'add-residence/',
        views.add_residence,
        name='add_residence'
    ),
    path('suspended-users/', views.suspended_users, name='suspended_users'),
    path('unsuspend-user/<int:user_id>/', views.unsuspend_user, name='unsuspend_user'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path(
        'admin-dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),
    path(
        'approve-residence/<int:pk>/',
        views.approve_residence,
        name='approve_residence'
    ),
    path(
        'reject-residence/<int:pk>/',
        views.reject_residence,
        name='reject_residence'
        ),


    path(
        'report-residence/<int:pk>/',
        views.report_residence,
        name='report_residence'
        ),    
    path(
        'review-report/<int:pk>/',
         views.review_report,
         name='review_report'
    ),
    path(
        'review-user-report/<int:pk>/',
         views.review_user_report,
         name='review_user_report'
    ),
    path('review-user-report/<int:pk>/', views.review_user_report, name='review_user_report'),
    path('suspend-user/<int:user_id>/', views.suspend_user, name='suspend_user'),
    path(
        'save-favorite/<int:pk>/',
        views.save_favorite,
        name='save_favorite'
     ),
    path('ai-fix-description/', views.ai_fix_description, name='ai_fix_description'),
    path(
        'my-favorites/',
        views.my_favorites,
        name='my_favorites'
        ), 

    path(
        'remove-favorite/<int:pk>/',
        views.remove_favorite,
        name='remove_favorite'
        ), 

    path(
        'owner/<int:user_id>/',
        views.owner_profile,
        name='owner_profile'
        ),

    path(
        'residence/<int:pk>/review/',
        views.add_review,
        name='add_review'
        ),

    path(
        'residence/<int:pk>/viewers/',
        views.residence_viewers,
        name='residence_viewers'
        ),

    path(
        'edit-profile/',
        views.edit_profile,
        name='edit_profile'
        ),

    path(
        'notifications/',
        views.notifications,
        name='notifications'
        ), 
    path('about/', views.about, name='about'), 
    path('residence/<int:pk>/verify-location/', views.verify_location, name='verify_location'),
    path('mover/<int:pk>/save/', views.save_mover_favorite, name='save_mover_favorite'),
    path('furniture-vendor/<int:pk>/save/', views.save_furniture_vendor_favorite, name='save_furniture_vendor_favorite'),


    path('admin-dashboard-redirect/', views.admin_dashboard, name='admin_dashboard_view'),
    path('add-mover/', views.add_mover, name='add_mover'),
    path('add-mover-sponsor/', views.add_mover_sponsor, name='add_mover_sponsor'),
    path('add-furniture-vendor/', views.add_furniture_vendor, name='add_furniture_vendor'),
    path('add-furniture-vendor-sponsor/', views.add_furniture_vendor_sponsor, name='add_furniture_vendor_sponsor'),
    path('mover/<int:pk>/', views.mover_detail, name='mover_detail'),
    path('furniture-vendor/<int:pk>/', views.furniture_vendor_detail, name='furniture_vendor_detail'),
    path('control-panel-2947/mover/<int:pk>/edit/', views.edit_mover, name='edit_mover'),
    path('control-panel-2947/mover/<int:pk>/delete/', views.delete_mover, name='delete_mover'),
    path('control-panel-2947/furniture-vendor/<int:pk>/edit/', views.edit_furniture_vendor, name='edit_furniture_vendor'),
    path('control-panel-2947/furniture-vendor/<int:pk>/delete/', views.delete_furniture_vendor, name='delete_furniture_vendor'),
    path('control-panel-2947/vendors/remove-expired/', views.remove_expired_vendors, name='remove_expired_vendors'),
    path('control-panel-2947/vendors/mover/<int:pk>/edit/', views.edit_mover, name='edit_mover'),
    path('control-panel-2947/vendors/mover/<int:pk>/delete/', views.delete_mover, name='delete_mover'),
    path('control-panel-2947/vendors/furniture/<int:pk>/edit/', views.edit_furniture_vendor, name='edit_furniture_vendor'),
    path('control-panel-2947/vendors/furniture/<int:pk>/delete/', views.delete_furniture_vendor, name='delete_furniture_vendor'),
    path('control-panel-2947/vendors/remove-expired/', views.remove_expired_vendors, name='remove_expired_vendors'),
    path(
        'compare/',
        views.compare_residences,
        name='compare_residences'
    ),
    path('admin-dashboard/export-csv/', views.export_residences_csv, name='export_residences_csv'),
    path('admin-dashboard/suspicious-users/', views.suspicious_users, name='suspicious_users'),
    path('warn-user/<int:user_id>/', views.warn_user, name='warn_user'),
    path('offline/', TemplateView.as_view(template_name='core/offline.html'), name='offline'),
    path('activity/', views.activity_feed, name='activity_feed'),
    path('residence/<int:pk>/generate-lease/', views.generate_lease, name='generate_lease'),
    path('lease/<int:pk>/download/', views.download_lease_pdf, name='download_lease_pdf'),
    path('roommates/', views.roommate_list, name='roommate_list'),
    path('roommates/profile/', views.roommate_profile_edit, name='roommate_profile_edit'),
    path('roommates/deactivate/', views.roommate_deactivate, name='roommate_deactivate'),
    path('donate/stk-push/', views.donate_stk_push, name='donate_stk_push'),
    path('initiate-donation/', views.initiate_donation, name='initiate_donation'),
    path('donate/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('residence/<int:pk>/download-pdf/', views.download_residence_pdf, name='download_residence_pdf'),
    path('privacy-policy/', TemplateView.as_view(template_name='core/privacy_policy.html'), name='privacy_policy'),
    path('terms-of-service/', TemplateView.as_view(template_name='core/terms_of_service.html'), name='terms_of_service'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='sw_js'),
    path('residences/ai-improve-description/', views.ai_improve_description, name='ai_improve_description'),
    path('residences/ai-recommendations/', views.ai_recommendations, name='ai_recommendations'),
    path('residence/<int:pk>/toggle-premium/', views.toggle_premium, name='toggle_premium'),
    path('residence/<int:pk>/toggle-hide/', views.toggle_hide, name='toggle_hide'),
    path('residence/<int:pk>/toggle-pause/', views.toggle_pause, name='toggle_pause'),
    path('residence/<int:pk>/request-boost/', views.request_boost, name='request_boost'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('report-user/<int:user_id>/', views.report_user, name='report_user'),
    path('save-search/', views.save_search, name='save_search'),
    path('saved-searches/', views.my_saved_searches, name='my_saved_searches'),
    path('saved-searches/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),

    
]
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)

