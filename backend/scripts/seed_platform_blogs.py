"""
scripts/seed_platform_blogs.py — Seed the 12 high-fidelity frontend travel blog posts into the backend.
Clears existing blog posts to ensure a clean state matching the frontend design and content.

Usage:
  .venv\\Scripts\\python -m backend.scripts.seed_platform_blogs
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import structlog

log = structlog.get_logger(__name__)

PLATFORM_BLOGS = [
    {
        "title": "Hidden Valleys of Meghalaya",
        "excerpt": "A journey into the untouched beauty of the Northeast.",
        "category": "Adventure",
        "date": "2024-05-18",
        "read_time": "8 min read",
        "image": "meghalaya-bridges.jpg",
        "author": "Rohan Das",
        "content": """
<p>Meghalaya, the "abode of clouds," is a land of jaw-dropping landscapes, misty canyons, and ancient green forests. Hidden deep within its valleys are some of the most remarkable natural and man-made wonders of the Indian subcontinent.</p>

<h3>The Living Root Bridges</h3>
<p>In the wettest regions of Cherrapunji (Sohra) and Mawlynnong, the indigenous Khasi and Jaintia tribes have perfected a unique form of bio-engineering. Over generations, they have trained the roots of the <i>Ficus elastica</i> tree to grow across wild mountain torrents, forming sturdy living bridges that grow stronger with time. The double-decker living root bridge in Nongriat village is a testament to this harmonious relationship between humanity and nature, requiring a descent of over 3,000 steps through lush jungle.</p>

<h3>Mawlynnong: Asia's Cleanest Village</h3>
<p>Mawlynnong is a picturesque village renowned for its extreme cleanliness, floral gardens, and community-led eco-tourism. Strolling through the village, you will see bamboo dustbins at every corner, manicured pathways, and friendly locals who take immense pride in preserving their natural heritage.</p>

<h3>Dawki and the Umngot River</h3>
<p>Further south, bordering Bangladesh, lies Dawki. Here, the Umngot River boasts waters so incredibly clear that boats floating on it appear as if they are suspended in mid-air. The emerald water, contrasting against the dark riverbed and surrounding cliffs, offers a surreal experience that stays with travelers forever.</p>
        """,
        "tags": ["Northeast", "Trekking", "Eco-tourism", "Nature"],
        "published": True
    },
    {
        "title": "10 Breathtaking Lakes You Must See Before You Die",
        "excerpt": "Discover the serene, crystal-clear, and high-altitude lakes of India that offer magical views and peace.",
        "category": "Grande Drive",
        "date": "2024-05-12",
        "read_time": "6 min read",
        "image": "kashmir.jpg",
        "author": "Aisha Sen",
        "content": """
<p>From the high-altitude water bodies of the Himalayas to the tranquil backwaters of the south, India is home to some of the most spectacular lakes on Earth. Here is our selection of the top ten lakes that should be on every traveler's bucket list.</p>

<h3>1. Pangong Tso, Ladakh</h3>
<p>Situated at a height of 4,225 meters, Pangong Tso is a long narrow basin of inland drainage that changes colors from deep blue to turquoise and light green throughout the day. It spans from India to Tibet and is one of the most photographed lakes in Asia.</p>

<h3>2. Gurudongmar Lake, Sikkim</h3>
<p>One of the highest lakes in the world, Gurudongmar is sacred to Buddhists, Sikhs, and Hindus alike. Surrounded by snow-clad peaks, a part of the lake never freezes even in the coldest winter, which is believed to be a blessing from Guru Padmasambhava.</p>

<h3>3. Dal Lake, Jammu & Kashmir</h3>
<p>Known as the "Jewel in the crown of Kashmir," Dal Lake is iconic for its houseboats and shikaras (wooden boats). The floating gardens and floating markets offer a glimpse into the traditional lifestyle of Srinagar.</p>
        """,
        "tags": ["Lakes", "Himalayas", "Ladakh", "Kashmir", "Scenic"],
        "published": True
    },
    {
        "title": "Coastal Bliss: Best Beaches in India for Your Next Escape",
        "excerpt": "From the pristine sands of Andaman to the vibrant shores of Goa, explore the ultimate coastal retreats.",
        "category": "Beach Escapes",
        "date": "2024-05-10",
        "read_time": "5 min read",
        "image": "andaman-islands.jpg",
        "author": "Vikram Malhotra",
        "content": """
<p>With a coastline stretching over 7,500 kilometers, India offers an incredible variety of beach destinations. Whether you are looking for vibrant beach parties, adventurous water sports, or secluded, quiet sands, there is a beach for you.</p>

<h3>Radhanagar Beach, Havelock Island</h3>
<p>Consistently rated as one of the best beaches in Asia, Radhanagar Beach in the Andaman and Nicobar Islands is famous for its powder-soft white sand, turquoise waters, and lush green forest canopy that runs right up to the shoreline.</p>

<h3>Varkala Beach, Kerala</h3>
<p>Varkala is unique for its dramatic red cliffs that overlook the Arabian Sea. It is a popular spot for yoga retreats, sunset views, and enjoying fresh seafood at cliffside cafes.</p>

<h3>Palolem Beach, Goa</h3>
<p>Located in South Goa, Palolem is a crescent-shaped beach lined with coconut palms and colorful beach shacks. Its calm waters make it perfect for swimming and kayaking.</p>
        """,
        "tags": ["Beaches", "Andaman", "Goa", "Coastal"],
        "published": True
    },
    {
        "title": "Cultural Journeys That Connect You Deeper",
        "excerpt": "Immerse yourself in India’s ancient traditions, spiritual centers, and historic architectures.",
        "category": "Culture",
        "date": "2024-05-08",
        "read_time": "7 min read",
        "image": "journal_varanasi.png",
        "author": "Meera Iyer",
        "content": """
<p>India is a living museum of ancient cultures, deep spiritual practices, and legendary architectures. A cultural journey here is not just about visiting monuments; it is about connecting with living traditions.</p>

<h3>Varanasi: The Spiritual Heart</h3>
<p>Varanasi, one of the oldest continuously inhabited cities in the world, is the spiritual capital of India. The evening Ganga Aarti ceremony at Dashashwamedh Ghat, with its synchronized brass lamps and chanting, is an intensely moving spectacle of devotion.</p>

<h3>Hampi: The Ruins of an Empire</h3>
<p>Hampi, the former capital of the Vijayanagara Empire, is a UNESCO World Heritage site scattered with hundreds of ancient temples, palaces, and ruins set amidst a surreal landscape of giant boulders and banana plantations.</p>
        """,
        "tags": ["Culture", "Varanasi", "Heritage", "History"],
        "published": True
    },
    {
        "title": "Luxury Retreats in India for the Soulful Traveler",
        "excerpt": "Experience world-class hospitality, heritage palaces, and nature wellness sanctuaries.",
        "category": "Luxury Stays",
        "date": "2024-05-05",
        "read_time": "6 min read",
        "image": "luxury-resort.jpg",
        "author": "Karan Oberoi",
        "content": """
<p>India is home to some of the most luxurious and iconic hotels in the world, many of which are historic palaces converted into ultra-luxury resorts that preserve their original royal splendor.</p>

<h3>Taj Lake Palace, Udaipur</h3>
<p>Floating in the middle of Lake Pichola, this white-marble palace is the epitome of romantic luxury. Originally built as a royal summer palace, it offers guests private butler service, royal boat rides, and stunning views of the City Palace.</p>

<h3>Ananda in the Himalayas, Rishikesh</h3>
<p>Located in the Himalayan foothills, Ananda is a world-renowned wellness sanctuary built around a Maharaja's palace estate. It offers personalized Ayurveda, yoga, and meditation programs to rejuvenate the body and mind.</p>
        """,
        "tags": ["Luxury", "Resorts", "Palaces", "Wellness"],
        "published": True
    },
    {
        "title": "Monsoon Magic: Best Places to Visit in India",
        "excerpt": "Lush green valleys and mist-covered hills await during the Indian monsoons.",
        "category": "Short Reads",
        "date": "2024-05-02",
        "read_time": "4 min read",
        "image": "munnar-tea.jpg",
        "author": "Ananya Rao",
        "content": "<p>Monsoons transform the Indian landscape into a vibrant green paradise. From the tea gardens of Munnar to the misty valleys of Coorg, experience the romance of the rains.</p>",
        "tags": ["Monsoon", "Nature", "Munnar"],
        "published": True
    },
    {
        "title": "Weekend Getaways from Delhi Under 300 km",
        "excerpt": "Quick weekend road trips to historic forts and scenic hills to escape the city.",
        "category": "Short Reads",
        "date": "2024-04-28",
        "read_time": "4 min read",
        "image": "jaipur-hawa.jpg",
        "author": "Kabir Mehta",
        "content": "<p>Need a break from the hustle and bustle of Delhi? Discover historic cities like Jaipur, peaceful hill stations like Lansdowne, and bird sanctuaries like Bharatpur—all just a short drive away.</p>",
        "tags": ["Weekend", "Road Trips", "Delhi", "Jaipur"],
        "published": True
    },
    {
        "title": "Scenic Train Journeys You Shouldn't Miss",
        "excerpt": "Take the slow route through stunning valleys, coastal bridges, and mountain passes.",
        "category": "Short Reads",
        "date": "2024-04-25",
        "read_time": "5 min read",
        "image": "journal_himachal.png",
        "author": "Arjun Sen",
        "content": "<p>Experience the romance of rail travel on India's most scenic routes. Climb the Nilgiri Mountain Railway toy train, cross the sea on the Pamban Bridge, or slide through the Konkan hills.</p>",
        "tags": ["Train", "Scenic", "Travel"],
        "published": True
    },
    {
        "title": "Spiritual Trails Across Incredible India",
        "excerpt": "Embark on a soulful journey through ancient temples, ashrams, and quiet mountain retreats.",
        "category": "Short Reads",
        "date": "2024-04-20",
        "read_time": "4 min read",
        "image": "rishikesh-yoga.jpg",
        "author": "Swati Sharma",
        "content": "<p>Find peace and inner harmony along India's historic spiritual pathways. From the yoga ashrams of Rishikesh to the ancient temples of Madurai, discover destinations that inspire self-reflection.</p>",
        "tags": ["Spiritual", "Yoga", "Rishikesh", "Temples"],
        "published": True
    },
    {
        "title": "Exploring the Backwaters of Alleppey",
        "excerpt": "Spend a peaceful night in a traditional Kettuvallam houseboat floating on Kerala's calm backwaters.",
        "category": "Beach Escapes",
        "date": "2024-04-15",
        "read_time": "5 min read",
        "image": "journal_kerala.png",
        "author": "Ananya Rao",
        "content": "<p>A cruise along the palm-fringed canals of Alleppey in a traditional Kerala houseboat is one of the most serene travel experiences in India. Watch local village life go by while enjoying freshly prepared local fish curry.</p>",
        "tags": ["Kerala", "Backwaters", "Houseboat", "Relaxing"],
        "published": True
    },
    {
        "title": "Jaipur: The Definitive Pink City Heritage Guide",
        "excerpt": "Discover the royal palaces, historic observatories, and vibrant bazaars of Rajasthan's capital.",
        "category": "Culture",
        "date": "2024-04-10",
        "read_time": "7 min read",
        "image": "jaipur-hawa.jpg",
        "author": "Kabir Mehta",
        "content": "<p>Jaipur is a sensory wonderland of colors, crafts, and heritage. From the intricate facade of the Hawa Mahal to the grand courtyards of the City Palace, explore the architectural wonders of the Kachwaha Rajputs.</p>",
        "tags": ["Jaipur", "Rajasthan", "Heritage", "Royal"],
        "published": True
    },
    {
        "title": "Trekking in the Western Ghats: Monsoon Trails",
        "excerpt": "Walk through mist-covered mountain ridges and lush tropical rain forests during the rainy season.",
        "category": "Adventure",
        "date": "2024-04-05",
        "read_time": "6 min read",
        "image": "gokarna-cliffs.jpg",
        "author": "Rohan Das",
        "content": "<p>The Western Ghats of India, a biological hotspot, come alive during the monsoon rains. Trek to the ancient forts of Maharashtra or explore the misty peak of Kudremukh in Karnataka for breathtaking panoramic views.</p>",
        "tags": ["Trekking", "Nature", "Monsoon", "Ghats"],
        "published": True
    }
]

def run_seed() -> dict:
    from backend.database import SessionLocal
    from backend.models import BlogPost

    db = SessionLocal()
    try:
        # Delete existing blogs
        deleted = db.query(BlogPost).delete()
        db.commit()
        print(f"Cleared {deleted} existing blog posts.")

        # Seed new ones
        for post_data in PLATFORM_BLOGS:
            post = BlogPost(**post_data)
            db.add(post)

        db.commit()
        count = len(PLATFORM_BLOGS)
        print(f"Seeded {count} platform blog posts successfully.")
        return {"seeded": count, "cleared": deleted}

    except Exception as e:
        db.rollback()
        print(f"Seeding platform blogs failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
