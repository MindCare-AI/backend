#!/usr/bin/env python
"""
Script to check mood data and generate mood trend analysis
"""

import os
import django
from datetime import timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mindcare.settings")
django.setup()

from mood.models import MoodLog
from users.models import CustomUser
from datawarehouse.models import MoodTrendAnalysis
import statistics


def check_database_status():
    """Check current database status"""
    print("=== DATABASE STATUS ===")
    print(f"Total mood logs: {MoodLog.objects.count()}")
    print(f"Total users: {CustomUser.objects.count()}")
    print(f"Total mood trend analyses: {MoodTrendAnalysis.objects.count()}")

    print("\n=== MOOD LOGS BY USER ===")
    for user in CustomUser.objects.all():
        count = MoodLog.objects.filter(user=user).count()
        if count > 0:
            print(f"User {user.id} ({user.username}): {count} mood logs")
            # Show recent mood logs
            recent_logs = MoodLog.objects.filter(user=user).order_by("-logged_at")[:5]
            for log in recent_logs:
                print(
                    f"  - {log.logged_at.strftime('%Y-%m-%d %H:%M')} - Mood: {log.mood_rating}/10 - Activities: {log.activities}"
                )
        else:
            print(f"User {user.id} ({user.username}): No mood logs")


def calculate_trend_direction(mood_values):
    """Calculate trend direction from mood values"""
    if len(mood_values) < 2:
        return "stable"

    # Calculate simple linear trend
    n = len(mood_values)
    x_values = list(range(n))
    y_values = mood_values

    # Simple slope calculation
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n

    numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    # Determine trend based on slope
    if slope > 0.5:
        return "strongly_improving"
    elif slope > 0.1:
        return "improving"
    elif slope < -0.5:
        return "strongly_declining"
    elif slope < -0.1:
        return "declining"
    else:
        return "stable"


def calculate_trend_strength(mood_values):
    """Calculate trend strength (0-1)"""
    if len(mood_values) < 2:
        return 0.0

    # Use correlation coefficient as trend strength
    n = len(mood_values)
    x_values = list(range(n))
    y_values = mood_values

    try:
        # Calculate correlation coefficient
        from scipy.stats import pearsonr

        corr, _ = pearsonr(x_values, y_values)
        return abs(corr)
    except ImportError:
        # Fallback manual calculation
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n

        numerator = sum(
            (x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n)
        )
        x_variance = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        y_variance = sum((y_values[i] - y_mean) ** 2 for i in range(n))

        denominator = (x_variance * y_variance) ** 0.5

        if denominator == 0:
            return 0.0

        return abs(numerator / denominator)


def generate_mood_trend_analysis(user, analysis_type="weekly", days_back=30):
    """Generate mood trend analysis for a user"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days_back)

    # Get mood logs for the period
    mood_logs = MoodLog.objects.filter(
        user=user, logged_at__date__range=[start_date, end_date]
    ).order_by("logged_at")

    if mood_logs.count() < 2:
        print(
            f"Not enough mood data for user {user.username} (need at least 2 entries)"
        )
        return None

    # Extract mood values
    mood_values = [log.mood_rating for log in mood_logs]

    # Calculate statistics
    avg_mood = statistics.mean(mood_values)
    median_mood = statistics.median(mood_values)
    min_mood = min(mood_values)
    max_mood = max(mood_values)
    mood_range = max_mood - min_mood

    # Calculate volatility (standard deviation)
    volatility_score = statistics.stdev(mood_values) if len(mood_values) > 1 else 0.0

    # Calculate trend direction and strength
    trend_direction = calculate_trend_direction(mood_values)
    trend_strength = calculate_trend_strength(mood_values)

    # Calculate consistency score (inverse of volatility, normalized)
    max_volatility = 3.0  # Assume max reasonable std dev for 1-10 scale
    consistency_score = max(0, 1 - (volatility_score / max_volatility))

    # Prepare pattern data
    pattern_data = {
        "daily_averages": [],
        "activity_correlations": {},
        "time_of_day_patterns": {},
    }

    # Calculate daily averages
    daily_moods = {}
    for log in mood_logs:
        day = log.logged_at.date()
        if day not in daily_moods:
            daily_moods[day] = []
        daily_moods[day].append(log.mood_rating)

    for day, moods in daily_moods.items():
        pattern_data["daily_averages"].append(
            {
                "date": day.isoformat(),
                "average_mood": statistics.mean(moods),
                "entries_count": len(moods),
            }
        )

    # Activity correlations
    activity_moods = {}
    for log in mood_logs:
        if log.activities:
            if log.activities not in activity_moods:
                activity_moods[log.activities] = []
            activity_moods[log.activities].append(log.mood_rating)

    for activity, moods in activity_moods.items():
        if len(moods) >= 2:
            pattern_data["activity_correlations"][activity] = {
                "average_mood": statistics.mean(moods),
                "count": len(moods),
            }

    # Simple prediction (linear extrapolation)
    next_period_prediction = None
    prediction_confidence = None

    if len(mood_values) >= 3:
        # Simple linear prediction
        recent_trend = mood_values[-3:]
        if len(recent_trend) >= 2:
            trend_slope = (recent_trend[-1] - recent_trend[0]) / (len(recent_trend) - 1)
            next_period_prediction = max(1, min(10, mood_values[-1] + trend_slope))
            prediction_confidence = min(0.8, trend_strength)  # Cap confidence at 80%

    # Create or update MoodTrendAnalysis
    analysis, created = MoodTrendAnalysis.objects.update_or_create(
        user=user,
        analysis_type=analysis_type,
        period_start=start_date,
        defaults={
            "period_end": end_date,
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "volatility_score": volatility_score,
            "consistency_score": consistency_score,
            "avg_mood": avg_mood,
            "median_mood": median_mood,
            "min_mood": min_mood,
            "max_mood": max_mood,
            "mood_range": mood_range,
            "pattern_data": pattern_data,
            "correlation_data": {},
            "anomalies": [],
            "next_period_prediction": next_period_prediction,
            "prediction_confidence": prediction_confidence,
        },
    )

    action = "Created" if created else "Updated"
    print(f"{action} mood trend analysis for {user.username}:")
    print(f"  - Period: {start_date} to {end_date}")
    print(f"  - Trend: {trend_direction} (strength: {trend_strength:.2f})")
    print(f"  - Average mood: {avg_mood:.2f}")
    print(f"  - Volatility: {volatility_score:.2f}")
    print(f"  - Data points: {len(mood_values)}")

    return analysis


def main():
    """Main function"""
    print("Checking mood data and generating trend analysis...\n")

    # Check current status
    check_database_status()

    print("\n=== GENERATING MOOD TREND ANALYSES ===")

    # Generate analyses for all users with mood data
    users_with_data = CustomUser.objects.filter(mood_logs__isnull=False).distinct()

    if not users_with_data.exists():
        print("No users found with mood data.")
        return

    for user in users_with_data:
        print(f"\nProcessing user: {user.username}")

        # Generate weekly analysis
        weekly_analysis = generate_mood_trend_analysis(user, "weekly", 14)

        # Generate monthly analysis if enough data
        mood_count = MoodLog.objects.filter(user=user).count()
        if mood_count >= 4:
            monthly_analysis = generate_mood_trend_analysis(user, "monthly", 30)

    print("\n=== FINAL STATUS ===")
    print(f"Total mood trend analyses: {MoodTrendAnalysis.objects.count()}")


if __name__ == "__main__":
    main()
