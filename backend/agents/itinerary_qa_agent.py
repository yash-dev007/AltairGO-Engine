"""
Itinerary QA Agent — Post-Generation Quality Assurance Pipeline
═══════════════════════════════════════════════════════════════
Inspired by: AI Agents/multimodal_uiux_feedback_agent_team/agent.py (Google ADK)

Multi-check QA pipeline that reviews generated itineraries for structural
issues, pacing problems, cost inconsistencies, and geographic sanity
before the final output is returned to the user.  Can auto-fix minor
issues like mismatched day_total sums.

Usage:
    qa = ItineraryQAAgent()
    report = qa.review_itinerary(itinerary_data)
    if not report["passed"]:
        fixed = qa.auto_fix(itinerary_data, report)
"""

import math
import logging

log = logging.getLogger(__name__)

# ── QA Thresholds ────────────────────────────────────────────────
MAX_ACTIVITIES_PER_DAY = 8
MAX_ACTIVE_HOURS = 12       # hours of scheduled activity per day
MIN_ACTIVITIES_PER_DAY = 2
MAX_TRAVEL_MINUTES_BETWEEN = 120  # flag if >2h between consecutive stops
MAX_COST_DRIFT_PCT = 10     # % deviation before flagging cost mismatch
MAX_DISTANCE_KM_INTRADAY = 50  # flag if intra-day distance exceeds this


class ItineraryQAAgent:
    """
    Reviews generated itineraries for quality, consistency, and
    geographic sanity.  Returns a QA report with scores, issues,
    and warnings.
    """

    # ── Public API ───────────────────────────────────────────────

    def review_itinerary(self, itinerary_data: dict) -> dict:
        """
        Run the full QA pipeline on an itinerary.

        Returns:
            dict with keys:
                score:    0–100 quality score
                passed:   bool (True if score >= 70)
                issues:   list of critical issue dicts
                warnings: list of warning dicts
                checks:   dict of individual check results
        """
        issues = []
        warnings = []
        checks = {}

        # ── Run all checks ───────────────────────────────────
        checks["structure"] = self._check_structure(itinerary_data, issues, warnings)
        checks["pacing"] = self._check_pacing(itinerary_data, issues, warnings)
        checks["costs"] = self._check_cost_consistency(itinerary_data, issues, warnings)
        checks["geography"] = self._check_geographic_sanity(itinerary_data, issues, warnings)
        checks["content"] = self._check_content_quality(itinerary_data, issues, warnings)
        checks["completeness"] = self._check_completeness(itinerary_data, issues, warnings)

        # ── Calculate score ──────────────────────────────────
        # Start at 100, deduct for issues/warnings
        score = 100
        score -= len(issues) * 25     # critical issues cost 25 points each
        score -= len(warnings) * 3    # warnings cost 3 points each
        score = max(0, min(100, score))

        # Auto-fail on critical structural issues
        has_structural_failure = any(
            i["type"] in ("missing_field", "empty_itinerary")
            for i in issues
        )
        passed = score >= 70 and not has_structural_failure

        report = {
            "score": score,
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "total_issues": len(issues),
            "total_warnings": len(warnings),
        }

        log.info(
            f"ItineraryQAAgent: Score {score}/100, "
            f"{len(issues)} issues, {len(warnings)} warnings. "
            f"{'PASSED' if passed else 'FAILED'}"
        )
        return report

    def auto_fix(self, itinerary_data: dict, report: dict) -> dict:
        """
        Auto-fix minor issues found in the QA report.
        Only fixes safe, deterministic corrections.

        Returns:
            The (potentially modified) itinerary_data.
        """
        fixes_applied = 0

        for issue in report.get("issues", []) + report.get("warnings", []):
            fix_type = issue.get("auto_fix")
            if not fix_type:
                continue

            if fix_type == "recalculate_day_total":
                day_num = issue.get("day")
                fixes_applied += self._fix_day_total(itinerary_data, day_num)

            elif fix_type == "recalculate_total_cost":
                fixes_applied += self._fix_total_cost(itinerary_data)

        if fixes_applied:
            log.info(f"ItineraryQAAgent: Auto-fixed {fixes_applied} issues.")

        return itinerary_data

    # ── Individual checks ────────────────────────────────────────

    def _check_structure(self, data: dict, issues: list, warnings: list) -> dict:
        """Verify the itinerary has the expected top-level structure."""
        result = {"ok": True}

        if "itinerary" not in data:
            issues.append({"type": "missing_field", "field": "itinerary",
                           "severity": "critical"})
            result["ok"] = False
            return result

        if not isinstance(data["itinerary"], list) or len(data["itinerary"]) == 0:
            issues.append({"type": "empty_itinerary", "severity": "critical"})
            result["ok"] = False

        if "total_cost" not in data:
            warnings.append({"type": "missing_field", "field": "total_cost",
                             "severity": "warning"})

        result["day_count"] = len(data.get("itinerary", []))
        return result

    def _check_pacing(self, data: dict, issues: list, warnings: list) -> dict:
        """Check that no day is overpacked or underpacked."""
        result = {"days_checked": 0, "intense_days": 0}

        for day in data.get("itinerary", []):
            result["days_checked"] += 1
            activities = day.get("activities", [])
            day_num = day.get("day", "?")

            # Too many activities
            if len(activities) > MAX_ACTIVITIES_PER_DAY:
                issues.append({
                    "type": "overpacked_day",
                    "day": day_num,
                    "activity_count": len(activities),
                    "max": MAX_ACTIVITIES_PER_DAY,
                    "severity": "critical",
                })

            # Too few activities
            if len(activities) < MIN_ACTIVITIES_PER_DAY:
                warnings.append({
                    "type": "underpacked_day",
                    "day": day_num,
                    "activity_count": len(activities),
                    "min": MIN_ACTIVITIES_PER_DAY,
                    "severity": "warning",
                })

            # Check total active hours
            total_minutes = sum(
                a.get("duration_minutes", 60) for a in activities
                if not a.get("is_break")
            )
            if total_minutes > MAX_ACTIVE_HOURS * 60:
                issues.append({
                    "type": "excessive_hours",
                    "day": day_num,
                    "hours": round(total_minutes / 60, 1),
                    "max": MAX_ACTIVE_HOURS,
                    "severity": "critical",
                })
                result["intense_days"] += 1

            # Pacing level consistency
            pacing = day.get("pacing_level", "moderate")
            if pacing == "intense" and total_minutes < 6 * 60:
                warnings.append({
                    "type": "pacing_mismatch",
                    "day": day_num,
                    "labeled": pacing,
                    "actual_hours": round(total_minutes / 60, 1),
                    "severity": "warning",
                })

        return result

    def _check_cost_consistency(self, data: dict, issues: list, warnings: list) -> dict:
        """Verify cost math adds up correctly."""
        result = {"cost_valid": True}

        total_declared = data.get("total_cost", 0)
        days = data.get("itinerary", [])

        # Sum of day_totals should ≈ total_cost
        sum_day_totals = sum(day.get("day_total", 0) for day in days)

        if total_declared > 0 and sum_day_totals > 0:
            drift_pct = abs(total_declared - sum_day_totals) / total_declared * 100
            if drift_pct > MAX_COST_DRIFT_PCT:
                issues.append({
                    "type": "cost_mismatch",
                    "declared_total": total_declared,
                    "sum_of_days": sum_day_totals,
                    "drift_pct": round(drift_pct, 1),
                    "severity": "critical",
                    "auto_fix": "recalculate_total_cost",
                })
                result["cost_valid"] = False

        # Check each day's activity costs vs day_total
        for day in days:
            day_total = day.get("day_total", 0)
            if day_total <= 0:
                continue
            activity_sum = sum(
                a.get("cost", 0) for a in day.get("activities", [])
                if not a.get("is_break")
            )
            # Activity costs should be a reasonable fraction of day_total
            # (accommodation+food make up the rest, so activity sum < day_total is fine)
            if activity_sum > day_total * 1.5:
                warnings.append({
                    "type": "day_cost_imbalance",
                    "day": day.get("day"),
                    "activity_sum": activity_sum,
                    "day_total": day_total,
                    "severity": "warning",
                    "auto_fix": "recalculate_day_total",
                })

        return result

    def _check_geographic_sanity(self, data: dict, issues: list, warnings: list) -> dict:
        """Check that activities within a day aren't too far apart."""
        result = {"geo_valid": True}

        for day in data.get("itinerary", []):
            activities = [
                a for a in day.get("activities", [])
                if not a.get("is_break") and a.get("latitude") and a.get("longitude")
            ]

            if len(activities) < 2:
                continue

            day_num = day.get("day", "?")
            max_dist_km = 0

            for i in range(len(activities) - 1):
                a1 = activities[i]
                a2 = activities[i + 1]
                dist = self._haversine_km(
                    a1["latitude"], a1["longitude"],
                    a2["latitude"], a2["longitude"],
                )
                max_dist_km = max(max_dist_km, dist)

                if dist > MAX_DISTANCE_KM_INTRADAY:
                    issues.append({
                        "type": "geographic_backtrack",
                        "day": day_num,
                        "from": a1.get("name", "?"),
                        "to": a2.get("name", "?"),
                        "distance_km": round(dist, 1),
                        "severity": "critical",
                    })
                    result["geo_valid"] = False

                # Flag long travel times
                travel_min = a2.get("travel_to_next_minutes", 0)
                if travel_min > MAX_TRAVEL_MINUTES_BETWEEN:
                    warnings.append({
                        "type": "long_travel_time",
                        "day": day_num,
                        "from": a1.get("name", "?"),
                        "to": a2.get("name", "?"),
                        "minutes": travel_min,
                        "severity": "warning",
                    })

        return result

    def _check_content_quality(self, data: dict, issues: list, warnings: list) -> dict:
        """Check for empty or placeholder content in text fields."""
        result = {"empty_descriptions": 0}

        for day in data.get("itinerary", []):
            for act in day.get("activities", []):
                if act.get("is_break"):
                    continue

                # Missing activity name
                name = act.get("activity") or act.get("name")
                if not name:
                    issues.append({
                        "type": "missing_activity_name",
                        "day": day.get("day"),
                        "severity": "critical",
                    })

                # Empty description after polish
                desc = act.get("description", "")
                if not desc or desc.strip() == "":
                    result["empty_descriptions"] += 1

        if result["empty_descriptions"] > 0:
            warnings.append({
                "type": "empty_descriptions",
                "count": result["empty_descriptions"],
                "severity": "warning",
            })

        return result

    def _check_completeness(self, data: dict, issues: list, warnings: list) -> dict:
        """Check for expected top-level fields."""
        result = {"complete": True}
        expected = ["itinerary", "total_cost", "cost_breakdown"]

        for field in expected:
            if field not in data:
                warnings.append({
                    "type": "missing_top_level_field",
                    "field": field,
                    "severity": "warning",
                })
                result["complete"] = False

        # Check for smart_insights and packing_tips (may be empty before polish)
        if not data.get("smart_insights"):
            warnings.append({
                "type": "missing_insights",
                "field": "smart_insights",
                "severity": "warning",
            })

        return result

    # ── Auto-fix methods ─────────────────────────────────────────

    def _fix_day_total(self, data: dict, day_num) -> int:
        """Recalculate day_total from component costs."""
        for day in data.get("itinerary", []):
            if day.get("day") == day_num:
                activity_cost = sum(
                    a.get("cost", 0) for a in day.get("activities", [])
                    if not a.get("is_break")
                )
                accom = day.get("accommodation", {})
                accom_cost = (
                    accom.get("cost_per_night", 0) if isinstance(accom, dict) else accom
                )
                day["day_total"] = activity_cost + accom_cost
                return 1
        return 0

    def _fix_total_cost(self, data: dict) -> int:
        """Recalculate total_cost from sum of day_totals."""
        total = sum(day.get("day_total", 0) for day in data.get("itinerary", []))
        data["total_cost"] = total
        return 1

    # ── Utility ──────────────────────────────────────────────────

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two coordinates in km."""
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
