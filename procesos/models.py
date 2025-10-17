from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class CarpetaProceso(models.Model):
    nombre = models.CharField(max_length=200)
    padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="hijas",
        on_delete=models.CASCADE,
    )
    orden = models.PositiveIntegerField(default=1)
    es_documento = models.BooleanField(default=False)
    # ⛔ Importante: NO declarar creada_en / actualizada_en porque la BD no tiene esas columnas

    class Meta:
        # Mantén un orden que no dependa de columnas que no existen en la BD
        ordering = ["orden", "nombre"]

    def save(self, *args, **kwargs):
        """
        Si pertenece al árbol 'Documentos', marca es_documento=True.
        También si es la raíz 'Documentos'.
        """
        root = self.padre
        while root and root.padre_id:
            root = root.padre
        if root and (root.nombre or "").strip().lower() == "documentos":
            self.es_documento = True
        if not self.padre_id and (self.nombre or "").strip().lower() == "documentos":
            self.es_documento = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Proceso(models.Model):
    ESTADOS = [
        ("SIN", "Sin empezar"),
        ("CUR", "En curso"),
        ("FIN", "Finalizado"),
        ("OBS", "Observación"),
        ("CAM", "Cambio de abogado"),
        ("CA", "Casación"),
    ]
    carpeta = models.ForeignKey(CarpetaProceso, related_name="procesos", on_delete=models.CASCADE)
    nombre = models.CharField(max_length=255)
    numero_proceso = models.CharField(max_length=50, blank=True)
    estado = models.CharField(max_length=3, choices=ESTADOS, default="SIN")
    fecha_revision = models.DateField(null=True, blank=True)
    ciudad = models.CharField(max_length=120, blank=True)
    observacion = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    carpeta_documentos = models.ForeignKey(
        'CarpetaProceso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procesos_documentales',
        verbose_name='Carpeta documental (auto)'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"


class DocumentoProceso(models.Model):
    carpeta = models.ForeignKey('CarpetaProceso', related_name='documentos', on_delete=models.CASCADE)
    nombre = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    archivo = models.FileField(upload_to='documentos/')
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)


    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        unique_together = (('carpeta', 'nombre', 'version'),)
        ordering = ['-creado_en', '-id']

    def __str__(self):
        return f'{self.nombre} v{self.version}'