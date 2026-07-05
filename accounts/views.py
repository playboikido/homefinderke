from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from core.forms import UserRegistrationForm, UserLoginForm


def register_view(request):
    next_url = request.GET.get('next')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            if next_url:
                return redirect(f"/accounts/custom/login/?next={next_url}")
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form, 'next_url': next_url})


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
                form.add_error(None, 'Invalid username or password.')
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'next_url': next_url})


def logout_view(request):
    logout(request)
    return redirect('home')