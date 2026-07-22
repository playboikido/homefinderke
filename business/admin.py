from django.contrib import admin
from .models import (
    Business, BusinessProduct, BusinessGalleryImage, BusinessVerificationDocument,
    BusinessInquiry, BusinessReview, BusinessFavorite, SubscriptionPlan,
    BusinessSubscription, BusinessPayment, BusinessAnalyticsEvent, BusinessStaff,
)


class BusinessProductInline(admin.TabularInline):
    model = BusinessProduct
    extra = 0


class BusinessGalleryImageInline(admin.TabularInline):
    model = BusinessGalleryImage
    extra = 0


class BusinessVerificationDocumentInline(admin.TabularInline):
    model = BusinessVerificationDocument
    extra = 0


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'owner', 'county', 'town', 'verification_status', 'is_active', 'is_featured', 'created_at')
    list_filter = ('category', 'verification_status', 'is_active', 'is_featured', 'county')
    search_fields = ('name', 'owner__username', 'owner__email', 'phone_number', 'email')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BusinessProductInline, BusinessGalleryImageInline, BusinessVerificationDocumentInline]
    actions = ['mark_verified', 'mark_rejected']

    def mark_verified(self, request, queryset):
        queryset.update(verification_status='verified')
    mark_verified.short_description = "Mark selected businesses as Verified"

    def mark_rejected(self, request, queryset):
        queryset.update(verification_status='rejected')
    mark_rejected.short_description = "Mark selected businesses as Rejected"


@admin.register(BusinessProduct)
class BusinessProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category', 'price', 'is_available', 'is_active', 'created_at')
    list_filter = ('is_available', 'is_active')
    search_fields = ('name', 'business__name')


@admin.register(BusinessInquiry)
class BusinessInquiryAdmin(admin.ModelAdmin):
    list_display = ('business', 'customer_name', 'customer_phone', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('business__name', 'customer_name', 'customer_phone', 'customer_email')


@admin.register(BusinessReview)
class BusinessReviewAdmin(admin.ModelAdmin):
    list_display = ('business', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('business__name', 'user__username')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price_monthly', 'price_yearly', 'max_products', 'max_gallery_images', 'is_active')
    list_filter = ('is_active',)


@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'billing_cycle', 'status', 'start_date', 'end_date')
    list_filter = ('plan', 'status', 'billing_cycle')
    search_fields = ('business__name',)


@admin.register(BusinessPayment)
class BusinessPaymentAdmin(admin.ModelAdmin):
    list_display = ('business', 'payment_type', 'payment_method', 'amount', 'status', 'created_at')
    list_filter = ('payment_type', 'payment_method', 'status')
    search_fields = ('business__name', 'transaction_ref')


@admin.register(BusinessAnalyticsEvent)
class BusinessAnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('business', 'event_type', 'product', 'visitor_county', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('business__name',)


@admin.register(BusinessStaff)
class BusinessStaffAdmin(admin.ModelAdmin):
    list_display = ('business', 'user', 'role', 'is_active', 'invited_at')
    list_filter = ('role', 'is_active')


admin.site.register(BusinessGalleryImage)
admin.site.register(BusinessFavorite)