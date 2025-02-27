from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse, JsonResponse
import io
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from .models import Trip
from .serializers import TripSerializer
from datetime import datetime

# Use OpenRouteService API key if available, otherwise use the free tier
OPENROUTESERVICE_API_KEY = getattr(settings, "OPENROUTESERVICE_API_KEY", "")


class TripAPI(APIView):
    """
    Handles creating and retrieving trip records using OpenRouteService for route calculations.
    """

    def post(self, request):
        """
        Create a new trip record, calculate the route using OpenRouteService, and validate the 70-hour/8-day rule.
        """
        serializer = TripSerializer(data=request.data)
        
        if serializer.is_valid():
            # Extract trip details
            current_location = serializer.validated_data.get('current_location')
            pickup = serializer.validated_data.get('pickup_location')
            dropoff = serializer.validated_data.get('dropoff_location')
            current_cycle_used = serializer.validated_data.get('current_cycle_used', 0)

            # Validate that locations exist
            if not current_location or not pickup or not dropoff:
                return Response({"error": "Current location, pickup, and dropoff locations are required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Geocode current, pickup, and dropoff locations
                geocode_url = "https://api.openrouteservice.org/geocode/search"
                headers = {}
                if OPENROUTESERVICE_API_KEY:
                    headers["Authorization"] = OPENROUTESERVICE_API_KEY

                current_geocode = requests.get(geocode_url, params={"text": current_location}, headers=headers).json()
                pickup_geocode = requests.get(geocode_url, params={"text": pickup}, headers=headers).json()
                dropoff_geocode = requests.get(geocode_url, params={"text": dropoff}, headers=headers).json()

                if not current_geocode.get("features") or not pickup_geocode.get("features") or not dropoff_geocode.get("features"):
                    return Response({"error": "Could not geocode locations. Please check the addresses."}, status=status.HTTP_400_BAD_REQUEST)

                current_coords = current_geocode["features"][0]["geometry"]["coordinates"]
                pickup_coords = pickup_geocode["features"][0]["geometry"]["coordinates"]
                dropoff_coords = dropoff_geocode["features"][0]["geometry"]["coordinates"]

                # Get route details from current to pickup
                directions_url = "https://api.openrouteservice.org/v2/directions/driving-car/json"

                directions_params_current_to_pickup = {
                    "coordinates": [[current_coords[0], current_coords[1]], [pickup_coords[0], pickup_coords[1]]]
                }

                directions_current_to_pickup = requests.post(directions_url, json=directions_params_current_to_pickup, headers=headers).json()

                # Get route details from pickup to dropoff
                directions_params_pickup_to_dropoff = {
                    "coordinates": [[pickup_coords[0], pickup_coords[1]], [dropoff_coords[0], dropoff_coords[1]]]
                }

                directions_pickup_to_dropoff = requests.post(directions_url, json=directions_params_pickup_to_dropoff, headers=headers).json()


                if not directions_current_to_pickup.get("routes") or not directions_pickup_to_dropoff.get("routes"):
                    return Response({"error": "No route found. Please check the locations."}, status=status.HTTP_400_BAD_REQUEST)

                # Extract route details
                distance_current_to_pickup_km = directions_current_to_pickup['routes'][0]['summary']['distance'] / 1000
                duration_current_to_pickup_hrs = directions_current_to_pickup['routes'][0]['summary']['duration'] / 3600

                distance_pickup_to_dropoff_km = directions_pickup_to_dropoff['routes'][0]['summary']['distance'] / 1000
                duration_pickup_to_dropoff_hrs = directions_pickup_to_dropoff['routes'][0]['summary']['duration'] / 3600

                total_distance_km = distance_current_to_pickup_km + distance_pickup_to_dropoff_km
                total_duration_hrs = duration_current_to_pickup_hrs + duration_pickup_to_dropoff_hrs + 2  # Add 2 hours for pickup and dropoff

                # Validate the 70-hour/8-day rule
                if current_cycle_used + total_duration_hrs > 70:
                    return Response({"error": "Exceeded 70-hour driving limit. Rest required."}, status=status.HTTP_400_BAD_REQUEST)

                # Calculate fueling stops (1 stop every 1,000 miles ≈ 1,609 km)
                fueling_stops = int(total_distance_km // 1609)

                # Save the trip
                trip = serializer.save()

                # Return trip details along with calculated route and fueling stops
                return Response({
                    "trip": serializer.data,
                    "route": {
                        "current_to_pickup": {
                            "distance": f"{distance_current_to_pickup_km:.2f} km",
                            "duration": f"{duration_current_to_pickup_hrs:.2f} hrs",
                            "steps": [step.get("instruction", "No instruction") for step in directions_current_to_pickup['routes'][0]['segments'][0]['steps']]
                        },
                        "pickup_to_dropoff": {
                            "distance": f"{distance_pickup_to_dropoff_km:.2f} km",
                            "duration": f"{duration_pickup_to_dropoff_hrs:.2f} hrs",
                            "steps": [step.get("instruction", "No instruction") for step in directions_pickup_to_dropoff['routes'][0]['segments'][0]['steps']]
                        },
                        "total_distance": f"{total_distance_km:.2f} km",
                        "total_duration": f"{total_duration_hrs:.2f} hrs",
                        "fueling_stops": fueling_stops
                    },
                    "current_cycle_used": current_cycle_used,
                    "hours_remaining": 70 - (current_cycle_used + total_duration_hrs)
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk=None):
        """
        Retrieve all trips or a single trip by ID.
        """
        if pk:
            # Retrieve a single trip by ID
            try:
                trip = Trip.objects.get(id=pk)
                serializer = TripSerializer(trip)
                return Response(serializer.data)
            except Trip.DoesNotExist:
                return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Retrieve all trips
            trips = Trip.objects.all()
            serializer = TripSerializer(trips, many=True)
            return Response(serializer.data)


class ELDLogAPI(APIView):
    """
    Generates and returns an ELD log sheet as a PDF file based on trip details.
    """

    def get(self, request, trip_id):
        """
        Generate a PDF ELD log for a specific trip and return it as a downloadable file.
        """
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

        # Create a buffer for the PDF
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # PDF Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(80, 750, "Driver's Daily Log (24 Hours)")

        # Date, From, To
        c.setFont("Helvetica", 12)
        c.drawString(80, 730, f"Date: {datetime.now().strftime('%m/%d/%Y')}")
        c.drawString(80, 710, f"From: {trip.pickup_location}")
        c.drawString(80, 690, f"To: {trip.dropoff_location}")

        # Hours of Service Log
        c.drawString(80, 670, "---")
        c.drawString(80, 650, "Hours of Service Log")
        c.drawString(80, 630, "| Hour  | 12 AM | 1 AM | 2 AM | 3 AM | 4 AM | 5 AM | 6 AM | 7 AM | 8 AM | 9 AM | 10 AM | 11 AM |")
        c.drawString(80, 610, "|-------|------|------|------|------|------|------|------|------|------|------|------|------|")
        c.drawString(80, 590, "| Status | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ |")
        c.drawString(80, 570, "| Hour  | 12 PM | 1 PM | 2 PM | 3 PM | 4 PM | 5 PM | 6 PM | 7 PM | 8 PM | 9 PM | 10 PM | 11 PM |")
        c.drawString(80, 550, "| Status | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ |")

        # Status Codes
        c.drawString(80, 530, "Status Codes:")
        c.drawString(80, 510, "1. Off Duty (OFF)")
        c.drawString(80, 490, "2. Sleeper Berth (SB)")
        c.drawString(80, 470, "3. Driving (D)")
        c.drawString(80, 450, "4. On Duty (Not Driving) (ON)")

        # Recap Summary
        c.drawString(80, 430, "---")
        c.drawString(80, 410, "Recap Summary")
        c.drawString(80, 390, f"- On Duty Hours Today: {trip.current_cycle_used} hrs")
        c.drawString(80, 370, f"- Total Hours in Last 7 Days (70-hour rule): {trip.current_cycle_used} hrs")
        c.drawString(80, 350, f"- Total Hours in Last 8 Days (60-hour rule): {trip.current_cycle_used} hrs")
        c.drawString(80, 330, "- If 34-Hour Reset Taken, Available Hours: _______________")

        # Driver's Signature
        c.drawString(80, 310, "---")
        c.drawString(80, 290, "Driver's Signature: ________________________")
        c.drawString(80, 270, "Date: _______________")

        c.showPage()
        c.save()
        
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"ELD_Log_Trip_{trip.id}.pdf")