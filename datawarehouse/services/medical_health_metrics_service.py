# datawarehouse/services/medical_health_metrics_service.py
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime, timedelta
import time
import logging
from django.db.models import Count, Avg, Max, Min
from django.utils import timezone
from patient.models.health_metric import HealthMetric
from patient.models.medical_history import MedicalHistoryEntry
from patient.models.patient_profile import PatientProfile

logger = logging.getLogger(__name__)


@dataclass
class MedicalHealthDataSnapshot:
    """Structured data snapshot for medical/health metrics analytics"""
    
    # Basic metrics
    total_health_metrics: int
    total_medical_history_entries: int
    metric_types_tracked: List[str]
    
    # Health metrics analysis
    health_metrics_statistics: Dict[str, Any]
    metric_trends: Dict[str, Any]
    
    # Medical history analysis
    medical_history_statistics: Dict[str, Any]
    condition_patterns: Dict[str, Any]
    
    # Risk assessment
    risk_indicators: Dict[str, Any]
    health_patterns: Dict[str, Any]
    
    # Temporal analysis
    temporal_patterns: Dict[str, Any]
    compliance_metrics: Dict[str, Any]
    
    # Performance metrics
    performance_metrics: Dict[str, Any]
    timestamp: datetime


class MedicalHealthMetricsCollectionService:
    """Dedicated service for collecting and analyzing medical/health metrics data"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    def collect_medical_health_data(self, user_id: int, days_back: int = 90) -> MedicalHealthDataSnapshot:
        """
        Main entry point for collecting medical/health metrics data.
        
        Args:
            user_id: The user ID to collect data for
            days_back: Number of days to look back for data
            
        Returns:
            MedicalHealthDataSnapshot with comprehensive medical/health analytics
        """
        start_time = time.time()
        
        try:
            # Get patient profile
            patient_profile = self._get_patient_profile(user_id)
            if not patient_profile:
                logger.warning(f"No patient profile found for user {user_id}")
                return self._create_empty_snapshot()
            
            # Get raw data
            health_metrics_data = self._collect_raw_health_metrics(patient_profile, days_back)
            medical_history_data = self._collect_raw_medical_history(patient_profile)
            
            # Calculate analytics
            health_stats = self._calculate_health_metrics_statistics(health_metrics_data)
            metric_trends = self._analyze_metric_trends(health_metrics_data)
            
            medical_stats = self._calculate_medical_history_statistics(medical_history_data)
            condition_patterns = self._analyze_condition_patterns(medical_history_data)
            
            risk_indicators = self._assess_risk_indicators(health_metrics_data, medical_history_data)
            health_patterns = self._analyze_health_patterns(health_metrics_data, medical_history_data)
            
            temporal_patterns = self._analyze_temporal_patterns(health_metrics_data)
            compliance_metrics = self._calculate_compliance_metrics(health_metrics_data, days_back)
            
            # Performance tracking
            processing_time = time.time() - start_time
            performance_metrics = {
                'processing_time_seconds': processing_time,
                'health_metrics_processed': len(health_metrics_data),
                'medical_history_entries_processed': len(medical_history_data),
                'timestamp': timezone.now().isoformat()
            }
            
            # Get unique metric types
            metric_types = list(set(metric.get('metric_type') for metric in health_metrics_data if metric.get('metric_type')))
            
            return MedicalHealthDataSnapshot(
                total_health_metrics=len(health_metrics_data),
                total_medical_history_entries=len(medical_history_data),
                metric_types_tracked=metric_types,
                health_metrics_statistics=health_stats,
                metric_trends=metric_trends,
                medical_history_statistics=medical_stats,
                condition_patterns=condition_patterns,
                risk_indicators=risk_indicators,
                health_patterns=health_patterns,
                temporal_patterns=temporal_patterns,
                compliance_metrics=compliance_metrics,
                performance_metrics=performance_metrics,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error collecting medical/health data for user {user_id}: {str(e)}")
            return self._create_empty_snapshot()
    
    def _get_patient_profile(self, user_id: int) -> PatientProfile:
        """Get patient profile for the user"""
        try:
            return PatientProfile.objects.get(user_id=user_id)
        except PatientProfile.DoesNotExist:
            return None
    
    def _collect_raw_health_metrics(self, patient_profile: PatientProfile, days_back: int) -> List[Dict]:
        """Collect raw health metrics data from the database"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)
            
            metrics = HealthMetric.objects.filter(
                patient=patient_profile,
                timestamp__gte=cutoff_date
            ).values(
                'id', 'metric_type', 'value', 'timestamp'
            ).order_by('timestamp')
            
            return list(metrics)
            
        except Exception as e:
            logger.error(f"Error collecting health metrics data: {str(e)}")
            return []
    
    def _collect_raw_medical_history(self, patient_profile: PatientProfile) -> List[Dict]:
        """Collect raw medical history data from the database"""
        try:
            history_entries = MedicalHistoryEntry.objects.filter(
                patient=patient_profile
            ).values(
                'id', 'title', 'description', 'date_occurred', 'is_chronic'
            ).order_by('-date_occurred')
            
            return list(history_entries)
            
        except Exception as e:
            logger.error(f"Error collecting medical history data: {str(e)}")
            return []
    
    def _calculate_health_metrics_statistics(self, health_metrics_data: List[Dict]) -> Dict[str, Any]:
        """Calculate comprehensive health metrics statistics"""
        if not health_metrics_data:
            return self._empty_health_stats()
        
        try:
            total_metrics = len(health_metrics_data)
            
            # Group by metric type
            metrics_by_type = {}
            for metric in health_metrics_data:
                metric_type = metric.get('metric_type')
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric)
            
            # Analyze each metric type
            type_analysis = {}
            for metric_type, metrics in metrics_by_type.items():
                type_analysis[metric_type] = self._analyze_metric_type(metrics, metric_type)
            
            # Overall statistics
            metric_frequency = {metric_type: len(metrics) for metric_type, metrics in metrics_by_type.items()}
            most_tracked_metric = max(metric_frequency.items(), key=lambda x: x[1]) if metric_frequency else ('No data', 0)
            
            # Recent measurements
            now = timezone.now()
            recent_metrics = [
                metric for metric in health_metrics_data 
                if (now - (metric['timestamp'] if isinstance(metric['timestamp'], datetime) 
                          else datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00')))).days <= 7
            ]
            
            return {
                'total_metrics_recorded': total_metrics,
                'unique_metric_types': len(metrics_by_type),
                'metrics_by_type': metric_frequency,
                'most_tracked_metric': most_tracked_metric[0],
                'most_tracked_metric_count': most_tracked_metric[1],
                'type_specific_analysis': type_analysis,
                'recent_measurements_7_days': len(recent_metrics),
                'measurement_consistency': self._calculate_measurement_consistency(health_metrics_data),
                'data_quality_score': self._calculate_data_quality_score(health_metrics_data)
            }
            
        except Exception as e:
            logger.error(f"Error calculating health metrics statistics: {str(e)}")
            return self._empty_health_stats()
    
    def _analyze_metric_type(self, metrics: List[Dict], metric_type: str) -> Dict[str, Any]:
        """Analyze a specific metric type"""
        try:
            if not metrics:
                return {'count': 0, 'analysis': 'No data'}
            
            values = []
            timestamps = []
            
            for metric in metrics:
                value_str = metric.get('value', '')
                timestamp = metric.get('timestamp')
                
                # Parse value based on metric type
                if metric_type == 'blood_pressure':
                    # Handle blood pressure format like "120/80"
                    if '/' in value_str:
                        try:
                            systolic, diastolic = value_str.split('/')
                            values.append({'systolic': int(systolic), 'diastolic': int(diastolic)})
                        except ValueError:
                            continue
                elif metric_type in ['weight', 'heart_rate']:
                    # Handle numeric values
                    try:
                        values.append(float(value_str))
                    except ValueError:
                        continue
                else:
                    # Store as string for other types
                    values.append(value_str)
                
                timestamps.append(timestamp)
            
            if not values:
                return {'count': len(metrics), 'analysis': 'No valid values'}
            
            # Type-specific analysis
            if metric_type == 'blood_pressure':
                return self._analyze_blood_pressure(values, timestamps)
            elif metric_type == 'weight':
                return self._analyze_weight(values, timestamps)
            elif metric_type == 'heart_rate':
                return self._analyze_heart_rate(values, timestamps)
            else:
                return {
                    'count': len(metrics),
                    'unique_values': len(set(values)),
                    'most_common_value': max(set(values), key=values.count) if values else None
                }
                
        except Exception as e:
            logger.error(f"Error analyzing metric type {metric_type}: {str(e)}")
            return {'count': len(metrics), 'error': str(e)}
    
    def _analyze_blood_pressure(self, values: List[Dict], timestamps: List[datetime]) -> Dict[str, Any]:
        """Analyze blood pressure metrics"""
        try:
            systolic_values = [v['systolic'] for v in values]
            diastolic_values = [v['diastolic'] for v in values]
            
            avg_systolic = sum(systolic_values) / len(systolic_values)
            avg_diastolic = sum(diastolic_values) / len(diastolic_values)
            
            # Blood pressure categories (American Heart Association guidelines)
            high_bp_readings = sum(1 for v in values if v['systolic'] >= 140 or v['diastolic'] >= 90)
            elevated_bp_readings = sum(1 for v in values if 120 <= v['systolic'] < 140 and v['diastolic'] < 90)
            normal_bp_readings = sum(1 for v in values if v['systolic'] < 120 and v['diastolic'] < 80)
            
            return {
                'count': len(values),
                'average_systolic': round(avg_systolic, 1),
                'average_diastolic': round(avg_diastolic, 1),
                'max_systolic': max(systolic_values),
                'min_systolic': min(systolic_values),
                'max_diastolic': max(diastolic_values),
                'min_diastolic': min(diastolic_values),
                'normal_readings': normal_bp_readings,
                'elevated_readings': elevated_bp_readings,
                'high_readings': high_bp_readings,
                'percentage_normal': (normal_bp_readings / len(values) * 100) if values else 0,
                'percentage_elevated': (elevated_bp_readings / len(values) * 100) if values else 0,
                'percentage_high': (high_bp_readings / len(values) * 100) if values else 0,
                'trend': self._calculate_simple_trend(systolic_values),
                'risk_level': self._assess_bp_risk_level(avg_systolic, avg_diastolic)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing blood pressure: {str(e)}")
            return {'count': len(values), 'error': str(e)}
    
    def _analyze_weight(self, values: List[float], timestamps: List[datetime]) -> Dict[str, Any]:
        """Analyze weight metrics"""
        try:
            avg_weight = sum(values) / len(values)
            
            # Calculate weight change trend
            if len(values) >= 2:
                first_weight = values[0]
                last_weight = values[-1]
                weight_change = last_weight - first_weight
                weight_change_percentage = (weight_change / first_weight * 100) if first_weight > 0 else 0
            else:
                weight_change = 0
                weight_change_percentage = 0
            
            return {
                'count': len(values),
                'average_weight': round(avg_weight, 1),
                'max_weight': max(values),
                'min_weight': min(values),
                'weight_range': round(max(values) - min(values), 1),
                'weight_change': round(weight_change, 1),
                'weight_change_percentage': round(weight_change_percentage, 2),
                'trend': self._calculate_simple_trend(values),
                'stability_score': self._calculate_weight_stability(values)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing weight: {str(e)}")
            return {'count': len(values), 'error': str(e)}
    
    def _analyze_heart_rate(self, values: List[float], timestamps: List[datetime]) -> Dict[str, Any]:
        """Analyze heart rate metrics"""
        try:
            avg_hr = sum(values) / len(values)
            
            # Heart rate categories (general guidelines)
            high_hr_readings = sum(1 for v in values if v > 100)
            low_hr_readings = sum(1 for v in values if v < 60)
            normal_hr_readings = sum(1 for v in values if 60 <= v <= 100)
            
            return {
                'count': len(values),
                'average_heart_rate': round(avg_hr, 1),
                'max_heart_rate': max(values),
                'min_heart_rate': min(values),
                'heart_rate_range': round(max(values) - min(values), 1),
                'normal_readings': normal_hr_readings,
                'high_readings': high_hr_readings,
                'low_readings': low_hr_readings,
                'percentage_normal': (normal_hr_readings / len(values) * 100) if values else 0,
                'percentage_high': (high_hr_readings / len(values) * 100) if values else 0,
                'percentage_low': (low_hr_readings / len(values) * 100) if values else 0,
                'trend': self._calculate_simple_trend(values),
                'variability_score': self._calculate_hr_variability(values)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing heart rate: {str(e)}")
            return {'count': len(values), 'error': str(e)}
    
    def _analyze_metric_trends(self, health_metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze trends in health metrics over time"""
        try:
            if not health_metrics_data:
                return {'overall_trends': {}, 'metric_specific_trends': {}, 'trend_analysis': {}}
            
            # Group by metric type and analyze trends
            metrics_by_type = {}
            for metric in health_metrics_data:
                metric_type = metric.get('metric_type')
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric)
            
            trend_analysis = {}
            overall_trend_score = 0
            
            for metric_type, metrics in metrics_by_type.items():
                # Sort by timestamp
                metrics.sort(key=lambda x: x.get('timestamp', datetime.min))
                
                if len(metrics) >= 3:  # Need at least 3 points for trend analysis
                    trend_data = self._calculate_detailed_trend(metrics, metric_type)
                    trend_analysis[metric_type] = trend_data
                    
                    # Contribute to overall trend score
                    if trend_data.get('trend_strength', 0) > 0.5:
                        if trend_data.get('trend_direction') == 'improving':
                            overall_trend_score += 1
                        elif trend_data.get('trend_direction') == 'declining':
                            overall_trend_score -= 1
            
            # Calculate measurement frequency trends
            measurement_frequency = self._analyze_measurement_frequency(health_metrics_data)
            
            return {
                'overall_trends': {
                    'overall_trend_score': overall_trend_score,
                    'metrics_with_trends': len(trend_analysis),
                    'trend_assessment': self._assess_overall_trend(overall_trend_score)
                },
                'metric_specific_trends': trend_analysis,
                'trend_analysis': {
                    'measurement_frequency_trend': measurement_frequency,
                    'data_consistency_trend': self._analyze_data_consistency_trend(health_metrics_data),
                    'trend_reliability_score': self._calculate_trend_reliability(trend_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing metric trends: {str(e)}")
            return {'overall_trends': {}, 'metric_specific_trends': {}, 'trend_analysis': {}}
    
    def _calculate_medical_history_statistics(self, medical_history_data: List[Dict]) -> Dict[str, Any]:
        """Calculate medical history statistics"""
        if not medical_history_data:
            return self._empty_medical_stats()
        
        try:
            total_entries = len(medical_history_data)
            chronic_conditions = [entry for entry in medical_history_data if entry.get('is_chronic', False)]
            acute_conditions = [entry for entry in medical_history_data if not entry.get('is_chronic', False)]
            
            # Analyze by time periods
            now = timezone.now().date()
            recent_entries = [
                entry for entry in medical_history_data 
                if entry.get('date_occurred') and 
                (now - entry['date_occurred']).days <= 365
            ]
            
            # Extract common keywords from titles and descriptions
            condition_keywords = {}
            for entry in medical_history_data:
                title = entry.get('title', '').lower()
                description = entry.get('description', '').lower()
                
                # Simple keyword extraction
                words = (title + ' ' + description).split()
                for word in words:
                    if len(word) > 3:  # Filter out short words
                        condition_keywords[word] = condition_keywords.get(word, 0) + 1
            
            # Get top keywords
            top_keywords = sorted(condition_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'total_medical_entries': total_entries,
                'chronic_conditions_count': len(chronic_conditions),
                'acute_conditions_count': len(acute_conditions),
                'chronic_percentage': (len(chronic_conditions) / total_entries * 100) if total_entries > 0 else 0,
                'recent_entries_last_year': len(recent_entries),
                'average_entries_per_year': self._calculate_avg_entries_per_year(medical_history_data),
                'top_condition_keywords': dict(top_keywords),
                'oldest_entry_date': min(entry['date_occurred'] for entry in medical_history_data if entry.get('date_occurred')),
                'newest_entry_date': max(entry['date_occurred'] for entry in medical_history_data if entry.get('date_occurred')),
                'medical_complexity_score': self._calculate_medical_complexity(medical_history_data)
            }
            
        except Exception as e:
            logger.error(f"Error calculating medical history statistics: {str(e)}")
            return self._empty_medical_stats()
    
    def _analyze_condition_patterns(self, medical_history_data: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns in medical conditions"""
        try:
            if not medical_history_data:
                return {'condition_categories': {}, 'temporal_patterns': {}, 'severity_patterns': {}}
            
            # Categorize conditions by common medical categories
            condition_categories = {
                'cardiovascular': ['heart', 'cardiac', 'blood pressure', 'hypertension', 'cholesterol'],
                'respiratory': ['lung', 'asthma', 'pneumonia', 'bronchitis', 'breathing'],
                'musculoskeletal': ['bone', 'joint', 'muscle', 'arthritis', 'fracture', 'back', 'spine'],
                'neurological': ['brain', 'nerve', 'headache', 'migraine', 'seizure', 'stroke'],
                'endocrine': ['diabetes', 'thyroid', 'hormone', 'insulin', 'metabolic'],
                'gastrointestinal': ['stomach', 'intestine', 'digestive', 'liver', 'bowel'],
                'mental_health': ['depression', 'anxiety', 'mental', 'psychiatric', 'mood']
            }
            
            category_counts = {category: 0 for category in condition_categories.keys()}
            
            for entry in medical_history_data:
                title = entry.get('title', '').lower()
                description = entry.get('description', '').lower()
                text = title + ' ' + description
                
                for category, keywords in condition_categories.items():
                    if any(keyword in text for keyword in keywords):
                        category_counts[category] += 1
            
            # Temporal patterns
            chronic_over_time = {}
            acute_over_time = {}
            
            for entry in medical_history_data:
                if entry.get('date_occurred'):
                    year = entry['date_occurred'].year
                    if entry.get('is_chronic'):
                        chronic_over_time[year] = chronic_over_time.get(year, 0) + 1
                    else:
                        acute_over_time[year] = acute_over_time.get(year, 0) + 1
            
            return {
                'condition_categories': category_counts,
                'temporal_patterns': {
                    'chronic_conditions_by_year': chronic_over_time,
                    'acute_conditions_by_year': acute_over_time,
                    'total_years_with_entries': len(set(chronic_over_time.keys()) | set(acute_over_time.keys()))
                },
                'severity_patterns': {
                    'chronic_condition_burden': len([e for e in medical_history_data if e.get('is_chronic')]),
                    'condition_recurrence': self._analyze_condition_recurrence(medical_history_data),
                    'most_affected_system': max(category_counts.items(), key=lambda x: x[1])[0] if any(category_counts.values()) else 'No clear pattern'
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing condition patterns: {str(e)}")
            return {'condition_categories': {}, 'temporal_patterns': {}, 'severity_patterns': {}}
    
    def _assess_risk_indicators(self, health_metrics_data: List[Dict], medical_history_data: List[Dict]) -> Dict[str, Any]:
        """Assess risk indicators based on health data"""
        try:
            risk_factors = {
                'cardiovascular_risk': 0,
                'metabolic_risk': 0,
                'chronic_disease_risk': 0,
                'overall_risk_score': 0
            }
            
            risk_details = {
                'blood_pressure_concerns': [],
                'weight_concerns': [],
                'heart_rate_concerns': [],
                'medical_history_concerns': []
            }
            
            # Analyze health metrics for risk factors
            metrics_by_type = {}
            for metric in health_metrics_data:
                metric_type = metric.get('metric_type')
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric)
            
            # Blood pressure risk assessment
            if 'blood_pressure' in metrics_by_type:
                bp_risk = self._assess_blood_pressure_risk(metrics_by_type['blood_pressure'])
                risk_factors['cardiovascular_risk'] += bp_risk['risk_score']
                risk_details['blood_pressure_concerns'] = bp_risk['concerns']
            
            # Weight risk assessment
            if 'weight' in metrics_by_type:
                weight_risk = self._assess_weight_risk(metrics_by_type['weight'])
                risk_factors['metabolic_risk'] += weight_risk['risk_score']
                risk_details['weight_concerns'] = weight_risk['concerns']
            
            # Heart rate risk assessment
            if 'heart_rate' in metrics_by_type:
                hr_risk = self._assess_heart_rate_risk(metrics_by_type['heart_rate'])
                risk_factors['cardiovascular_risk'] += hr_risk['risk_score']
                risk_details['heart_rate_concerns'] = hr_risk['concerns']
            
            # Medical history risk assessment
            history_risk = self._assess_medical_history_risk(medical_history_data)
            risk_factors['chronic_disease_risk'] = history_risk['risk_score']
            risk_details['medical_history_concerns'] = history_risk['concerns']
            
            # Calculate overall risk score
            overall_risk = (
                risk_factors['cardiovascular_risk'] + 
                risk_factors['metabolic_risk'] + 
                risk_factors['chronic_disease_risk']
            ) / 3
            
            risk_factors['overall_risk_score'] = round(overall_risk, 2)
            
            return {
                'risk_factors': risk_factors,
                'risk_details': risk_details,
                'risk_level': self._categorize_risk_level(overall_risk),
                'recommendations': self._generate_risk_recommendations(risk_factors, risk_details)
            }
            
        except Exception as e:
            logger.error(f"Error assessing risk indicators: {str(e)}")
            return {'risk_factors': {}, 'risk_details': {}, 'risk_level': 'unknown', 'recommendations': []}
    
    def _analyze_health_patterns(self, health_metrics_data: List[Dict], medical_history_data: List[Dict]) -> Dict[str, Any]:
        """Analyze overall health patterns and correlations"""
        try:
            patterns = {
                'measurement_patterns': {},
                'correlation_analysis': {},
                'health_trajectory': {},
                'predictive_indicators': {}
            }
            
            # Measurement patterns
            if health_metrics_data:
                patterns['measurement_patterns'] = {
                    'measurement_frequency': self._analyze_measurement_frequency(health_metrics_data),
                    'measurement_consistency': self._calculate_measurement_consistency(health_metrics_data),
                    'measurement_gaps': self._identify_measurement_gaps(health_metrics_data)
                }
            
            # Health trajectory
            patterns['health_trajectory'] = {
                'improvement_indicators': self._identify_improvement_indicators(health_metrics_data),
                'decline_indicators': self._identify_decline_indicators(health_metrics_data),
                'stability_indicators': self._identify_stability_indicators(health_metrics_data)
            }
            
            # Correlation analysis between different metrics
            if len(health_metrics_data) > 10:  # Need sufficient data for correlation
                patterns['correlation_analysis'] = self._analyze_metric_correlations(health_metrics_data)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing health patterns: {str(e)}")
            return {'measurement_patterns': {}, 'correlation_analysis': {}, 'health_trajectory': {}, 'predictive_indicators': {}}
    
    def _analyze_temporal_patterns(self, health_metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal patterns in health measurements"""
        try:
            if not health_metrics_data:
                return {'daily_patterns': {}, 'weekly_patterns': {}, 'monthly_patterns': {}}
            
            # Analyze measurement timing patterns
            hourly_measurements = {}
            daily_measurements = {}
            monthly_measurements = {}
            
            for metric in health_metrics_data:
                timestamp = metric.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    hour = timestamp.hour
                    day = timestamp.strftime('%A')
                    month = timestamp.strftime('%Y-%m')
                    
                    hourly_measurements[hour] = hourly_measurements.get(hour, 0) + 1
                    daily_measurements[day] = daily_measurements.get(day, 0) + 1
                    monthly_measurements[month] = monthly_measurements.get(month, 0) + 1
            
            # Find patterns
            peak_measurement_hour = max(hourly_measurements.items(), key=lambda x: x[1]) if hourly_measurements else (0, 0)
            peak_measurement_day = max(daily_measurements.items(), key=lambda x: x[1]) if daily_measurements else ('Unknown', 0)
            
            return {
                'daily_patterns': {
                    'hourly_distribution': hourly_measurements,
                    'peak_measurement_hour': peak_measurement_hour[0],
                    'peak_hour_count': peak_measurement_hour[1]
                },
                'weekly_patterns': {
                    'daily_distribution': daily_measurements,
                    'peak_measurement_day': peak_measurement_day[0],
                    'peak_day_count': peak_measurement_day[1]
                },
                'monthly_patterns': {
                    'monthly_distribution': monthly_measurements,
                    'active_months': len(monthly_measurements),
                    'most_active_month': max(monthly_measurements.items(), key=lambda x: x[1])[0] if monthly_measurements else 'No data'
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {'daily_patterns': {}, 'weekly_patterns': {}, 'monthly_patterns': {}}
    
    def _calculate_compliance_metrics(self, health_metrics_data: List[Dict], days_back: int) -> Dict[str, Any]:
        """Calculate compliance and adherence metrics"""
        try:
            if not health_metrics_data:
                return {'measurement_compliance': 0, 'consistency_score': 0, 'adherence_patterns': {}}
            
            # Calculate expected vs actual measurements
            # Assume recommended measurement frequency (this could be configurable)
            recommended_frequency = {
                'blood_pressure': 3,  # per week
                'weight': 1,  # per week  
                'heart_rate': 2   # per week
            }
            
            weeks_in_period = days_back / 7
            compliance_by_type = {}
            
            metrics_by_type = {}
            for metric in health_metrics_data:
                metric_type = metric.get('metric_type')
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric)
            
            for metric_type, metrics in metrics_by_type.items():
                if metric_type in recommended_frequency:
                    expected_measurements = recommended_frequency[metric_type] * weeks_in_period
                    actual_measurements = len(metrics)
                    compliance_rate = min(1.0, actual_measurements / expected_measurements) if expected_measurements > 0 else 0
                    
                    compliance_by_type[metric_type] = {
                        'expected': int(expected_measurements),
                        'actual': actual_measurements,
                        'compliance_rate': round(compliance_rate, 2),
                        'compliance_percentage': round(compliance_rate * 100, 1)
                    }
            
            # Overall compliance score
            overall_compliance = sum(comp['compliance_rate'] for comp in compliance_by_type.values()) / len(compliance_by_type) if compliance_by_type else 0
            
            # Consistency analysis
            consistency_score = self._calculate_measurement_consistency(health_metrics_data)
            
            return {
                'measurement_compliance': round(overall_compliance, 2),
                'consistency_score': consistency_score,
                'adherence_patterns': compliance_by_type,
                'compliance_level': self._categorize_compliance_level(overall_compliance),
                'improvement_suggestions': self._generate_compliance_suggestions(compliance_by_type)
            }
            
        except Exception as e:
            logger.error(f"Error calculating compliance metrics: {str(e)}")
            return {'measurement_compliance': 0, 'consistency_score': 0, 'adherence_patterns': {}}
    
    # Helper methods
    def _calculate_simple_trend(self, values: List[float]) -> str:
        """Calculate simple trend direction"""
        if len(values) < 2:
            return 'insufficient_data'
        
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg * 1.05:
            return 'increasing'
        elif second_avg < first_avg * 0.95:
            return 'decreasing'
        else:
            return 'stable'
    
    def _assess_bp_risk_level(self, systolic: float, diastolic: float) -> str:
        """Assess blood pressure risk level"""
        if systolic >= 140 or diastolic >= 90:
            return 'high'
        elif systolic >= 120 or diastolic >= 80:
            return 'elevated'
        else:
            return 'normal'
    
    def _calculate_weight_stability(self, weights: List[float]) -> float:
        """Calculate weight stability score (0-1, higher is more stable)"""
        if len(weights) < 2:
            return 1.0
        
        weight_range = max(weights) - min(weights)
        avg_weight = sum(weights) / len(weights)
        
        # Stability is inversely related to the range relative to average weight
        stability = 1.0 - min(1.0, weight_range / (avg_weight * 0.1))  # 10% range threshold
        return round(stability, 2)
    
    def _calculate_hr_variability(self, hr_values: List[float]) -> float:
        """Calculate heart rate variability score"""
        if len(hr_values) < 2:
            return 0.0
        
        differences = [abs(hr_values[i] - hr_values[i-1]) for i in range(1, len(hr_values))]
        avg_difference = sum(differences) / len(differences)
        
        # Normalize to 0-1 scale (higher values indicate more variability)
        variability = min(1.0, avg_difference / 20.0)  # 20 bpm as reference
        return round(variability, 2)
    
    def _calculate_measurement_consistency(self, health_metrics_data: List[Dict]) -> float:
        """Calculate how consistently measurements are taken"""
        if len(health_metrics_data) < 2:
            return 0.0
        
        # Calculate time intervals between measurements
        timestamps = []
        for metric in health_metrics_data:
            timestamp = metric.get('timestamp')
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamps.append(timestamp)
        
        timestamps.sort()
        intervals = [(timestamps[i] - timestamps[i-1]).days for i in range(1, len(timestamps))]
        
        if not intervals:
            return 0.0
        
        # Calculate consistency based on interval variance
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((interval - avg_interval) ** 2 for interval in intervals) / len(intervals)
        
        # Convert to 0-1 scale (lower variance = higher consistency)
        consistency = 1.0 / (1.0 + variance / 10.0)  # Normalize with factor of 10
        return round(consistency, 2)
    
    def _calculate_data_quality_score(self, health_metrics_data: List[Dict]) -> float:
        """Calculate overall data quality score"""
        if not health_metrics_data:
            return 0.0
        
        quality_factors = []
        
        # Completeness (presence of values)
        complete_entries = sum(1 for metric in health_metrics_data if metric.get('value'))
        completeness = complete_entries / len(health_metrics_data)
        quality_factors.append(completeness)
        
        # Consistency (measurement frequency)
        consistency = self._calculate_measurement_consistency(health_metrics_data)
        quality_factors.append(consistency)
        
        # Recency (how recent are the measurements)
        now = timezone.now()
        recent_measurements = [
            metric for metric in health_metrics_data 
            if metric.get('timestamp') and 
            (now - (metric['timestamp'] if isinstance(metric['timestamp'], datetime) 
                   else datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00')))).days <= 30
        ]
        recency = len(recent_measurements) / len(health_metrics_data)
        quality_factors.append(recency)
        
        overall_quality = sum(quality_factors) / len(quality_factors)
        return round(overall_quality, 2)
    
    def _create_empty_snapshot(self) -> MedicalHealthDataSnapshot:
        """Create an empty snapshot for error cases"""
        return MedicalHealthDataSnapshot(
            total_health_metrics=0,
            total_medical_history_entries=0,
            metric_types_tracked=[],
            health_metrics_statistics=self._empty_health_stats(),
            metric_trends={'overall_trends': {}, 'metric_specific_trends': {}, 'trend_analysis': {}},
            medical_history_statistics=self._empty_medical_stats(),
            condition_patterns={'condition_categories': {}, 'temporal_patterns': {}, 'severity_patterns': {}},
            risk_indicators={'risk_factors': {}, 'risk_details': {}, 'risk_level': 'unknown', 'recommendations': []},
            health_patterns={'measurement_patterns': {}, 'correlation_analysis': {}, 'health_trajectory': {}, 'predictive_indicators': {}},
            temporal_patterns={'daily_patterns': {}, 'weekly_patterns': {}, 'monthly_patterns': {}},
            compliance_metrics={'measurement_compliance': 0, 'consistency_score': 0, 'adherence_patterns': {}},
            performance_metrics={'processing_time_seconds': 0, 'health_metrics_processed': 0, 'medical_history_entries_processed': 0, 'timestamp': timezone.now().isoformat()},
            timestamp=timezone.now()
        )
    
    def _empty_health_stats(self) -> Dict[str, Any]:
        """Return empty health statistics"""
        return {
            'total_metrics_recorded': 0,
            'unique_metric_types': 0,
            'metrics_by_type': {},
            'most_tracked_metric': 'No data',
            'most_tracked_metric_count': 0,
            'type_specific_analysis': {},
            'recent_measurements_7_days': 0,
            'measurement_consistency': 0,
            'data_quality_score': 0
        }
    
    def _empty_medical_stats(self) -> Dict[str, Any]:
        """Return empty medical statistics"""
        return {
            'total_medical_entries': 0,
            'chronic_conditions_count': 0,
            'acute_conditions_count': 0,
            'chronic_percentage': 0,
            'recent_entries_last_year': 0,
            'average_entries_per_year': 0,
            'top_condition_keywords': {},
            'oldest_entry_date': None,
            'newest_entry_date': None,
            'medical_complexity_score': 0
        }
    
    # Additional helper methods would be implemented here for:
    # - _calculate_detailed_trend
    # - _analyze_measurement_frequency  
    # - _assess_overall_trend
    # - _analyze_data_consistency_trend
    # - _calculate_trend_reliability
    # - _calculate_avg_entries_per_year
    # - _calculate_medical_complexity
    # - _analyze_condition_recurrence
    # - _assess_blood_pressure_risk
    # - _assess_weight_risk
    # - _assess_heart_rate_risk
    # - _assess_medical_history_risk
    # - _categorize_risk_level
    # - _generate_risk_recommendations
    # - _identify_improvement_indicators
    # - _identify_decline_indicators
    # - _identify_stability_indicators
    # - _analyze_metric_correlations
    # - _identify_measurement_gaps
    # - _categorize_compliance_level
    # - _generate_compliance_suggestions
    
    # These would be implemented with similar patterns to the existing methods
