import logging
from typing import Any

from backend.constants import (
    LUXURY_MIN_DAILY_PP,
    MID_MIN_DAILY_PP,
    GROUP_DISCOUNT_THRESHOLD_SM,
    GROUP_DISCOUNT_THRESHOLD_LG,
    GROUP_DISCOUNT_PCT_SM,
    GROUP_DISCOUNT_PCT_LG,
)

log = logging.getLogger(__name__)

BUDGET_SPLITS: dict[str, dict[str, float]] = {
    'budget':  {'accommodation': 0.30, 'food': 0.28, 'transport': 0.22, 'activities': 0.15, 'misc': 0.05},
    'mid':     {'accommodation': 0.35, 'food': 0.25, 'transport': 0.20, 'activities': 0.15, 'misc': 0.05},
    'luxury':  {'accommodation': 0.45, 'food': 0.20, 'transport': 0.15, 'activities': 0.15, 'misc': 0.05},
}


class BudgetAllocator:
    def allocate(
        self,
        total_budget: int,
        num_days: int,
        num_travelers: int,
        tier: str,
        clusters: dict,
        actual_hotel_cost_per_night: float | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Calculates daily budget caps based on tier splits and attraction clusters.

        actual_hotel_cost_per_night: when provided (fetched from HotelPrice table),
          this overrides the tier-split percentage for accommodation, producing
          an accurate accommodation figure instead of a theoretical percentage.

        Auto-demotes the tier when the daily budget per person falls below the
        minimum for that tier:
          luxury → mid  if daily_budget/person < LUXURY_MIN_DAILY_PP (₹2,000)
          mid → budget   if daily_budget/person < MID_MIN_DAILY_PP   (₹1,000)

        Returns a dict mapping day keys to per-person cost breakdowns:
          {"day_1": {"accommodation": …, "food": …, …, "day_total": …}, …}
        """
        # Clamp inputs to safe minimums so division never hits zero.
        num_days = max(int(num_days or 1), 1)
        num_travelers = max(int(num_travelers or 1), 1)
        tier = tier if tier in BUDGET_SPLITS else "mid"

        # Auto-demotion: check if the per-person daily budget justifies the tier
        daily_budget_pp: float = total_budget / (num_days * num_travelers)
        if tier == "luxury" and daily_budget_pp < LUXURY_MIN_DAILY_PP:
            log.info(
                f"BudgetAllocator: demoting luxury → mid "
                f"(₹{daily_budget_pp:.0f}/person/day < ₹{LUXURY_MIN_DAILY_PP})"
            )
            tier = "mid"
        if tier == "mid" and daily_budget_pp < MID_MIN_DAILY_PP:
            log.info(
                f"BudgetAllocator: demoting mid → budget "
                f"(₹{daily_budget_pp:.0f}/person/day < ₹{MID_MIN_DAILY_PP})"
            )
            tier = "budget"

        splits = BUDGET_SPLITS[tier]

        # Use real hotel price when available; fall back to percentage allocation.
        if actual_hotel_cost_per_night is not None and actual_hotel_cost_per_night > 0:
            hotel_cost_per_night = float(actual_hotel_cost_per_night)
            log.info(
                f"BudgetAllocator: using real hotel cost ₹{hotel_cost_per_night:.0f}/night "
                f"(was ₹{(total_budget * splits['accommodation']) / num_days:.0f} from % split)"
            )
        else:
            hotel_cost_per_night = (total_budget * splits['accommodation']) / num_days

        food_per_day: float         = (total_budget * splits['food']) / num_days
        transport_per_day: float    = (total_budget * splits['transport']) / num_days
        misc_per_day: float         = (total_budget * splits['misc']) / num_days

        allocation: dict[str, dict[str, float]] = {}

        # Group discount on activity entry costs — common for large groups in India.
        if num_travelers >= GROUP_DISCOUNT_THRESHOLD_LG:
            group_discount = GROUP_DISCOUNT_PCT_LG
            log.info(
                f"BudgetAllocator: applying {int(group_discount*100)}% group discount "
                f"(group size={num_travelers} ≥ {GROUP_DISCOUNT_THRESHOLD_LG})"
            )
        elif num_travelers >= GROUP_DISCOUNT_THRESHOLD_SM:
            group_discount = GROUP_DISCOUNT_PCT_SM
            log.info(
                f"BudgetAllocator: applying {int(group_discount*100)}% group discount "
                f"(group size={num_travelers} ≥ {GROUP_DISCOUNT_THRESHOLD_SM})"
            )
        else:
            group_discount = 0.0

        for day_key, day_attractions in clusters.items():
            # Calculate actual minimum activity costs for the day (per group)
            day_act_cost_group: float = 0.0
            for act in day_attractions:
                cost_min: int = getattr(act, "entry_cost_min", 0) or 0
                cost_max: int = getattr(act, "entry_cost_max", getattr(act, "entry_cost", 0)) or 0
                # Use max cost for conservative budgeting; multiply by travelers (group cost)
                day_act_cost_group += max(cost_min, cost_max) * num_travelers
            # Apply group discount to activity costs
            if group_discount:
                day_act_cost_group *= (1.0 - group_discount)

            day_total_group = (
                hotel_cost_per_night
                + food_per_day
                + transport_per_day
                + day_act_cost_group
                + misc_per_day
            )

            # Output is per-person so the frontend can display individual cost
            allocation[day_key] = {
                "accommodation": hotel_cost_per_night / num_travelers,
                "food": food_per_day / num_travelers,
                "transport": transport_per_day / num_travelers,
                "activities": day_act_cost_group / num_travelers,
                "misc": misc_per_day / num_travelers,
                "day_total": day_total_group / num_travelers,
            }

        return allocation
