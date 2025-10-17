# cuentas/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from cuentas.models import Perfil

class CedulaAuthForm(AuthenticationForm):
    def clean(self):
        # Deja que Django intente primero con username normal
        try:
            return super().clean()
        except forms.ValidationError:
            pass  # Si falla, probamos con cédula

        cleaned = self.cleaned_data
        login = cleaned.get('username')
        password = cleaned.get('password')
        if not login or not password:
            raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')

        # Si el “username” ingresado parece cédula o quieres siempre intentar cédula:
        try:
            perfil = Perfil.objects.select_related('user').get(cedula=login)
        except Perfil.DoesNotExist:
            raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')

        user = authenticate(self.request, username=perfil.user.username, password=password)
        if user is None:
            raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')

        self.confirm_login_allowed(user)
        self.user_cache = user
        return cleaned
