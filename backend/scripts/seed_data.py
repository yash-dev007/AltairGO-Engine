"""
seed_data.py — Populate the database with real Indian travel destinations,
attractions, hotels, and sample users/trips so the dashboard shows live data.

Usage:
    python -m backend.scripts.seed_data
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app import create_app
from backend.database import db
from backend.models import (
    Country, State, Destination, Attraction, HotelPrice,
    User, Trip, AnalyticsEvent, EngineSetting
)
from werkzeug.security import generate_password_hash

app = create_app()

TRAVELERS = ["solo_male", "solo_female", "couple", "family", "group"]

# ── Destinations payload ──────────────────────────────────────────────────────

DESTINATIONS = [
    {
        "state": "Rajasthan",
        "name": "Jaipur",
        "slug": "jaipur",
        "desc": "The Pink City — regal forts, vibrant bazaars, and royal heritage.",
        "description": "Jaipur, capital of Rajasthan, is famous for its stunning pink-painted buildings, grand forts, and opulent palaces. The city blends Mughal and Rajput architectural styles in monuments like Amber Fort and City Palace.",
        "location": "Rajasthan, India",
        "price_str": "₹3,500/day",
        "estimated_cost_per_day": 3500,
        "rating": 4.6,
        "tag": "Heritage",
        "lat": 26.9124, "lng": 75.7873,
        "highlights": ["Amber Fort", "City Palace", "Hawa Mahal", "Jantar Mantar"],
        "best_time_months": ["oct", "nov", "dec", "jan", "feb"],
        "vibe_tags": ["heritage", "culture", "royal", "architecture"],
        "popularity_score": 92,
        "budget_category": "mid-range",
        "attractions": [
            {
                "name": "Amber Fort",
                "description": "Magnificent hilltop fort with stunning views over Maota Lake, blend of Hindu and Mughal architecture.",
                "entry_cost": 550, "duration": "2-3 hours", "rating": 4.7, "type": "fort",
                "latitude": 26.9855, "longitude": 75.8513,
                "popularity_score": 95, "avg_visit_duration_hours": 2.5,
                "best_visit_time_hour": 9, "budget_category": "mid-range",
                "seasonal_score": {"oct": 95, "nov": 95, "dec": 90, "jan": 95, "feb": 90, "jun": 40, "jul": 35},
            },
            {
                "name": "Hawa Mahal",
                "description": "Palace of Winds with 953 intricately carved windows — an iconic pink sandstone facade.",
                "entry_cost": 200, "duration": "1 hour", "rating": 4.5, "type": "palace",
                "latitude": 26.9239, "longitude": 75.8267,
                "popularity_score": 88, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 8, "budget_category": "budget",
                "seasonal_score": {"oct": 90, "nov": 90, "dec": 85, "jan": 90, "jun": 50},
            },
            {
                "name": "City Palace",
                "description": "Royal complex with museums, courtyards, and galleries still partially inhabited by the royal family.",
                "entry_cost": 700, "duration": "2 hours", "rating": 4.6, "type": "palace",
                "latitude": 26.9258, "longitude": 75.8237,
                "popularity_score": 85, "avg_visit_duration_hours": 2.0,
                "best_visit_time_hour": 10, "budget_category": "mid-range",
                "seasonal_score": {"oct": 90, "nov": 90, "dec": 88, "jan": 90, "jun": 55},
            },
            {
                "name": "Jantar Mantar",
                "description": "UNESCO World Heritage astronomical observatory with 19 instruments built in the 18th century.",
                "entry_cost": 200, "duration": "1-1.5 hours", "rating": 4.3, "type": "heritage",
                "latitude": 26.9249, "longitude": 75.8237,
                "popularity_score": 75, "avg_visit_duration_hours": 1.5,
                "best_visit_time_hour": 10, "budget_category": "budget",
                "seasonal_score": {"oct": 90, "nov": 90, "dec": 85, "jun": 50},
            },
            {
                "name": "Nahargarh Fort",
                "description": "Hilltop fort offering panoramic views of Jaipur city, ideal for sunsets.",
                "entry_cost": 200, "duration": "1.5 hours", "rating": 4.4, "type": "fort",
                "latitude": 26.9421, "longitude": 75.8057,
                "popularity_score": 78, "avg_visit_duration_hours": 1.5,
                "best_visit_time_hour": 17, "budget_category": "budget",
                "seasonal_score": {"oct": 88, "nov": 90, "dec": 85, "jan": 88, "jun": 45},
            },
        ],
        "hotels": [
            {"name": "Rambagh Palace", "star_rating": 5, "category": "luxury", "price_per_night_min": 25000, "price_per_night_max": 60000},
            {"name": "ITC Rajputana", "star_rating": 5, "category": "luxury", "price_per_night_min": 8000, "price_per_night_max": 18000},
            {"name": "Hotel Pearl Palace", "star_rating": 3, "category": "mid", "price_per_night_min": 2500, "price_per_night_max": 5000},
            {"name": "Hotel Arya Niwas", "star_rating": 2, "category": "budget", "price_per_night_min": 900, "price_per_night_max": 2000},
        ],
    },
    {
        "state": "Goa",
        "name": "Goa",
        "slug": "goa",
        "desc": "Sun, sand, and spice — India's party capital with Portuguese heritage.",
        "description": "Goa blends Indian and Portuguese cultures with stunning beaches, vibrant nightlife, colonial churches, and excellent seafood. From the bustling Baga beach to the serene Palolem, there's a Goa for everyone.",
        "location": "Goa, India",
        "price_str": "₹4,000/day",
        "estimated_cost_per_day": 4000,
        "rating": 4.5,
        "tag": "Beach",
        "lat": 15.2993, "lng": 74.1240,
        "highlights": ["Baga Beach", "Old Goa Churches", "Dudhsagar Falls", "Anjuna Flea Market"],
        "best_time_months": ["nov", "dec", "jan", "feb", "mar"],
        "vibe_tags": ["beach", "party", "relaxation", "seafood", "nightlife"],
        "popularity_score": 95,
        "budget_category": "mid-range",
        "attractions": [
            {
                "name": "Baga Beach",
                "description": "The most popular beach in North Goa, famous for water sports, shacks, and nightlife.",
                "entry_cost": 0, "duration": "3-4 hours", "rating": 4.3, "type": "beach",
                "latitude": 15.5553, "longitude": 73.7517,
                "popularity_score": 90, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 8, "budget_category": "budget",
                "seasonal_score": {"nov": 95, "dec": 95, "jan": 95, "feb": 90, "mar": 85, "jun": 30},
            },
            {
                "name": "Basilica of Bom Jesus",
                "description": "UNESCO World Heritage church housing the remains of St. Francis Xavier, built in 1605.",
                "entry_cost": 0, "duration": "1 hour", "rating": 4.7, "type": "church",
                "latitude": 15.5009, "longitude": 73.9116,
                "popularity_score": 85, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 9, "budget_category": "budget",
                "seasonal_score": {"nov": 90, "dec": 90, "jan": 92, "feb": 90, "jun": 55},
            },
            {
                "name": "Dudhsagar Falls",
                "description": "One of India's tallest waterfalls, cascading 310m through lush forest near the Karnataka border.",
                "entry_cost": 400, "duration": "4-5 hours", "rating": 4.6, "type": "waterfall",
                "latitude": 15.3144, "longitude": 74.3144,
                "popularity_score": 82, "avg_visit_duration_hours": 4.0,
                "best_visit_time_hour": 9, "budget_category": "budget",
                "seasonal_score": {"jul": 90, "aug": 92, "sep": 95, "oct": 85, "nov": 70, "dec": 50},
            },
            {
                "name": "Anjuna Flea Market",
                "description": "Iconic Wednesday market selling handicrafts, clothes, spices, and antiques since the 1960s.",
                "entry_cost": 0, "duration": "2 hours", "rating": 4.0, "type": "market",
                "latitude": 15.5784, "longitude": 73.7442,
                "popularity_score": 72, "avg_visit_duration_hours": 2.0,
                "best_visit_time_hour": 10, "budget_category": "budget",
                "seasonal_score": {"nov": 85, "dec": 90, "jan": 88, "feb": 85, "mar": 75},
            },
            {
                "name": "Palolem Beach",
                "description": "Crescent-shaped pristine beach in South Goa, perfect for peaceful sunsets and kayaking.",
                "entry_cost": 0, "duration": "3 hours", "rating": 4.5, "type": "beach",
                "latitude": 15.0101, "longitude": 74.0232,
                "popularity_score": 80, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 16, "budget_category": "budget",
                "seasonal_score": {"nov": 92, "dec": 92, "jan": 92, "feb": 88, "mar": 80, "jun": 25},
            },
        ],
        "hotels": [
            {"name": "W Goa", "star_rating": 5, "category": "luxury", "price_per_night_min": 18000, "price_per_night_max": 45000},
            {"name": "Taj Exotica Resort & Spa", "star_rating": 5, "category": "luxury", "price_per_night_min": 15000, "price_per_night_max": 40000},
            {"name": "Resort Baga Marina", "star_rating": 3, "category": "mid", "price_per_night_min": 3500, "price_per_night_max": 7000},
            {"name": "Zostel Goa", "star_rating": 1, "category": "budget", "price_per_night_min": 600, "price_per_night_max": 1500},
        ],
    },
    {
        "state": "Kerala",
        "name": "Munnar",
        "slug": "munnar",
        "desc": "Misty tea estates and rolling green hills in God's Own Country.",
        "description": "Munnar is a charming hill station in Kerala known for its sprawling tea plantations, cool climate, and stunning landscapes. Eravikulam National Park is home to the endangered Nilgiri Tahr.",
        "location": "Kerala, India",
        "price_str": "₹3,000/day",
        "estimated_cost_per_day": 3000,
        "rating": 4.7,
        "tag": "Nature",
        "lat": 10.0889, "lng": 77.0595,
        "highlights": ["Tea Plantations", "Eravikulam National Park", "Mattupetty Dam", "Top Station"],
        "best_time_months": ["sep", "oct", "nov", "dec", "jan", "feb", "mar"],
        "vibe_tags": ["nature", "hills", "tea", "trekking", "wildlife"],
        "popularity_score": 88,
        "budget_category": "mid-range",
        "attractions": [
            {
                "name": "Eravikulam National Park",
                "description": "UNESCO Biosphere Reserve and home to the rare Nilgiri Tahr. Magnificent views of Western Ghats.",
                "entry_cost": 125, "duration": "3 hours", "rating": 4.7, "type": "wildlife",
                "latitude": 10.1502, "longitude": 77.0670,
                "popularity_score": 88, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 8, "budget_category": "budget",
                "seasonal_score": {"sep": 80, "oct": 90, "nov": 92, "dec": 90, "jan": 92, "feb": 88},
            },
            {
                "name": "Tea Museum",
                "description": "Dedicated to the history of tea cultivation in Munnar, with vintage machinery and tea-tasting sessions.",
                "entry_cost": 100, "duration": "1 hour", "rating": 4.2, "type": "museum",
                "latitude": 10.0889, "longitude": 77.0595,
                "popularity_score": 72, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 10, "budget_category": "budget",
                "seasonal_score": {"sep": 75, "oct": 85, "nov": 88, "dec": 88, "jan": 88, "feb": 85},
            },
            {
                "name": "Mattupetty Dam",
                "description": "Scenic reservoir surrounded by tea estates, popular for boating and wildlife spotting.",
                "entry_cost": 30, "duration": "1.5 hours", "rating": 4.3, "type": "dam",
                "latitude": 10.1153, "longitude": 77.0950,
                "popularity_score": 76, "avg_visit_duration_hours": 1.5,
                "best_visit_time_hour": 9, "budget_category": "budget",
                "seasonal_score": {"oct": 85, "nov": 88, "dec": 88, "jan": 88, "feb": 85, "jun": 60},
            },
        ],
        "hotels": [
            {"name": "Windermere Estate", "star_rating": 4, "category": "luxury", "price_per_night_min": 8000, "price_per_night_max": 18000},
            {"name": "Tall Trees Resort", "star_rating": 3, "category": "mid", "price_per_night_min": 3000, "price_per_night_max": 6000},
            {"name": "JJ Cottage", "star_rating": 2, "category": "budget", "price_per_night_min": 1200, "price_per_night_max": 2500},
        ],
    },
    {
        "state": "Rajasthan",
        "name": "Udaipur",
        "slug": "udaipur",
        "desc": "The City of Lakes — romantic palaces reflected in shimmering waters.",
        "description": "Udaipur is often called the 'Venice of the East' for its beautiful lakes, whitewashed palaces, and romantic atmosphere. The City Palace and Lake Pichola are must-visits.",
        "location": "Rajasthan, India",
        "price_str": "₹4,000/day",
        "estimated_cost_per_day": 4000,
        "rating": 4.8,
        "tag": "Romance",
        "lat": 24.5854, "lng": 73.7125,
        "highlights": ["City Palace", "Lake Pichola", "Jag Mandir", "Saheliyon ki Bari"],
        "best_time_months": ["oct", "nov", "dec", "jan", "feb"],
        "vibe_tags": ["romantic", "heritage", "lakes", "royal", "architecture"],
        "popularity_score": 91,
        "budget_category": "mid-range",
        "attractions": [
            {
                "name": "City Palace",
                "description": "The largest palace complex in Rajasthan, built over 400 years with stunning lake views.",
                "entry_cost": 300, "duration": "3 hours", "rating": 4.8, "type": "palace",
                "latitude": 24.5756, "longitude": 73.6857,
                "popularity_score": 93, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 9, "budget_category": "mid-range",
                "seasonal_score": {"oct": 92, "nov": 95, "dec": 92, "jan": 95, "feb": 92, "jun": 55},
            },
            {
                "name": "Lake Pichola Boat Ride",
                "description": "Scenic boat ride on the serene lake offering views of palaces, temples, and ghats.",
                "entry_cost": 400, "duration": "1 hour", "rating": 4.7, "type": "lake",
                "latitude": 24.5757, "longitude": 73.6797,
                "popularity_score": 89, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 17, "budget_category": "budget",
                "seasonal_score": {"oct": 90, "nov": 92, "dec": 90, "jan": 92, "feb": 90, "jun": 60},
            },
            {
                "name": "Jag Mandir",
                "description": "Island palace on Lake Pichola, once refuge of Mughal Prince Khurram, with ornate gardens.",
                "entry_cost": 250, "duration": "1.5 hours", "rating": 4.6, "type": "palace",
                "latitude": 24.5681, "longitude": 73.6818,
                "popularity_score": 80, "avg_visit_duration_hours": 1.5,
                "best_visit_time_hour": 11, "budget_category": "mid-range",
                "seasonal_score": {"oct": 88, "nov": 90, "dec": 88, "jan": 90, "feb": 88},
            },
        ],
        "hotels": [
            {"name": "Taj Lake Palace", "star_rating": 5, "category": "luxury", "price_per_night_min": 30000, "price_per_night_max": 80000},
            {"name": "Fateh Garh", "star_rating": 4, "category": "luxury", "price_per_night_min": 7000, "price_per_night_max": 15000},
            {"name": "Hotel Mahendra Prakash", "star_rating": 3, "category": "mid", "price_per_night_min": 2000, "price_per_night_max": 4500},
        ],
    },
    {
        "state": "Maharashtra",
        "name": "Mumbai",
        "slug": "mumbai",
        "desc": "The City of Dreams — Bollywood, street food, and a relentless buzz.",
        "description": "Mumbai is India's financial and entertainment capital, a city that never sleeps. From the Gateway of India and Marine Drive to Dharavi and Bollywood studios, it's an overwhelming sensory experience.",
        "location": "Maharashtra, India",
        "price_str": "₹5,000/day",
        "estimated_cost_per_day": 5000,
        "rating": 4.3,
        "tag": "Urban",
        "lat": 19.0760, "lng": 72.8777,
        "highlights": ["Gateway of India", "Marine Drive", "Elephanta Caves", "Chhatrapati Shivaji Terminus"],
        "best_time_months": ["nov", "dec", "jan", "feb"],
        "vibe_tags": ["urban", "food", "bollywood", "history", "coastal"],
        "popularity_score": 89,
        "budget_category": "mid-range",
        "attractions": [
            {
                "name": "Gateway of India",
                "description": "Iconic 26m arch built in 1924 to commemorate the visit of King George V, overlooking Arabian Sea.",
                "entry_cost": 0, "duration": "1 hour", "rating": 4.4, "type": "monument",
                "latitude": 18.9220, "longitude": 72.8347,
                "popularity_score": 91, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 8, "budget_category": "budget",
                "seasonal_score": {"nov": 85, "dec": 88, "jan": 88, "feb": 85, "oct": 80, "jun": 40},
            },
            {
                "name": "Elephanta Caves",
                "description": "UNESCO World Heritage Site — rock-cut temples dedicated to Shiva on an island in Mumbai Harbour.",
                "entry_cost": 600, "duration": "3 hours", "rating": 4.5, "type": "heritage",
                "latitude": 18.9633, "longitude": 72.9315,
                "popularity_score": 82, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 9, "budget_category": "mid-range",
                "seasonal_score": {"nov": 85, "dec": 88, "jan": 88, "feb": 85, "oct": 78, "jun": 20},
            },
            {
                "name": "Marine Drive",
                "description": "3km long promenade along the Queen's Necklace bay, perfect for sunset walks.",
                "entry_cost": 0, "duration": "1.5 hours", "rating": 4.5, "type": "promenade",
                "latitude": 18.9432, "longitude": 72.8236,
                "popularity_score": 86, "avg_visit_duration_hours": 1.5,
                "best_visit_time_hour": 18, "budget_category": "budget",
                "seasonal_score": {"nov": 85, "dec": 88, "jan": 88, "feb": 85, "jun": 55},
            },
            {
                "name": "Chhatrapati Shivaji Terminus",
                "description": "UNESCO World Heritage railway station — masterpiece of Victorian Gothic architecture, built in 1887.",
                "entry_cost": 0, "duration": "45 minutes", "rating": 4.6, "type": "architecture",
                "latitude": 18.9401, "longitude": 72.8353,
                "popularity_score": 79, "avg_visit_duration_hours": 0.75,
                "best_visit_time_hour": 10, "budget_category": "budget",
                "seasonal_score": {"nov": 82, "dec": 85, "jan": 85, "feb": 82, "jun": 60},
            },
        ],
        "hotels": [
            {"name": "Taj Mahal Palace", "star_rating": 5, "category": "luxury", "price_per_night_min": 20000, "price_per_night_max": 55000},
            {"name": "ITC Grand Central", "star_rating": 5, "category": "luxury", "price_per_night_min": 10000, "price_per_night_max": 22000},
            {"name": "Hotel Suba Palace", "star_rating": 3, "category": "mid", "price_per_night_min": 3500, "price_per_night_max": 7000},
            {"name": "Zostel Mumbai", "star_rating": 1, "category": "budget", "price_per_night_min": 700, "price_per_night_max": 1800},
        ],
    },
    {
        "state": "Himachal Pradesh",
        "name": "Manali",
        "slug": "manali",
        "desc": "Snow-capped peaks, adventure sports, and Himalayan serenity.",
        "description": "Manali is a high-altitude Himalayan resort town in Himachal Pradesh. It's a gateway to Lahaul-Spiti and Leh-Ladakh, offering adventure activities like skiing, trekking, and paragliding.",
        "location": "Himachal Pradesh, India",
        "price_str": "₹3,200/day",
        "estimated_cost_per_day": 3200,
        "rating": 4.5,
        "tag": "Adventure",
        "lat": 32.2396, "lng": 77.1887,
        "highlights": ["Rohtang Pass", "Solang Valley", "Hadimba Temple", "Old Manali"],
        "best_time_months": ["dec", "jan", "feb", "mar", "oct", "nov"],
        "vibe_tags": ["adventure", "snow", "trekking", "mountains", "skiing"],
        "popularity_score": 88,
        "budget_category": "budget",
        "attractions": [
            {
                "name": "Rohtang Pass",
                "description": "High mountain pass at 3,978m on the Beas River, offering spectacular views of glaciers and peaks.",
                "entry_cost": 550, "duration": "Full day", "rating": 4.6, "type": "mountain",
                "latitude": 32.3726, "longitude": 77.2500,
                "popularity_score": 90, "avg_visit_duration_hours": 6.0,
                "best_visit_time_hour": 7, "budget_category": "mid-range",
                "seasonal_score": {"may": 85, "jun": 80, "sep": 85, "oct": 90, "dec": 70, "jan": 60},
            },
            {
                "name": "Solang Valley",
                "description": "Adventure hub offering skiing, paragliding, zorbing and cable car rides in a snow-covered valley.",
                "entry_cost": 0, "duration": "3 hours", "rating": 4.5, "type": "valley",
                "latitude": 32.3200, "longitude": 77.1500,
                "popularity_score": 85, "avg_visit_duration_hours": 3.0,
                "best_visit_time_hour": 9, "budget_category": "mid-range",
                "seasonal_score": {"dec": 92, "jan": 95, "feb": 92, "mar": 85, "may": 70, "oct": 75},
            },
            {
                "name": "Hadimba Devi Temple",
                "description": "Ancient wooden temple in a cedar forest dedicated to the goddess Hadimba, wife of Bhima.",
                "entry_cost": 0, "duration": "1 hour", "rating": 4.4, "type": "temple",
                "latitude": 32.2406, "longitude": 77.1752,
                "popularity_score": 78, "avg_visit_duration_hours": 1.0,
                "best_visit_time_hour": 9, "budget_category": "budget",
                "seasonal_score": {"oct": 88, "nov": 85, "dec": 80, "jan": 78, "feb": 80, "mar": 85},
            },
        ],
        "hotels": [
            {"name": "Span Resort & Spa", "star_rating": 4, "category": "luxury", "price_per_night_min": 8000, "price_per_night_max": 18000},
            {"name": "Hotel Manali Inn", "star_rating": 3, "category": "mid", "price_per_night_min": 2500, "price_per_night_max": 5500},
            {"name": "The Hosteller Manali", "star_rating": 1, "category": "budget", "price_per_night_min": 600, "price_per_night_max": 1400},
        ],
    },
]

SAMPLE_USERS = [
    {"name": "Aarav Sharma", "email": "aarav@example.com", "password": "SecurePass123!"},
    {"name": "Priya Nair", "email": "priya@example.com", "password": "SecurePass123!"},
    {"name": "Rohan Mehta", "email": "rohan@example.com", "password": "SecurePass123!"},
    {"name": "Sneha Patel", "email": "sneha@example.com", "password": "SecurePass123!"},
    {"name": "Vikram Iyer", "email": "vikram@example.com", "password": "SecurePass123!"},
]

SAMPLE_TRIPS = [
    {"trip_title": "Jaipur Heritage Explorer — 4 Days", "destination_country": "India", "budget": 15000, "duration": 4, "travelers": 2, "style": "heritage", "traveler_type": "couple", "total_cost": 13800},
    {"trip_title": "Goa Beach Bliss — 5 Days", "destination_country": "India", "budget": 20000, "duration": 5, "travelers": 4, "style": "relaxation", "traveler_type": "group", "total_cost": 18500},
    {"trip_title": "Munnar Nature Escape — 3 Days", "destination_country": "India", "budget": 10000, "duration": 3, "travelers": 2, "style": "nature", "traveler_type": "couple", "total_cost": 8900},
    {"trip_title": "Mumbai City Rush — 2 Days", "destination_country": "India", "budget": 12000, "duration": 2, "travelers": 1, "style": "urban", "traveler_type": "solo_male", "total_cost": 9500},
    {"trip_title": "Udaipur Royal Romance — 4 Days", "destination_country": "India", "budget": 18000, "duration": 4, "travelers": 2, "style": "luxury", "traveler_type": "couple", "total_cost": 16200},
    {"trip_title": "Manali Snow Adventure — 6 Days", "destination_country": "India", "budget": 22000, "duration": 6, "travelers": 3, "style": "adventure", "traveler_type": "group", "total_cost": 20100},
    {"trip_title": "Jaipur Royal Circuit — 3 Days", "destination_country": "India", "budget": 12000, "duration": 3, "travelers": 1, "style": "culture", "traveler_type": "solo_female", "total_cost": 10800},
    {"trip_title": "Goa Party Weekend — 3 Days", "destination_country": "India", "budget": 15000, "duration": 3, "travelers": 5, "style": "party", "traveler_type": "group", "total_cost": 13200},
]


def run():
    with app.app_context():
        # ── Countries & States ────────────────────────────────────────────────
        print("Seeding country...")
        india = db.session.query(Country).filter_by(code="IN").first()
        if not india:
            india = Country(name="India", code="IN", currency="INR", image="india.jpg")
            db.session.add(india)
            db.session.flush()

        state_map = {}
        for dest_data in DESTINATIONS:
            state_name = dest_data["state"]
            if state_name not in state_map:
                state = db.session.query(State).filter_by(name=state_name).first()
                if not state:
                    state = State(name=state_name, image=f"{state_name.lower().replace(' ', '_')}.jpg", country_id=india.id)
                    db.session.add(state)
                    db.session.flush()
                state_map[state_name] = state

        print(f"  States: {list(state_map.keys())}")

        # ── Destinations & Attractions ────────────────────────────────────────
        print("Seeding destinations and attractions...")
        for dest_data in DESTINATIONS:
            existing = db.session.query(Destination).filter_by(slug=dest_data["slug"]).first()
            if existing:
                print(f"  Skipping {dest_data['name']} (already exists)")
                continue

            state = state_map[dest_data["state"]]
            dest = Destination(
                name=dest_data["name"],
                slug=dest_data["slug"],
                desc=dest_data["desc"],
                description=dest_data["description"],
                image=f"{dest_data['slug']}.jpg",
                location=dest_data["location"],
                price_str=dest_data["price_str"],
                estimated_cost_per_day=dest_data["estimated_cost_per_day"],
                rating=dest_data["rating"],
                tag=dest_data["tag"],
                lat=dest_data["lat"],
                lng=dest_data["lng"],
                latitude=dest_data["lat"],
                longitude=dest_data["lng"],
                highlights=dest_data["highlights"],
                best_time_months=dest_data["best_time_months"],
                vibe_tags=dest_data["vibe_tags"],
                popularity_score=dest_data["popularity_score"],
                budget_category=dest_data["budget_category"],
                state_id=state.id,
            )
            db.session.add(dest)
            db.session.flush()
            print(f"  + Destination: {dest.name}")

            for a in dest_data["attractions"]:
                attraction = Attraction(
                    name=a["name"],
                    description=a["description"],
                    entry_cost=a["entry_cost"],
                    duration=a["duration"],
                    rating=a["rating"],
                    type=a["type"],
                    destination_id=dest.id,
                    latitude=a["latitude"],
                    longitude=a["longitude"],
                    lat=a["latitude"],
                    lng=a["longitude"],
                    popularity_score=a["popularity_score"],
                    avg_visit_duration_hours=a["avg_visit_duration_hours"],
                    best_visit_time_hour=a["best_visit_time_hour"],
                    budget_category=a["budget_category"],
                    compatible_traveler_types=TRAVELERS,
                    seasonal_score=a["seasonal_score"],
                )
                db.session.add(attraction)
            print(f"    + {len(dest_data['attractions'])} attractions")

            for h in dest_data["hotels"]:
                hotel = HotelPrice(
                    destination_id=dest.id,
                    hotel_name=h["name"],
                    star_rating=h["star_rating"],
                    category=h["category"],
                    price_per_night_min=h["price_per_night_min"],
                    price_per_night_max=h["price_per_night_max"],
                    partner="booking.com",
                    availability_score=0.9,
                )
                db.session.add(hotel)
            print(f"    + {len(dest_data['hotels'])} hotels")

        # ── Sample Users ──────────────────────────────────────────────────────
        print("Seeding users...")
        created_users = []
        for u in SAMPLE_USERS:
            existing = db.session.query(User).filter_by(email=u["email"]).first()
            if not existing:
                user = User(
                    name=u["name"],
                    email=u["email"],
                    password_hash=generate_password_hash(u["password"]),
                )
                db.session.add(user)
                db.session.flush()
                created_users.append(user)
                print(f"  + User: {user.name}")
            else:
                created_users.append(existing)

        # ── Sample Trips ──────────────────────────────────────────────────────
        print("Seeding trips...")
        for i, t in enumerate(SAMPLE_TRIPS):
            user = created_users[i % len(created_users)]
            existing = db.session.query(Trip).filter_by(trip_title=t["trip_title"]).first()
            if not existing:
                trip = Trip(
                    user_id=user.id,
                    trip_title=t["trip_title"],
                    destination_country=t["destination_country"],
                    budget=t["budget"],
                    duration=t["duration"],
                    travelers=t["travelers"],
                    style=t["style"],
                    traveler_type=t["traveler_type"],
                    total_cost=t["total_cost"],
                    itinerary_json={},
                )
                db.session.add(trip)
                # Add analytics event for each trip
                db.session.add(AnalyticsEvent(
                    event_type="GenerateItinerary",
                    user_id=user.id,
                    payload={"trip_title": t["trip_title"], "destination": t["destination_country"]},
                ))
                print(f"  + Trip: {t['trip_title']}")

        # ── Engine Settings ───────────────────────────────────────────────────
        print("Seeding engine settings...")
        defaults = [
            ("VALIDATION_STRICT", "false", "Enforce strict schema validation"),
            ("GEMINI_MODEL", "gemini-2.0-flash", "Primary LLM model for generation"),
            ("THEME_THRESHOLD", "0.20", "Minimum relevance score for themed attractions"),
        ]
        for key, value, desc in defaults:
            existing = db.session.query(EngineSetting).filter_by(key=key).first()
            if not existing:
                db.session.add(EngineSetting(key=key, value=value, description=desc))
                print(f"  + Setting: {key} = {value}")
            elif key == "GEMINI_MODEL" and existing.value == "gemini-1.5-pro":
                existing.value = "gemini-2.0-flash"
                print(f"  ~ Updated GEMINI_MODEL to gemini-2.0-flash")

        db.session.commit()
        print("\nSeed complete!")

        # ── Summary ───────────────────────────────────────────────────────────
        print(f"\nDatabase summary:")
        print(f"  Destinations : {db.session.query(Destination).count()}")
        print(f"  Attractions  : {db.session.query(Attraction).count()}")
        print(f"  Hotels       : {db.session.query(HotelPrice).count()}")
        print(f"  Users        : {db.session.query(User).count()}")
        print(f"  Trips        : {db.session.query(Trip).count()}")
        print(f"  States       : {db.session.query(State).count()}")


if __name__ == "__main__":
    run()
