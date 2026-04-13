from django.urls import path
from faces import views

urlpatterns = [
    path('', views.faces_list, name='faces_list'),
    path('enroll/', views.enroll_person, name='faces_enroll'),
    path('<str:person_id>/delete/', views.delete_person, name='faces_delete'),
]
