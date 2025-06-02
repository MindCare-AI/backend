"""
Medical and Health Metrics Collection Service for Data Warehouse

This service handles collection and analysis of medical and health data:
- Health metrics (vitals, symptoms, measurements)
- Medical history entries
- Treatment responses
- Health trend analysis

Provides comprehensive health analytics and clinical insights.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from django.utils import timezone
from collections import defaultdict
import statistics

# Import Django models
from patient.models.health_metric import HealthMetric
from patient.models.medical_history import MedicalHistoryEntry

logger = logging.getLogger(__name__)


@dataclass
class HealthTrendData:
    """Health trend data for a specific metric"""
    metric_type: str = ""
    values: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    trend_direction: str = ""  # 'improving', 'declining', 'stable'
    trend_strength: float = 0.0  # 0-1 scale
    average_value: float = 0.0
    latest_value: float = 0.0
    reference_range: Dict[str, float] = field(default_factory=dict)
    out_of_range_count: int = 0


@dataclass
class MedicalAnalysisResult:
    """Comprehensive medical and health analysis result"""
    # Basic metrics
    total_health_records: int = 0
    total_medical_entries: int = 0
    data_completeness_score: float = 0.0
    
    # Health metrics analysis
    health_trends: Dict[str, HealthTrendData] = field(default_factory=dict)
    vital_signs_summary: Dict[str, Dict[str, float]] = field(default_factory=dict)
    symptom_patterns: Dict[str, List[Tuple[datetime, int]]] = field(default_factory=dict)
    
    # Medical history analysis
    condition_timeline: List[Dict[str, Any]] = field(default_factory=list)
    medication_adherence: Dict[str, float] = field(default_factory=dict)
    treatment_responses: Dict[str, List[Dict[str, Any]]] = field(default_factory=list)
    
    # Risk assessment
    health_risk_indicators: List[Dict[str, Any]] = field(default_factory=list)
    anomaly_detections: List[Dict[str, Any]] = field(default_factory=list)
    critical_values: List[Dict[str, Any]] = field(default_factory=list)
    
    # Progress tracking
    improvement_metrics: Dict[str, float] = field(default_factory=dict)
    goal_achievements: List[Dict[str, Any]] = field(default_factory=list)
    adherence_scores: Dict[str, float] = field(default_factory=dict)
    
    # Clinical insights
    overall_health_score: float = 0.0
    health_stability_index: float = 0.0
    care_recommendations: List[str] = field(default_factory=list)
    
    # Insights and alerts
    insights: List[str] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    collection_timestamp: datetime = field(default_factory=timezone.now)
    analysis_period: str = ""


class MedicalCollectionService:
    """Service for collecting and analyzing medical and health data"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Reference ranges for common health metrics
        self.reference_ranges = {
            'blood_pressure_systolic': {'min': 90, 'max': 140, 'optimal_min': 110, 'optimal_max': 120},
            'blood_pressure_diastolic': {'min': 60, 'max': 90, 'optimal_min': 70, 'optimal_max': 80},
            'heart_rate': {'min': 60, 'max': 100, 'optimal_min': 60, 'optimal_max': 80},
            'temperature': {'min': 36.1, 'max': 37.2, 'optimal_min': 36.5, 'optimal_max': 37.0},
            'weight': {'min': 0, 'max': 1000},  # Will be personalized based on patient
            'blood_glucose': {'min': 70, 'max': 140, 'optimal_min': 80, 'optimal_max': 110},
            'oxygen_saturation': {'min': 95, 'max': 100, 'optimal_min': 97, 'optimal_max': 100},
            'pain_level': {'min': 0, 'max': 10, 'optimal_min': 0, 'optimal_max': 3}
        }
        
        # Critical thresholds that require immediate attention
        self.critical_thresholds = {
            'blood_pressure_systolic': {'low': 90, 'high': 180},
            'blood_pressure_diastolic': {'low': 60, 'high': 110},
            'heart_rate': {'low': 50, 'high': 120},
            'temperature': {'low': 35.0, 'high': 38.5},
            'blood_glucose': {'low': 60, 'high': 200},
            'oxygen_saturation': {'low': 90, 'high': 100},
            'pain_level': {'low': 0, 'high': 8}
        }
    
    def collect_medical_data(self, patient_id: int, days: int = 30) -> MedicalAnalysisResult:
        """
        Collect and analyze medical and health data for a patient
        
        Args:
            patient_id: ID of the patient
            days: Number of days to analyze (default: 30)
            
        Returns:
            MedicalAnalysisResult with comprehensive analysis
        """
        try:
            self.logger.info(f"Starting medical data collection for patient {patient_id}")
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Initialize result
            result = MedicalAnalysisResult(
                analysis_period=f"{start_date.date()} to {end_date.date()}"
            )
            
            # Collect health metrics
            self._analyze_health_metrics(patient_id, start_date, end_date, result)
            
            # Collect medical history
            self._analyze_medical_history(patient_id, start_date, end_date, result)
            
            # Perform advanced analysis
            self._analyze_health_trends(result)
            self._detect_anomalies(result)
            self._assess_health_risks(result)
            self._calculate_health_scores(result)
            self._generate_medical_insights(result)
            
            self.logger.info(f"Medical data collection completed for patient {patient_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error collecting medical data for patient {patient_id}: {str(e)}")
            raise
    
    def _analyze_health_metrics(self, patient_id: int, start_date: datetime, 
                              end_date: datetime, result: MedicalAnalysisResult):
        """Analyze health metrics and vital signs"""
        try:
            health_metrics = HealthMetric.objects.filter(
                patient_id=patient_id,
                recorded_at__range=[start_date, end_date]
            ).order_by('recorded_at')
            
            result.total_health_records = health_metrics.count()
            
            if not health_metrics.exists():
                return
            
            # Group metrics by type
            metrics_by_type = defaultdict(list)
            for metric in health_metrics:
                metrics_by_type[metric.metric_type].append({
                    'value': float(metric.value),
                    'timestamp': metric.recorded_at,
                    'unit': metric.unit,
                    'notes': metric.notes
                })
            
            # Analyze each metric type
            for metric_type, metrics in metrics_by_type.items():
                trend_data = HealthTrendData(metric_type=metric_type)
                
                # Extract values and timestamps
                trend_data.values = [m['value'] for m in metrics]
                trend_data.timestamps = [m['timestamp'] for m in metrics]
                
                # Calculate basic statistics
                if trend_data.values:
                    trend_data.average_value = statistics.mean(trend_data.values)
                    trend_data.latest_value = trend_data.values[-1]
                    
                    # Set reference range if available
                    if metric_type in self.reference_ranges:
                        trend_data.reference_range = self.reference_ranges[metric_type]
                        
                        # Count out-of-range values
                        ref_range = self.reference_ranges[metric_type]
                        trend_data.out_of_range_count = sum(
                            1 for value in trend_data.values 
                            if value < ref_range['min'] or value > ref_range['max']
                        )
                    
                    # Calculate trend direction and strength
                    if len(trend_data.values) >= 3:
                        trend_data.trend_direction, trend_data.trend_strength = \
                            self._calculate_trend(trend_data.values)
                
                result.health_trends[metric_type] = trend_data
                
                # Create vital signs summary
                if trend_data.values:
                    result.vital_signs_summary[metric_type] = {
                        'current': trend_data.latest_value,
                        'average': trend_data.average_value,
                        'min': min(trend_data.values),
                        'max': max(trend_data.values),
                        'count': len(trend_data.values)
                    }
                
                # Track symptom patterns (for pain, fatigue, etc.)
                if metric_type in ['pain_level', 'fatigue_level', 'mood_score']:
                    result.symptom_patterns[metric_type] = [
                        (m['timestamp'], int(m['value'])) for m in metrics
                    ]
            
        except Exception as e:
            self.logger.error(f"Error analyzing health metrics: {str(e)}")
    
    def _analyze_medical_history(self, patient_id: int, start_date: datetime, 
                               end_date: datetime, result: MedicalAnalysisResult):
        """Analyze medical history entries"""
        try:
            medical_entries = MedicalHistoryEntry.objects.filter(
                patient_id=patient_id,
                date_recorded__range=[start_date, end_date]
            ).order_by('date_recorded')
            
            result.total_medical_entries = medical_entries.count()
            
            if not medical_entries.exists():
                return
            
            # Build condition timeline
            for entry in medical_entries:
                timeline_item = {
                    'date': entry.date_recorded,
                    'condition': entry.condition,
                    'diagnosis': entry.diagnosis,
                    'treatment': entry.treatment,
                    'notes': entry.notes,
                    'severity': getattr(entry, 'severity', 'unknown')
                }
                result.condition_timeline.append(timeline_item)
            
            # Analyze medication adherence (if medication tracking is available)
            self._analyze_medication_adherence(medical_entries, result)
            
            # Analyze treatment responses
            self._analyze_treatment_responses(medical_entries, result)
            
        except Exception as e:
            self.logger.error(f"Error analyzing medical history: {str(e)}")
    
    def _analyze_medication_adherence(self, medical_entries, result: MedicalAnalysisResult):
        """Analyze medication adherence patterns"""
        try:
            medication_entries = [
                entry for entry in medical_entries 
                if 'medication' in entry.treatment.lower() or 'drug' in entry.treatment.lower()
            ]
            
            if not medication_entries:
                return
            
            # Group by medication type/name
            medications = defaultdict(list)
            for entry in medication_entries:
                med_name = entry.treatment.lower()
                medications[med_name].append(entry)
            
            # Calculate adherence scores
            for med_name, entries in medications.items():
                if len(entries) >= 2:
                    # Simple adherence calculation based on regularity
                    expected_intervals = []
                    actual_intervals = []
                    
                    for i in range(1, len(entries)):
                        actual_interval = (entries[i].date_recorded - entries[i-1].date_recorded).days
                        actual_intervals.append(actual_interval)
                    
                    if actual_intervals:
                        avg_interval = statistics.mean(actual_intervals)
                        consistency = 1.0 - (statistics.stdev(actual_intervals) / avg_interval 
                                           if avg_interval > 0 else 1.0)
                        result.medication_adherence[med_name] = max(0.0, min(1.0, consistency))
            
        except Exception as e:
            self.logger.error(f"Error analyzing medication adherence: {str(e)}")
    
    def _analyze_treatment_responses(self, medical_entries, result: MedicalAnalysisResult):
        """Analyze treatment effectiveness and responses"""
        try:
            treatments = defaultdict(list)
            
            for entry in medical_entries:
                if entry.treatment:
                    treatment_key = entry.treatment.lower()
                    treatments[treatment_key].append({
                        'date': entry.date_recorded,
                        'condition': entry.condition,
                        'diagnosis': entry.diagnosis,
                        'notes': entry.notes
                    })
            
            # Analyze each treatment's effectiveness
            for treatment_name, entries in treatments.items():
                if len(entries) >= 2:
                    response_data = {
                        'treatment': treatment_name,
                        'duration': (entries[-1]['date'] - entries[0]['date']).days,
                        'entries_count': len(entries),
                        'conditions_treated': list(set(e['condition'] for e in entries if e['condition'])),
                        'effectiveness_indicators': []
                    }
                    
                    # Look for improvement keywords in notes
                    improvement_keywords = ['better', 'improved', 'reduced', 'decreased', 'stable']
                    decline_keywords = ['worse', 'increased', 'worsened', 'deteriorated']
                    
                    for entry in entries:
                        if entry['notes']:
                            notes_lower = entry['notes'].lower()
                            if any(keyword in notes_lower for keyword in improvement_keywords):
                                response_data['effectiveness_indicators'].append('positive')
                            elif any(keyword in notes_lower for keyword in decline_keywords):
                                response_data['effectiveness_indicators'].append('negative')
                    
                    result.treatment_responses[treatment_name] = [response_data]
            
        except Exception as e:
            self.logger.error(f"Error analyzing treatment responses: {str(e)}")
    
    def _analyze_health_trends(self, result: MedicalAnalysisResult):
        """Analyze overall health trends and patterns"""
        try:
            improving_trends = 0
            declining_trends = 0
            stable_trends = 0
            
            for metric_type, trend_data in result.health_trends.items():
                if trend_data.trend_direction == 'improving':
                    improving_trends += 1
                    result.improvement_metrics[metric_type] = trend_data.trend_strength
                elif trend_data.trend_direction == 'declining':
                    declining_trends += 1
                else:
                    stable_trends += 1
            
            # Calculate overall trend score
            total_trends = improving_trends + declining_trends + stable_trends
            if total_trends > 0:
                trend_score = (improving_trends - declining_trends) / total_trends
                result.health_stability_index = (trend_score + 1) / 2  # Normalize to 0-1
            
        except Exception as e:
            self.logger.error(f"Error analyzing health trends: {str(e)}")
    
    def _detect_anomalies(self, result: MedicalAnalysisResult):
        """Detect anomalies and critical values in health data"""
        try:
            for metric_type, trend_data in result.health_trends.items():
                if not trend_data.values:
                    continue
                
                # Check for critical values
                if metric_type in self.critical_thresholds:
                    thresholds = self.critical_thresholds[metric_type]
                    
                    for i, (value, timestamp) in enumerate(zip(trend_data.values, trend_data.timestamps)):
                        if value <= thresholds['low'] or value >= thresholds['high']:
                            critical_alert = {
                                'metric_type': metric_type,
                                'value': value,
                                'timestamp': timestamp,
                                'severity': 'high' if (value <= thresholds['low'] * 0.8 or 
                                                     value >= thresholds['high'] * 1.2) else 'medium',
                                'type': 'low' if value <= thresholds['low'] else 'high'
                            }
                            result.critical_values.append(critical_alert)
                
                # Detect statistical anomalies
                if len(trend_data.values) >= 5:
                    mean_value = statistics.mean(trend_data.values)
                    std_dev = statistics.stdev(trend_data.values)
                    
                    for i, (value, timestamp) in enumerate(zip(trend_data.values, trend_data.timestamps)):
                        z_score = abs(value - mean_value) / std_dev if std_dev > 0 else 0
                        
                        if z_score > 2.5:  # More than 2.5 standard deviations
                            anomaly = {
                                'metric_type': metric_type,
                                'value': value,
                                'timestamp': timestamp,
                                'z_score': z_score,
                                'severity': 'high' if z_score > 3 else 'medium'
                            }
                            result.anomaly_detections.append(anomaly)
            
        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {str(e)}")
    
    def _assess_health_risks(self, result: MedicalAnalysisResult):
        """Assess health risks based on trends and patterns"""
        try:
            risk_factors = []
            
            # Check for declining trends in critical metrics
            critical_metrics = ['blood_pressure_systolic', 'heart_rate', 'oxygen_saturation']
            
            for metric in critical_metrics:
                if metric in result.health_trends:
                    trend_data = result.health_trends[metric]
                    
                    if trend_data.trend_direction == 'declining' and trend_data.trend_strength > 0.6:
                        risk_factors.append({
                            'type': 'declining_vital',
                            'metric': metric,
                            'severity': 'high',
                            'description': f"Declining trend in {metric}",
                            'trend_strength': trend_data.trend_strength
                        })
            
            # Check for high variability in important metrics
            for metric_type, trend_data in result.health_trends.items():
                if len(trend_data.values) >= 5:
                    cv = statistics.stdev(trend_data.values) / statistics.mean(trend_data.values)
                    
                    if cv > 0.2 and metric_type in critical_metrics:  # High coefficient of variation
                        risk_factors.append({
                            'type': 'high_variability',
                            'metric': metric_type,
                            'severity': 'medium',
                            'description': f"High variability in {metric_type}",
                            'coefficient_variation': cv
                        })
            
            # Check medication adherence risks
            for med_name, adherence in result.medication_adherence.items():
                if adherence < 0.7:  # Less than 70% adherence
                    risk_factors.append({
                        'type': 'poor_adherence',
                        'medication': med_name,
                        'severity': 'high' if adherence < 0.5 else 'medium',
                        'description': f"Poor adherence to {med_name}",
                        'adherence_score': adherence
                    })
            
            result.health_risk_indicators = risk_factors
            
        except Exception as e:
            self.logger.error(f"Error assessing health risks: {str(e)}")
    
    def _calculate_health_scores(self, result: MedicalAnalysisResult):
        """Calculate overall health and adherence scores"""
        try:
            health_components = []
            
            # Vital signs component
            vital_score = 0.0
            vital_count = 0
            
            for metric_type, trend_data in result.health_trends.items():
                if metric_type in self.reference_ranges and trend_data.values:
                    ref_range = self.reference_ranges[metric_type]
                    latest_value = trend_data.latest_value
                    
                    # Score based on how close to optimal range
                    if 'optimal_min' in ref_range and 'optimal_max' in ref_range:
                        if ref_range['optimal_min'] <= latest_value <= ref_range['optimal_max']:
                            score = 1.0
                        elif ref_range['min'] <= latest_value <= ref_range['max']:
                            score = 0.7
                        else:
                            score = 0.3
                    else:
                        # Basic range check
                        if ref_range['min'] <= latest_value <= ref_range['max']:
                            score = 0.8
                        else:
                            score = 0.2
                    
                    vital_score += score
                    vital_count += 1
            
            if vital_count > 0:
                health_components.append(vital_score / vital_count)
            
            # Trend component
            if result.health_stability_index > 0:
                health_components.append(result.health_stability_index)
            
            # Risk factors component (inverse of risk)
            risk_score = max(0, 1.0 - (len(result.health_risk_indicators) * 0.2))
            health_components.append(risk_score)
            
            # Calculate overall health score
            if health_components:
                result.overall_health_score = sum(health_components) / len(health_components)
            
            # Calculate adherence scores
            if result.medication_adherence:
                avg_adherence = sum(result.medication_adherence.values()) / len(result.medication_adherence)
                result.adherence_scores['medication'] = avg_adherence
            
        except Exception as e:
            self.logger.error(f"Error calculating health scores: {str(e)}")
    
    def _generate_medical_insights(self, result: MedicalAnalysisResult):
        """Generate medical insights and recommendations"""
        try:
            insights = []
            recommendations = []
            alerts = []
            
            # Overall health assessment
            if result.overall_health_score >= 0.8:
                insights.append("Overall health indicators are within good ranges")
            elif result.overall_health_score >= 0.6:
                insights.append("Health indicators show moderate status with room for improvement")
            else:
                insights.append("Health indicators suggest need for increased monitoring and care")
                alerts.append({
                    'type': 'health_status',
                    'severity': 'medium',
                    'message': 'Overall health score indicates concerning patterns'
                })
            
            # Trend insights
            improving_metrics = [m for m, t in result.health_trends.items() 
                               if t.trend_direction == 'improving']
            declining_metrics = [m for m, t in result.health_trends.items() 
                               if t.trend_direction == 'declining']
            
            if improving_metrics:
                insights.append(f"Positive trends observed in: {', '.join(improving_metrics)}")
            
            if declining_metrics:
                insights.append(f"Concerning trends in: {', '.join(declining_metrics)}")
                recommendations.append(f"Monitor and address declining trends in {', '.join(declining_metrics)}")
            
            # Critical values
            if result.critical_values:
                high_severity_criticals = [c for c in result.critical_values if c['severity'] == 'high']
                if high_severity_criticals:
                    alerts.append({
                        'type': 'critical_values',
                        'severity': 'high',
                        'message': f"Critical health values detected in {len(high_severity_criticals)} measurements"
                    })
                    recommendations.append("Immediate medical consultation recommended for critical values")
            
            # Adherence insights
            poor_adherence = [med for med, score in result.medication_adherence.items() if score < 0.7]
            if poor_adherence:
                insights.append(f"Poor medication adherence detected for: {', '.join(poor_adherence)}")
                recommendations.append("Improve medication adherence through reminders and education")
            
            # Data completeness
            expected_daily_records = 3  # Assume 3 health records per day as baseline
            expected_total = expected_daily_records * 30  # 30 days
            if result.total_health_records > 0:
                completeness = min(result.total_health_records / expected_total, 1.0)
                result.data_completeness_score = completeness
                
                if completeness < 0.5:
                    insights.append("Low health data recording frequency detected")
                    recommendations.append("Increase frequency of health metric recording for better monitoring")
            
            # Risk-based recommendations
            for risk in result.health_risk_indicators:
                if risk['severity'] == 'high':
                    recommendations.append(f"Address high-risk factor: {risk['description']}")
            
            result.insights = insights
            result.recommendations = recommendations
            result.alerts = alerts
            
        except Exception as e:
            self.logger.error(f"Error generating medical insights: {str(e)}")
    
    def _calculate_trend(self, values: List[float]) -> Tuple[str, float]:
        """Calculate trend direction and strength"""
        if len(values) < 3:
            return 'stable', 0.0
        
        # Simple linear regression to determine trend
        x = list(range(len(values)))
        n = len(values)
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        # Determine direction and strength
        abs_slope = abs(slope)
        max_value = max(values)
        min_value = min(values)
        value_range = max_value - min_value
        
        if value_range == 0:
            return 'stable', 0.0
        
        # Normalize slope by value range
        normalized_slope = abs_slope / value_range * len(values)
        strength = min(normalized_slope, 1.0)
        
        if slope > 0.01:
            direction = 'improving'
        elif slope < -0.01:
            direction = 'declining'
        else:
            direction = 'stable'
        
        return direction, strength


# Singleton instance
medical_collection_service = MedicalCollectionService()
