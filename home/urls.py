# home/urls.py
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import dashboard

urlpatterns = [
    # login como página inicial
    path(
        "",
        LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("inicio/", dashboard, name="dashboard"),
path('inicio/', dashboard, name='dashboard'),
    path('post-login/', post_login_redirect, name='post_login_redirect'),
]
