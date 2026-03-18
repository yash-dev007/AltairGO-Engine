import logging
from collections import Counter
from typing import Any

import h3

from backend.constants import MAX_ATTRACTIONS_PER_DAY

log = logging.getLogger(__name__)


def _hex_dominant_type(attractions: list) -> str:
    """Return the most common attraction type in a hex group."""
    if not attractions:
        return "general"
    types = [getattr(a, "type", "general") or "general" for a in attractions]
    return Counter(types).most_common(1)[0][0]


def _geo_to_h3(lat, lng, resolution):
    if hasattr(h3, "geo_to_h3"):
        return h3.geo_to_h3(lat, lng, resolution)
    if hasattr(h3, "latlng_to_cell"):
        return h3.latlng_to_cell(lat, lng, resolution)
    raise AttributeError("No supported H3 conversion function found")


class ClusterEngine:
    def cluster(
        self,
        attractions: list,
        num_days: int,
        max_per_day: int | None = None,
    ) -> dict:
        """
        Groups filtered attractions into geographic day-clusters using H3 hex indexing.
        Returns {day_1: [attraction_objects], day_2: [attraction_objects], ...}
        Each day's attractions share the same H3 r7 hex (~5km radius).

        max_per_day: override MAX_ATTRACTIONS_PER_DAY (used for variant generation).

        When there are fewer geographic clusters than requested days, remaining
        attractions are redistributed round-robin so no day is left completely empty.
        """
        cap = max_per_day if max_per_day is not None else MAX_ATTRACTIONS_PER_DAY
        result_dict = {f"day_{i+1}": [] for i in range(num_days)}
        if not attractions:
            return result_dict

        # Group by H3 r7 hex (~5km radius)
        hex_groups = {}
        for a in attractions:
            h_idx = getattr(a, 'h3_index_r7', None)
            if h_idx is None:
                lat = getattr(a, 'latitude', getattr(a, 'lat', None))
                lng = getattr(a, 'longitude', getattr(a, 'lng', None))
                # Treat (0.0, 0.0) as missing GPS — don't cluster into Gulf of Guinea.
                # Also reject coordinates outside valid WGS-84 ranges.
                if lat == 0.0 and lng == 0.0:
                    h_idx = f"missing:{getattr(a, 'id', getattr(a, 'name', 'unknown'))}"
                elif lat is not None and lng is not None:
                    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                        log.warning(
                            f"ClusterEngine: invalid GPS ({lat}, {lng}) for "
                            f"'{getattr(a, 'name', 'unknown')}' — treating as missing."
                        )
                        h_idx = "unknown"
                    else:
                        try:
                            h_idx = _geo_to_h3(lat, lng, 7)
                        except Exception as e:
                            log.warning(f"h3 error for {getattr(a, 'name', 'unknown')}: {e}")
                            h_idx = "unknown"
                else:
                    h_idx = 'unknown'

            hex_groups.setdefault(h_idx, []).append(a)

        # Score each hex by sum of popularity_scores; use enumerate index as tie-breaker
        scored_hexes = sorted(
            enumerate(hex_groups.items()),
            key=lambda x: (sum(getattr(a, 'popularity_score', 0) or 0 for a in x[1][1]), x[0]),
            reverse=True
        )

        # ── Diversity-aware day selection ─────────────────────────────────────
        # Day 1 always gets the highest-scored hex. For subsequent days, prefer a
        # hex whose dominant attraction type differs from the last two days so the
        # traveler doesn't visit the same category of place every single day.
        candidates = list(scored_hexes)  # mutable copy; sorted best-first
        selected: list[tuple] = []       # (hex_id, [attractions])
        recent_types: list[str] = []     # dominant type per selected day

        for _ in range(num_days):
            if not candidates:
                break

            if not selected:
                # Day 1: unconditionally take the top-scored hex
                _orig_idx, (hex_id, hex_attractions) = candidates.pop(0)
            else:
                last_two = set(recent_types[-2:])
                diverse = [
                    c for c in candidates
                    if _hex_dominant_type(c[1][1]) not in last_two
                ]
                if diverse:
                    best = diverse[0]
                    candidates.remove(best)
                else:
                    best = candidates.pop(0)
                _orig_idx, (hex_id, hex_attractions) = best

            selected.append((hex_id, hex_attractions))
            recent_types.append(_hex_dominant_type(hex_attractions))

        for rank_idx, (hex_id, hex_attractions) in enumerate(selected):
            sorted_attractions = sorted(
                hex_attractions,
                key=lambda x: (getattr(x, 'popularity_score', 0) or 0, getattr(x, 'id', 0)),
                reverse=True
            )
            day_schedule = sorted_attractions[:cap]
            day_schedule.sort(key=lambda a: getattr(a, "best_visit_time_hour", 10) or 10)
            result_dict[f"day_{rank_idx+1}"] = day_schedule

        # ── Fallback: fewer clusters than requested days ──────────────────────
        # If we have M hexes for N days where M < N, redistribute ALL filtered
        # attractions round-robin so every day gets at least something.
        filled_days = sum(1 for v in result_dict.values() if v)
        if filled_days < num_days:
            log.warning(
                f"ClusterEngine: only {filled_days} geographic cluster(s) for "
                f"{num_days}-day trip. Redistributing {len(attractions)} attractions round-robin."
            )
            all_sorted = sorted(
                attractions,
                key=lambda a: (getattr(a, 'popularity_score', 0) or 0, getattr(a, 'id', 0)),
                reverse=True
            )
            # Reset all days and redistribute, capping each day at cap
            for key in result_dict:
                result_dict[key] = []
            for i, attr in enumerate(all_sorted[:num_days * cap]):
                day_key = f"day_{(i % num_days) + 1}"
                if len(result_dict[day_key]) < cap:
                    result_dict[day_key].append(attr)
            # Re-sort each day by best visit time
            for day_key in result_dict:
                result_dict[day_key].sort(
                    key=lambda a: getattr(a, "best_visit_time_hour", 10) or 10
                )

        log.info(
            f"ClusterEngine: {len(attractions)} attractions → "
            f"{sum(1 for d in result_dict.values() if d)} active clusters"
        )
        return result_dict

    def cluster_multi_city(self, city_attractions: dict, days_per_city: dict) -> dict:
        """
        For multi-city trips — assigns day ranges to each city.

        Args:
            city_attractions: dict mapping city_name -> list of attraction objects
                e.g. {"Delhi": [...], "Agra": [...], "Jaipur": [...]}
            days_per_city: dict mapping city_name -> number of days
                e.g. {"Delhi": 2, "Agra": 1, "Jaipur": 2}

        Returns:
            dict mapping day_N -> {"city": city_name, "attractions": [attraction_objects]}
        """
        result = {}
        day_counter = 1

        for city, num_days in days_per_city.items():
            attractions = city_attractions.get(city, [])
            if not attractions:
                for _ in range(num_days):
                    result[f"day_{day_counter}"] = {"city": city, "attractions": []}
                    day_counter += 1
                continue

            city_clusters = self.cluster(attractions, num_days)

            for day_key in sorted(city_clusters.keys(), key=lambda k: int(k.split("_")[1])):
                cluster_attractions = city_clusters[day_key]
                result[f"day_{day_counter}"] = {
                    "city": city,
                    "attractions": cluster_attractions
                }
                day_counter += 1

        log.info(f"ClusterMultiCity: {len(city_attractions)} cities → {day_counter - 1} days")
        return result

    @staticmethod
    def _calculate_days_per_city(city_sequence: list, total_days: int) -> dict:
        """
        Distribute days across cities proportionally.
        Each city gets at least 1 day; remaining days go to first cities.
        """
        num_cities = len(city_sequence)
        if num_cities == 0:
            return {}

        base_days = max(1, total_days // num_cities)
        remainder = total_days - (base_days * num_cities)

        result = {}
        for i, city in enumerate(city_sequence):
            days = base_days + (1 if i < remainder else 0)
            result[city] = days

        return result
