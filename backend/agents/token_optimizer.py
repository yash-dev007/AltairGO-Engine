"""
Token Optimizer — Context Compression for Gemini API Cost Reduction
══════════════════════════════════════════════════════════════════
Inspired by: AI Agents/toonify_token_optimization/toonify_app.py (Toonify)

Compresses the assembled itinerary JSON before sending to Gemini,
reducing token count by 30-60%.  Uses field stripping (remove coords,
IDs, URLs) and compact skeleton building to create a minimal text
representation that Gemini can still parse for text-polish operations.

Usage:
    optimizer = TokenOptimizer()
    compressed = optimizer.compress_for_gemini(itinerary_data)
    savings    = optimizer.estimate_savings(itinerary_data)
"""

import json
import logging
from copy import deepcopy

log = logging.getLogger(__name__)

# ── Fields to strip before sending to Gemini ─────────────────────
#    These are engine-locked fields that Gemini should never see/modify
STRIP_FIELDS = {
    "latitude", "longitude", "h3_index_r7", "h3_index_r9",
    "osm_id", "wikidata_id", "attraction_id", "destination_id",
    "booking_url", "google_maps_search_query", "gallery_images",
    "popularity_score", "skip_rate", "seasonal_score",
    "compatible_traveler_types", "crowd_peak_hours",
    "price_last_synced", "review_count", "google_rating",
    "budget_category", "entry_cost_min", "entry_cost_max",
    "entry_cost_child", "availability_score", "partner",
}

# Fields to keep compact (shorten key names)
KEY_ALIASES = {
    "accommodation": "accom",
    "cost_per_night": "cpn",
    "travel_to_next_minutes": "travel_min",
    "duration_minutes": "dur",
    "pacing_level": "pace",
    "day_total": "dtotal",
    "total_cost": "tcost",
    "cost_breakdown": "costs",
    "activities": "acts",
    "description": "desc",
    "why_this_fits": "why",
    "local_secret": "secret",
    "how_to_reach": "reach",
    "travel_between_cities": "transport",
}


class TokenOptimizer:
    """
    Reduces Gemini API costs by compressing itinerary JSON before
    the text-polish phase.
    """

    def __init__(self, use_key_aliases: bool = True):
        self.use_key_aliases = use_key_aliases

    # ── Public API ───────────────────────────────────────────────

    def compress_for_gemini(self, itinerary_data: dict) -> str:
        """
        Build a minimal text representation of the itinerary for Gemini.

        Steps:
          1. Deep-copy to avoid mutating original
          2. Strip engine-internal fields
          3. Optionally alias verbose keys
          4. Serialize as compact JSON (no indent)

        Returns:
            Compressed JSON string ready for the Gemini prompt.
        """
        data = deepcopy(itinerary_data)

        # Strip fields recursively
        data = self._strip_fields(data)

        # Alias keys
        if self.use_key_aliases:
            data = self._alias_keys(data)

        # Compact JSON
        compressed = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

        orig_len = len(json.dumps(itinerary_data))
        comp_len = len(compressed)
        pct = ((orig_len - comp_len) / orig_len * 100) if orig_len else 0.0
        log.info(
            f"TokenOptimizer: compressed from "
            f"{orig_len} → {comp_len} chars ({pct:.1f}% reduction)"
        )
        return compressed

    def build_skeleton(self, itinerary_data: dict) -> list[dict]:
        """
        Extract a minimal skeleton for Gemini polish — just day, theme,
        and activity names. This is what gets sent to the meta-prompt
        for trip_title, smart_insights, packing_tips generation.

        Returns:
            List of dicts: [{day, theme, activities: [names]}]
        """
        skeleton = []
        for day in itinerary_data.get("itinerary", []):
            day_skel = {
                "day": day.get("day"),
                "theme": day.get("theme", ""),
                "activities": [],
            }
            for act in day.get("activities", []):
                name = act.get("activity") or act.get("name", "Unknown")
                day_skel["activities"].append(name)
            skeleton.append(day_skel)
        return skeleton

    def estimate_savings(self, itinerary_data: dict) -> dict:
        """
        Estimate token and cost savings from compression.

        Returns:
            dict with: original_chars, compressed_chars, char_reduction_pct,
                       estimated_token_reduction_pct

        Fix 7: compute inline (strip + alias + serialize) instead of calling
        compress_for_gemini(), which would log a second compression event and
        run the same work twice per generation.
        """
        original = json.dumps(itinerary_data)

        data = self._strip_fields(deepcopy(itinerary_data))
        if self.use_key_aliases:
            data = self._alias_keys(data)
        compressed = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

        orig_chars = len(original)
        comp_chars = len(compressed)
        char_pct = ((orig_chars - comp_chars) / orig_chars * 100) if orig_chars else 0

        # Token reduction roughly tracks char reduction for JSON
        # (empirically ~0.85x the char reduction percentage)
        token_pct = char_pct * 0.85

        return {
            "original_chars": orig_chars,
            "compressed_chars": comp_chars,
            "char_reduction_pct": round(char_pct, 1),
            "estimated_token_reduction_pct": round(token_pct, 1),
        }

    # ── Internal helpers ─────────────────────────────────────────

    def _strip_fields(self, obj):
        """Recursively remove engine-internal fields from a data structure."""
        if isinstance(obj, dict):
            return {
                k: self._strip_fields(v)
                for k, v in obj.items()
                if k not in STRIP_FIELDS
            }
        elif isinstance(obj, list):
            return [self._strip_fields(item) for item in obj]
        return obj

    def _alias_keys(self, obj):
        """Recursively replace verbose key names with short aliases."""
        if isinstance(obj, dict):
            return {
                KEY_ALIASES.get(k, k): self._alias_keys(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._alias_keys(item) for item in obj]
        return obj

    @staticmethod
    def _pct_reduction(orig_len: int, compressed_str: str) -> float:
        """Compute percentage reduction. Accepts pre-computed orig_len to avoid re-serialization."""
        if orig_len == 0:
            return 0.0
        return ((orig_len - len(compressed_str)) / orig_len) * 100
