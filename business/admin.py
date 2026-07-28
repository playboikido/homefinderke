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
    BusinessCoupon,
    BusinessPromotion,
    BusinessService,
    BusinessBooking,
    BusinessQuotation,
    BusinessOrder,
    BusinessOrderItem,
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
    list_display = ('business', 'purpose', 'amount', 'status', 'plan', 'created_at')
    list_filter = ('purpose', 'status', 'method', 'plan')
    actions = ['mark_completed_and_activate']

    @admin.action(description="Mark as completed & activate the business's plan")
    def mark_completed_and_activate(self, request, queryset):
        activated = 0
        for payment in queryset.exclude(status='completed'):
            payment.activate()
            activated += 1
        self.message_user(request, f"Activated {activated} payment(s).")


admin.site.register(BusinessStaffMember)
admin.site.register(BusinessGalleryImage)
admin.site.register(BusinessFavorite)
admin.site.register(BusinessAnalyticsEvent)
admin.site.register(BusinessCoupon)
admin.site.register(BusinessService)


@admin.register(BusinessBooking)
class BusinessBookingAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'business', 'service', 'requested_date', 'status')
    list_filter = ('status',)
    search_fields = ('customer_name', 'business__name')


@admin.register(BusinessQuotation)
class BusinessQuotationAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'business', 'status', 'quoted_amount', 'created_at')
    list_filter = ('status',)
    search_fields = ('customer_name', 'business__name')


class BusinessOrderItemInline(admin.TabularInline):
    model = BusinessOrderItem
    extra = 0


@admin.register(BusinessOrder)
class BusinessOrderAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'business', 'status', 'total_amount', 'created_at')
    list_filter = ('status',)
    search_fields = ('customer_name', 'business__name')
    inlines = [BusinessOrderItemInline]


@admin.register(BusinessPromotion)
class BusinessPromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'business', 'placement', 'status', 'starts_on', 'ends_on')
    list_filter = ('placement', 'status')
    search_fields = ('title', 'business__name')