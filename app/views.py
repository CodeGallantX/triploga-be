from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse
import googlemaps
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Trip
from .serializers import TripSerializer


# Initialize Google Maps API client
gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)


class TripAPI(APIView):
    """
    Handles creating and retrieving trip records.
    """

    def post(self, request):
        """
        Create a new trip record and calculate the route.
        """
        serializer = TripSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            
            # Extract trip details
            pickup = serializer.validated_data.get('pickup_location')
            dropoff = serializer.validated_data.get('dropoff_location')

            # Validate that locations exist
            if not pickup or not dropoff:
                return Response({"error": "Pickup and dropoff locations are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Get route details from Google Maps API
            directions = gmaps.directions(pickup, dropoff, mode="driving")
            
            if not directions:
                return Response({"error": "No route found. Please check the locations."}, status=status.HTTP_400_BAD_REQUEST)

            # Extract route details
            route_info = {
                "distance": directions[0]['legs'][0]['distance']['text'],
                "duration": directions[0]['legs'][0]['duration']['text'],
                "start_address": directions[0]['legs'][0]['start_address'],
                "end_address": directions[0]['legs'][0]['end_address'],
                "steps": [step['html_instructions'] for step in directions[0]['legs'][0]['steps']]
            }

            # Return trip details along with calculated route
            return Response({
                "trip": serializer.data,
                "route": route_info
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """
        Retrieve all trips.
        """
        trips = Trip.objects.all()
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class ELDLogAPI(APIView):
    """
    Generates and returns an ELD log sheet as a PDF file.
    """

    def get(self, request):
        """
        Generate a PDF ELD log and return it as a downloadable file.
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # PDF Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "Driver's Daily ELD Log")

        # Basic log info
        c.setFont("Helvetica", 12)
        c.drawString(100, 730, "Total Hours: 70/8 days")
        c.drawString(100, 710, "Hours Remaining: 34")
        c.line(100, 700, 500, 700)  # Divider Line
        c.drawString(100, 680, "Log Entries:")

        # Example log entries
        y_position = 660
        for i in range(1, 5):
            c.drawString(100, y_position, f"Entry {i}: Driving {i * 2} hrs")
            y_position -= 20

        c.showPage()
        c.save()
        
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename="ELD_Log.pdf")
