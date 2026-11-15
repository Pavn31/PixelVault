from django.urls import path

from .views import csrf, decode, encode, health

urlpatterns = [
    path("health/", health, name="health"),
    path("csrf/", csrf, name="csrf"),
    path("encode/", encode, name="encode"),
    path("decode/", decode, name="decode"),
]
