from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from allauth.account.forms import LoginForm, SignupForm


class CaptchaLoginForm(LoginForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())


class CaptchaSignupForm(SignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())