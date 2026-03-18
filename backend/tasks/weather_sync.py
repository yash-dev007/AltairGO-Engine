"""
weather_sync.py — Fetches weather forecasts and writes WeatherAlert rows.

Integration: Open-Meteo free API (no key required).
  Docs: https://open-meteo.com/en/docs

Alert thresholds:
  rain:         precipitation_sum > 10mm/day   → moderate; > 25mm → high; > 50mm → extreme
  storm:        wind_gusts_10m_max  > 60 km/h  → high; > 80 km/h → extreme
  extreme_heat: temperature_2m_max  > 42°C     → high; > 45°C    → extreme

Only destinations with lat/lng coordinates can be synced.
Already-expired alerts are purged during each run.
"""
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# ── Open-Meteo API ─────────────────────────────────────────────────────────────
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7  # How many days ahead to fetch
ALERT_EXPIRE_HOURS = 36  # Auto-expire alerts after this long if not renewed

# Rain thresholds (mm/day)
RAIN_MOD_MM = 10.0
RAIN_HIGH_MM = 25.0
RAIN_EXTREME_MM = 50.0

# Wind gust thresholds (km/h)
WIND_HIGH_KMH = 60.0
WIND_EXTREME_KMH = 80.0

# Heat thresholds (°C)
HEAT_HIGH_C = 42.0
HEAT_EXTREME_C = 45.0


def _classify_rain(mm: float) -> str | None:
    if mm >= RAIN_EXTREME_MM:
        return "extreme"
    if mm >= RAIN_HIGH_MM:
        return "high"
    if mm >= RAIN_MOD_MM:
        return "moderate"
    return None


def _classify_wind(kmh: float) -> str | None:
    if kmh >= WIND_EXTREME_KMH:
        return "extreme"
    if kmh >= WIND_HIGH_KMH:
        return "high"
    return None


def _classify_heat(c: float) -> str | None:
    if c >= HEAT_EXTREME_C:
        return "extreme"
    if c >= HEAT_HIGH_C:
        return "high"
    return None


def _fetch_forecast(lat: float, lng: float) -> dict | None:
    """Call Open-Meteo and return parsed JSON or None on failure."""
    try:
        import urllib.request, json
        params = (
            f"?latitude={lat}&longitude={lng}"
            f"&daily=precipitation_sum,wind_gusts_10m_max,temperature_2m_max"
            f"&forecast_days={FORECAST_DAYS}"
            f"&timezone=auto"
        )
        url = OPEN_METEO_URL + params
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        log.debug(f"Open-Meteo fetch failed: {exc}")
        return None


def sync_weather_alerts() -> dict:
    """
    Main entry point called by Celery.

    Iterates all active destinations with coordinates, fetches 7-day
    forecasts from Open-Meteo, and writes/updates WeatherAlert rows.
    Purges alerts that have passed their expiry time.
    """
    from backend.database import SessionLocal
    from backend.models import Destination, WeatherAlert

    db = SessionLocal()
    created = updated = purged = skipped = 0

    try:
        now = datetime.now(timezone.utc)
        expiry_threshold = now + timedelta(hours=ALERT_EXPIRE_HOURS)

        # Purge stale alerts
        stale = db.query(WeatherAlert).filter(
            WeatherAlert.expires_at.isnot(None),
            WeatherAlert.expires_at < now,
        ).all()
        for s in stale:
            db.delete(s)
        purged = len(stale)

        destinations = db.query(Destination).filter(
            Destination.lat.isnot(None),
            Destination.lng.isnot(None),
        ).all()

        for dest in destinations:
            data = _fetch_forecast(dest.lat, dest.lng)
            if not data:
                skipped += 1
                continue

            daily = data.get("daily", {})
            dates: list[str] = daily.get("time", [])
            precip_list: list = daily.get("precipitation_sum") or []
            wind_list:   list = daily.get("wind_gusts_10m_max") or []
            heat_list:   list = daily.get("temperature_2m_max") or []

            for i, date_str in enumerate(dates):
                alerts_to_write = []

                if i < len(precip_list) and precip_list[i] is not None:
                    sev = _classify_rain(float(precip_list[i]))
                    if sev in ("moderate", "high", "extreme"):
                        alerts_to_write.append({
                            "type": "rain",
                            "severity": sev,
                            "probability_pct": None,
                            "description": f"{precip_list[i]:.1f}mm precipitation forecast.",
                        })

                if i < len(wind_list) and wind_list[i] is not None:
                    sev = _classify_wind(float(wind_list[i]))
                    if sev:
                        alerts_to_write.append({
                            "type": "storm",
                            "severity": sev,
                            "probability_pct": None,
                            "description": f"Wind gusts up to {wind_list[i]:.0f} km/h forecast.",
                        })

                if i < len(heat_list) and heat_list[i] is not None:
                    sev = _classify_heat(float(heat_list[i]))
                    if sev:
                        alerts_to_write.append({
                            "type": "extreme_heat",
                            "severity": sev,
                            "probability_pct": None,
                            "description": f"Max temperature {heat_list[i]:.1f}°C forecast.",
                        })

                for alert_data in alerts_to_write:
                    existing = db.query(WeatherAlert).filter_by(
                        destination_id=dest.id,
                        alert_date=date_str,
                        alert_type=alert_data["type"],
                    ).first()
                    if existing:
                        existing.severity = alert_data["severity"]
                        existing.description = alert_data["description"]
                        existing.expires_at = expiry_threshold
                        updated += 1
                    else:
                        db.add(WeatherAlert(
                            destination_id=dest.id,
                            alert_date=date_str,
                            alert_type=alert_data["type"],
                            severity=alert_data["severity"],
                            probability_pct=alert_data["probability_pct"],
                            description=alert_data["description"],
                            source="open_meteo",
                            expires_at=expiry_threshold,
                        ))
                        created += 1

        db.commit()
        result = {
            "created": created,
            "updated": updated,
            "purged": purged,
            "skipped": skipped,
            "destinations_checked": len(destinations),
        }
        log.info(f"Weather sync done: {result}")
        return result

    except Exception as exc:
        db.rollback()
        log.error(f"Weather sync failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sync_weather_alerts()
