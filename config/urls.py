# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView
from home.views import dashboard
from cuentas.forms import CedulaAuthForm
urlpatterns = [
    path('admin/', admin.site.urls),

    # Login en raíz
    path(
        '',
        LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True,
            authentication_form=CedulaAuthForm,  # ← aquí
        ),
        name='login'
    ),

    path('logout/', LogoutView.as_view(), name='logout'),

    # Dashboard al que redirigimos después del login
    path('inicio/', dashboard, name='dashboard'),
    path('cuentas/', include(('cuentas.urls', 'cuentas'), namespace='cuentas')),
    path('cuentas/', include('cuentas.urls')),
    path("procesos/", include(("procesos.urls", "procesos"), namespace="procesos")),
]
