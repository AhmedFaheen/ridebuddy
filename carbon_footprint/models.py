from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_rides = models.IntegerField(default=0)
    total_co2_saved = models.FloatField(default=0)
    total_distance = models.FloatField(default=0)
    preferred_vehicle_type = models.CharField(max_length=20, null=True, blank=True)
    
    def update_profile_stats(self, ride):
        """Update user profile statistics after each ride"""
        self.total_rides += 1
        self.total_distance += ride.distance
        self.total_co2_saved += ride.co2_savings
        
        # Update preferred vehicle type
        if not self.preferred_vehicle_type:
            self.preferred_vehicle_type = ride.fuel_type
        else:
            # Simple logic to determine preferred vehicle type
            vehicle_counts = {
                'petrol': 0,
                'diesel': 0,
                'ev': 0
            }
            recent_rides = RideRecord.objects.filter(user=self.user).order_by('-ride_time')[:10]
            for recent_ride in recent_rides:
                vehicle_counts[recent_ride.fuel_type] += 1
            
            # Update preferred vehicle type based on most frequent
            self.preferred_vehicle_type = max(vehicle_counts, key=vehicle_counts.get)
        
        self.save()

class RideRecord(models.Model):
    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('ev', 'Electric Vehicle')
    ]
    
    TRAFFIC_CHOICES = [
        ('light', 'Light Traffic'),
        ('moderate', 'Moderate Traffic'), 
        ('heavy', 'Heavy Traffic')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    distance = models.FloatField(help_text="Distance in kilometers")
    fuel_type = models.CharField(max_length=20, choices=FUEL_CHOICES)
    num_riders = models.IntegerField(default=1, help_text="Number of passengers")
    traffic_condition = models.CharField(max_length=20, choices=TRAFFIC_CHOICES)
    idle_time = models.IntegerField(default=0, help_text="Idle time in minutes")
    ride_time = models.DateTimeField()
    co2_emissions = models.FloatField(null=True, blank=True)
    co2_savings = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Calculate emissions and savings before saving
        self.calculate_carbon_impact()
        
        # Update user profile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.update_profile_stats(self)
        
        super().save(*args, **kwargs)

    def calculate_carbon_impact(self):
        BASE_EMISSIONS = 251  # grams per kilometer for petrol vehicles
        IDLE_EMISSIONS_RATE = 10  # grams per minute for idle time

        # Fuel type adjustments
        FUEL_ADJUSTMENTS = {
            'petrol': 1.0,
            'diesel': 1.15,
            'ev': 0.0  # EVs have no direct emissions
        }

        # Traffic condition adjustments
        TRAFFIC_ADJUSTMENTS = {
            'light': 1.0,
            'moderate': 1.1,
            'heavy': 1.2
        }

        # Nighttime discount (5% reduction for rides between 8 PM to 6 AM)
        nighttime_discount = 0.95 if self.ride_time and (20 <= self.ride_time.hour or self.ride_time.hour < 6) else 1.0

        # Step 1: Check for EV (Zero emissions for EV driving and idle)
        if self.fuel_type == 'ev':
            base_emissions = 0  # No CO2 emissions for EV (both driving and idle)
            idle_emissions = 0  # No idle emissions for EVs
        else:
            # Step 1 (non-EV): Calculate fuel and traffic-adjusted emissions
            fuel_adjustment = FUEL_ADJUSTMENTS.get(self.fuel_type, 1.0)
            traffic_adjustment = TRAFFIC_ADJUSTMENTS.get(self.traffic_condition, 1.0)
            
            base_emissions = self.distance * BASE_EMISSIONS * fuel_adjustment * traffic_adjustment
            # Idle emissions for petrol/diesel vehicles
            idle_emissions = self.idle_time * IDLE_EMISSIONS_RATE

        # Step 2: Divide emissions by riders and apply nighttime discount
        if self.num_riders > 0:
            emissions_per_rider = (base_emissions / self.num_riders) * nighttime_discount
        else:
            emissions_per_rider = base_emissions * nighttime_discount

        # Step 3: Calculate total emissions
        total_emissions = emissions_per_rider + idle_emissions

        # Ensure no negative emissions and return
        self.co2_emissions = max(total_emissions, 0)
        self.co2_savings = max(base_emissions - total_emissions, 0)
        
        return self.co2_emissions, self.co2_savings

    
def get_user_eco_impact(user):
    """
    Retrieve comprehensive eco-impact statistics for a user
    """
    profile = UserProfile.objects.get(user=user)
    total_rides = RideRecord.objects.filter(user=user).count()
    total_distance = RideRecord.objects.filter(user=user).aggregate(
        total_distance=Sum('distance')
    )['total_distance'] or 0
    
    vehicle_breakdown = RideRecord.objects.filter(user=user).values('fuel_type').annotate(
        count=models.Count('fuel_type')
    )
    
    return {
        'total_rides': total_rides,
        'total_co2_saved': profile.total_co2_saved,
        'total_distance': total_distance,
        'preferred_vehicle': profile.preferred_vehicle_type,
        'vehicle_breakdown': list(vehicle_breakdown)
    }