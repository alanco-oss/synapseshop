"""
URL configuration for products project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from . import health, openapi

urlpatterns = [
    path('admin/', admin.site.urls),
    # Rota de healthcheck do mini-backend (Aula 11)
    path('health', health.health, name='health'),
    # Documentação interativa da API (Aula 13)
    path('api/v1/schema/', openapi.schema, name='openapi-schema'),
    path('api/v1/docs/', openapi.docs, name='swagger-ui'),
    path('api/v1/redoc/', openapi.redoc, name='redoc'),
    path('api/v1/', include('catalog.urls')),
    path('api/v1/', include('orders.urls')),
    path('api/v1/', include('assist.urls')),
    path('api/v1/', include('ask_sql.urls')),
]
