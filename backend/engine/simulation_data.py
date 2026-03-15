from collections import namedtuple

# Define the Big Tech POI structure
POI = namedtuple('POI', [
    'id', 'name', 'lat', 'lng', 'h3_index_r9', 
    'entry_cost', 'type', 'avg_visit_duration_hours', 
    'budget_category', 'popularity_score', 'user_skip_rate', 
    'best_visit_time_hour', 'crowd_level_by_hour', 
    'destination_id', 'destination_name',
    'intensity_score', 'local_secret', 'best_visit_window',
    'hidden_gem_factor', 'why_fits'
])

SIMULATED_CITIES = {
    "Jaipur": [
        POI(101, "Amber Fort", 26.9855, 75.8513, None, 200, "heritage", 3.0, 2, 98.0, 0.02, 10, {9:1, 10:2, 11:3, 12:3}, 1, "Jaipur", 8, "Reach early for the elephant ride before queues peak.", [8, 11], 0.1, "Iconic landmark for history buffs."),
        POI(102, "Hawa Mahal", 26.9239, 75.8267, None, 50, "heritage", 1.0, 1, 95.0, 0.05, 9, {8:1, 9:2, 17:3}, 1, "Jaipur", 5, "Best photographed from the rooftop cafes opposite.", [8, 10], 0.2, "Breathtaking Rajput architecture."),
        POI(103, "Jantar Mantar", 26.9248, 75.8245, None, 50, "scientific", 1.5, 1, 90.0, 0.08, 14, {14:3, 15:3, 16:2}, 1, "Jaipur", 4, "Hire a guide to explain the astronomical instruments.", [14, 16], 0.4, "World's largest stone sundial."),
        POI(104, "Nahargarh Fort Dusk View", 26.9374, 75.8155, None, 50, "nature", 2.0, 1, 92.0, 0.1, 17, {17:3, 18:3, 19:3}, 1, "Jaipur", 6, "Watch the sunset overlooking the Pink City.", [17, 19], 0.3, "Stunning panoramic views."),
        POI(105, "Panna Meena ka Kund", 26.9839, 75.8532, None, 0, "heritage", 0.5, 1, 85.0, 0.15, 8, {8:1, 9:2}, 1, "Jaipur", 3, "A symmetrical stepwell, perfect for photos.", [8, 10], 0.8, "An photogenic hidden gem."),
        POI(106, "Chokhi Dhani", 26.7667, 75.8333, None, 800, "cultural", 4.0, 2, 88.0, 0.12, 19, {19:2, 20:3, 21:3}, 1, "Jaipur", 7, "A village-themed dinner experience with folk dances.", [19, 23], 0.2, "Deep dive into Rajasthani culture."),
    ],
    "Goa": [
        POI(201, "Basilica of Bom Jesus", 15.5009, 73.9116, None, 0, "religious", 1.0, 1, 97.0, 0.03, 10, {10:2, 11:3}, 2, "Goa", 4, "Unesco World Heritage site, houses body of St. Francis Xavier.", [9, 12], 0.1, "Spiritual heart of Old Goa."),
        POI(202, "Dudhsagar Falls", 15.3144, 74.3142, None, 400, "nature", 6.0, 2, 94.0, 0.05, 9, {9:1, 10:2}, 2, "Goa", 9, "Advance booking for the jeep safari is mandatory.", [8, 15], 0.3, "Majestic milky white waterfalls."),
        POI(203, "Fontainhas Latin Quarter", 15.4989, 73.8340, None, 0, "heritage", 2.0, 1, 90.0, 0.08, 16, {16:1, 17:2}, 2, "Goa", 5, "Vibrant Portuguese houses; walk the narrow streets.", [16, 18], 0.5, "Colorful colonial charm."),
        POI(204, "Anjuna Beach Flea Market", 15.5724, 73.7437, None, 0, "shopping", 3.0, 1, 85.0, 0.1, 14, {14:2, 15:3, 16:3}, 2, "Goa", 6, "Only on Wednesdays; great for bohemian vibes.", [11, 17], 0.4, "Eclectic shopping experience."),
        POI(205, "Cabo de Rama Fort", 15.0883, 73.9213, None, 0, "nature", 1.5, 1, 82.0, 0.2, 17, {17:2, 18:3}, 2, "Goa", 5, "Best sunset views in South Goa, less crowded.", [16, 18], 0.9, "Remote, peaceful coastal fort."),
        POI(206, "Thalassa Vibe Dinner", 15.5947, 73.7348, None, 1500, "culinary", 3.0, 3, 92.0, 0.04, 19, {19:3, 20:3}, 2, "Goa", 7, "Greek taverna with world-famous sunset fire shows.", [18, 22], 0.3, "Premium dining with a view."),
    ],
    "Mumbai": [
        POI(301, "Gateway of India", 18.9220, 72.8347, None, 0, "heritage", 1.0, 1, 99.0, 0.01, 9, {8:1, 9:2, 10:3}, 3, "Mumbai", 6, "Take the ferry to Elephanta Caves from here.", [8, 10], 0.0, "The face of Mumbai."),
        POI(302, "Marine Drive (Queen's Necklace)", 18.9430, 72.8230, None, 0, "recreation", 1.5, 1, 96.0, 0.05, 18, {18:3, 19:3, 20:3}, 3, "Mumbai", 4, "A midnight walk here is peaceful and safe.", [17, 21], 0.1, "Iconic seaside promenade."),
        POI(303, "Dhobi Ghat Viewpoint", 18.9830, 72.8270, None, 0, "cultural", 0.5, 1, 85.0, 0.15, 8, {8:2, 9:3}, 3, "Mumbai", 5, "World's largest outdoor laundry; best from the bridge.", [8, 10], 0.6, "Industrial soul of the city."),
        POI(304, "Leopold Cafe", 18.9234, 72.8317, None, 800, "culinary", 1.5, 2, 88.0, 0.1, 13, {13:3, 14:3}, 3, "Mumbai", 5, "Historic cafe mentioned in 'Shantaram'.", [11, 22], 0.2, "Cosmopolitan vibes."),
        POI(305, "Elephanta Caves", 18.9633, 72.9315, None, 300, "heritage", 4.0, 2, 82.0, 0.2, 10, {10:2, 11:3, 12:3}, 3, "Mumbai", 8, "Ferry ride takes 1 hour; check tide timings.", [9, 14], 0.4, "Ancient rock-cut temples."),
    ]
}

def GET_SIM_DATA(city="Jaipur"):
    return SIMULATED_CITIES.get(city, SIMULATED_CITIES["Jaipur"])
