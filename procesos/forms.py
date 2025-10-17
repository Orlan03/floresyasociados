from django import forms
from .models import CarpetaProceso, Proceso, DocumentoProceso


class CarpetaForm(forms.ModelForm):
    class Meta:
        model = CarpetaProceso
        fields = ["nombre"]


class ProcesoForm(forms.ModelForm):
    # Campo NO de modelo: el usuario elige la carpeta PADRE dentro de Documentos
    carpeta_doc_padre = forms.ModelChoiceField(
        queryset=CarpetaProceso.objects.none(),  # se setea en __init__
        required=True,
        label="Carpeta de Documentos (padre)",
        help_text="Se creará una subcarpeta con el número de proceso dentro de esta carpeta."
    )

    class Meta:
        model = Proceso
        fields = ["nombre", "numero_proceso", "estado", "fecha_revision", "ciudad", "observacion"]
        widgets = {
            "fecha_revision": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "nombre": "Nombre del proceso",
            "numero_proceso": "Número de proceso",
            "estado": "Estado",
            "fecha_revision": "Fecha de revisión",
            "ciudad": "Ciudad",
            "observacion": "Observación",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Solo carpetas marcadas como documentales, excluyendo el contenedor raíz "Documentos"
        qs = CarpetaProceso.objects.filter(es_documento=True).exclude(
            nombre__iexact="Documentos"
        ).order_by("orden", "nombre")
        self.fields["carpeta_doc_padre"].queryset = qs

        # Placeholders bonitos
        self.fields["nombre"].widget.attrs.update({"placeholder": "Ej.: Juicio civil - López vs. Pérez"})
        self.fields["numero_proceso"].widget.attrs.update({"placeholder": "Ej.: 09321-2025-00123"})
        self.fields["ciudad"].widget.attrs.update({"placeholder": "Ciudad / Jurisdicción"})
        self.fields["observacion"].widget.attrs.update({"placeholder": "Notas u observaciones del caso"})

    def clean_numero_proceso(self):
        """
        Validamos que el número no venga vacío y que NO se repita.
        (Si no quieres validar unicidad lógica aquí, comenta el bloque de exists()).
        """
        num = (self.cleaned_data.get("numero_proceso") or "").strip()
        if not num:
            raise forms.ValidationError("El número de proceso es obligatorio.")

        # Evitar duplicados (case-insensitive). Permitimos editar el mismo proceso.
        qs = Proceso.objects.filter(numero_proceso__iexact=num)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un proceso con ese número.")
        return num


class DocumentoFormSimple(forms.ModelForm):
    class Meta:
        model = DocumentoProceso
        fields = ["nombre", "archivo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Nombre del documento"}),
            # "archivo": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.jpg,.png"})  # opcional
        }
