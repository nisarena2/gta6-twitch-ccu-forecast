#!/usr/bin/env python3
"""Forecast launch-day Twitch viewers hour by hour, as five quantiles.

Method: for each past big launch in the case's comparables, take the
hourly viewers on its release day and divide by that launch's hour-1
print, giving a ratio curve r_h.  Across launches, log r_h is regressed
on log(hour-1 print): big launches grow less, in ratio terms, than
small ones, because their first hour already holds most of the world
that has unlocked.  The fitted line at this case's hour-1 print is the
median ratio; the spread is a robust (MAD) residual scale, so a few
launches whose first hour fell before their unlock do not blow the
intervals up.  The slope is capped at -0.5 so the forecast stays
sensible when the hour-1 print is larger than any comparable's.

Only the standard library is used.  No network, no randomness: two
runs on the same case write byte-identical output.
"""

import json
import math
import os
import statistics
from datetime import datetime, timedelta, timezone

Z = (-1.645, -0.674, 0.0, 0.674, 1.645)
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
SLOPE_MIN = -0.5
SLOPE_MAX = 0.0
SIGMA_FLOOR = 0.08
SIGMA_CAP = 1.0
MIN_POINTS = 5
MAX_VIEWERS = 1_000_000_000.0


def _parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def _hour_key(base, hour):
    return (base + timedelta(hours=hour - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _median(values):
    return statistics.median(values)


def _quantile(sorted_values, q):
    n = len(sorted_values)
    if n == 0:
        return None
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _robust_sigma(residuals):
    med = _median(residuals)
    mad = _median([abs(r - med) for r in residuals])
    # Cap the spread: a comparable set with a broken curve must not
    # produce absurdly wide intervals for every hour.
    return min(max(1.4826 * mad, SIGMA_FLOOR), SIGMA_CAP)


def _fit_line(points):
    """OLS of y on x for [(x, y)]. Returns (intercept, slope, sigma)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    slope = sxy / sxx if sxx > 0 else 0.0
    if slope < SLOPE_MIN or slope > SLOPE_MAX:
        slope = max(min(slope, SLOPE_MAX), SLOPE_MIN)
        intercept = my - slope * mx
    else:
        intercept = my - slope * mx
    residuals = [y - (intercept + slope * x) for x, y in points]
    return intercept, slope, _robust_sigma(residuals)


def _comparable_curves(case):
    """Yield (hour1_print, {hour: ratio}) for each usable comparable."""
    curves = []
    for comp in case.get("comparables") or []:
        name = comp.get("name") or ""
        # The GTA VI category's own pre-release curve is a trailer
        # premiere, not a launch day: it must not shape launch ratios.
        if "Grand Theft Auto VI category before release" in name:
            continue
        hourly = comp.get("hourly") or []
        if not hourly:
            continue
        try:
            base = _parse_time(comp["day_start"])
        except (KeyError, TypeError, ValueError):
            continue
        by_time = {}
        for row in hourly:
            viewers = row.get("viewers")
            if isinstance(viewers, (int, float)) and viewers > 0:
                by_time[row.get("from")] = float(viewers)
        p1 = by_time.get(_hour_key(base, 1))
        if not p1 or p1 <= 0:
            continue
        ratios = {}
        for hour in range(2, 25):
            value = by_time.get(_hour_key(base, hour))
            if value and value > 0:
                ratios[hour] = value / p1
        if ratios:
            curves.append((p1, ratios))
    return curves


def _forecast_hours(p1, curves):
    log_p1 = math.log(p1)
    rows = []
    for hour in range(2, 25):
        points = [
            (math.log(c_p1), math.log(ratios[hour]))
            for c_p1, ratios in curves
            if hour in ratios
        ]
        if len(points) >= MIN_POINTS:
            intercept, slope, sigma = _fit_line(points)
            mu = intercept + slope * log_p1
        elif points:
            logs = sorted(y for _, y in points)
            mu = _quantile(logs, 0.5)
            sigma = min(max((_quantile(logs, 0.75) - _quantile(logs, 0.25)) / 1.349,
                            SIGMA_FLOOR), SIGMA_CAP)
        else:
            # No comparable has this hour: fall back to a flat median
            # with a spread that widens over the day.
            mu = 0.0
            sigma = min(0.15 * math.sqrt(hour - 1), SIGMA_CAP)
        quantiles = []
        for z in Z:
            q = p1 * math.exp(mu + z * sigma)
            q = min(max(q, 1.0), MAX_VIEWERS)
            quantiles.append(round(q, 2))
        # Keep the row non-decreasing after rounding and clamping.
        for i in range(1, 5):
            if quantiles[i] < quantiles[i - 1]:
                quantiles[i] = quantiles[i - 1]
        rows.append({"hour": hour, "q": quantiles})
    return rows


def _hour1_print(case):
    known = case.get("known") or []
    if known:
        viewers = known[0].get("viewers")
        if isinstance(viewers, (int, float)) and viewers > 0:
            return float(viewers)
    hourly = case.get("history_hourly") or []
    if hourly:
        viewers = hourly[-1].get("viewers")
        if isinstance(viewers, (int, float)) and viewers > 0:
            return float(viewers)
    return 1.0


def forecast_case(case):
    p1 = _hour1_print(case)
    curves = _comparable_curves(case)
    return {"hours": _forecast_hours(p1, curves)}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    names = sorted(
        name for name in os.listdir(input_dir) if name.endswith(".in")
    )
    for name in names:
        case_id = name[:-3]
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast_case(case)
        text = json.dumps(result, separators=(",", ":"), sort_keys=False)
        out_path = os.path.join(output_dir, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
