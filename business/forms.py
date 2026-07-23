from django import forms
from django.core.validators import FileExtensionValidator
from django.forms import modelformset_factory

from .models import Business, BusinessProduct

ALLOWED_DOC_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']
MAX_DOC_SIZE_MB = 5


def validate_doc_size(value):
    if value and value.size > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise forms.ValidationError(f"File must be under {MAX_DOC_SIZE_MB}MB.")


class BusinessInfoForm(forms.ModelForm):
    REQUIRED_FIELDS = ['name', 'category', 'description', 'cover_image']

    class Meta:
        model = Business
        fields = ['name', 'category', 'description', 'logo', 'cover_image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True


class BusinessContactForm(forms.ModelForm):
    REQUIRED_FIELDS = ['phone_number']

    class Meta:
        model = Business
        # whatsapp_number is auto-filled from phone_number in Business.save()
        # if left blank, so it stays optional here.
        fields = ['phone_number', 'whatsapp_number', 'email', 'website', 'facebook', 'instagram', 'tiktok']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True


class BusinessLocationForm(forms.ModelForm):
    REQUIRED_FIELDS = ['county', 'town', 'estate', 'street', 'latitude', 'longitude', 'opens_at', 'closes_at']

    class Meta:
        model = Business
        fields = [
            'county', 'town', 'estate', 'street', 'service_counties',
            'latitude', 'longitude', 'opens_at', 'closes_at', 'closed_weekdays',
        ]
        widgets = {
            'opens_at': forms.TimeInput(attrs={'type': 'time'}),
            'closes_at': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True


BusinessProductFormSet = modelformset_factory(
    BusinessProduct,
    fields=['name', 'category', 'price', 'description', 'image', 'is_available'],
    extra=1,
    can_delete=True,
)


class BusinessVerificationForm(forms.Form):
    registration_certificate = forms.FileField(
        required=False, validators=[FileExtensionValidator(ALLOWED_DOC_EXTENSIONS), validate_doc_size])
    kra_pin = forms.FileField(
        required=False, validators=[FileExtensionValidator(ALLOWED_DOC_EXTENSIONS), validate_doc_size])
    business_permit = forms.FileField(
        required=False, validators=[FileExtensionValidator(ALLOWED_DOC_EXTENSIONS), validate_doc_size])
    national_id = forms.FileField(
        required=False, validators=[FileExtensionValidator(ALLOWED_DOC_EXTENSIONS), validate_doc_size])


class BusinessEditForm(forms.ModelForm):
    REQUIRED_FIELDS = [
        'name', 'category', 'description', 'cover_image',
        'phone_number',
        'county', 'town', 'estate', 'street', 'latitude', 'longitude', 'opens_at', 'closes_at',
    ]

    class Meta:
        model = Business
        fields = [
            'name', 'category', 'description', 'logo', 'cover_image',
            'phone_number', 'whatsapp_number', 'email', 'website', 'facebook', 'instagram', 'tiktok',
            'county', 'town', 'estate', 'street', 'service_counties',
            'latitude', 'longitude', 'opens_at', 'closes_at', 'closed_weekdays',
        ]
        widgets = {
            'opens_at': forms.TimeInput(attrs={'type': 'time'}),
            'closes_at': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True