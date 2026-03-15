import logging
import math

log = logging.getLogger(__name__)

BUDGET_SPLITS = {
    'budget':  {'accommodation': 0.30, 'food': 0.28, 'transport': 0.22, 'activities': 0.15, 'misc': 0.05},
    'mid':     {'accommodation': 0.35, 'food': 0.25, 'transport': 0.20, 'activities': 0.15, 'misc': 0.05},
    'luxury':  {'accommodation': 0.45, 'food': 0.20, 'transport': 0.15, 'activities': 0.15, 'misc': 0.05},
}

class BudgetAllocator:
    def allocate(self, total_budget: int, num_days: int, num_travelers: int, tier: str, clusters: dict) -> dict:
        """
        Calculates daily budget caps based on tier splits and attraction clusters.
        Returns a dict mapping days to their cost breakdown.
        """
        # Clamp inputs to safe minimums so division never hits zero.
        num_days = max(int(num_days or 1), 1)
        num_travelers = max(int(num_travelers or 1), 1)
        tier = tier if tier in BUDGET_SPLITS else 'mid'
        
        # Over-budget check (demote hotel tier if costs exceed budget)
        # We do this mathematically by checking if daily budget per person is exceptionally low
        daily_budget_pp = total_budget / (num_days * num_travelers)
        if tier == 'luxury' and daily_budget_pp < 2000:
            tier = 'mid'
        if tier == 'mid' and daily_budget_pp < 1000:
            tier = 'budget'
            
        splits = BUDGET_SPLITS[tier]

        hotel_cost_per_night = (total_budget * splits['accommodation']) / num_days
        food_per_day         = (total_budget * splits['food']) / num_days
        transport_per_day    = (total_budget * splits['transport']) / num_days
        misc_per_day         = (total_budget * splits['misc']) / num_days
        activity_pool        = (total_budget * splits['activities']) / num_days

        allocation = {}
        
        for day_key, day_attractions in clusters.items():
            # Calculate actual minimum activity costs for the day (Per Group)
            day_act_cost_group = 0.0
            for act in day_attractions:
                cost_min = getattr(act, "entry_cost_min", 0) or 0
                cost_max = getattr(act, "entry_cost_max", getattr(act, "entry_cost", 0)) or 0
                # Using max cost for conservative budgeting (cost is per person, so multiply by travelers)
                day_act_cost_group += max(cost_min, cost_max) * num_travelers

            day_total_group = hotel_cost_per_night + food_per_day + transport_per_day + day_act_cost_group + misc_per_day

            # The test suite expects the allocation output parameters to represent 
            # the PER-PERSON cost breakdown, so we divide the group pools by travelers.
            allocation[day_key] = {
                "accommodation": hotel_cost_per_night / num_travelers,
                "food": food_per_day / num_travelers,
                "transport": transport_per_day / num_travelers,
                "activities": day_act_cost_group / num_travelers,
                "misc": misc_per_day / num_travelers,
                "day_total": day_total_group / num_travelers
            }
            
        return allocation
