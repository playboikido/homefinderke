from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.contrib import messages
from core.forms import UserRegistrationForm, UserLoginForm


def register_view(request):
    next_url = request.GET.get('next')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # locked until they verify their email
            user.save()

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            verify_url = request.build_absolute_uri(f'/accounts/verify-email/{uid}/{token}/')

            try:
                send_mail(
                    subject='Verify your HomeFinder KE account',
                    message=(
                        f'Hi {user.username},\n\n'
                        f'Please verify your email by clicking this link:\n{verify_url}\n\n'
                        f'If you did not sign up for HomeFinder KE, you can ignore this email.'
                    ),
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                messages.success(request, 'Account created! Check your email to verify your account before logging in.')
            except Exception as e:
                print("VERIFICATION EMAIL ERROR:", e)
                messages.warning(request, 'Account created, but the verification email failed to send. Contact support.')

            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form, 'next_url': next_url})


def verify_email_view(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Email verified! You can now log in.')
    else:
        messages.error(request, 'This verification link is invalid or has expired.')

    return redirect('login')


def login_view(request):
    next_url = request.GET.get('next')
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                if next_url:
                    return redirect(next_url)
                return redirect('home')
            else:
                try:
                    existing = User.objects.get(username=form.cleaned_data['username'])
                    if not existing.is_active:
                        form.add_error(None, 'Please verify your email before logging in — check your inbox for the link.')
                    else:
                        form.add_error(None, 'Invalid username or password.')
                except User.DoesNotExist:
                    form.add_error(None, 'Invalid username or password.')
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'next_url': next_url})


def logout_view(request):
    logout(request)
    return redirect('home')