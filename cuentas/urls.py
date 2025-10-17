# apps/cuentas/urls.py
from django.urls import path
from . import views

app_name = "cuentas"

urlpatterns = [
    path("usuarios/nuevo/", views.crear_usuario_simple, name="crear_usuario_simple"),
    path("usuarios/", views.lista_usuarios, name="lista_usuarios"),
]
