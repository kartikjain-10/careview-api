from __future__ import annotations

from typing import List
from app.models.schemas import WearableSnapshotRecord


def format_wearable_summary(snapshots: List[WearableSnapshotRecord]) -> str:
    """Convert a list of wearable snapshots into a concise human-readable summary."""
    if not snapshots:
        return "No recent wearable data available."

    lines = ["Date        | Steps  | Sleep(h) | HR  | Active(min) | Mood"]
    lines.append("-" * 60)
    for s in snapshots:
        lines.append(
            f"{s.date}  | {s.steps:>6} | {s.sleep_hours:>8.1f} | "
            f"{s.resting_heart_rate:>3} | {s.active_minutes:>11} | {s.mood_score}/10"
        )

    avg_steps = sum(s.steps for s in snapshots) / len(snapshots)
    avg_sleep = sum(s.sleep_hours for s in snapshots) / len(snapshots)
    avg_hr = sum(s.resting_heart_rate for s in snapshots) / len(snapshots)
    avg_mood = sum(s.mood_score for s in snapshots) / len(snapshots)

    lines.append("")
    lines.append(
        f"7-day averages — Steps: {avg_steps:.0f} | Sleep: {avg_sleep:.1f}h "
        f"| HR: {avg_hr:.0f} bpm | Mood: {avg_mood:.1f}/10"
    )
    return "\n".join(lines)
