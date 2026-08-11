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
    path(
        'residences/<int:pk>/next/',
        views.residence_next_detail_api,
        name='residence_next_detail_api'
    ),
    path('staff-tools/vendors/', views.vendor_dashboard, name='vendor_dashboard'),
    path('residence/<int:pk>/edit/', views.edit_residence, name='edit_residence'),
    path(
        'add-residence/',
        views.add_residence,
        name='add_residence'
    ),
    path('control-panel-2947/residence/<int:pk>/agreement-pdf/', views.download_agreement_pdf, name='download_agreement_pdf'),
    path('listing-terms/', views.listing_terms, name='listing_terms'),
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
        'approve-business/<int:pk>/',
        views.approve_business,
        name='approve_business'
    ),
    path(
        'reject-business/<int:pk>/',
        views.reject_business,
        name='reject_business'
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
    path('ai-check-image/', views.check_image_ai, name='check_image_ai'),
    path('ai-check-location/', views.check_location_ai, name='check_location_ai'),
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
    path('help-center/', views.help_center, name='help_center'),
    path('help-center/report/', views.report_incident, name='report_incident'),
    path('help-center/bot/', views.help_bot_chat, name='help_bot_chat'),
    path('help-center/bot/message/', views.help_bot_message, name='help_bot_message'),
    path(
        'edit-profile/',
        views.edit_profile,
        name='edit_profile'
        ),
    path('help-center/contact/', views.contact_us, name='contact_us'),
    path(
        'settings/profile/',
        views.settings_profile,
        name='settings_profile'
        ),

    path(
        'settings/security/',
        views.settings_security,
        name='settings_security'
        ),

    path(
        'settings/notifications/',
        views.settings_notifications,
        name='settings_notifications'
        ),

    path(
        'settings/appearance/',
        views.settings_appearance,
        name='settings_appearance'
        ),

    path(
        'settings/privacy/',
        views.settings_privacy,
        name='settings_privacy'
        ),

    path(
        'settings/saved/',
        views.settings_saved,
        name='settings_saved'
        ),

    path(
        'settings/help/',
        views.settings_help,
        name='settings_help'
        ),

    path(
        'settings/verification/',
        views.settings_verification,
        name='settings_verification'
        ),

    path(
        'settings/danger/',
        views.settings_danger,
        name='settings_danger'
        ),

    path(
        'settings/export-data/',
        views.settings_export_data,
        name='settings_export_data'
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
    path('add-furniture-vendor/', views.add_furniture_vendor, name='add_furniture_vendor'),
    path('mover/<int:pk>/', views.mover_detail, name='mover_detail'),
    path('furniture-vendor/<int:pk>/', views.furniture_vendor_detail, name='furniture_vendor_detail'),
    path('biz/<slug:slug>/', views.business_detail, name='business_detail'),
    path('biz/<slug:slug>/track/<str:event_type>/', views.business_track_click, name='business_track_click'),
    path('staff-tools/mover/<int:pk>/edit/', views.edit_mover, name='edit_mover'),
    path('staff-tools/mover/<int:pk>/delete/', views.delete_mover, name='delete_mover'),
    path('staff-tools/furniture-vendor/<int:pk>/edit/', views.edit_furniture_vendor, name='edit_furniture_vendor'),
    path('staff-tools/furniture-vendor/<int:pk>/delete/', views.delete_furniture_vendor, name='delete_furniture_vendor'),
    path('staff-tools/vendors/remove-expired/', views.remove_expired_vendors, name='remove_expired_vendors'),
    path(
        'compare/',
        views.compare_residences,
        name='compare_residences'
    ),
    path(
        'save-favorite/<int:pk>/',
        views.save_favorite,
        name='save_favorite'
    ),
    path(
        'follow/<int:user_id>/',
        views.toggle_follow,
        name='toggle_follow'
    ),
    path('sponsorship/', views.sponsorship_plans, name='sponsorship_plans'),
    path('sponsorship/<int:pk>/pay/', views.initiate_sponsorship, name='initiate_sponsorship'),
    path('mpesa/residence-callback/', views.residence_mpesa_callback, name='residence_mpesa_callback'),
    path('business/', include('business.urls')),
    path('moving-essentials/', views.moving_essentials, name='moving_essentials'),
    path('directory-search/', views.directory_search_suggestions, name='directory_search_suggestions'),
    path('sentry-test/', views.sentry_test, name='sentry_test'),
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
    path('residence/<int:pk>/download-pdf/', views.download_residence_pdf, name='download_residence_pdf'),
    path('get-started/', views.get_started, name='get_started'),
    path('get-started/<str:account_type>/', views.set_account_intent, name='set_account_intent'),
    path('resident/onboarding/', views.resident_onboarding_start, name='resident_onboarding_start'),
    path('resident/onboarding/details/', views.resident_onboarding_details, name='resident_onboarding_details'),
    path('resident/onboarding/role/', views.resident_onboarding_role, name='resident_onboarding_role'),
    path('resident/onboarding/verification/', views.resident_onboarding_verification, name='resident_onboarding_verification'),
    path('resident/onboarding/agreement/', views.resident_onboarding_agreement, name='resident_onboarding_agreement'),
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
    path('discovery-feed/api/', views.discovery_feed_api, name='discovery_feed_api'),
    path('residences/<int:pk>/favorite/', views.toggle_favorite_api, name='toggle_favorite_api'),
]
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)