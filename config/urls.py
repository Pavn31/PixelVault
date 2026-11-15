from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import include, path


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("encoder/", TemplateView.as_view(template_name="encoder.html"), name="encoder"),
    path("decoder/", TemplateView.as_view(template_name="decoder.html"), name="decoder"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
]
