from django.urls import re_path

from .views import AssistView

# Aceita /api/v1/assist e /api/v1/assist/ (a spec usa a forma sem barra).
urlpatterns = [
    re_path(r"^assist/?$", AssistView.as_view(), name="assist"),
]