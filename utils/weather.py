# utils/weather.py
import requests
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# District coordinates for Kerala (approximate)
DISTRICT_COORDINATES = {
    "Thiruvananthapuram": {"lat": 8.5241, "lon": 76.9366},
    "Kollam": {"lat": 8.8932, "lon": 76.6141},
    "Pathanamthitta": {"lat": 9.2648, "lon": 76.7870},
    "Alappuzha": {"lat": 9.4981, "lon": 76.3388},
    "Kottayam": {"lat": 9.5916, "lon": 76.5222},
    "Idukki": {"lat": 9.9189, "lon": 77.1025},
    "Ernakulam": {"lat": 9.9816, "lon": 76.2999},
    "Thrissur": {"lat": 10.5276, "lon": 76.2144},
    "Palakkad": {"lat": 10.7867, "lon": 76.6548},
    "Malappuram": {"lat": 11.0732, "lon": 76.0740},
    "Kozhikode": {"lat": 11.2588, "lon": 75.7804},
    "Wayanad": {"lat": 11.6850, "lon": 76.1320},
    "Kannur": {"lat": 11.8745, "lon": 75.3704},
    "Kasaragod": {"lat": 12.4996, "lon": 74.9869},
}

def get_weather_for_district(district_name):
    """
    Fetch weather data for a Kerala district using OpenWeatherMap API
    """
    try:
        # Get coordinates for the district
        coords = DISTRICT_COORDINATES.get(district_name)
        if not coords:
            logger.error(f"Coordinates not found for district: {district_name}")
            return None
        
        # Get API key from settings (you'll need to add this to your settings.py)
        api_key = getattr(settings, 'OPENWEATHER_API_KEY', None)
        if not api_key:
            logger.error("OpenWeather API key not configured")
            return None
        
        # API URL for current weather
        url = f"https://api.openweathermap.org/data/2.5/weather"
        
        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': api_key,
            'units': 'metric',  # Use metric units (Celsius, m/s, etc.)
            'lang': 'en'
        }
        
        # Make API call
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Process the data [citation:3]
            weather_info = {
                'temperature': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': round(data['wind']['speed'] * 3.6, 1),  # Convert m/s to km/h
                'wind_direction': get_wind_direction(data['wind'].get('deg', 0)),
                'description': data['weather'][0]['description'].title(),
                'main_weather': data['weather'][0]['main'],
                'icon': data['weather'][0]['icon'],
                'icon_url': f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
                'clouds': data['clouds']['all'],
                'visibility': round(data['visibility'] / 1000, 1) if 'visibility' in data else None,  # Convert to km
                'rain_1h': data.get('rain', {}).get('1h', 0),
                'district': district_name,
                'timestamp': datetime.fromtimestamp(data['dt']).strftime('%I:%M %p'),
                'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%I:%M %p'),
                'sunset': datetime.fromtimestamp(data['sys']['sunset']).strftime('%I:%M %p'),
            }
            
            # Calculate rain probability based on rain data and clouds
            weather_info['rain_probability'] = calculate_rain_probability(
                weather_info['rain_1h'],
                weather_info['clouds'],
                weather_info['main_weather']
            )
            
            return weather_info
            
        else:
            logger.error(f"Weather API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return None
    except KeyError as e:
        logger.error(f"Data parsing error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return None

def get_wind_direction(degrees):
    """Convert wind degrees to compass direction"""
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    index = round(degrees / 22.5) % 16
    return directions[index]

def calculate_rain_probability(rain_1h, cloud_cover, main_weather):
    """Calculate rain probability based on current conditions"""
    probability = 0
    
    # Base probability on cloud cover
    probability += min(cloud_cover * 0.6, 40)  # Max 40% from clouds
    
    # Add probability if it's currently raining
    if rain_1h > 0:
        probability += min(rain_1h * 20, 40)  # Max 40% from current rain
    
    # Add probability based on weather type
    if main_weather in ['Rain', 'Thunderstorm', 'Drizzle']:
        probability += 30
    
    # Cap at 95% (never 100% in weather forecasts)
    return min(int(probability), 95)