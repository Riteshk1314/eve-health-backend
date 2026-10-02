from django.urls import path

from . import views

urlpatterns = [
    path("centres/", views.centre_list, name="centre-list"),
    path("centres/<int:centre_id>/", views.centre_detail, name="centre-detail"),
    path("tests/", views.test_list, name="test-list"),
    path("tests/<int:test_id>/", views.test_detail, name="test-detail"),
    path("centre-tests/", views.centre_test_list, name="centre-test-list"),
    path("centre-tests/<int:offering_id>/", views.centre_test_detail, name="centre-test-detail"),
]
