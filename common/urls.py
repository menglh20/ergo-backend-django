from django.contrib import admin
from django.urls import path
from django.urls.conf import include

urlpatterns = [
    path("image/", include("image.urls")),
]
