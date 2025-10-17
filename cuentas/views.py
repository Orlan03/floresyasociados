# apps/cuentas/views.py
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import render, redirect

from .models import Perfil  # Perfil pertenece a la app 'cuentas'

User = get_user_model()


# ========== Forms ==========
class CrearUsuarioSimpleForm(forms.Form):
    cedula = forms.CharField(
        label="Cédula",
        max_length=10,
        min_length=10,
        help_text="10 dígitos",
    )
    first_name = forms.CharField(label="Nombres", max_length=150, required=False)
    last_name = forms.CharField(label="Apellidos", max_length=150, required=False)
    email = forms.EmailField(label="Correo", required=False)
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repetir contraseña", widget=forms.PasswordInput)
    is_staff = forms.BooleanField(
        label="Dar acceso al admin (/admin)", required=False, initial=False
    )

    def clean_cedula(self):
        ced = self.cleaned_data["cedula"].strip()
        if not ced.isdigit() or len(ced) != 10:
            raise forms.ValidationError("La cédula debe tener exactamente 10 dígitos.")
        # username será la cédula
        if User.objects.filter(username=ced).exists():
            raise forms.ValidationError("Ya existe un usuario con esa cédula.")
        if Perfil.objects.filter(cedula=ced).exists():
            raise forms.ValidationError("Ya existe un perfil con esa cédula.")
        return ced

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return data


# Solo superusuarios
def _solo_superuser(user):
    return user.is_superuser


# ========== Vistas ==========
@login_required
@user_passes_test(_solo_superuser)
def crear_usuario_simple(request):
    """
    Crea un usuario con username = cédula y su Perfil asociado.
    Solo accesible por superuser.
    """
    if request.method == "POST":
        form = CrearUsuarioSimpleForm(request.POST)
        if form.is_valid():
            cedula = form.cleaned_data["cedula"]
            first_name = form.cleaned_data.get("first_name", "")
            last_name = form.cleaned_data.get("last_name", "")
            email = form.cleaned_data.get("email", "")
            telefono = form.cleaned_data.get("telefono", "")
            password = form.cleaned_data["password1"]
            is_staff = form.cleaned_data["is_staff"]

            try:
                # username = cédula (para que el login sea por cédula directamente)
                user = User.objects.create_user(
                    username=cedula,
                    email=email or "",
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.is_active = True
                user.is_staff = bool(is_staff)
                user.save()

                Perfil.objects.create(user=user, cedula=cedula, telefono=telefono or "")

                messages.success(
                    request,
                    f"Usuario {cedula} creado correctamente.",
                )
                return redirect("cuentas:lista_usuarios")
            except IntegrityError as e:
                messages.error(
                    request,
                    "No se pudo crear el usuario (posible cédula/username repetido).",
                )
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = CrearUsuarioSimpleForm()

    return render(request, "cuentas/crear_usuario_simple.html", {"form": form})


@login_required
@user_passes_test(_solo_superuser)
def lista_usuarios(request):
    """
    Lista de usuarios con búsqueda básica.
    Solo accesible por superuser.
    """
    q = request.GET.get("q", "").strip()
    usuarios = User.objects.all().order_by("-id")
    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    # Traer perfiles para mostrar cédula/teléfono en la tabla si quieres
    perfiles = {
        p.user_id: p for p in Perfil.objects.filter(user_id__in=usuarios.values_list("id", flat=True))
    }

    ctx = {
        "usuarios": usuarios,
        "perfiles": perfiles,  # en template: perfiles.get(u.id).cedula, etc.
        "q": q,
    }
    return render(request, "cuentas/lista_usuarios.html", ctx)
