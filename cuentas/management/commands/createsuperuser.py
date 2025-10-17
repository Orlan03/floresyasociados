from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from cuentas.models import Perfil

class Command(BaseCommand):
    help = "Crea un superusuario pidiendo nombres, apellidos y cédula."

    def handle(self, *args, **options):
        User = get_user_model()

        username = input("Usuario (username): ").strip()
        if not username:
            raise CommandError("El usuario es obligatorio.")
        if User.objects.filter(username=username).exists():
            raise CommandError("Ya existe un usuario con ese username.")

        first_name = input("Nombres: ").strip()
        last_name  = input("Apellidos: ").strip()
        cedula     = input("Cédula: ").strip()
        if not cedula:
            raise CommandError("La cédula es obligatoria.")
        if Perfil.objects.filter(cedula=cedula).exists():
            raise CommandError("Ya existe un perfil con esa cédula.")

        while True:
            password  = getpass("Contraseña: ")
            password2 = getpass("Confirmar contraseña: ")
            if not password:
                self.stderr.write(self.style.ERROR("La contraseña no puede estar vacía."))
                continue
            if password != password2:
                self.stderr.write(self.style.ERROR("Las contraseñas no coinciden, intenta otra vez."))
                continue
            break

        with transaction.atomic():
            user = User.objects.create_superuser(username=username, password=password)
            user.first_name = first_name
            user.last_name  = last_name
            user.save(update_fields=["first_name", "last_name"])

            Perfil.objects.create(user=user, cedula=cedula)

        self.stdout.write(self.style.SUCCESS(f"Superusuario '{username}' creado correctamente."))
