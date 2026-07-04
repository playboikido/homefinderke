from django.contrib import admin
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


@admin.register(FurnitureVendor)
class FurnitureVendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'phone_number', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'location')
    search_fields = ('name', 'location', 'phone_number', 'description')
    list_editable = ('is_approved',)
    ordering = ('-created_at',)
