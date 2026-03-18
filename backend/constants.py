"""
constants.py — Central repository for all magic numbers and configuration constants.

All hard-coded numeric thresholds that were previously scattered across engine files
are defined here. Import from this module instead of repeating literal values.
"""
import os

# ── FilterEngine ─────────────────────────────────────────────────────
POPULARITY_HARD_FLOOR = 25          # Minimum popularity score (primary gate)
POPULARITY_SOFT_FLOOR = 10          # Fallback floor when hard floor yields 0 results
SEASONAL_SCORE_DEFAULT = 70         # Default seasonal score when month key absent
SEASONAL_SCORE_GATE = 40            # Minimum seasonal score to pass filter
MAX_ATTRACTIONS_PER_DAY = 6         # Maximum attractions per day cluster
MAX_ATTRACTIONS_LOAD = int(os.getenv("MAX_ATTRACTIONS_PER_GENERATION", "500"))

# Graduated entry-cost cap by tier (multiple of daily_activity_budget)
# budget: 1.0x cap, mid: 3.0x cap, luxury: no cap (None)
BUDGET_ENTRY_COST_MULTIPLIERS: dict[str, float | None] = {
    "budget": 1.0,
    "mid": 3.0,
    "luxury": None,
}

# ── BudgetAllocator ───────────────────────────────────────────────────
LUXURY_MIN_DAILY_PP = 2000          # INR/person/day — minimum to stay at luxury tier
MID_MIN_DAILY_PP = 1000             # INR/person/day — minimum to stay at mid tier

# ── RouteOptimizer ────────────────────────────────────────────────────
AVG_URBAN_SPEED_KMH = 15            # km/h assumed for urban travel (Indian city traffic)
DAY_START_HOUR = 9                  # Default start hour for daily schedule
DAY_START_HOUR_ARRIVAL = 15         # Arrival day: activities start at 3pm (after check-in)
SUNRISE_MAX_HOUR = 7                # Attractions at/before this hour are "sunrise" spots
MIN_TRAVEL_MINUTES = 10             # Minimum assumed travel time between any two spots

# ── Validation ────────────────────────────────────────────────────────
MAX_ACTIVITIES_PER_DAY_WARN = 5     # Warn if a day has more than this many activities
BUDGET_TOLERANCE = 0.05             # Allow 5% overage above user budget
DAY_TOTAL_TOLERANCE = 0.15          # Allow 15% variance between day totals and total_cost
GEO_DISTANCE_FLAG_KM = 100          # Flag same-day routes longer than this (km)
UNREASONABLE_HOUR_LATE = 23         # Activities at/after this hour flagged
UNREASONABLE_HOUR_EARLY = 5         # Activities before this hour flagged

# ── FilterEngine — interests boost ────────────────────────────────────
# When a user's declared interest matches an attraction type, the category cap
# for that type is multiplied by this factor so more of it passes through.
INTERESTS_CATEGORY_MULTIPLIER = 2

# ── Assembler ─────────────────────────────────────────────────────────
THEME_DETECTION_THRESHOLD = float(os.getenv("THEME_THRESHOLD", "0.20"))

# ── Cache TTLs (seconds) ──────────────────────────────────────────────
TTL_ITINERARY_SEC = int(os.getenv("TTL_ITINERARY_SEC", str(72 * 3600)))      # 72 h
TTL_CLUSTERS_SEC  = int(os.getenv("TTL_CLUSTERS_SEC",  str(7 * 24 * 3600)))  # 7 d
TTL_HOTELS_SEC    = int(os.getenv("TTL_HOTELS_SEC",    str(12 * 3600)))      # 12 h
TTL_FLIGHTS_SEC   = int(os.getenv("TTL_FLIGHTS_SEC",   str(6 * 3600)))       # 6 h
TTL_SCORES_SEC    = int(os.getenv("TTL_SCORES_SEC",    str(30 * 24 * 3600))) # 30 d
TTL_POLISH_SEC    = int(os.getenv("TTL_POLISH_SEC",    str(30 * 24 * 3600))) # 30 d
TTL_GEN_TIMES_SEC = 7 * 24 * 3600  # 7 d — rolling generation-time sample window

# ── Pagination ────────────────────────────────────────────────────────
PAGINATION_MAX_PAGE = 100_000       # Reject page numbers above this to prevent DoS
PAGINATION_MAX_PAGE_SIZE = 200      # Hard cap on page_size in all list endpoints

# ── Group discounts (INR; applied to activities budget) ───────────────
GROUP_DISCOUNT_THRESHOLD_SM = 5   # 5–9 travelers: 10% off activity costs
GROUP_DISCOUNT_THRESHOLD_LG = 10  # 10+ travelers: 15% off activity costs
GROUP_DISCOUNT_PCT_SM = 0.10
GROUP_DISCOUNT_PCT_LG = 0.15

# ── Engine config — whitelist of keys that the API is allowed to update ──
ALLOWED_ENGINE_CONFIG_KEYS = frozenset({
    "VALIDATION_STRICT",
    "GEMINI_MODEL",
    "THEME_THRESHOLD",
    "MAX_ATTRACTIONS_PER_GENERATION",
    "POPULARITY_HARD_FLOOR",
    "POPULARITY_SOFT_FLOOR",
    "SEASONAL_SCORE_GATE",
    "INTERESTS_CATEGORY_MULTIPLIER",
    "AVG_URBAN_SPEED_KMH",
    "MAX_ACTIVITIES_PER_DAY",
})
