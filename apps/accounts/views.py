from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('/overview/')
        else:
            return render(request, 'pages/login.html', {'error': 'Sai email hoặc mật khẩu'})
    return render(request, 'pages/login.html')

def logout_view(request):
    logout(request)
    return redirect('/')

def register_view(request):
    return render(request, 'pages/register.html')
