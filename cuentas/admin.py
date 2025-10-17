from django.contrib import admin
from .models import Perfil

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display  = ("user", "cedula")
    search_fields = ("user__username", "user__first_name", "user__last_name", "cedula")
