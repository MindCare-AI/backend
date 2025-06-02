# datawarehouse/urls.py
from django.urls import path
from . import views

app_name = 'datawarehouse'

urlpatterns = [
    # Data Collection Runs
    path('collection-runs/', views.DataCollectionRunViewSet.as_view({'get': 'list', 'post': 'create'}), name='datacollectionrun-list'),
    path('collection-runs/<uuid:pk>/', views.DataCollectionRunViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='datacollectionrun-detail'),
    path('collection-runs/latest/', views.DataCollectionRunViewSet.as_view({'get': 'latest'}), name='datacollectionrun-latest'),
    path('collection-runs/performance/', views.DataCollectionRunViewSet.as_view({'get': 'performance_comparison'}), name='datacollectionrun-performance'),
    
    # User Data Snapshots
    path('user-snapshots/', views.UserDataSnapshotViewSet.as_view({'get': 'list', 'post': 'create'}), name='userdatasnapshot-list'),
    path('user-snapshots/<int:pk>/', views.UserDataSnapshotViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='userdatasnapshot-detail'),
    path('user-snapshots/user-trends/', views.UserDataSnapshotViewSet.as_view({'get': 'user_trends'}), name='userdatasnapshot-user-trends'),
    path('user-snapshots/risk-dashboard/', views.UserDataSnapshotViewSet.as_view({'get': 'risk_dashboard'}), name='userdatasnapshot-risk-dashboard'),
    
    # Mood Trend Analysis
    path('mood-trends/', views.MoodTrendAnalysisViewSet.as_view({'get': 'list', 'post': 'create'}), name='moodtrendanalysis-list'),
    path('mood-trends/<int:pk>/', views.MoodTrendAnalysisViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='moodtrendanalysis-detail'),
    
    # Journal Insight Cache
    path('journal-insights/', views.JournalInsightCacheViewSet.as_view({'get': 'list', 'post': 'create'}), name='journalinsightcache-list'),
    path('journal-insights/<int:pk>/', views.JournalInsightCacheViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='journalinsightcache-detail'),
    
    # Communication Metrics
    path('communication-metrics/', views.CommunicationMetricsViewSet.as_view({'get': 'list', 'post': 'create'}), name='communicationmetrics-list'),
    path('communication-metrics/<int:pk>/', views.CommunicationMetricsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='communicationmetrics-detail'),
    
    # Feature Usage Metrics
    path('feature-usage/', views.FeatureUsageMetricsViewSet.as_view({'get': 'list', 'post': 'create'}), name='featureusagemetrics-list'),
    path('feature-usage/<int:pk>/', views.FeatureUsageMetricsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='featureusagemetrics-detail'),
    path('feature-usage/engagement-stats/', views.FeatureUsageMetricsViewSet.as_view({'get': 'engagement_stats'}), name='featureusagemetrics-engagement-stats'),
    
    # Predictive Models
    path('predictive-models/', views.PredictiveModelViewSet.as_view({'get': 'list', 'post': 'create'}), name='predictivemodel-list'),
    path('predictive-models/<int:pk>/', views.PredictiveModelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='predictivemodel-detail'),
    
    # Data Quality Reports
    path('quality-reports/', views.DataQualityReportViewSet.as_view({'get': 'list', 'post': 'create'}), name='dataqualityreport-list'),
    path('quality-reports/<int:pk>/', views.DataQualityReportViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='dataqualityreport-detail'),
    
    # Unified Data Collection
    path('unified-data/', views.UnifiedDataCollectionViewSet.as_view({'get': 'list', 'post': 'create'}), name='unifieddatacollection-list'),
    path('unified-data/<int:pk>/', views.UnifiedDataCollectionViewSet.as_view({'get': 'retrieve'}), name='unifieddatacollection-detail'),
    path('unified-data/collect/', views.UnifiedDataCollectionViewSet.as_view({'post': 'collect_data'}), name='unifieddatacollection-collect'),
    
    # Health and Monitoring
    path('health/', views.DatawarehouseHealthView.as_view({'get': 'list'}), name='health'),
    path('dashboard/', views.DatawarehouseDashboardView.as_view({'get': 'list'}), name='dashboard'),
    
    # Data Export
    path('export/user-data/', views.DataExportView.as_view({'get': 'user_data'}), name='export-user-data'),
    path('export/system-summary/', views.DataExportView.as_view({'get': 'system_summary'}), name='export-system-summary'),
]
