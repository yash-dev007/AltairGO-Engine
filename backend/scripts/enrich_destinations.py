import sys
import os
import json
import logging
from sqlalchemy import text

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# FIXES FROM ORIGINAL:
#
# 1. JSON serialization: used str().replace() — WRONG. Produces invalid
#    JSON like [10, 11] instead of [10, 11]. Fixed: use json.dumps().
#
# 2. Missing solo_male in traveler types for many destinations.
#    FilterEngine queries compatible_traveler_types @> '["solo_male"],

#    If a destination has no solo_male, ALL solo male trips return 0
#    attractions. Fixed: added solo_male + solo_female + elderly where
#    appropriate. Also added "elderly" category which was fully missing.
#
# 3. Missing crowd_level_by_hour on ALL destinations.
#    FilterEngine and Phase 4 scoring both need this. Fixed: added
#    realistic crowd patterns for every destination.
#
# 4. Missing avg_visit_duration_hours on ALL destinations.
#    ItineraryAssembler uses this to estimate day pacing. Fixed: added.
#
# 5. Missing H3 indexing after coordinate update.
#    Fixed: added h3_index_r7 and h3_index_r9 on every upsert.
#
# 6. Missing connects_well_with for route suggestion logic.
#    Fixed: added for all destinations.
#
# 7. Incomplete destination list — missing entire states.
#    Fixed: added Andhra Pradesh, Telangana, Odisha, West Bengal,
#    Gujarat, Madhya Pradesh, Bihar, Punjab, Northeast India,
#    Andaman & Nicobar, Jammu & Kashmir (full Ladakh circuit).
#
# 8. ST_GeomFromText used instead of ST_MakePoint — less reliable
#    with some PostGIS versions. Fixed: use ST_MakePoint.
# ─────────────────────────────────────────────────────────────────

# ── Traveler type values used throughout the engine ────────────────
# "solo_male" | "solo_female" | "couple" | "family" | "group" | "elderly"

DESTINATIONS = [

    # ═══════════════════════════════════════════════════════
    # RAJASTHAN
    # ═══════════════════════════════════════════════════════
    {
        "name": "Jaipur",
        "lat": 26.9124, "lng": 75.7873,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","family","group","elderly"],
        "crowd": {"8":3,"9":5,"10":7,"11":9,"12":8,"14":8,"15":9,"16":8,"17":6,"18":4},
        "connects": ["Agra","Udaipur","Ranthambore"],
    },
    {
        "name": "Udaipur",
        "lat": 24.5854, "lng": 73.7125,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 3, "dur": 3.5,
        "types": ["solo_female","couple","family","elderly"],
        "crowd": {"9":3,"10":5,"11":7,"14":7,"15":8,"16":9,"17":8,"18":7,"19":6},
        "connects": ["Jaipur","Jodhpur","Mount Abu"],
    },
    {
        "name": "Jodhpur",
        "lat": 26.2389, "lng": 73.0243,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"8":2,"9":4,"10":6,"11":8,"14":6,"15":8,"16":7,"17":5},
        "connects": ["Jaisalmer","Udaipur","Jaipur"],
    },
    {
        "name": "Jaisalmer",
        "lat": 26.9157, "lng": 70.9160,
        "best_months": [11,12,1,2],
        "budget": 2, "dur": 4.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"9":2,"10":4,"14":4,"16":8,"17":9,"18":8},
        "connects": ["Jodhpur","Bikaner"],
    },
    {
        "name": "Pushkar",
        "lat": 26.4897, "lng": 74.5511,
        "best_months": [10,11,12,1,2],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"7":4,"8":6,"9":8,"10":7,"16":6,"17":8,"18":9},
        "connects": ["Jaipur","Jodhpur"],
    },
    {
        "name": "Ranthambore",
        "lat": 25.9961, "lng": 76.3533,
        "best_months": [10,11,12,1,2,3,4,5],
        "budget": 3, "dur": 5.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":5,"7":9,"8":8,"15":7,"16":9,"17":8},
        "connects": ["Jaipur","Agra"],
    },
    {
        "name": "Mount Abu",
        "lat": 24.5925, "lng": 72.7156,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","elderly"],
        "crowd": {"9":3,"10":5,"11":7,"14":6,"16":7,"17":6},
        "connects": ["Udaipur","Jodhpur"],
    },
    {
        "name": "Bikaner",
        "lat": 28.0229, "lng": 73.3119,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","couple","group","family"],
        "crowd": {"9":3,"10":5,"14":5,"15":6,"16":5},
        "connects": ["Jaisalmer","Jodhpur"],
    },
    {
        "name": "Chittorgarh",
        "lat": 24.8887, "lng": 74.6269,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"8":2,"9":4,"10":6,"11":7,"14":5,"15":6,"16":5},
        "connects": ["Udaipur","Jaipur"],
    },

    # ═══════════════════════════════════════════════════════
    # GOA
    # ═══════════════════════════════════════════════════════
    {
        "name": "North Goa",
        "lat": 15.5947, "lng": 73.7348,
        "best_months": [11,12,1,2,3],
        "budget": 2, "dur": 5.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"10":5,"12":7,"14":7,"16":9,"18":9,"20":9,"21":8},
        "connects": ["South Goa","Panjim","Mumbai"],
    },
    {
        "name": "South Goa",
        "lat": 15.0883, "lng": 73.9213,
        "best_months": [11,12,1,2],
        "budget": 3, "dur": 5.0,
        "types": ["couple","family","elderly"],
        "crowd": {"9":3,"10":5,"11":6,"14":6,"16":7,"18":6},
        "connects": ["North Goa","Panjim"],
    },
    {
        "name": "Panjim",
        "lat": 15.4909, "lng": 73.8278,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.0,
        "types": ["solo_female","couple","family","group"],
        "crowd": {"9":4,"10":6,"14":7,"16":8,"18":8},
        "connects": ["North Goa","South Goa"],
    },

    # ═══════════════════════════════════════════════════════
    # KERALA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Munnar",
        "lat": 10.0889, "lng": 77.0595,
        "best_months": [9,10,11,12,1,2,3,4],
        "budget": 2, "dur": 3.5,
        "types": ["couple","family","elderly","solo_female"],
        "crowd": {"7":3,"8":5,"9":7,"10":8,"11":7,"14":6,"15":7,"16":6,"17":4},
        "connects": ["Alleppey","Thekkady","Kochi"],
    },
    {
        "name": "Alleppey",
        "lat": 9.4981, "lng": 76.3329,
        "best_months": [10,11,12,1,2],
        "budget": 2, "dur": 5.0,
        "types": ["couple","family","elderly","solo_female"],
        "crowd": {"8":3,"9":5,"10":6,"11":7,"14":7,"15":6,"16":5,"17":4},
        "connects": ["Munnar","Kovalam","Kochi"],
    },
    {
        "name": "Kochi",
        "lat": 9.9312, "lng": 76.2673,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"9":4,"10":6,"11":7,"14":7,"16":8,"17":7,"18":6},
        "connects": ["Munnar","Alleppey","Thekkady"],
    },
    {
        "name": "Wayanad",
        "lat": 11.6854, "lng": 76.1320,
        "best_months": [9,10,11,12,1,2,3,4,5],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"8":3,"9":5,"10":6,"11":7,"14":5,"15":6,"16":5},
        "connects": ["Kochi","Ooty","Coorg"],
    },
    {
        "name": "Varkala",
        "lat": 8.7303, "lng": 76.7032,
        "best_months": [11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_female","couple","group"],
        "crowd": {"9":3,"10":5,"11":6,"14":6,"16":7,"17":6},
        "connects": ["Kovalam","Kochi"],
    },
    {
        "name": "Kovalam",
        "lat": 8.4004, "lng": 76.9787,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_female","couple","family"],
        "crowd": {"9":3,"10":5,"14":6,"16":7,"17":6},
        "connects": ["Varkala","Alleppey"],
    },
    {
        "name": "Thekkady",
        "lat": 9.6000, "lng": 77.1600,
        "best_months": [9,10,11,12,1,2,3,4,5],
        "budget": 2, "dur": 3.0,
        "types": ["family","couple","group"],
        "crowd": {"6":5,"7":8,"8":7,"14":5,"15":6,"16":7},
        "connects": ["Munnar","Alleppey"],
    },
    {
        "name": "Kozhikode",
        "lat": 11.2588, "lng": 75.7804,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","family","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":7},
        "connects": ["Wayanad","Kochi"],
    },

    # ═══════════════════════════════════════════════════════
    # HIMACHAL PRADESH
    # ═══════════════════════════════════════════════════════
    {
        "name": "Manali",
        "lat": 32.2432, "lng": 77.1892,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 4.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7,"16":6,"17":4},
        "connects": ["Shimla","Kasol","Spiti Valley"],
    },
    {
        "name": "Shimla",
        "lat": 31.1048, "lng": 77.1734,
        "best_months": [3,4,5,6,9,10,11,12,1,2],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","elderly","solo_male","solo_female"],
        "crowd": {"9":4,"10":6,"11":8,"12":7,"14":7,"15":8,"16":7,"17":6},
        "connects": ["Manali","Kasol","Dharamshala"],
    },
    {
        "name": "Dharamshala",
        "lat": 32.2190, "lng": 76.3234,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"8":2,"9":4,"10":6,"11":7,"14":6,"15":7,"16":5,"17":4},
        "connects": ["Shimla","Manali","Amritsar"],
    },
    {
        "name": "Spiti Valley",
        "lat": 32.2461, "lng": 78.0349,
        "best_months": [6,7,8,9],
        "budget": 1, "dur": 5.0,
        "types": ["solo_male","group"],
        "crowd": {"9":2,"10":4,"14":5,"15":4},
        "connects": ["Manali","Leh"],
    },
    {
        "name": "Kasol",
        "lat": 32.0100, "lng": 77.3150,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","solo_female","group"],
        "crowd": {"9":3,"10":5,"14":5,"16":6,"17":5},
        "connects": ["Manali","Dharamshala"],
    },
    {
        "name": "Bir Billing",
        "lat": 32.0374, "lng": 76.7225,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","group"],
        "crowd": {"8":3,"9":5,"10":6,"14":4,"15":5},
        "connects": ["Dharamshala","Shimla"],
    },
    {
        "name": "Dalhousie",
        "lat": 32.5388, "lng": 75.9735,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","elderly"],
        "crowd": {"9":3,"10":5,"14":5,"16":6},
        "connects": ["Dharamshala","Shimla"],
    },

    # ═══════════════════════════════════════════════════════
    # UTTARAKHAND
    # ═══════════════════════════════════════════════════════
    {
        "name": "Rishikesh",
        "lat": 30.0869, "lng": 78.2676,
        "best_months": [3,4,5,9,10,11],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"6":3,"7":6,"8":8,"9":7,"16":6,"17":8,"18":9,"19":7},
        "connects": ["Haridwar","Mussoorie","Nainital"],
    },
    {
        "name": "Haridwar",
        "lat": 29.9457, "lng": 78.1642,
        "best_months": [3,4,5,10,11],
        "budget": 1, "dur": 2.5,
        "types": ["family","elderly","solo_male","solo_female"],
        "crowd": {"5":7,"6":9,"7":8,"8":6,"17":7,"18":9,"19":8},
        "connects": ["Rishikesh","Delhi"],
    },
    {
        "name": "Nainital",
        "lat": 29.3919, "lng": 79.4542,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","elderly"],
        "crowd": {"9":4,"10":6,"11":8,"14":7,"15":8,"16":7},
        "connects": ["Jim Corbett","Mussoorie"],
    },
    {
        "name": "Mussoorie",
        "lat": 30.4598, "lng": 78.0664,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","elderly"],
        "crowd": {"9":4,"10":6,"11":8,"14":7,"16":8},
        "connects": ["Rishikesh","Nainital"],
    },
    {
        "name": "Jim Corbett",
        "lat": 29.5300, "lng": 78.7747,
        "best_months": [11,12,1,2,3,4,5,6],
        "budget": 3, "dur": 5.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":7,"7":9,"8":8,"15":7,"16":9},
        "connects": ["Nainital","Rishikesh"],
    },
    {
        "name": "Auli",
        "lat": 30.5226, "lng": 79.5638,
        "best_months": [1,2,3,12],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"9":3,"10":5,"14":5,"15":6},
        "connects": ["Rishikesh","Nainital"],
    },
    {
        "name": "Chopta",
        "lat": 30.4165, "lng": 79.1440,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","group"],
        "crowd": {"7":3,"8":5,"9":6,"14":4,"15":5},
        "connects": ["Rishikesh","Auli"],
    },

    # ═══════════════════════════════════════════════════════
    # UTTAR PRADESH
    # ═══════════════════════════════════════════════════════
    {
        "name": "Varanasi",
        "lat": 25.3176, "lng": 82.9739,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.5,
        "types": ["solo_male","solo_female","family","elderly","group"],
        "crowd": {"5":7,"6":9,"7":8,"8":6,"9":5,"16":5,"17":7,"18":9,"19":9},
        "connects": ["Agra","Prayagraj","Bodh Gaya"],
    },
    {
        "name": "Agra",
        "lat": 27.1767, "lng": 78.0081,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","family","group","elderly"],
        "crowd": {"6":3,"7":5,"8":7,"9":9,"10":9,"11":8,"14":8,"15":9,"16":8,"17":6},
        "connects": ["Jaipur","Delhi","Varanasi"],
    },
    {
        "name": "Ayodhya",
        "lat": 26.7914, "lng": 82.1931,
        "best_months": [10,11,12,1,2,3,4],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly"],
        "crowd": {"6":6,"7":8,"8":7,"16":6,"17":8,"18":8},
        "connects": ["Varanasi","Lucknow"],
    },
    {
        "name": "Lucknow",
        "lat": 26.8467, "lng": 80.9462,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":7,"17":6},
        "connects": ["Varanasi","Agra","Ayodhya"],
    },
    {
        "name": "Mathura",
        "lat": 27.4924, "lng": 77.6737,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly"],
        "crowd": {"6":5,"7":8,"8":7,"16":6,"17":8,"18":9},
        "connects": ["Agra","Delhi","Vrindavan"],
    },
    {
        "name": "Prayagraj",
        "lat": 25.4358, "lng": 81.8463,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly","group"],
        "crowd": {"5":6,"6":8,"17":7,"18":8},
        "connects": ["Varanasi","Lucknow"],
    },

    # ═══════════════════════════════════════════════════════
    # DELHI
    # ═══════════════════════════════════════════════════════
    {
        "name": "Delhi",
        "lat": 28.6139, "lng": 77.2090,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"9":5,"10":7,"11":8,"14":7,"16":9,"17":8},
        "connects": ["Agra","Jaipur","Amritsar"],
    },

    # ═══════════════════════════════════════════════════════
    # MAHARASHTRA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Mumbai",
        "lat": 19.0760, "lng": 72.8777,
        "best_months": [10,11,12,1,2,3],
        "budget": 3, "dur": 2.5,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"8":5,"9":7,"10":8,"14":7,"16":9,"17":9,"18":9},
        "connects": ["Goa","Pune","Lonavala"],
    },
    {
        "name": "Pune",
        "lat": 18.5204, "lng": 73.8567,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":8,"17":7},
        "connects": ["Mumbai","Lonavala","Mahabaleshwar"],
    },
    {
        "name": "Lonavala",
        "lat": 18.7500, "lng": 73.4000,
        "best_months": [6,7,8,9,10,11,12],
        "budget": 2, "dur": 2.0,
        "types": ["couple","family","group"],
        "crowd": {"9":4,"10":6,"11":8,"14":7,"16":8},
        "connects": ["Mumbai","Pune","Mahabaleshwar"],
    },
    {
        "name": "Mahabaleshwar",
        "lat": 17.9227, "lng": 73.6589,
        "best_months": [10,11,12,1,2,3,4,5,6],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","elderly"],
        "crowd": {"9":3,"10":5,"11":7,"14":6,"16":7},
        "connects": ["Pune","Lonavala"],
    },
    {
        "name": "Aurangabad",
        "lat": 19.8762, "lng": 75.3433,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7},
        "connects": ["Mumbai","Pune"],
    },
    {
        "name": "Nashik",
        "lat": 19.9975, "lng": 73.7898,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","group","elderly"],
        "crowd": {"7":4,"8":7,"9":6,"16":5,"17":7,"18":8},
        "connects": ["Mumbai","Pune"],
    },

    # ═══════════════════════════════════════════════════════
    # KARNATAKA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Bangalore",
        "lat": 12.9716, "lng": 77.5946,
        "best_months": [1,2,3,4,5,6,7,8,9,10,11,12],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"9":4,"10":6,"11":7,"14":7,"16":7,"17":9},
        "connects": ["Mysore","Coorg","Hampi"],
    },
    {
        "name": "Mysore",
        "lat": 12.2958, "lng": 76.6394,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","family","elderly"],
        "crowd": {"8":3,"9":5,"10":8,"11":9,"14":7,"15":8,"16":7,"17":5},
        "connects": ["Bangalore","Coorg","Ooty"],
    },
    {
        "name": "Hampi",
        "lat": 15.3350, "lng": 76.4600,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 4.0,
        "types": ["solo_male","solo_female","couple","group"],
        "crowd": {"7":2,"8":4,"9":6,"10":7,"11":6,"14":5,"15":6,"16":7,"17":5},
        "connects": ["Bangalore","Goa","Badami"],
    },
    {
        "name": "Coorg",
        "lat": 12.3375, "lng": 75.8061,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 2, "dur": 4.0,
        "types": ["couple","family","group","elderly"],
        "crowd": {"8":2,"9":3,"10":5,"11":6,"14":5,"15":6,"16":5,"17":4},
        "connects": ["Mysore","Bangalore","Wayanad"],
    },
    {
        "name": "Gokarna",
        "lat": 14.5479, "lng": 74.3188,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","solo_female","group"],
        "crowd": {"9":3,"10":5,"14":6,"15":7,"16":6},
        "connects": ["Goa","Hampi"],
    },
    {
        "name": "Badami",
        "lat": 15.9200, "lng": 75.6800,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"8":2,"9":4,"10":6,"11":7,"14":5,"15":6},
        "connects": ["Hampi","Goa"],
    },
    {
        "name": "Chikmagalur",
        "lat": 13.3161, "lng": 75.7720,
        "best_months": [9,10,11,12,1,2,3,4],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"8":2,"9":4,"10":5,"14":5,"15":6},
        "connects": ["Coorg","Bangalore"],
    },

    # ═══════════════════════════════════════════════════════
    # TAMIL NADU
    # ═══════════════════════════════════════════════════════
    {
        "name": "Ooty",
        "lat": 11.4102, "lng": 76.6950,
        "best_months": [3,4,5,6,9,10,11,12],
        "budget": 2, "dur": 3.5,
        "types": ["couple","family","elderly"],
        "crowd": {"8":3,"9":5,"10":6,"11":7,"14":6,"15":7},
        "connects": ["Mysore","Coorg","Kodaikanal"],
    },
    {
        "name": "Kodaikanal",
        "lat": 10.2381, "lng": 77.4892,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","elderly"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7},
        "connects": ["Ooty","Madurai"],
    },
    {
        "name": "Madurai",
        "lat": 9.9252, "lng": 78.1198,
        "best_months": [10,11,12,1,2],
        "budget": 1, "dur": 2.5,
        "types": ["family","elderly","group"],
        "crowd": {"5":5,"6":8,"7":7,"16":5,"17":7,"18":8,"19":8},
        "connects": ["Rameswaram","Kanyakumari","Kodaikanal"],
    },
    {
        "name": "Rameswaram",
        "lat": 9.2881, "lng": 79.3174,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly"],
        "crowd": {"5":6,"6":8,"7":7,"16":5,"17":7,"18":8},
        "connects": ["Madurai","Kanyakumari"],
    },
    {
        "name": "Kanyakumari",
        "lat": 8.0883, "lng": 77.5385,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.0,
        "types": ["family","couple","elderly"],
        "crowd": {"6":4,"7":7,"8":6,"16":5,"17":7,"18":8},
        "connects": ["Madurai","Kovalam"],
    },
    {
        "name": "Mahabalipuram",
        "lat": 12.6269, "lng": 80.1927,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7},
        "connects": ["Chennai","Pondicherry"],
    },
    {
        "name": "Chennai",
        "lat": 13.0827, "lng": 80.2707,
        "best_months": [11,12,1,2,3],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"9":5,"10":7,"14":7,"16":8,"17":8},
        "connects": ["Mahabalipuram","Pondicherry"],
    },
    {
        "name": "Pondicherry",
        "lat": 11.9416, "lng": 79.8083,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_female","couple","group"],
        "crowd": {"9":4,"10":6,"11":7,"14":7,"16":8,"17":7},
        "connects": ["Mahabalipuram","Chennai"],
    },

    # ═══════════════════════════════════════════════════════
    # ANDHRA PRADESH & TELANGANA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Hyderabad",
        "lat": 17.3850, "lng": 78.4867,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"9":5,"10":7,"14":7,"16":8,"17":8},
        "connects": ["Hampi","Mumbai","Visakhapatnam"],
    },
    {
        "name": "Tirupati",
        "lat": 13.6288, "lng": 79.4192,
        "best_months": [1,2,3,4,5,6,7,8,9,10,11,12],
        "budget": 1, "dur": 1.5,
        "types": ["family","elderly"],
        "crowd": {"4":7,"5":9,"6":8,"15":7,"16":8,"17":7},
        "connects": ["Chennai","Hyderabad"],
    },
    {
        "name": "Visakhapatnam",
        "lat": 17.6868, "lng": 83.2185,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":7},
        "connects": ["Hyderabad","Araku Valley"],
    },
    {
        "name": "Araku Valley",
        "lat": 18.3273, "lng": 82.8736,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"8":3,"9":5,"10":6,"14":5,"15":6},
        "connects": ["Visakhapatnam"],
    },

    # ═══════════════════════════════════════════════════════
    # ODISHA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Puri",
        "lat": 19.8135, "lng": 85.8312,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly","group"],
        "crowd": {"6":6,"7":8,"8":7,"16":6,"17":8,"18":8},
        "connects": ["Bhubaneswar","Konark"],
    },
    {
        "name": "Bhubaneswar",
        "lat": 20.2961, "lng": 85.8245,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.5,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7},
        "connects": ["Puri","Konark"],
    },
    {
        "name": "Konark",
        "lat": 19.8876, "lng": 86.0945,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":8,"14":6,"15":7},
        "connects": ["Puri","Bhubaneswar"],
    },

    # ═══════════════════════════════════════════════════════
    # WEST BENGAL
    # ═══════════════════════════════════════════════════════
    {
        "name": "Kolkata",
        "lat": 22.5726, "lng": 88.3639,
        "best_months": [10,11,12,1,2],
        "budget": 2, "dur": 2.5,
        "types": ["solo_male","solo_female","couple","family","group"],
        "crowd": {"9":5,"10":7,"14":7,"16":8,"17":8},
        "connects": ["Darjeeling","Sundarbans"],
    },
    {
        "name": "Darjeeling",
        "lat": 27.0360, "lng": 88.2627,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 3.5,
        "types": ["couple","family","group","elderly"],
        "crowd": {"6":3,"7":6,"8":7,"9":7,"14":6,"15":7,"16":6},
        "connects": ["Kolkata","Gangtok","Kalimpong"],
    },
    {
        "name": "Sundarbans",
        "lat": 21.9497, "lng": 88.9468,
        "best_months": [9,10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"7":5,"8":7,"9":6,"14":5,"15":6},
        "connects": ["Kolkata"],
    },
    {
        "name": "Kalimpong",
        "lat": 27.0669, "lng": 88.4675,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","group"],
        "crowd": {"8":3,"9":5,"10":6,"14":5,"15":6},
        "connects": ["Darjeeling","Gangtok"],
    },

    # ═══════════════════════════════════════════════════════
    # GUJARAT
    # ═══════════════════════════════════════════════════════
    {
        "name": "Rann of Kutch",
        "lat": 23.7337, "lng": 69.8597,
        "best_months": [11,12,1,2],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"8":2,"9":4,"10":6,"14":5,"15":7,"16":8,"17":9},
        "connects": ["Ahmedabad","Dwarka"],
    },
    {
        "name": "Ahmedabad",
        "lat": 23.0225, "lng": 72.5714,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":7,"17":6},
        "connects": ["Rann of Kutch","Somnath","Vadodara"],
    },
    {
        "name": "Somnath",
        "lat": 20.9008, "lng": 70.3932,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 1.5,
        "types": ["family","elderly"],
        "crowd": {"5":5,"6":8,"7":7,"16":5,"17":7,"18":8},
        "connects": ["Dwarka","Gir National Park","Ahmedabad"],
    },
    {
        "name": "Dwarka",
        "lat": 22.2394, "lng": 68.9678,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["family","elderly"],
        "crowd": {"5":5,"6":7,"7":6,"16":5,"17":7,"18":8},
        "connects": ["Somnath","Rann of Kutch"],
    },
    {
        "name": "Gir National Park",
        "lat": 21.1240, "lng": 70.8260,
        "best_months": [12,1,2,3,4,5,6],
        "budget": 3, "dur": 4.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":6,"7":9,"8":8,"15":7,"16":8},
        "connects": ["Somnath","Ahmedabad"],
    },
    {
        "name": "Vadodara",
        "lat": 22.3072, "lng": 73.1812,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","couple","family"],
        "crowd": {"9":4,"10":6,"14":6,"16":7},
        "connects": ["Ahmedabad","Mumbai"],
    },

    # ═══════════════════════════════════════════════════════
    # MADHYA PRADESH
    # ═══════════════════════════════════════════════════════
    {
        "name": "Khajuraho",
        "lat": 24.8319, "lng": 79.9199,
        "best_months": [10,11,12,1,2,3],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"7":2,"8":4,"9":6,"10":7,"11":6,"14":5,"15":6,"16":5},
        "connects": ["Varanasi","Orchha","Panna"],
    },
    {
        "name": "Orchha",
        "lat": 25.3519, "lng": 78.6400,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.5,
        "types": ["solo_male","couple","group"],
        "crowd": {"7":2,"8":4,"9":6,"10":7,"14":5,"15":6},
        "connects": ["Khajuraho","Gwalior"],
    },
    {
        "name": "Bandhavgarh",
        "lat": 23.7220, "lng": 81.0100,
        "best_months": [11,12,1,2,3,4,5,6],
        "budget": 3, "dur": 4.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":6,"7":9,"8":8,"15":7,"16":9},
        "connects": ["Kanha","Khajuraho"],
    },
    {
        "name": "Kanha",
        "lat": 22.3310, "lng": 80.6110,
        "best_months": [11,12,1,2,3,4,5,6],
        "budget": 3, "dur": 4.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":6,"7":9,"8":8,"15":7,"16":9},
        "connects": ["Bandhavgarh","Pench"],
    },
    {
        "name": "Bhopal",
        "lat": 23.2599, "lng": 77.4126,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","couple","family"],
        "crowd": {"9":4,"10":6,"14":6,"16":7},
        "connects": ["Khajuraho","Orchha"],
    },

    # ═══════════════════════════════════════════════════════
    # PUNJAB & CHANDIGARH
    # ═══════════════════════════════════════════════════════
    {
        "name": "Amritsar",
        "lat": 31.6340, "lng": 74.8723,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","solo_female","couple","family","elderly"],
        "crowd": {"4":5,"5":7,"6":8,"9":6,"10":8,"18":8,"19":7},
        "connects": ["Delhi","Dharamshala","Chandigarh"],
    },
    {
        "name": "Chandigarh",
        "lat": 30.7333, "lng": 76.7794,
        "best_months": [9,10,11,12,1,2,3,4,5],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"9":4,"10":6,"14":6,"16":7},
        "connects": ["Amritsar","Shimla","Delhi"],
    },

    # ═══════════════════════════════════════════════════════
    # NORTHEAST INDIA
    # ═══════════════════════════════════════════════════════
    {
        "name": "Kaziranga",
        "lat": 26.5775, "lng": 93.1700,
        "best_months": [11,12,1,2,3,4],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","family","group"],
        "crowd": {"6":6,"7":9,"8":8,"15":6,"16":8},
        "connects": ["Guwahati","Majuli"],
    },
    {
        "name": "Majuli",
        "lat": 26.9500, "lng": 94.2000,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.5,
        "types": ["solo_male","solo_female","group"],
        "crowd": {"8":2,"9":4,"10":5,"14":4,"15":5},
        "connects": ["Kaziranga","Jorhat"],
    },
    {
        "name": "Cherrapunji",
        "lat": 25.2840, "lng": 91.7320,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","solo_female","group"],
        "crowd": {"8":3,"9":5,"10":6,"14":5,"15":6},
        "connects": ["Shillong"],
    },
    {
        "name": "Shillong",
        "lat": 25.5788, "lng": 91.8933,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 2.5,
        "types": ["couple","family","group"],
        "crowd": {"9":3,"10":5,"11":6,"14":6,"16":7},
        "connects": ["Cherrapunji","Guwahati"],
    },
    {
        "name": "Ziro",
        "lat": 27.5449, "lng": 93.8269,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 1, "dur": 3.0,
        "types": ["solo_male","group"],
        "crowd": {"8":2,"9":3,"10":4,"14":3,"15":4},
        "connects": ["Tawang"],
    },
    {
        "name": "Tawang",
        "lat": 27.5860, "lng": 91.8678,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 3.5,
        "types": ["solo_male","group"],
        "crowd": {"8":2,"9":4,"10":5,"14":4,"15":5},
        "connects": ["Ziro","Guwahati"],
    },
    {
        "name": "Gangtok",
        "lat": 27.3314, "lng": 88.6138,
        "best_months": [3,4,5,6,9,10,11],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":7,"14":6,"15":7,"16":6},
        "connects": ["Darjeeling","Kalimpong","Lachen"],
    },

    # ═══════════════════════════════════════════════════════
    # BIHAR & JHARKHAND
    # ═══════════════════════════════════════════════════════
    {
        "name": "Bodh Gaya",
        "lat": 24.6961, "lng": 84.9913,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","solo_female","family","elderly","group"],
        "crowd": {"6":5,"7":8,"8":7,"15":6,"16":7,"17":6},
        "connects": ["Varanasi","Nalanda","Rajgir"],
    },
    {
        "name": "Nalanda",
        "lat": 25.1358, "lng": 85.4446,
        "best_months": [10,11,12,1,2,3],
        "budget": 1, "dur": 2.0,
        "types": ["solo_male","couple","group","family"],
        "crowd": {"8":3,"9":5,"10":7,"11":7,"14":5,"15":6},
        "connects": ["Bodh Gaya","Rajgir"],
    },

    # ═══════════════════════════════════════════════════════
    # ANDAMAN & NICOBAR
    # ═══════════════════════════════════════════════════════
    {
        "name": "Havelock Island",
        "lat": 12.0304, "lng": 92.9826,
        "best_months": [11,12,1,2,3,4,5],
        "budget": 3, "dur": 4.0,
        "types": ["couple","solo_female","group"],
        "crowd": {"9":3,"10":5,"11":6,"14":6,"15":7,"16":6},
        "connects": ["Port Blair","Neil Island"],
    },
    {
        "name": "Port Blair",
        "lat": 11.6234, "lng": 92.7265,
        "best_months": [11,12,1,2,3,4,5],
        "budget": 2, "dur": 2.0,
        "types": ["couple","family","group"],
        "crowd": {"9":4,"10":6,"14":7,"15":7,"16":6},
        "connects": ["Havelock Island","Neil Island"],
    },
    {
        "name": "Neil Island",
        "lat": 11.8300, "lng": 93.0500,
        "best_months": [11,12,1,2,3,4,5],
        "budget": 2, "dur": 3.0,
        "types": ["couple","solo_female","group"],
        "crowd": {"9":2,"10":4,"14":5,"15":5,"16":4},
        "connects": ["Port Blair","Havelock Island"],
    },

    # ═══════════════════════════════════════════════════════
    # JAMMU & KASHMIR / LADAKH
    # ═══════════════════════════════════════════════════════
    {
        "name": "Leh",
        "lat": 34.1526, "lng": 77.5770,
        "best_months": [5,6,7,8,9],
        "budget": 3, "dur": 4.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"8":3,"9":5,"10":7,"11":7,"14":6,"15":7,"16":5},
        "connects": ["Nubra Valley","Pangong Lake","Spiti Valley"],
    },
    {
        "name": "Nubra Valley",
        "lat": 34.6500, "lng": 77.5500,
        "best_months": [6,7,8,9],
        "budget": 2, "dur": 3.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"9":3,"10":5,"14":5,"15":6,"16":5},
        "connects": ["Leh","Pangong Lake"],
    },
    {
        "name": "Pangong Lake",
        "lat": 33.7500, "lng": 78.6700,
        "best_months": [6,7,8,9],
        "budget": 2, "dur": 2.0,
        "types": ["solo_male","couple","group"],
        "crowd": {"8":2,"9":4,"10":6,"14":5,"15":7,"16":6},
        "connects": ["Leh","Nubra Valley"],
    },
    {
        "name": "Srinagar",
        "lat": 34.0837, "lng": 74.7973,
        "best_months": [4,5,6,9,10,11,12],
        "budget": 2, "dur": 3.5,
        "types": ["couple","family","elderly"],
        "crowd": {"8":3,"9":5,"10":7,"11":7,"14":6,"15":7,"16":6,"17":5},
        "connects": ["Gulmarg","Pahalgam"],
    },
    {
        "name": "Gulmarg",
        "lat": 34.0484, "lng": 74.3805,
        "best_months": [12,1,2,3,4,5,6,9,10,11],
        "budget": 3, "dur": 3.0,
        "types": ["couple","family","group"],
        "crowd": {"9":4,"10":6,"11":7,"14":6,"15":7},
        "connects": ["Srinagar","Pahalgam"],
    },
    {
        "name": "Pahalgam",
        "lat": 34.0122, "lng": 75.3153,
        "best_months": [4,5,6,9,10,11],
        "budget": 2, "dur": 3.0,
        "types": ["couple","family","elderly"],
        "crowd": {"8":3,"9":5,"10":6,"14":5,"15":6},
        "connects": ["Srinagar","Gulmarg"],
    },
]


def seed_destinations():
    db = SessionLocal()
    inserted = updated = failed = 0

    try:
        try:
            import h3 as h3lib
            # H3 Version Compatibility Wrapper (handles v3 and v4)
            def geo_to_h3_compat(lat, lng, res):
                if hasattr(h3lib, 'latlng_to_h3'): # v4
                    return h3lib.latlng_to_h3(lat, lng, res)
                return h3lib.geo_to_h3(lat, lng, res) # v3
            H3_AVAILABLE = True
        except ImportError:
            H3_AVAILABLE = False
            log.warning("h3 package not found — h3 indexes will be skipped. Run: pip install h3")

        for d in DESTINATIONS:
            try:
                existing = db.execute(
                    text("SELECT id FROM destination WHERE name = :name"),
                    {"name": d["name"]}
                ).fetchone()

                # Properly serialize lists to JSON strings
                best_months_json              = json.dumps(d["best_months"])
                compatible_traveler_types_json = json.dumps(d["types"])
                crowd_json                     = json.dumps(d.get("crowd", {}))
                connects_json                  = json.dumps(d.get("connects", []))

                # H3 indexes via compat wrapper
                h3_r7 = geo_to_h3_compat(d["lat"], d["lng"], 7) if H3_AVAILABLE else None
                h3_r9 = geo_to_h3_compat(d["lat"], d["lng"], 9) if H3_AVAILABLE else None

                params = {
                    "name":                       d["name"],
                    "lat":                        d["lat"],
                    "lng":                        d["lng"],
                    "best_months":                best_months_json,
                    "budget_category":            d["budget"],
                    "avg_visit_duration_hours":   d.get("dur", 3.0),
                    "compatible_traveler_types":   compatible_traveler_types_json,
                    "crowd_level_by_hour":         crowd_json,
                    "connects_well_with":          connects_json,
                    "h3_index_r7":                h3_r7,
                    "h3_index_r9":                h3_r9,
                }

                if existing:
                    db.execute(text("""
                        UPDATE destination SET
                            lat                        = :lat,
                            lng                        = :lng,
                            coordinates                = ST_MakePoint(:lng, :lat)::geography,
                            best_months                = :best_months::jsonb,
                            budget_category            = :budget_category,
                            avg_visit_duration_hours   = :avg_visit_duration_hours,
                            compatible_traveler_types  = :compatible_traveler_types::jsonb,
                            crowd_level_by_hour        = :crowd_level_by_hour::jsonb,
                            connects_well_with         = :connects_well_with::jsonb,
                            h3_index_r7                = :h3_index_r7,
                            h3_index_r9                = :h3_index_r9
                        WHERE id = :id
                    """), {**params, "id": existing.id})
                    log.info(f"  Updated : {d['name']}")

                    updated += 1
                else:
                    db.execute(text("""
                        INSERT INTO destination (
                            name, lat, lng, coordinates,
                            best_months, budget_category, avg_visit_duration_hours,
                            compatible_traveler_types, crowd_level_by_hour,
                            connects_well_with, h3_index_r7, h3_index_r9
                        ) VALUES (
                            :name, :lat, :lng, ST_MakePoint(:lng, :lat)::geography,
                            :best_months::jsonb, :budget_category, :avg_visit_duration_hours,
                            :compatible_traveler_types::jsonb, :crowd_level_by_hour::jsonb,
                            :connects_well_with::jsonb, :h3_index_r7, :h3_index_r9
                        )
                    """), params)
                    log.info(f"  Inserted: {d['name']}")

                    inserted += 1

            except Exception as row_err:
                log.error(f"  FAILED  : {d['name']} — {row_err}")

                failed += 1
                continue   # skip bad row, continue with rest

        db.commit()

    except Exception as e:
        db.rollback()
        log.error(f"Transaction failed: {e}")

        raise
    finally:
        db.close()

    log.info("─" * 50)
    log.info(f"Seeding complete: {inserted} inserted, {updated} updated, {failed} failed")
    log.info(f"Total destinations: {inserted + updated} / {len(DESTINATIONS)}")



if __name__ == "__main__":
    seed_destinations()