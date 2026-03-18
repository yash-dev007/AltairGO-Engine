"""
Memory Agent — User Preference Learning from Behavioral Signals
═══════════════════════════════════════════════════════════════
Inspired by: AI Agents/ai_travel_agent_memory/travel_agent_memory.py (Mem0)

Instead of using Qdrant/Mem0 vector stores, this agent learns from the
existing AttractionSignal table. It aggregates save/remove/swap patterns
to build a persistent user preference profile that the FilterEngine
can consume to personalize itineraries for returning users.

Usage:
    agent = MemoryAgent(db_session)
    prefs  = agent.get_user_preferences(user_id=42)
    merged = agent.inject_preferences(user_id=42, base_prefs={...})
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# ── Signal weight map ────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "save":       +2.0,
    "book_click": +3.0,
    "view":       +0.5,
    "remove":     -2.0,
    "swap":       -1.0,
}

# Minimum signals needed before we trust the learned preferences
MIN_SIGNALS_THRESHOLD = 5


class MemoryAgent:
    """
    Learns and persists user travel preferences from AttractionSignal
    behavioral data. Merges learned preferences with explicit request
    preferences before the FilterEngine runs.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    def set_session(self, db_session):
        """Set or update the database session."""
        self.db = db_session

    # ── Core API ─────────────────────────────────────────────────

    def learn_from_signals(self, user_id: int) -> dict:
        """
        Analyze all AttractionSignal records for a user and derive
        learned preferences.

        Returns:
            dict with keys:
                preferred_types: list of attraction types user likes
                excluded_types:  list of attraction types user dislikes
                preferred_budget_tier: str or None
                preferred_time_of_day: "morning" | "afternoon" | "evening" | None
                signal_count: int (total signals analyzed)
        """
        if not self.db:
            log.warning("MemoryAgent: No DB session, returning empty preferences.")
            return self._empty_preferences()

        try:
            from backend.models import AttractionSignal, Attraction

            signals = (
                self.db.query(AttractionSignal)
                .filter(AttractionSignal.user_id == user_id)
                .order_by(AttractionSignal.created_at.desc())
                .limit(500)  # cap to recent history
                .all()
            )

            if len(signals) < MIN_SIGNALS_THRESHOLD:
                log.info(
                    f"MemoryAgent: User {user_id} has {len(signals)} signals "
                    f"(below threshold {MIN_SIGNALS_THRESHOLD}), skipping."
                )
                return self._empty_preferences()

            # ── Aggregate type affinities ────────────────────────
            type_scores = defaultdict(float)
            budget_counter = Counter()
            time_slots = defaultdict(float)

            attraction_ids = [s.attraction_id for s in signals]
            attractions = {
                a.id: a
                for a in self.db.query(Attraction)
                .filter(Attraction.id.in_(attraction_ids))
                .all()
            }

            for signal in signals:
                signal_name = getattr(signal, "event_type", getattr(signal, "signal_type", None))
                weight = SIGNAL_WEIGHTS.get(signal_name, 0)
                attr = attractions.get(signal.attraction_id)
                if not attr:
                    continue

                # Type affinity
                if attr.type:
                    type_scores[attr.type] += weight

                # Budget tier tracking (only positive signals)
                if weight > 0 and signal.budget_tier:
                    budget_counter[signal.budget_tier] += 1

                # Time-of-day preference
                if weight > 0 and attr.best_visit_time_hour is not None:
                    hour = attr.best_visit_time_hour
                    if hour <= 9:
                        time_slots["morning"] += weight
                    elif hour <= 14:
                        time_slots["afternoon"] += weight
                    else:
                        time_slots["evening"] += weight

            # ── Derive preferences ───────────────────────────────
            preferred_types = [
                t for t, score in type_scores.items() if score >= 2.0
            ]
            excluded_types = [
                t for t, score in type_scores.items() if score <= -3.0
            ]

            preferred_budget = (
                budget_counter.most_common(1)[0][0]
                if budget_counter
                else None
            )

            preferred_time = (
                max(time_slots, key=time_slots.get)
                if time_slots
                else None
            )

            result = {
                "preferred_types": sorted(preferred_types),
                "excluded_types": sorted(excluded_types),
                "preferred_budget_tier": preferred_budget,
                "preferred_time_of_day": preferred_time,
                "signal_count": len(signals),
            }

            log.info(
                f"MemoryAgent: Learned preferences for user {user_id}: "
                f"{len(preferred_types)} preferred, {len(excluded_types)} excluded types."
            )
            return result

        except Exception as e:
            log.error(f"MemoryAgent: Error learning from signals: {e}")
            return self._empty_preferences()

    def get_user_preferences(self, user_id: int) -> dict:
        """Alias for learn_from_signals — reads current preference state."""
        return self.learn_from_signals(user_id)

    def inject_preferences(
        self, user_id: int, base_preferences: dict
    ) -> dict:
        """
        Merge learned preferences with explicit request preferences.
        Priority order (highest → lowest):
          1. Explicit request fields (always win)
          2. Learned signals (AttractionSignal aggregation)
          3. UserProfile.preferences (persistent profile JSON)

        Args:
            user_id: user whose memory to consult
            base_preferences: the user's explicit request (from API payload)

        Returns:
            Enhanced preferences dict with memory-injected fields.
        """
        learned = self.learn_from_signals(user_id)
        merged = dict(base_preferences)

        # ── Layer 1: UserProfile.preferences ─────────────────────────────────
        # Apply first so learned signals can override profile defaults.
        if self.db:
            try:
                from backend.models import UserProfile
                profile = (
                    self.db.query(UserProfile)
                    .filter(UserProfile.user_id == user_id)
                    .first()
                )
                if profile and profile.preferences:
                    for key, value in profile.preferences.items():
                        # Only fill keys not already in the explicit request.
                        # This lets the request always win over persisted prefs.
                        if key not in merged or merged.get(key) is None:
                            merged[key] = value
                    log.info(
                        f"MemoryAgent: Merged UserProfile.preferences for user {user_id} "
                        f"({len(profile.preferences)} keys)."
                    )
            except Exception as e:
                log.warning(f"MemoryAgent: UserProfile fetch failed: {e}")

        # ── Layer 2: Behavioral signal learning ───────────────────────────────
        if learned["signal_count"] < MIN_SIGNALS_THRESHOLD:
            return merged  # not enough signals yet — profile layer is enough

        # Inject excluded types (additive — never remove user's explicit choices)
        existing_excludes = merged.get("excluded_types", []) or []
        merged["excluded_types"] = list(
            set(existing_excludes + learned["excluded_types"])
        )

        # Suggest preferred types if user didn't specify style preferences
        if not merged.get("preferred_attraction_types"):
            merged["preferred_attraction_types"] = learned["preferred_types"]

        # Suggest budget tier if not explicitly set
        if not merged.get("budget_tier") and learned["preferred_budget_tier"]:
            merged["suggested_budget_tier"] = learned["preferred_budget_tier"]

        # Add time-of-day hint
        if learned["preferred_time_of_day"]:
            merged["preferred_time_of_day"] = learned["preferred_time_of_day"]

        # Mark that memory was applied
        merged["_memory_applied"] = True
        merged["_memory_signal_count"] = learned["signal_count"]

        log.info(
            f"MemoryAgent: Injected preferences for user {user_id} "
            f"({learned['signal_count']} signals)."
        )
        return merged

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _empty_preferences() -> dict:
        return {
            "preferred_types": [],
            "excluded_types": [],
            "preferred_budget_tier": None,
            "preferred_time_of_day": None,
            "signal_count": 0,
        }
