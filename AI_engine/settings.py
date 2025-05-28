"""
AI Engine specific settings and configuration
"""

# Default AI Engine Settings
DEFAULT_AI_ENGINE_SETTINGS = {
    "ANALYSIS_BATCH_SIZE": 50,
    "MAX_ANALYSIS_PERIOD": 90,  # days
    "MIN_DATA_POINTS": 5,
    "RISK_THRESHOLD": 0.7,
    "CACHE_TIMEOUT": 900,  # 15 minutes
    "MODEL_TIMEOUT": 30,  # seconds
    "MAX_PROMPT_LENGTH": 4000,  # characters
    "DEFAULT_MODEL": "mistral",
}


def get_ai_engine_settings():
    """Get AI engine settings with fallbacks"""
    from django.conf import settings

    ai_settings = getattr(settings, "AI_ENGINE_SETTINGS", {})

    # Merge with defaults
    final_settings = DEFAULT_AI_ENGINE_SETTINGS.copy()
    final_settings.update(ai_settings)

    return final_settings
