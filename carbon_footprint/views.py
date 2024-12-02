from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import RideRecordForm
from django.db import models
from .models import RideRecord, UserProfile

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from .models import UserProfile

def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create associated UserProfile
            UserProfile.objects.create(user=user)
            
            # Authenticate and login
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            
            if user is not None:
                login(request, user)
                messages.success(request, 'Account created successfully!')
                return redirect('record_ride')  # Redirect to main app page
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('record_ride')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def profile_view(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        user_profile = UserProfile.objects.create(user=request.user)
    
    # Get eco impact details
    from .models import get_user_eco_impact
    eco_impact = get_user_eco_impact(request.user)
    
    return render(request, 'accounts/profile.html', {
        'profile': user_profile,
        'eco_impact': eco_impact
    })

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

@login_required
def record_ride(request):
    if request.method == 'POST':
        form = RideRecordForm(request.POST)
        if form.is_valid():
            ride = form.save(commit=False)
            ride.user = request.user
            ride.save()
            return redirect('ride_results', ride_id=ride.id)
    else:
        form = RideRecordForm()
    return render(request, 'carbon_tracker/index.html', {'form': form})

@login_required
def ride_results(request, ride_id):
    ride = RideRecord.objects.get(id=ride_id)
    total_user_savings = RideRecord.objects.filter(user=request.user).aggregate(total=models.Sum('co2_savings'))['total'] or 0
    return render(request, 'carbon_tracker/results.html', {
        'ride': ride,
        'total_savings': total_user_savings
    })


# Extra helper function for emissions comparison
def compare_emissions_by_vehicle():
    """
    Compare average emissions across different vehicle types
    """
    emissions_by_vehicle = {}
    for fuel_type in ['petrol', 'diesel', 'ev']:
        rides = RideRecord.objects.filter(fuel_type=fuel_type)
        if rides.exists():
            avg_emissions = rides.aggregate(
                avg_emissions=models.Avg('co2_emissions')
            )['avg_emissions']
            emissions_by_vehicle[fuel_type] = avg_emissions
    
    return emissions_by_vehicle