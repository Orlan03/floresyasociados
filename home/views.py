# apps/home/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone

from procesos.models import CarpetaProceso, Proceso, DocumentoProceso


@login_required
def dashboard(request):
    total_usuarios = User.objects.count()
    total_procesos = Proceso.objects.count()

    # Procesos recientes (usa el campo existente en tu modelo)
    recientes_procesos = Proceso.objects.order_by('-creado_en', '-id')[:6]

    # Documentos recientes (robusto sin depender de 'creado')
    recientes_documentos = (
        DocumentoProceso.objects
        .select_related('carpeta')
        .order_by('-id')[:6]
    )

    # Avisos por fecha de revisión
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=2)

    # Próximos 2 días (excluye finalizados)
    avisos_revision = (
        Proceso.objects
        .filter(
            fecha_revision__isnull=False,
            fecha_revision__range=[hoy, limite]
        )
        .exclude(estado='FIN')
        .select_related('creado_por')
        .order_by('fecha_revision', 'id')
    )

    # Vencidos (top 10)
    vencidos_revision = (
        Proceso.objects
        .filter(fecha_revision__isnull=False, fecha_revision__lt=hoy)
        .exclude(estado='FIN')
        .select_related('creado_por')
        .order_by('fecha_revision', 'id')[:10]
    )

    # URL destino para la “tabla” (primer carpeta raíz de procesos)
    first_carpeta = (
        CarpetaProceso.objects
        .filter(padre__isnull=True, es_documento=False)
        .order_by("orden", "nombre")
        .first()
    )
    if first_carpeta:
        url_tabla_procesos = reverse("procesos:carpeta_detalle", args=[first_carpeta.id])
    else:
        url_tabla_procesos = reverse("procesos:lista")

    return render(request, "home/dashboard.html", {
        "total_usuarios": total_usuarios,
        "total_procesos": total_procesos,
        "recientes_procesos": recientes_procesos,
        "recientes_documentos": recientes_documentos,
        "avisos_revision": avisos_revision,
        "vencidos_revision": vencidos_revision,
        "url_tabla_procesos": url_tabla_procesos,
    })
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from django.urls import reverse, NoReverseMatch


@login_required
def post_login_redirect(request):
    if request.user.groups.filter(name='SoloCrearUsuarios').exists() and not request.user.is_superuser:
        try:
            return redirect('cuentas:crear_usuario_simple')
        except NoReverseMatch:
            return redirect('dashboard')
    return redirect('dashboard')