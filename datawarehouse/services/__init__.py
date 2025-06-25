# datawarehouse/services/__init__.py
from .data_collection import data_collector, DataCollectionService
from .etl_service import etl_service, ETLService

# Import unified data collection service
try:
    from .unified_data_collection_service import (
        unified_data_collector,
        UnifiedDataCollectionService,
    )
except ImportError:
    unified_data_collector = None
    UnifiedDataCollectionService = None

# Import specialized services if available
try:
    from .feeds_service import FeedsCollectionService
except ImportError:
    FeedsCollectionService = None

try:
    from .therapist_session_notes_service import TherapistSessionNotesCollectionService
except ImportError:
    TherapistSessionNotesCollectionService = None

__all__ = [
    "data_collector",
    "DataCollectionService",
    "etl_service",
    "ETLService",
    "unified_data_collector",
    "UnifiedDataCollectionService",
    "FeedsCollectionService",
    "TherapistSessionNotesCollectionService",
]
