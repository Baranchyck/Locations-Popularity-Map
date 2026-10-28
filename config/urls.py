from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    # Login/logout links for the DRF browsable API.
    path("api-auth/", include("rest_framework.urls")),
]
