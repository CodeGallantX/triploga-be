from django.urls import path
from .views import TripAPI, ELDLogAPI  # Import the views

urlpatterns = [
    path('trips/', TripAPI.as_view(), name='trip-api'),  # For listing all trips and creating a new trip
    path('trips/<int:pk>/', TripAPI.as_view(), name='trip-detail-api'),  # For retrieving a single trip
    path('eld-log/<int:trip_id>/', ELDLogAPI.as_view(), name='eld-log-api'),  # ELDLogAPI for generating logs
]