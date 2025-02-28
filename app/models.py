from django.db import models

# Create your models here.
class Trip(models.Model):
    current_location = models.CharField(max_length=100)
    pickup_location = models.CharField(max_length=100)
    dropoff_location = models.CharField(max_length=100)
    current_cycle_used = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Trip from {self.pickup_location} to {self.dropoff_location}"