from django.urls import re_path

from .views import AskSqlView

# Aceita /api/v1/ask_sql e /api/v1/ask_sql/.
urlpatterns = [
    re_path(r"^ask_sql/?$", AskSqlView.as_view(), name="ask_sql"),
]
