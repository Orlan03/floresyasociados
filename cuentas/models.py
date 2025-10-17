# cuentas/models.py
from django.db import models
from django.contrib.auth.models import User

class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    cedula = models.CharField(max_length=20, unique=True)

    # Hazlos opcionales y con default vacío para evitar NOT NULL
    telefono  = models.CharField(max_length=30, blank=True, null=True, default="")
    direccion = models.CharField(max_length=255, blank=True, null=True, default="")

    def __str__(self):
        full = self.user.get_full_name() or self.user.username
        return f"{full} ({self.cedula})"
