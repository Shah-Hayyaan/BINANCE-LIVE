from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import JsonResponse

# Health check view
def health_check(request):
    return JsonResponse({"status": "ok"}, status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('backendapp.urls')),  # Ensure 'backendapp/urls.py' exists
    path('', lambda request: redirect('api/')),  # Redirect to API root
    path('health/', health_check),  # JSON health check
]
