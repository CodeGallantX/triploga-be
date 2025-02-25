from django.urls import path
from .views import TripAPI

urlpatterns = [
    path("trip/", TripAPI.as_view(), name='trip-api')
]
