from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('lots/', views.lot_list, name='lot_list'),
    path('lots/new/', views.lot_create, name='lot_create'),
    path('lots/<int:pk>/', views.lot_detail, name='lot_detail'),
    path('lots/<int:pk>/edit/', views.lot_edit, name='lot_edit'),
    path('lots/<int:lot_pk>/items/new/', views.unit_create, name='unit_create'),
    path('units/', views.unit_list, name='unit_list'),
    path('units/<int:pk>/', views.unit_detail, name='unit_detail'),
    path('levels/', views.inventory_levels, name='inventory_levels'),
    path('locations/', views.location_list, name='location_list'),
    path('locations/new/', views.location_create, name='location_create'),
    path('upc-lookup/', views.upc_lookup, name='upc_lookup'),
]
