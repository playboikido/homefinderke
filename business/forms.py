from django import forms

from .models import Business, BusinessProduct, BusinessVerificationDocument


class BusinessInfoForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['name', 'category', 'description', 'logo', 'cover_image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell customers what you do...'}),
        }


class BusinessContactForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['phone_number', 'whatsapp_number', 'email', 'website', 'facebook', 'instagram', 'tiktok']
        widgets = {
            'phone_number': forms.TextInput(attrs={'placeholder': '07XX XXX XXX'}),
        }


class BusinessLocationForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            'county', 'town', 'estate', 'street',
            'latitude', 'longitude', 'service_counties',
            'opens_at', 'closes_at', 'closed_weekdays',
        ]
        widgets = {
            'opens_at': forms.TimeInput(attrs={'type': 'time'}),
            'closes_at': forms.TimeInput(attrs={'type': 'time'}),
            'closed_weekdays': forms.TextInput(attrs={'placeholder': "e.g. 6 for closed Sundays"}),
        }


class BusinessProductForm(forms.ModelForm):
    class Meta:
        model = BusinessProduct
        fields = ['name', 'category', 'price', 'description', 'image', 'is_available']


BusinessProductFormSet = forms.modelformset_factory(
    BusinessProduct, form=BusinessProductForm, extra=3, can_delete=True
)


class BusinessVerificationForm(forms.Form):
    registration_certificate = forms.FileField(required=False)
    kra_pin = forms.FileField(required=False)
    business_permit = forms.FileField(required=False)
    national_id = forms.FileField(required=False)

    def save(self, business):
        for doc_type, _ in BusinessVerificationDocument.DOC_TYPE_CHOICES:
            if doc_type == 'logo':
                continue
            f = self.cleaned_data.get(doc_type)
            if f:
                BusinessVerificationDocument.objects.update_or_create(
                    business=business, doc_type=doc_type, defaults={'file': f}
                )