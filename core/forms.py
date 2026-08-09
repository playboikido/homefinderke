from django import forms
from .models import Residence, ResidenceReport
from .models import Residence, LeaseAgreement, RoommateProfile, HOUSE_TYPES
# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox


class ResidenceForm(forms.ModelForm):

    class Meta:
        
        model = Residence

        fields = [
            'name',
            'description',
            'county',
            'town',
            'plot_number',
            'landmark',

            'house_type',      # ← THIS MUST EXIST

            'rent_price',
            'deposit_amount',
            'phone_number',
            'nearest_stage',
            'nearby_school',
            'nearby_hospital',
            'latitude',
            'longitude',
            'water_available',
            'fibre_available',
            'gated_community',
            'cctv_available',
            'security_guard',
            'front_image',
            'vacancy_poster',
        ]

        exclude = (
            'owner',
            'approved',
            'views_count',
            'created_at',
        )

        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Example: Green View Apartments'
            }),

            'description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Describe the residence'
            }),

            'county': forms.TextInput(attrs={
                'placeholder': 'Example: Nairobi'
            }),

            'town': forms.TextInput(attrs={
                'placeholder': 'Example: Kasarani, Zimmerman, Ruiru'
            }),

            'phone_number': forms.TextInput(attrs={
                'placeholder': 'Caretaker phone number'
            }),

            'rent_price': forms.NumberInput(attrs={
                'placeholder': 'Monthly Rent in KES'
            }),

            'deposit_amount': forms.NumberInput(attrs={
                'placeholder': 'Deposit Amount in KES'
            }),
        }
  

class ResidenceReportForm(forms.ModelForm):

    class Meta:
        model = ResidenceReport

        fields = [
            'reason',
            'comment'
        ]

        widgets = {
            'reason': forms.Select(
                attrs={
                    'class': 'form-control'
                }
            ),

            'comment': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Additional information (optional)'
                }
            ),
        }

from .models import Review

class ReviewForm(forms.ModelForm):

    class Meta:
        model = Review

        fields = [
            'rating',
            'comment'
        ]

        widgets = {
            'rating': forms.Select(
                attrs={
                    'class': 'form-control'
                }
            ),

            'comment': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Write your review here...'
                }
            ),
        }

from .models import Profile, NotificationPreference, IDVerification


class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile

        fields = [
            'profile_picture',
            'phone_number',
            'bio',
        ]

        widgets = {
            'phone_number': forms.TextInput(
                attrs={
                    'class': 'form-control'
                }
            ),

            'bio': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4
                }
            ),
        }   


from django.contrib.auth.models import User


class IDVerificationForm(forms.ModelForm):
    class Meta:
        model = IDVerification
        fields = ['document']
        widgets = {
            'document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class PrivacyForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_visibility', 'hide_phone', 'hide_email']
        widgets = {
            'profile_visibility': forms.RadioSelect(),
            'hide_phone': forms.CheckboxInput(),
            'hide_email': forms.CheckboxInput(),
        }


class AppearanceForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['theme_preference', 'reduce_motion', 'compact_mode']
        widgets = {
            'theme_preference': forms.RadioSelect(),
            'reduce_motion': forms.CheckboxInput(),
            'compact_mode': forms.CheckboxInput(),
        }


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_notifications',
            'sms_notifications',
            'push_notifications',
            'favourite_residence_updates',
            'new_inquiry_alerts',
            'new_review_alerts',
            'newsletter',
            'marketing_emails',
            'notification_sounds',
        ]
        widgets = {name: forms.CheckboxInput() for name in fields}


class SettingsUserForm(forms.ModelForm):
    """Full Name / Username / Email fields for Settings > My Profile.
    These live on Django's User model, not Profile."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('That email is already in use on another account.')
        return email


class SettingsProfileForm(forms.ModelForm):
    """Profile Photo / Cover Photo / Phone / County / Town / Bio / Language
    for Settings > My Profile (Residence Workspace)."""

    class Meta:
        model = Profile
        fields = [
            'profile_picture',
            'cover_photo',
            'phone_number',
            'county',
            'town',
            'bio',
            'language',
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07XX XXX XXX'}),
            'county': forms.Select(attrs={'class': 'form-control'}),
            'town': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Kilimani'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'maxlength': 300}),
            'language': forms.Select(attrs={'class': 'form-control'}),
        }




from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    subject = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea)
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

from .models import Residence, LeaseAgreement

class LeaseAgreementForm(forms.ModelForm):
    class Meta:
        model = LeaseAgreement
        fields = [
            'tenant_full_name', 'tenant_id_number', 'tenant_phone',
            'landlord_full_name', 'landlord_phone',
            'monthly_rent', 'deposit_amount',
            'lease_start_date', 'lease_duration_months',
        ]
        widgets = {
            'lease_start_date': forms.DateInput(attrs={'type': 'date'}),
        }

class RoommateProfileForm(forms.ModelForm):
    class Meta:
        model = RoommateProfile
        fields = ['budget_min', 'budget_max', 'preferred_county', 'preferred_town', 'move_in_timeline', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': "e.g. Quiet professional, non-smoker, works night shifts..."}),
        }        

from .models import Mover, FurnitureVendor

class MoverForm(forms.ModelForm):
    class Meta:
        model = Mover
        fields = ['name', 'logo', 'phone_number', 'description', 'website', 'service_counties']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Example: Peak Movers'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712345678'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe services, pricing, areas of operation...'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com (optional)'}),
            'service_counties': forms.TextInput(attrs={'placeholder': 'e.g. Nairobi, Kiambu — which counties this mover serves'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class FurnitureVendorForm(forms.ModelForm):
    class Meta:
        model = FurnitureVendor
        fields = ['name', 'image', 'phone_number', 'location', 'description', 'website', 'service_counties']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Example: Elegant Sofa World'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712345678'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Kasarani, Nairobi'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe types of furniture, custom work, delivery options...'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com (optional)'}),
            'service_counties': forms.TextInput(attrs={'placeholder': 'e.g. Nairobi, Kiambu — which counties this vendor serves'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class MoverSponsorForm(forms.ModelForm):
    """Sponsor-tier mover — adds service_counties and scrape config on top of the base fields."""
    class Meta:
        model = Mover
        fields = ['name', 'logo', 'phone_number', 'description', 'website', 'service_counties',
                   'data_source', 'scrape_config']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Example: Peak Movers'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712345678'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe services, pricing, areas of operation...'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com (optional)'}),
            'service_counties': forms.TextInput(attrs={'placeholder': 'e.g. Nairobi, Kiambu'}),
            'scrape_config': forms.Textarea(attrs={'rows': 5, 'placeholder':
                '{"product_page_url": "https://vendor.com/shop", "item_selector": ".product-card", '
                '"name_selector": ".product-title", "price_selector": ".price", "image_selector": "img"}'
            }),
        }


class FurnitureVendorSponsorForm(forms.ModelForm):
    """Sponsor-tier furniture vendor — adds service_counties and scrape config on top of the base fields."""
    class Meta:
        model = FurnitureVendor
        fields = ['name', 'image', 'phone_number', 'location', 'description', 'website', 'service_counties',
                   'data_source', 'scrape_config']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Example: Elegant Sofa World'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712345678'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Kasarani, Nairobi'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe types of furniture, custom work, delivery options...'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com (optional)'}),
            'service_counties': forms.TextInput(attrs={'placeholder': 'e.g. Nairobi, Kiambu'}),
            'scrape_config': forms.Textarea(attrs={'rows': 5, 'placeholder':
                '{"product_page_url": "https://vendor.com/shop", "item_selector": ".product-card", '
                '"name_selector": ".product-title", "price_selector": ".price", "image_selector": "img"}'
            }),
        }

from .models import UserReport

class UserReportForm(forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ['reason', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional — add any extra detail'}),
        }

from .models import Incident

class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ['category', 'subject', 'description', 'contact_phone']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe what happened in as much detail as possible...'}),
            'subject': forms.TextInput(attrs={'placeholder': 'Brief summary, e.g. "Charged twice for premium plan"'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': 'Optional — for us to reach you back'}),
        }        

class ResidentDetailsForm(forms.Form):
    """Step 1 of resident onboarding — name, phone, email, bio, photo."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Last name'}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'placeholder': '07XX XXX XXX'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'placeholder': 'Optional'}))
    bio = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'A short description about you (optional)'}))
    profile_picture = forms.ImageField(required=False)
    show_phone_publicly = forms.BooleanField(
        required=False,
        label='Show my phone number on my public profile',
        help_text='Off by default — only your name, bio, photo, verification status, and account type show publicly either way.',
    )   

class ResidentRoleForm(forms.Form):
    """Step 2 of resident onboarding — which role are they?"""

    resident_role = forms.ChoiceField(
        choices=Profile.RESIDENT_ROLE_CHOICES,
        widget=forms.RadioSelect,
        label='Which best describes you?',
    )       

class ResidentVerificationForm(forms.ModelForm):
    """Step 3 of resident onboarding — document uploads, tailored to role:
    normal -> none, caretaker -> ID only, landlord/agent -> ID + KRA + proof."""

    class Meta:
        model = IDVerification
        fields = ['document', 'kra_pin_document', 'property_proof_document']
        labels = {
            'document': 'National ID',
            'kra_pin_document': 'KRA PIN Certificate',
            'property_proof_document': 'Proof of ownership / payment (title deed, rent receipt, management agreement, etc.)',
        }

    def __init__(self, *args, resident_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        needs_landlord_docs = resident_role in ('landlord', 'agent')
        self.fields['document'].required = resident_role in ('caretaker', 'landlord', 'agent')
        self.fields['kra_pin_document'].required = needs_landlord_docs
        self.fields['property_proof_document'].required = needs_landlord_docs
        if not needs_landlord_docs:
            # Caretakers only need the ID field.
            del self.fields['kra_pin_document']
            del self.fields['property_proof_document']

class ResidentAgreementForm(forms.Form):
    """Step 4 of resident onboarding — final role-specific consent."""

    agree = forms.BooleanField(
        required=True,
        label='I have read and agree to the terms above',
        error_messages={'required': 'You must agree to the terms above to continue.'},
    )            