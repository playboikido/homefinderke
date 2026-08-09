from django.contrib import admin
from .models import Mover, FurnitureVendor, MoverProduct, FurnitureProduct
from .models import (
    Residence,
    ResidencePhoto,
    Review,
    Profile,
    ResidenceReport,
    Favorite,
    Notification,
    Mover,
    FurnitureVendor,
)


admin.site.register(Residence)
admin.site.register(Profile)
admin.site.register(ResidencePhoto)
admin.site.register(ResidenceReport)
admin.site.register(Favorite)
admin.site.register(Notification)


@admin.register(Mover)
class MoverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'is_approved', 'created_at')
    list_filter = ('is_approved',)
    search_fields = ('name', 'phone_number', 'description')
    list_editable = ('is_approved',)
    ordering = ('-created_at',)

@admin.register(MoverProduct)
class MoverProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'mover', 'price', 'source', 'is_active', 'updated_at')
    list_filter = ('source', 'is_active')

@admin.register(FurnitureProduct)
class FurnitureProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'source', 'is_active', 'updated_at')
    list_filter = ('source', 'is_active')

@admin.register(FurnitureVendor)
class FurnitureVendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'phone_number', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'location')
    search_fields = ('name', 'location', 'phone_number', 'description')
    list_editable = ('is_approved',)
    ordering = ('-created_at',)

from .models import UserReport
admin.site.register(UserReport)

from .models import IDVerification
admin.site.register(IDVerification)

from .models import Incident

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('subject', 'category', 'status', 'reporter', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('subject', 'description', 'contact_phone')
    list_editable = ('status',)
    ordering = ('-created_at',)
    readonly_fields = ('reporter', 'created_at')

# ResidenceSponsorship was never actually created as a model — admin was
# registered ahead of the model existing, which crashes app boot (admin
# autodiscovery runs on every startup, not per-request). Re-enable once
# that model + its migration exist.
# from .models import ResidenceSponsorship
#
# @admin.register(ResidenceSponsorship)
# class ResidenceSponsorshipAdmin(admin.ModelAdmin):
#     list_display = ('residence', 'owner', 'amount', 'status', 'mpesa_receipt', 'created_at')
#     list_filter = ('status',)
#     search_fields = ('residence__name', 'owner__username', 'mpesa_receipt', 'checkout_request_id')
#     actions = ['activate_selected']
#
#     @admin.action(description='Activate selected (grants Premium) — use for manual/cash payments')
#     def activate_selected(self, request, queryset):
#         for payment in queryset.filter(status='pending'):
#             payment.activate()
#         self.message_user(request, f"Activated {queryset.filter(status='completed').count()} payment(s).")