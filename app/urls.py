from django.urls import path
from .views import TripAPI, ELDLogAPI  # Import the views

urlpatterns = [
    path('trips/', TripAPI.as_view(), name='trip-api'),  # TripAPI for creating and retrieving trips
    path('eld-log/<int:trip_id>/', ELDLogAPI.as_view(), name='eld-log-api'),  # ELDLogAPI for generating logs
]
