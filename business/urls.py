from django.urls import path

from . import views

app_name = 'business'

urlpatterns = [
    path('get-started/', views.choose_view, name='choose'),
    path('onboarding/', views.onboarding_start, name='onboarding_start'),
    path('onboarding/info/', views.onboarding_info, name='onboarding_info'),
    path('onboarding/contact/', views.onboarding_contact, name='onboarding_contact'),
    path('onboarding/location/', views.onboarding_location, name='onboarding_location'),
    path('onboarding/products/', views.onboarding_products, name='onboarding_products'),
    path('onboarding/verification/', views.onboarding_verification, name='onboarding_verification'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit/', views.business_edit, name='edit'),
    path('products/', views.products_manage, name='products'),
    path('plans/', views.plans_view, name='plans'),
]