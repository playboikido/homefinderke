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

from .models import Profile


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

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    agree_to_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service to create an account.'}
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class UserLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


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