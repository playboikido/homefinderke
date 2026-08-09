from django import forms
from django.utils import timezone
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from allauth.account.forms import LoginForm, SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupFormBase

from core.models import Profile


class CaptchaLoginForm(LoginForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


class CaptchaSignupForm(SignupForm):
    account_type = forms.ChoiceField(
        choices=Profile.ACCOUNT_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='resident',
        label="I'm signing up as a",
    )
    terms_agreed = forms.BooleanField(
        required=True,
        label="I agree to the Terms of Service and Privacy Policy",
        error_messages={"required": "You must agree to the Terms of Service and Privacy Policy to create an account."},
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

    def save(self, request):
        user = super().save(request)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.account_type = self.cleaned_data['account_type']
        profile.terms_accepted_at = timezone.now()
        profile.save(update_fields=['account_type', 'terms_accepted_at'])
        return user


class SocialSignupForm(SocialSignupFormBase):
    account_type = forms.ChoiceField(
        choices=Profile.ACCOUNT_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='resident',
        label="I'm signing up as a",
    )
    terms_agreed = forms.BooleanField(
        required=True,
        label="I agree to the Terms of Service and Privacy Policy",
        error_messages={"required": "You must agree to the Terms of Service and Privacy Policy to create an account."},
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self.sociallogin, 'request', None)
        intended = request.session.get('intended_account_type') if request else None
        if intended in ('resident', 'business'):
            self.fields['account_type'].initial = intended

    def save(self, request):
        user = super().save(request)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.account_type = self.cleaned_data['account_type']
        profile.terms_accepted_at = timezone.now()
        profile.save(update_fields=['account_type', 'terms_accepted_at'])
        request.session.pop('intended_account_type', None)
        return user