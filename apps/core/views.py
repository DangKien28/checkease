from django.shortcuts import render

def landing_view(request):
    return render(request, 'pages/landing.html')

def settings_view(request):
    return render(request, 'pages/settings.html')
