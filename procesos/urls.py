# apps/procesos/urls.py
from django.urls import path
from . import views

app_name = "procesos"

urlpatterns = [
    # Raíces y carpetas
    path("", views.CarpetaListView.as_view(), name="lista"),
    path("documentos/", views.DocumentosListView.as_view(), name="documentos_lista"),
    path("carpeta/nueva/", views.crear_carpeta, name="crear_carpeta"),
    path("carpeta/<int:carpeta_id>/", views.carpeta_detalle, name="carpeta_detalle"),
    path("documentos/buscar/", views.DocumentosBuscarView.as_view(), name="documentos_buscar"),
    # Procesos
    path("proceso/nuevo/<int:carpeta_id>/", views.ProcesoCreateView.as_view(), name="proceso_nuevo"),
    path("proceso/<int:pk>/", views.ProcesoDetailView.as_view(), name="proceso_detalle"),
    path("proceso/<int:pk>/editar/", views.ProcesoUpdateView.as_view(), name="proceso_editar"),      # <- ESTA
    path("proceso/<int:pk>/eliminar/", views.ProcesoDeleteView.as_view(), name="proceso_eliminar"),  # <- Y ESTA
    path("proceso/<int:pk>/inline-update/", views.ProcesoInlineUpdateView.as_view(), name="proceso_inline_update"),
    path("proceso/<int:pk>/agregar-observacion/", views.agregar_observacion, name="agregar_observacion"),

    # Documentos
    path("documentos/subir/", views.SubirDocumentoView.as_view(), name="subir_documento"),
    path("documento/<int:doc_id>/descargar/", views.descargar, name="descargar"),
    path("api/carpeta-doc/new/", views.api_crear_carpeta_documental, name="api_carpeta_doc_crear"),
]
