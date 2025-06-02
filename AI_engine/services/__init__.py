from .ai_analysis import ai_service, AIAnalysisService
from .predictive_service import predictive_service

# Import communication analysis service if available
try:
    from .communication_analysis import communication_analysis_service
except ImportError:
    communication_analysis_service = None

# Import other services that may be referenced
try:
    from .therapy_analysis import therapy_analysis_service
except ImportError:
    therapy_analysis_service = None

try:
    from .social_analysis import SocialInteractionAnalysisService
except ImportError:
    SocialInteractionAnalysisService = None

try:
    from .crisis_monitoring import CrisisMonitoringService
except ImportError:
    CrisisMonitoringService = None

try:
    from .conversation_summary import ConversationSummaryService
except ImportError:
    ConversationSummaryService = None

try:
    from .medication_analysis import MedicationAnalysisService
except ImportError:
    MedicationAnalysisService = None

__all__ = [
    "ai_service",
    "predictive_service",
    "communication_analysis_service",
    "therapy_analysis_service",
    "SocialInteractionAnalysisService",
    "AIAnalysisService",
]
