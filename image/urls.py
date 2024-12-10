from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("generate/", views.generate),
    path("edit/", views.edit),
    path("hello", views.hello)
]
