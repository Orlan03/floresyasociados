# apps/procesos/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView, View,DetailView
import os
import mimetypes
from .forms import DocumentoFormSimple, ProcesoForm
from .models import CarpetaProceso, DocumentoProceso, Proceso
from django.utils.encoding import smart_str
from django.contrib.auth.models import User
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.db import transaction
from django.db.models import Max
from django.views.decorators.http import require_POST
from django.utils.text import slugify
# ---------------------------
# Helpers
# ---------------------------
def get_documentos_root():
    """
    Si quieres seguir teniendo un contenedor 'Documentos' lo puedes crear aquí.
    Ya NO lo usamos para forzar el padre al crear.
    """
    root = CarpetaProceso.objects.filter(padre__isnull=True, nombre__iexact="Documentos").first()
    if not root:
        max_orden = CarpetaProceso.objects.filter(padre__isnull=True).aggregate(m=Max("orden"))["m"] or 0
        root = CarpetaProceso.objects.create(nombre="Documentos", orden=max_orden + 1, es_documento=True)
    return root


def is_under_documentos(carpeta: CarpetaProceso | None) -> bool:
    if carpeta is None:
        return False
    root = carpeta
    while root.padre_id:
        root = root.padre
    return (root.nombre or "").strip().lower() == "documentos"


# ---------------------------
# Listados RAÍZ
# ---------------------------
class CarpetaListView(LoginRequiredMixin, ListView):
    """Raíz de PROCESOS (solo carpetas raíz no documentales)."""
    model = CarpetaProceso
    template_name = "procesos/listado_procesos.html"
    context_object_name = "raiz"

    def get_queryset(self):
        return (
            CarpetaProceso.objects
            .filter(padre__isnull=True, es_documento=False)
            .annotate(cant_subs=Count("hijas", distinct=True),
                      cant_procesos=Count("procesos", distinct=True))
            .order_by("orden", "nombre")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modo"] = "procesos"
        return ctx


class DocumentosListView(LoginRequiredMixin, ListView):
    """Raíz de DOCUMENTOS (solo carpetas raíz documentales)."""
    model = CarpetaProceso
    template_name = "procesos/listado_documentos.html"
    context_object_name = "raiz"

    def get_queryset(self):
        # Si tienes un contenedor llamado 'Documentos' y NO quieres verlo, lo puedes excluir:
        return (
            CarpetaProceso.objects
            .filter(padre__isnull=True, es_documento=True)
            .exclude(nombre__iexact="Documentos")      # <-- oculta el contenedor si existe
            .annotate(cant_subs=Count("hijas", distinct=True),
                      cant_procesos=Count("procesos", distinct=True))
            .order_by("orden", "nombre")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modo"] = "documentos"
        return ctx


# ---------------------------
# Crear carpeta (único endpoint)
# ---------------------------
@login_required
def crear_carpeta(request):
    """
    Crea una carpeta exactamente donde indique el form:
      - Si 'padre' viene vacío -> se crea en RAÍZ de la sección.
      - Si 'padre' trae id -> se crea dentro de esa carpeta.
    NO forzamos el padre a la carpeta 'Documentos'.
    """
    if request.method != "POST":
        return render(request, "procesos/crear_carpeta.html", {})

    next_url = request.POST.get("next") or reverse("procesos:lista")
    nombre = (request.POST.get("nombre") or "").strip()
    seccion = (request.POST.get("seccion") or "procesos").strip().lower()
    padre_id = (request.POST.get("padre") or "").strip()

    if not nombre:
        messages.error(request, "El nombre es obligatorio.")
        return redirect(next_url)

    padre = get_object_or_404(CarpetaProceso, pk=padre_id) if padre_id else None

    # Reglas de cada sección (solo validación, no reasignamos padre):
    if seccion == "documentos":
        # Si te preocupa que alguien intente colgar una carpeta documental fuera del árbol,
        # simplemente marcamos es_documento=True y ya (el listado de documentos sólo mira raíz).
        pass
    else:  # seccion == "procesos"
        # Evitar crear carpetas de procesos dentro del árbol Documentos
        if padre and is_under_documentos(padre):
            messages.error(request, "Las carpetas de procesos no pueden crearse dentro de 'Documentos'.")
            return redirect(next_url)

    last = CarpetaProceso.objects.filter(padre=padre).aggregate(m=Max("orden"))["m"] or 0

    kwargs = dict(nombre=nombre, padre=padre, orden=last + 1)
    # Marcamos el tipo por sección o por herencia del padre
    kwargs["es_documento"] = (seccion == "documentos") or is_under_documentos(padre)

    # Unicidad por nivel
    if CarpetaProceso.objects.filter(padre=padre, nombre__iexact=nombre).exists():
        messages.error(request, "Ya existe una carpeta con ese nombre en este nivel.")
        return redirect(next_url)

    CarpetaProceso.objects.create(**kwargs)
    messages.success(request, "Carpeta creada.")
    return redirect(next_url)


# ---------------------------
# Procesos: crear
# ---------------------------
class ProcesoCreateView(LoginRequiredMixin, View):
    def get(self, request, carpeta_id):
        carpeta = get_object_or_404(CarpetaProceso, pk=carpeta_id)
        if is_under_documentos(carpeta):
            messages.error(request, "No puedes crear procesos dentro de Documentos.")
            return redirect("procesos:documentos_lista")

        form = ProcesoForm()
        return render(request, "procesos/proceso_form.html", {
            "form": form,
            "carpeta": carpeta,
            "modo": "crear",
        })

    def post(self, request, carpeta_id):
        carpeta = get_object_or_404(CarpetaProceso, pk=carpeta_id)
        if is_under_documentos(carpeta):
            messages.error(request, "No puedes crear procesos dentro de Documentos.")
            return redirect("procesos:documentos_lista")

        form = ProcesoForm(request.POST)
        if not form.is_valid():
            return render(request, "procesos/proceso_form.html", {
                "form": form, "carpeta": carpeta, "modo": "crear",
            })

        carpeta_doc_padre = form.cleaned_data["carpeta_doc_padre"]
        numero = form.cleaned_data["numero_proceso"].strip()

        # Seguridad: el padre elegido debe ser documental
        if not getattr(carpeta_doc_padre, "es_documento", False) and not is_under_documentos(carpeta_doc_padre):
            messages.error(request, "Debes elegir una carpeta del árbol 'Documentos'.")
            return render(request, "procesos/proceso_form.html", {
                "form": form, "carpeta": carpeta, "modo": "crear",
            })

        with transaction.atomic():
            # 1) Crear o reutilizar la subcarpeta con el número de proceso
            last_orden = CarpetaProceso.objects.filter(padre=carpeta_doc_padre).aggregate(
                m=Max("orden")
            )["m"] or 0

            subcarpeta, creada = CarpetaProceso.objects.get_or_create(
                padre=carpeta_doc_padre,
                nombre=numero,
                defaults={"orden": last_orden + 1, "es_documento": True},
            )

            # 2) Crear el Proceso y vincular su carpeta documental
            p = form.save(commit=False)
            p.carpeta = carpeta
            p.carpeta_documentos = subcarpeta
            p.creado_por = request.user
            p.save()

        messages.success(request, "Proceso creado y carpeta documental generada.")
        # Redirige directo a la carpeta documental para subir archivos
        return redirect("procesos:carpeta_detalle", carpeta_id=carpeta.id)

# ---------------------------
# Documentos: subir / descargar
# ---------------------------
# views.py  (reemplaza el método get)
class SubirDocumentoView(LoginRequiredMixin, View):
    def get(self, request):
        carpeta_id = request.GET.get("carpeta")
        if not carpeta_id:
            messages.info(request, "Primero elige una carpeta para subir el archivo.")
            return redirect("procesos:documentos_lista")

        carpeta = get_object_or_404(CarpetaProceso, pk=carpeta_id)

        # ✅ Acepta carpeta si es documental o si está bajo el árbol 'Documentos'
        es_doc = bool(getattr(carpeta, "es_documento", False))
        if not (es_doc or is_under_documentos(carpeta)):
            messages.error(request, "Los archivos sólo se pueden subir dentro de 'Documentos'.")
            return redirect("procesos:documentos_lista")

        form = DocumentoFormSimple()
        return render(request, "procesos/subir_documento.html", {"form": form, "carpeta": carpeta})

    def post(self, request):
        carpeta_id = request.POST.get("carpeta")
        if not carpeta_id:
            messages.error(request, "Falta la carpeta de destino.")
            return redirect(request.POST.get("next") or reverse("procesos:documentos_lista"))

        carpeta = get_object_or_404(CarpetaProceso, pk=carpeta_id)


        es_doc = bool(getattr(carpeta, "es_documento", False))
        if not (es_doc or is_under_documentos(carpeta)):
            messages.error(request, "Los archivos sólo se pueden subir dentro de 'Documentos'.")
            return redirect("procesos:documentos_lista")

        form = DocumentoFormSimple(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "procesos/subir_documento.html", {"form": form, "carpeta": carpeta})

        doc = form.save(commit=False)
        doc.carpeta = carpeta
        doc.subido_por = request.user
        last = DocumentoProceso.objects.filter(carpeta=carpeta, nombre=doc.nombre).order_by("-version").first()
        doc.version = (last.version + 1) if last else 1
        doc.save()

        messages.success(request, f'Documento "{doc.nombre}" subido (v{doc.version}).')
        return redirect("procesos:carpeta_detalle", carpeta_id=carpeta.id)

def descargar(request, doc_id: int):
    """
    - Si el archivo es PDF (o imagen) => se muestra en el navegador (inline).
    - Para el resto => se fuerza la descarga (attachment).
    """
    doc = get_object_or_404(DocumentoProceso, pk=doc_id)
    if not doc.archivo:
        raise Http404("Archivo no disponible")

    path = doc.archivo.path
    if not os.path.exists(path):
        raise Http404("Archivo no encontrado en el servidor")

    # Detectar MIME por nombre (mejor que por contenido para streaming)
    mime, _ = mimetypes.guess_type(doc.archivo.name)
    mime = mime or "application/octet-stream"

    # Inline si es PDF o imagen (png/jpg/webp/gif/svg, etc.)
    inline_types = ("application/pdf",)
    is_image = mime.startswith("image/")
    is_inline = mime in inline_types or is_image

    # Nombre de archivo (con extensión real)
    filename = os.path.basename(doc.archivo.name)

    # Stream del archivo
    resp = FileResponse(open(path, "rb"), content_type=mime)

    # Content-Disposition acorde
    dispo = "inline" if is_inline else "attachment"
    # smart_str evita problemas con acentos/espacios
    resp["Content-Disposition"] = f'{dispo}; filename="{smart_str(filename)}"'

    return resp

# ---------------------------
# Detalle de carpeta
# ---------------------------
def carpeta_detalle(request, carpeta_id: int):
    carpeta = get_object_or_404(CarpetaProceso, pk=carpeta_id)

    es_documento = is_under_documentos(carpeta) or bool(getattr(carpeta, "es_documento", False))
    hijas = carpeta.hijas.all().order_by("orden", "nombre")

    page_obj = None
    docs = None
    procesos = None

    if es_documento:
        docs = carpeta.documentos.all().order_by( "-id")
        paginator = Paginator(docs, 20)
        page_obj = paginator.get_page(request.GET.get("page"))
    else:
        procesos = carpeta.procesos.all()
        q = (request.GET.get("q") or "").strip()
        if q:
            procesos = procesos.filter(
                Q(nombre__icontains=q) |
                Q(numero_proceso__icontains=q) |
                Q(ciudad__icontains=q)
            )
        procesos = procesos.order_by("-creado_en", "-id")
        paginator = Paginator(procesos, 20)
        page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "procesos/carpeta_detalle.html", {
        "carpeta": carpeta,
        "hijas": hijas,
        "es_documento": es_documento,
        "page_obj": page_obj,
        "docs": docs,
        "procesos": procesos,
    })


def dashboard(request):
    total_usuarios = User.objects.count()
    total_procesos = Proceso.objects.count()

    # Usa el campo de fecha que realmente tengas: "creado_en" es el que ya usas en carpeta_detalle
    recientes_procesos = Proceso.objects.order_by('-creado_en', '-id')[:6]

    # Para documentos, si tienes "creado" úsalo; si no, por id descendente
    try:
        recientes_documentos = DocumentoProceso.objects.order_by('-creado')[:6]
    except Exception:
        recientes_documentos = DocumentoProceso.objects.order_by('-id')[:6]

    return render(request, "dashboard.html", {
        "total_usuarios": total_usuarios,
        "total_procesos": total_procesos,
        "recientes_procesos": recientes_procesos,
        "recientes_documentos": recientes_documentos,
    })

class ProcesoDetailView(LoginRequiredMixin, DetailView):
    model = Proceso
    template_name = "procesos/proceso_detalle.html"
    context_object_name = "proceso"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["carpeta"] = getattr(self.object, "carpeta", None)
        return ctx


class ProcesoInlineUpdateView(LoginRequiredMixin, View):
    """
    Actualiza un solo campo del Proceso vía fetch() (AJAX).
    Campos permitidos: estado, observacion, fecha_revision
    """
    def post(self, request, pk):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

        field = (data.get("field") or "").strip()
        value = data.get("value", "")

        allowed = {"estado", "observacion", "fecha_revision"}
        if field not in allowed:
            return JsonResponse({"ok": False, "error": "Campo no permitido"}, status=400)

        proceso = get_object_or_404(Proceso, pk=pk)

        # Validaciones por campo
        if field == "estado":
            valid_keys = {k for k, _ in Proceso.ESTADOS}
            if value not in valid_keys:
                return JsonResponse({"ok": False, "error": "Estado inválido"}, status=400)

            proceso.estado = value
            # Si lo marcan como finalizado, limpiamos la fecha de revisión para que no genere alertas
            if value == "FIN":
                proceso.fecha_revision = None
                proceso.save(update_fields=["estado", "fecha_revision", "actualizado_en"])
            else:
                proceso.save(update_fields=["estado", "actualizado_en"])

            return JsonResponse({"ok": True})

        if field == "observacion":
            # Observación puede ser vacía
            proceso.observacion = (value or "").strip() or None
            proceso.save(update_fields=["observacion", "actualizado_en"])
            return JsonResponse({"ok": True})

        if field == "fecha_revision":
            # value esperado en formato YYYY-MM-DD o vacío
            if (value or "").strip():
                d = parse_date(value)
                if not d:
                    return JsonResponse({"ok": False, "error": "Fecha inválida"}, status=400)
                proceso.fecha_revision = d
            else:
                proceso.fecha_revision = None
            proceso.save(update_fields=["fecha_revision", "actualizado_en"])
            return JsonResponse({"ok": True})

        return JsonResponse({"ok": False, "error": "Sin cambios"}, status=400)

class ProcesoUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        proceso = get_object_or_404(Proceso, pk=pk)
        if is_under_documentos(proceso.carpeta):
            messages.error(request, "No puedes editar procesos dentro de 'Documentos'.")
            return redirect("procesos:documentos_lista")
        form = ProcesoForm(instance=proceso)
        next_url = request.GET.get("next") or reverse("procesos:carpeta_detalle", args=[proceso.carpeta_id])
        return render(request, "procesos/proceso_form.html", {
            "form": form, "carpeta": proceso.carpeta, "proceso": proceso,
            "modo": "editar", "next_url": next_url,
        })

    def post(self, request, pk):
        proceso = get_object_or_404(Proceso, pk=pk)
        if is_under_documentos(proceso.carpeta):
            messages.error(request, "No puedes editar procesos dentro de 'Documentos'.")
            return redirect("procesos:documentos_lista")

        form = ProcesoForm(request.POST, instance=proceso)
        if form.is_valid():
            proceso = form.save()
            if proceso.estado == "FIN" and proceso.fecha_revision is not None:
                proceso.fecha_revision = None
                proceso.save(update_fields=["fecha_revision", "actualizado_en"])

            messages.success(request, "Proceso actualizado correctamente.")
            next_url = request.POST.get("next") or reverse("procesos:carpeta_detalle", args=[proceso.carpeta_id])
            return redirect(next_url)

        next_url = request.POST.get("next") or reverse("procesos:carpeta_detalle", args=[proceso.carpeta_id])
        return render(request, "procesos/proceso_form.html", {
            "form": form, "carpeta": proceso.carpeta, "proceso": proceso,
            "modo": "editar", "next_url": next_url,
        })
class ProcesoDeleteView(LoginRequiredMixin, View):
    def get(self, request, pk):
        proceso = get_object_or_404(Proceso, pk=pk)
        return render(request, "procesos/proceso_confirm_delete.html", {
            "proceso": proceso,
            "carpeta": proceso.carpeta,
            "next_url": request.GET.get("next") or reverse("procesos:carpeta_detalle", args=[proceso.carpeta_id]),
        })

    def post(self, request, pk):
        proceso = get_object_or_404(Proceso, pk=pk)
        next_url = request.POST.get("next") or reverse("procesos:carpeta_detalle", args=[proceso.carpeta_id])
        nombre = proceso.nombre
        proceso.delete()
        messages.success(request, f"Proceso “{nombre}” eliminado.")
        return redirect(next_url)



from django.views.decorators.http import require_POST

@login_required
@require_POST
def api_crear_carpeta_documental(request):
    import json
    data = json.loads(request.body.decode("utf-8"))
    nombre = (data.get("nombre") or "").strip()
    modo = (data.get("modo") or "root").strip()  # "root" | "selected"
    padre_id = data.get("padre_id")

    if not nombre:
        return JsonResponse({"ok": False, "error": "El nombre es obligatorio."}, status=400)

    padre = None
    if modo == "selected" and padre_id:
        padre = get_object_or_404(CarpetaProceso, pk=padre_id)
        if not (getattr(padre, "es_documento", False) or is_under_documentos(padre)):
            return JsonResponse({"ok": False, "error": "Solo en el árbol 'Documentos'."}, status=400)

    if CarpetaProceso.objects.filter(padre=padre, nombre__iexact=nombre).exists():
        return JsonResponse({"ok": False, "error": "Ya existe una carpeta con ese nombre."}, status=400)

    last = CarpetaProceso.objects.filter(padre=padre).aggregate(m=Max("orden"))["m"] or 0
    carpeta = CarpetaProceso.objects.create(
        nombre=nombre, padre=padre, orden=last + 1, es_documento=True
    )
    return JsonResponse({"ok": True, "id": carpeta.id, "nombre": carpeta.nombre})
@login_required
@require_POST
def agregar_observacion(request, pk):
    proceso = get_object_or_404(Proceso, pk=pk)

    # Misma regla de seguridad que usas en otras vistas
    if is_under_documentos(proceso.carpeta):
        messages.error(request, "No puedes editar procesos dentro de 'Documentos'.")
        return redirect("procesos:documentos_lista")

    texto = (request.POST.get("observacion") or "").strip()
    proceso.observacion = texto or None
    proceso.save(update_fields=["observacion", "actualizado_en"])

    messages.success(request, "Observación guardada.")
    return redirect("procesos:proceso_detalle", pk=pk)
# --- imports necesarios (al inicio del archivo, si aún no están) ---
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import render, redirect

from .models import CarpetaProceso, DocumentoProceso
# -------------------------------------------------------------------


class DocumentosBuscarView(LoginRequiredMixin, View):
    """
    Búsqueda global en TODO el árbol documental:
      - Carpetas documentales (CarpetaProceso.es_documento=True)
      - Documentos (DocumentoProceso)
    Resultados paginados por separado (carpetas y documentos).
    """
    template_name = "procesos/buscar_documentos.html"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q:
            messages.info(request, "Ingresa un término de búsqueda.")
            return redirect("procesos:documentos_lista")

        # Carpetas en el árbol documental (excluye el contenedor raíz 'Documentos')
        carpetas_qs = (
            CarpetaProceso.objects
            .filter(es_documento=True, nombre__icontains=q)
            .exclude(nombre__iexact="Documentos")
            .annotate(
                cant_subs=Count("hijas", distinct=True),
                cant_docs=Count("documentos", distinct=True),
            )
            .order_by("nombre")
        )

        # Documentos por nombre visible o nombre de archivo
        documentos_qs = (
            DocumentoProceso.objects
            .filter(Q(nombre__icontains=q) | Q(archivo__icontains=q))
            .select_related("carpeta")
            .order_by("-id")
        )

        # Paginación independiente para carpetas y documentos
        pc = request.GET.get("pc")  # página de carpetas
        pd = request.GET.get("pd")  # página de documentos
        page_c = Paginator(carpetas_qs, 30).get_page(pc)
        page_d = Paginator(documentos_qs, 30).get_page(pd)

        ctx = {
            "q": q,
            "page_c": page_c,
            "page_d": page_d,
            "total_c": carpetas_qs.count(),
            "total_d": documentos_qs.count(),
        }
        return render(request, self.template_name, ctx)
