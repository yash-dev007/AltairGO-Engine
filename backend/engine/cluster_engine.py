import logging
import h3

log = logging.getLogger(__name__)


def _geo_to_h3(lat, lng, resolution):
    if hasattr(h3, "geo_to_h3"):
        return h3.geo_to_h3(lat, lng, resolution)
    if hasattr(h3, "latlng_to_cell"):
        return h3.latlng_to_cell(lat, lng, resolution)
    raise AttributeError("No supported H3 conversion function found")


class ClusterEngine:
    def cluster(self, attractions: list, num_days: int) -> dict:
        """
        Groups filtered attractions into geographic day-clusters using H3 hex indexing.
        Returns {day_1: [attraction_objects], day_2: [attraction_objects], ...}
        Each day's attractions share the same H3 r7 hex (~5km radius).
        """
        result_dict = {f"day_{i+1}": [] for i in range(num_days)}
        if not attractions:
            return result_dict

        # Group by H3 r7 hex (~5km radius)
        hex_groups = {}
        for a in attractions:
            # Fallback to r9 or compute if missing
            # Fix 9: Coerce NULL h3_index_r7 columns
            h_idx = getattr(a, 'h3_index_r7', None)
            if h_idx is None:
                lat = getattr(a, 'latitude', getattr(a, 'lat', None))
                lng = getattr(a, 'longitude', getattr(a, 'lng', None))
                # Treat (0.0, 0.0) as missing GPS data so attractions do not cluster into the Gulf of Guinea.
                if lat == 0.0 and lng == 0.0:
                    h_idx = f"missing:{getattr(a, 'id', getattr(a, 'name', 'unknown'))}"
                elif lat is not None and lng is not None:
                    try:
                        h_idx = _geo_to_h3(lat, lng, 7)
                    except Exception as e:
                        log.warning(f"h3 error for {getattr(a, 'name', 'unknown')}: {e}")
                        h_idx = 'unknown'
                else:
                    h_idx = 'unknown'

            hex_groups.setdefault(h_idx, []).append(a)

        # Score each hex by sum of popularity_scores
        # We add an index 'i' to the tuples so that Python's 'sorted' has a deterministic
        # integer tie-breaker and never attempts to compare the MagicMock objects.
        scored_hexes = sorted(
            enumerate(hex_groups.items()),
            key=lambda x: (sum(getattr(a, 'popularity_score', 0) or 0 for a in x[1][1]), x[0]),
            reverse=True
        )

        # Assign top N hexes to days (N = num_days)
        for rank_idx, (orig_idx, (hex_id, hex_attractions)) in enumerate(scored_hexes[:num_days]):
            # Sort within day by popularity, cap at 6 activities per day limits
            # Add id as tie-breaker
            sorted_attractions = sorted(
                hex_attractions,
                key=lambda x: (getattr(x, 'popularity_score', 0) or 0, getattr(x, 'id', 0)),
                reverse=True
            )

            # Sort each day sequentially: morning attractions first
            day_schedule = sorted_attractions[:6]
            day_schedule.sort(key=lambda a: getattr(a, "best_visit_time_hour", 10) or 10)

            result_dict[f"day_{rank_idx+1}"] = day_schedule

        log.info(f"ClusterEngine: {len(attractions)} attractions → {sum(1 for d in result_dict.values() if d)} active clusters")
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
                # Still assign empty days for this city
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
