#!/usr/bin/env python3
"""
Quick script to generate mood trend analyses from existing mood logs
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mindcare.settings")
sys.path.append("/home/siaziz/Desktop/backend")
django.setup()

from django.contrib.auth import get_user_model
from mood.models import MoodLog
from datawarehouse.models import MoodTrendAnalysis
from django.utils import timezone
from datetime import timedelta
import numpy as np
from scipy import stats
from collections import defaultdict

User = get_user_model()


def generate_mood_trends():
    """Generate mood trend analyses for all users with mood logs"""
    print("🔍 Generating mood trend analyses from existing mood logs...")

    # Find users with mood logs
    users_with_moods = User.objects.filter(mood_logs__isnull=False).distinct()
    print(f"Found {users_with_moods.count()} users with mood logs")

    total_analyses_created = 0

    for user in users_with_moods:
        print(f"\n📊 Processing user {user.id} ({user.username})...")

        # Get user's mood logs
        mood_logs = MoodLog.objects.filter(user=user).order_by("logged_at")
        print(f"  Found {mood_logs.count()} mood logs")

        if mood_logs.count() < 2:
            print("  ⚠️  Skipping - need at least 2 mood logs")
            continue

        # Generate analyses for different periods
        end_date = timezone.now().date()
        analyses_created = 0

        # Weekly analysis (last 14 days)
        weekly_start = end_date - timedelta(days=14)
        weekly_logs = mood_logs.filter(logged_at__date__gte=weekly_start)

        if weekly_logs.count() >= 2:
            analysis_data = calculate_mood_trends(weekly_logs)
            analysis, created = MoodTrendAnalysis.objects.update_or_create(
                user=user,
                analysis_type="weekly",
                period_start=weekly_start,
                period_end=end_date,
                defaults=analysis_data,
            )
            if created:
                analyses_created += 1
                print("  ✅ Created weekly analysis")

        # Monthly analysis (last 30 days)
        monthly_start = end_date - timedelta(days=30)
        monthly_logs = mood_logs.filter(logged_at__date__gte=monthly_start)

        if monthly_logs.count() >= 2:
            analysis_data = calculate_mood_trends(monthly_logs)
            analysis, created = MoodTrendAnalysis.objects.update_or_create(
                user=user,
                analysis_type="monthly",
                period_start=monthly_start,
                period_end=end_date,
                defaults=analysis_data,
            )
            if created:
                analyses_created += 1
                print("  ✅ Created monthly analysis")

        # All-time analysis
        if mood_logs.count() >= 2:
            all_time_start = mood_logs.first().logged_at.date()
            analysis_data = calculate_mood_trends(mood_logs)
            analysis, created = MoodTrendAnalysis.objects.update_or_create(
                user=user,
                analysis_type="all_time",
                period_start=all_time_start,
                period_end=end_date,
                defaults=analysis_data,
            )
            if created:
                analyses_created += 1
                print("  ✅ Created all-time analysis")

        total_analyses_created += analyses_created
        print(f"  📈 Created {analyses_created} analyses for user {user.username}")

    print(f"\n🎉 Completed! Created {total_analyses_created} mood trend analyses")
    print(f"📊 Total analyses in database: {MoodTrendAnalysis.objects.count()}")


def calculate_mood_trends(mood_logs):
    """Calculate mood trend metrics from mood logs"""
    # Convert to lists for analysis
    dates = []
    moods = []
    activities = defaultdict(list)

    for log in mood_logs:
        dates.append(log.logged_at.date())
        moods.append(float(log.mood_rating))
        if log.activities:
            activities[log.activities].append(float(log.mood_rating))

    # Convert dates to numeric for regression
    base_date = min(dates)
    x_values = [(d - base_date).days for d in dates]
    y_values = moods

    # Calculate trend direction using linear regression
    if len(x_values) > 1:
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            x_values, y_values
        )
        trend_strength = abs(r_value)

        # Determine trend direction
        if slope > 0.5:
            trend_direction = "strongly_improving"
        elif slope > 0.1:
            trend_direction = "improving"
        elif slope < -0.5:
            trend_direction = "strongly_declining"
        elif slope < -0.1:
            trend_direction = "declining"
        else:
            trend_direction = "stable"
    else:
        slope = 0
        trend_direction = "stable"
        trend_strength = 0

    # Calculate statistics
    mood_array = np.array(moods)
    avg_mood = float(np.mean(mood_array))
    median_mood = float(np.median(mood_array))
    min_mood = float(np.min(mood_array))
    max_mood = float(np.max(mood_array))
    mood_range = max_mood - min_mood
    volatility_score = float(np.std(mood_array))

    # Calculate consistency (inverse of volatility, normalized)
    consistency_score = max(0, 1 - (volatility_score / 5))  # Assuming 1-10 scale

    # Calculate activity correlations
    correlation_data = {}
    for activity, activity_moods in activities.items():
        if len(activity_moods) > 1:
            activity_avg = np.mean(activity_moods)
            correlation_data[activity] = {
                "average_mood": float(activity_avg),
                "sessions": len(activity_moods),
                "compared_to_overall": float(activity_avg - avg_mood),
            }

    # Daily averages pattern
    daily_averages = defaultdict(list)
    for date, mood in zip(dates, moods):
        daily_averages[date.strftime("%Y-%m-%d")].append(mood)

    pattern_data = {
        "daily_averages": {
            date: float(np.mean(mood_list))
            for date, mood_list in daily_averages.items()
        },
        "trend_slope": float(slope) if slope else 0,
        "data_points": len(moods),
        "activity_correlations": correlation_data,
    }

    # Simple prediction (next period average based on trend)
    next_period_prediction = avg_mood + (slope * 7)  # Project 7 days ahead
    next_period_prediction = max(
        1, min(10, next_period_prediction)
    )  # Clamp to 1-10 range
    prediction_confidence = min(0.9, trend_strength)  # Cap at 90%

    return {
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
        "correlation_data": correlation_data,
        "anomalies": [],  # TODO: Implement anomaly detection
        "next_period_prediction": next_period_prediction,
        "prediction_confidence": prediction_confidence,
    }


if __name__ == "__main__":
    generate_mood_trends()
