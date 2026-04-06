"""
scripts/seed_blogs.py — Seed initial blog posts for AltairGO CMS.

Inserts 8 curated India travel blog posts covering key categories.
Idempotent: skips if any posts already exist.

Usage:
  python -m backend.scripts.seed_blogs
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import structlog

log = structlog.get_logger(__name__)

BLOG_POSTS = [
    {
        "title": "India on a Budget: 10 Destinations Under ₹2,000/Day",
        "category": "Budget Travel",
        "date": "2026-03-15",
        "read_time": "7 min read",
        "image": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=800",
        "excerpt": "Explore India's most iconic destinations without breaking the bank. From Varanasi's ghats to Hampi's ruins, we reveal how to travel India for under ₹2,000 a day.",
        "content": """# India on a Budget: 10 Destinations Under ₹2,000/Day

India is one of the most affordable travel destinations in the world — if you know where to go and how to plan. Here are 10 incredible destinations where you can live well for under ₹2,000 per day.

## 1. Hampi, Karnataka
The ancient ruins of the Vijayanagara Empire spread across a surreal boulder-strewn landscape. Guesthouses near the Hampi Bazaar cost ₹400–700/night and local meals are under ₹100.

## 2. Pushkar, Rajasthan
A sacred town on the banks of a holy lake. Budget guesthouses line every lane and the famous Pushkar Lake draws pilgrims and backpackers alike.

## 3. Varanasi, Uttar Pradesh
Witness the eternal rituals on the Ganges ghats. Rooftop guesthouses with river views start from ₹500/night.

## 4. Mcleodganj, Himachal Pradesh
Home to the Dalai Lama and a thriving Tibetan community. Momos cost ₹60, cafes are plentiful, and the trekking is free.

## 5. Pondicherry, Tamil Nadu
French colonial architecture meets Tamil culture. Hostels run from ₹400/night and the beaches are free.

## 6. Orchha, Madhya Pradesh
An underrated gem with 16th-century temples and cenotaphs. Virtually no tourist crowds and budget rooms from ₹350/night.

## 7. Spiti Valley, Himachal Pradesh
Remote Himalayan monasteries and stark moonscapes. Homestays are cheap and deeply authentic.

## 8. Gokarna, Karnataka
A quieter alternative to Goa with pristine beaches. Beach shacks offer rooms from ₹500/night.

## 9. Ujjain, Madhya Pradesh
One of the holiest cities in India with free temple access and dharmashala accommodation from ₹200/night.

## 10. Coorg, Karnataka
India's coffee capital. Plantation homestays are surprisingly affordable outside peak season.

**Pro tip:** Use AltairGO to generate a cost-optimized itinerary for any of these destinations — our budget allocator automatically finds the cheapest accommodation tier for your travel party.
""",
        "tags": ["budget", "backpacking", "india", "affordable"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "Monsoon Magic: Why Rainy Season is India's Best-Kept Secret",
        "category": "Seasonal Travel",
        "date": "2026-04-01",
        "read_time": "6 min read",
        "image": "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=800",
        "excerpt": "Most tourists flee India in July. Smart travelers know that monsoon season transforms the country into a lush, crowd-free paradise with waterfalls you won't believe.",
        "content": """# Monsoon Magic: Why Rainy Season is India's Best-Kept Secret

From June to September, India receives the southwest monsoon — and while most tourists avoid it, seasoned travellers consider it the most spectacular time to visit.

## Why Monsoon is Underrated

**Prices drop 30–50%.** Peak-season crowds vanish. The landscapes turn intensely green. Waterfalls appear from nowhere. Festivals like Onam and Teej coincide with the rains.

## Best Monsoon Destinations

### Kerala Backwaters
The backwaters fill up and the rice fields turn electric green. Houseboat rates drop significantly and the air is cool and fragrant.

### Coorg & Wayanad
These coffee and spice plantations receive heavy rainfall, making them misty, atmospheric, and deeply romantic. Waterfalls like Abbey Falls are at peak flow.

### Meghalaya
Home to the wettest place on Earth (Mawsynram), Meghalaya's living root bridges are surrounded by roaring rivers during monsoon — a UNESCO-worthy spectacle.

### Rajasthan Deserts
Even the Thar Desert gets a brief green flush. The Rann of Kutch transforms into a shallow lake reflecting the sky.

## What to Pack
- Lightweight rain jacket (not umbrella — too unwieldy)
- Waterproof sandals or quick-dry footwear
- Dry bags for electronics

## What to Avoid
The Himalayas during peak monsoon carry landslide risk on mountain roads. Plan Leh-Ladakh between June and September only if flying in.

AltairGO's itinerary engine automatically factors in seasonal scores for each destination — so your generated trip will always account for monsoon conditions.
""",
        "tags": ["monsoon", "seasonal", "kerala", "meghalaya", "offbeat"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "Hidden Gems of India: 8 Places Most Tourists Miss",
        "category": "Offbeat Travel",
        "date": "2026-03-20",
        "read_time": "8 min read",
        "image": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
        "excerpt": "Beyond the Golden Triangle and Goa lies a staggering India that most visitors never see. These 8 destinations will completely reframe what you think India is.",
        "content": """# Hidden Gems of India: 8 Places Most Tourists Miss

The Golden Triangle (Delhi-Agra-Jaipur) is magnificent, but India has thousands of destinations that see a fraction of the footfall they deserve.

## 1. Ziro Valley, Arunachal Pradesh
A UNESCO World Heritage nomination site. The Apatani tribe's paddy fields and pine forests create a landscape unlike anywhere in India. Almost zero tourist infrastructure — bring a tent.

## 2. Mandu, Madhya Pradesh
A ruined medieval capital on a plateau, with massive Afghan-style mosques, royal palaces and stepwells. You'll have most of it to yourself.

## 3. Chettinad, Tamil Nadu
The heartland of one of India's most complex cuisines. The palatial mansions of the Nattukotai Chettiars are architectural wonders slowly being restored.

## 4. Majuli, Assam
The world's largest river island, home to the Vaishnav satras (monasteries) that preserve a 600-year-old tradition of masked dance and manuscript art.

## 5. Lepakshi, Andhra Pradesh
A 16th-century temple complex with the largest Nandi statue in India, a hanging pillar that defies physics, and frescoes in perfect condition.

## 6. Dholavira, Gujarat
The best-preserved city of the Indus Valley Civilisation, a UNESCO site with a 5,000-year-old water conservation system that still works.

## 7. Unakoti, Tripura
A cliff face carved with enormous bas-relief sculptures of Shiva — some rising 9 metres tall — hidden in a jungle.

## 8. Tawang, Arunachal Pradesh
A Tibetan-Buddhist monastery town at 10,000 feet. The monastery is the second largest in the world after Lhasa.

AltairGO includes all of these destinations in its database. Just tell it your travel style and budget — it will find the hidden gems that match.
""",
        "tags": ["offbeat", "hidden gems", "northeast india", "unexplored"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "A Foodie's Guide to India: 12 Cities, 12 Signature Dishes",
        "category": "Food & Culture",
        "date": "2026-03-25",
        "read_time": "9 min read",
        "image": "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=800",
        "excerpt": "India's food map is as diverse as its geography. Every city has a dish it owns. Here's the definitive eat-your-way-around guide.",
        "content": """# A Foodie's Guide to India: 12 Cities, 12 Signature Dishes

Indian cuisine is not one cuisine — it's dozens of distinct regional traditions that happen to share a subcontinent.

## The Map

| City | Signature Dish | Where to Eat |
|------|---------------|--------------|
| Mumbai | Vada Pav | Anand Stall, Dadar |
| Delhi | Butter Chicken | Moti Mahal, Daryaganj |
| Kolkata | Kathi Roll | Nizam's, New Market |
| Chennai | Chettinad Chicken | Ponnusamy Hotel |
| Hyderabad | Dum Biryani | Paradise Restaurant |
| Lucknow | Galouti Kebab | Tunday Kababi |
| Amritsar | Amritsari Kulcha | Kanha Sweets |
| Indore | Poha-Jalebi | Sarafa Bazaar |
| Pune | Misal Pav | Bedekar Tea Stall |
| Ahmedabad | Dhokla & Undhiyu | Old City stalls |
| Jaipur | Laal Maas | Niro's Restaurant |
| Kochi | Fish Molee | Oceanos |

## Food Trail Tips

**Eat where locals eat.** The best food in India is rarely in tourist restaurants. Follow office workers at lunch.

**Street food is safe** when it's hot, freshly cooked, and the stall is busy. Avoid pre-cut fruit at roadside stalls.

**Vegetarian travellers** will find India paradise — roughly 40% of Indians are vegetarian and restaurants cater accordingly.

**Timing matters.** Lucknow's Tunday Kababi sells out by 2pm. Kolkata's Kathi Roll stalls only open at dinner.

AltairGO's itinerary engine adds local food recommendations to every day's plan — look for the `foodie` tag in vibe preferences when generating your trip.
""",
        "tags": ["food", "culture", "street food", "cuisine"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "Family Travel in India: The Complete 2026 Guide",
        "category": "Family Travel",
        "date": "2026-04-05",
        "read_time": "10 min read",
        "image": "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800",
        "excerpt": "Travelling India with kids requires planning — but the payoff is extraordinary. Wildlife safaris, sand dunes, ancient forts, and train journeys that children never forget.",
        "content": """# Family Travel in India: The Complete 2026 Guide

India is a spectacular family destination — chaotic, yes, but endlessly rewarding when planned well.

## Top Family Destinations

### Ranthambore National Park
A tiger reserve where sightings are genuinely likely. Safari jeeps are safe and guides are excellent. Stay in a resort with a pool — kids need downtime after game drives.

### Jaisalmer, Rajasthan
The golden fort, camel safaris into the Thar Desert, and folk music under the stars. Children find the scale of the desert profoundly impressive.

### Jim Corbett National Park
India's oldest national park. Elephant safaris, jungle walks, and river rafting on the Kosi River nearby.

### Coorg
Zip-lining through coffee plantations, elephant camps (ethical — check ratings), and cool mountain air that avoids the heat problem.

### Goa (North)
Calangute and Baga beaches are calm enough for young children. Spice farm tours and the Old Goa churches add culture between beach days.

## Practical Tips for Families

**Train travel** is one of the highlights for children — book 2AC tier for comfort, book 60 days in advance.

**Monsoon + families** — Avoid July/August unless going to hill stations. The rain is too heavy for outdoor activities with young kids.

**Accommodation** — Select hotels with a pool. Heat management is the biggest challenge with children under 10.

**Food** — Most Indian cities now have reliable continental options for picky eaters. Stick to cooked food; avoid raw salads.

AltairGO marks attractions with `family_friendly` compatibility tags. When generating your trip, set traveller type to `family` for age-appropriate recommendations.
""",
        "tags": ["family", "kids", "wildlife", "rajasthan"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "The Himalayan Trekking Calendar: When to Go Where",
        "category": "Adventure",
        "date": "2026-03-10",
        "read_time": "7 min read",
        "image": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800",
        "excerpt": "The Himalayas are accessible year-round — but the window for each trek varies by just a few weeks. Get the calendar wrong and you'll face closed passes or whiteouts.",
        "content": """# The Himalayan Trekking Calendar: When to Go Where

India's Himalayan range stretches 2,500km across six states. Each zone has a different climate — and different optimal trekking windows.

## The Calendar

### March–May (Pre-Monsoon)
Best for: **Uttarakhand** (Valley of Flowers opens in late June), **Himachal Pradesh** (Hampta Pass, Kheerganga)

Snow is receding, rhododendrons are in bloom, and the air is crisp. Crowds are lower than post-monsoon.

### June–September (Monsoon)
Best for: **Ladakh** (rain shadow zone — dry while rest of India is wet), **Spiti Valley**, **Zanskar**

While the rest of India is drenched, Leh-Ladakh gets only 50mm of annual rainfall. The Markha Valley and Stok Kangri window is June–September.

### September–November (Post-Monsoon)
Best for: **Sikkim** (Goecha La, Dzongri), **Arunachal Pradesh**, **entire Uttarakhand**

This is the sweet spot for most Himalayan treks. Skies are clear, visibility is exceptional, and the golden-brown landscapes are stunning.

### December–February (Winter)
Best for: **Chadar Trek** (frozen Zanskar River), **Kedarkantha** (snow camping)

Only experienced trekkers in proper gear. Temperatures drop to -30°C in Ladakh.

## Permit Requirements
- Uttarakhand: No permit for most trails; Inner Line Permit for Niti/Mana villages
- Ladakh: Inner Line Permit for Nubra, Pangong, Hanle
- Arunachal Pradesh: Protected Area Permit (apply 2 weeks ahead)

AltairGO includes permit requirements and seasonal warnings in every generated Himalayan itinerary.
""",
        "tags": ["trekking", "himalayas", "adventure", "ladakh", "uttarakhand"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "Luxury India: 7 Palaces Where Maharajas Still Live",
        "category": "Luxury Travel",
        "date": "2026-03-28",
        "read_time": "6 min read",
        "image": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800",
        "excerpt": "India invented palatial hospitality. These seven palace hotels are still owned by royal families — and staying in them is an experience unlike any hotel chain can offer.",
        "content": """# Luxury India: 7 Palaces Where Maharajas Still Live

India has more palace hotels than any country on Earth — and the finest are still owned and managed by the royal families who built them.

## The Seven Palaces

### 1. Umaid Bhawan Palace, Jodhpur
The world's sixth-largest private residence, part of which is now a Taj Hotel. The current Maharaja still lives in one wing. The pool is legendary.

### 2. Taj Lake Palace, Udaipur
Built on an island in Lake Pichola in 1746, it appears to float on the water. One of the world's most photographed hotels.

### 3. Samode Palace, Rajasthan
A hilltop fort 40km from Jaipur. The tented camp in the valley below is equally extraordinary.

### 4. Neemrana Fort Palace, Alwar
A 15th-century fort converted into India's first heritage hotel. The tiered gardens and infinity pool over the valley are breathtaking.

### 5. Falaknuma Palace, Hyderabad
A Nizam's palace that Taj Hotels restored to its original 1894 grandeur. The 32-seat dining table where the Nizam hosted kings is still in use.

### 6. Ahilya Fort, Maheshwar
A boutique river palace on the Narmada owned by the descendants of Ahilya Bai Holkar. Just 12 rooms; three-course dinners on the terrace.

### 7. Coorg Wilderness Resort (Private Estate)
Not a palace, but a working 400-acre coffee estate that hosts 8 guests. The family has farmed this land for 200 years.

AltairGO's luxury tier activates palace and heritage hotel options in budget allocation when your daily per-person budget exceeds ₹8,000.
""",
        "tags": ["luxury", "palace hotels", "rajasthan", "heritage"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
    {
        "title": "Solo Female Travel in India: An Honest 2026 Guide",
        "category": "Solo Travel",
        "date": "2026-04-03",
        "read_time": "11 min read",
        "image": "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800",
        "excerpt": "India can be an incredible destination for solo women travellers — with the right preparation, destination choices, and mindset. Here's what no one else will tell you.",
        "content": """# Solo Female Travel in India: An Honest 2026 Guide

India receives more solo female travellers every year — and the experience has genuinely improved over the past decade. This guide is honest about both the rewards and the realities.

## The Tier System

Not all of India is the same for solo women. Think in tiers:

**Tier 1 — Most comfortable:** Goa, Kerala, Pondicherry, Himachal Pradesh (Manali, Kasol, Mcleodganj), Rajasthan tourist circuit (Jaipur, Jodhpur, Udaipur), Mumbai, Bengaluru.

**Tier 2 — Good with awareness:** Delhi (South Delhi, Hauz Khas), Kolkata, Hyderabad, Coorg, Rishikesh, Varanasi, Hampi.

**Tier 3 — Requires extra preparation:** Rural Uttar Pradesh, rural Bihar, isolated areas without tourist infrastructure.

## Practical Safety

**Accommodation:** Book the first night before arrival. Read reviews specifically mentioning solo female safety. Hostels with female-only dorms are a good option.

**Transport:** Use Ola/Uber for rides — digital trail, driver accountability. Avoid unmarked autos after dark. Women-only compartments exist on many trains.

**Dress:** Context-dependent. Western clothes are fine in Goa and Bengaluru. Cover shoulders and knees in temple towns and rural areas.

**Instincts:** If a situation feels off, leave it. India's social fabric means there are always other people nearby. Ask women for help — shopkeepers, hotel staff, other travellers.

## What No One Tells You

The warmth of Indian hospitality is real and it transforms the experience. Families on trains will share food and worry about your wellbeing. Temple priests will offer blessings. Children will want selfies.

The uncomfortable attention is also real. Having a strategy for managing it — polite but firm deflection, moving on quickly — makes the difference.

AltairGO marks destinations with `solo_female` compatibility in the traveller type filter. Use it when generating your itinerary.
""",
        "tags": ["solo female", "safety", "women travel", "practical"],
        "author": "AltairGO Travel Team",
        "published": True,
    },
]


def run_seed() -> dict:
    from backend.database import SessionLocal
    from backend.models import BlogPost

    db = SessionLocal()
    try:
        existing = db.query(BlogPost).count()
        if existing > 0:
            print(f"Skipping: {existing} blog posts already exist.")
            return {"seeded": 0, "skipped": existing}

        for post_data in BLOG_POSTS:
            post = BlogPost(**post_data)
            db.add(post)

        db.commit()
        count = len(BLOG_POSTS)
        print(f"Seeded {count} blog posts.")
        return {"seeded": count, "skipped": 0}

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
