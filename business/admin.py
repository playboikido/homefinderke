from django.contrib import admin

from .models import (
    Business,
    BusinessStaffMember,
    BusinessProduct,
    BusinessGalleryImage,
    BusinessVerificationDocument,
    BusinessInquiry,
    BusinessReview,
    BusinessFavorite,
    BusinessSubscription,
    BusinessPayment,
    BusinessAnalyticsEvent,
)


class BusinessProductInline(admin.TabularInline):
    model = BusinessProduct
    extra = 0


class BusinessVerificationDocumentInline(admin.TabularInline):
    model = BusinessVerificationDocument
    extra = 0


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'owner', 'plan', 'verification_status', 'is_approved', 'is_active', 'created_at')
    list_filter = ('category', 'plan', 'verification_status', 'is_approved', 'is_active')
    search_fields = ('name', 'owner__username', 'owner__email', 'phone_number', 'email')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BusinessProductInline, BusinessVerificationDocumentInline]


@admin.register(BusinessProduct)
class BusinessProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'price', 'is_available', 'created_at')
    list_filter = ('is_available',)
    search_fields = ('name', 'business__name')


@admin.register(BusinessInquiry)
class BusinessInquiryAdmin(admin.ModelAdmin):
    list_display = ('business', 'customer_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('customer_name', 'business__name')


@admin.register(BusinessReview)
class BusinessReviewAdmin(admin.ModelAdmin):
    list_display = ('business', 'user', 'rating', 'created_at')
    list_filter = ('rating',)


@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'status', 'renewal_date')
    list_filter = ('plan', 'status')


@admin.register(BusinessPayment)
class BusinessPaymentAdmin(admin.ModelAdmin):
    list_display = ('business', 'purpose', 'amount', 'status', 'created_at')
    list_filter = ('purpose', 'status', 'method')


admin.site.register(BusinessStaffMember)
admin.site.register(BusinessGalleryImage)
admin.site.register(BusinessFavorite)
admin.site.register(BusinessAnalyticsEvent)