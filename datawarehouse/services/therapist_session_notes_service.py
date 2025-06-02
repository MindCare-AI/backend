# datawarehouse/services/therapist_session_notes_service.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db.models import Count, Avg, Q
import logging
import numpy as np
import time
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)


@dataclass
class TherapistSessionNotesDataSnapshot:
    """Data snapshot for therapist session notes analytics"""
    
    # Basic metrics
    total_sessions: int
    total_notes: int
    total_patients: int
    active_patients: int
    
    # Session statistics
    session_frequency_stats: Dict[str, Any]
    session_duration_analysis: Dict[str, Any]
    appointment_completion_stats: Dict[str, Any]
    
    # Notes analysis
    notes_quality_metrics: Dict[str, Any]
    therapeutic_content_analysis: Dict[str, Any]
    progress_tracking_metrics: Dict[str, Any]
    
    # Patient care patterns
    patient_engagement_patterns: Dict[str, Any]
    therapeutic_approaches: Dict[str, Any]
    session_outcomes: Dict[str, Any]
    
    # Temporal patterns
    temporal_patterns: Dict[str, Any]
    workload_analysis: Dict[str, Any]
    consistency_metrics: Dict[str, Any]
    
    # Performance metrics
    analysis_timestamp: datetime
    data_quality_score: float
    cache_performance: Dict[str, Any]


class TherapistSessionNotesCollectionService:
    """Service for collecting and analyzing therapist session notes data"""

    def __init__(self):
        self.cache_timeout = 900  # 15 minutes
        self.performance_metrics = {}

    def collect_therapist_session_data(self, user=None, days: int = 30) -> TherapistSessionNotesDataSnapshot:
        """
        Main entry point for collecting therapist session notes data
        
        Args:
            user: Specific user (therapist) to analyze, if None analyze all therapists
            days: Number of days to look back for analysis
            
        Returns:
            TherapistSessionNotesDataSnapshot with comprehensive session analytics
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting therapist session notes data collection for {days} days")
            
            # Collect raw data
            raw_data = self._collect_raw_session_data(user, days)
            
            # Calculate comprehensive statistics
            session_stats = self._calculate_session_statistics(raw_data)
            notes_analysis = self._analyze_notes_content(raw_data)
            patient_patterns = self._analyze_patient_care_patterns(raw_data)
            temporal_patterns = self._analyze_temporal_patterns(raw_data)
            performance_metrics = self._calculate_performance_metrics(raw_data)
            
            # Create snapshot
            snapshot = TherapistSessionNotesDataSnapshot(
                total_sessions=session_stats['total_sessions'],
                total_notes=session_stats['total_notes'],
                total_patients=session_stats['total_patients'],
                active_patients=session_stats['active_patients'],
                session_frequency_stats=session_stats['frequency_stats'],
                session_duration_analysis=session_stats['duration_analysis'],
                appointment_completion_stats=session_stats['completion_stats'],
                notes_quality_metrics=notes_analysis['quality_metrics'],
                therapeutic_content_analysis=notes_analysis['content_analysis'],
                progress_tracking_metrics=notes_analysis['progress_tracking'],
                patient_engagement_patterns=patient_patterns['engagement_patterns'],
                therapeutic_approaches=patient_patterns['therapeutic_approaches'],
                session_outcomes=patient_patterns['session_outcomes'],
                temporal_patterns=temporal_patterns['patterns'],
                workload_analysis=temporal_patterns['workload_analysis'],
                consistency_metrics=temporal_patterns['consistency_metrics'],
                analysis_timestamp=timezone.now(),
                data_quality_score=self._calculate_data_quality_score(raw_data),
                cache_performance={
                    'collection_time': time.time() - start_time,
                    'data_points_processed': len(raw_data.get('session_notes', [])),
                    'cache_hits': 0,
                    'cache_misses': 1
                }
            )
            
            logger.info(f"Therapist session notes data collection completed in {time.time() - start_time:.2f}s")
            return snapshot
            
        except Exception as e:
            logger.error(f"Error in therapist session notes data collection: {str(e)}")
            raise

    def _collect_raw_session_data(self, user, days: int) -> Dict[str, Any]:
        """Collect raw session notes and appointment data"""
        try:
            from therapist.models.session_note import SessionNote
            from appointments.models import Appointment
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Build query filters
            session_filter = Q(timestamp__range=(start_date, end_date))
            appointment_filter = Q(appointment_date__range=(start_date, end_date))
            
            if user and hasattr(user, 'user_type') and user.user_type == 'therapist':
                session_filter &= Q(therapist=user)
                appointment_filter &= Q(therapist__user=user)
            
            # Collect session notes
            session_notes = SessionNote.objects.filter(session_filter).select_related(
                'therapist', 'patient', 'appointment'
            ).order_by('session_date')
            
            # Collect appointments
            appointments = Appointment.objects.filter(appointment_filter).select_related(
                'therapist', 'patient'
            ).order_by('appointment_date')
            
            return {
                'session_notes': list(session_notes),
                'appointments': list(appointments),
                'start_date': start_date,
                'end_date': end_date,
                'target_user': user
            }
            
        except Exception as e:
            logger.error(f"Error collecting raw session data: {str(e)}")
            return {}

    def _calculate_session_statistics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive session statistics"""
        try:
            session_notes = raw_data.get('session_notes', [])
            appointments = raw_data.get('appointments', [])
            
            # Basic counts
            total_sessions = len(session_notes)
            total_notes = len(session_notes)
            unique_patients = set()
            unique_therapists = set()
            
            for note in session_notes:
                if hasattr(note, 'patient'):
                    unique_patients.add(note.patient.id)
                if hasattr(note, 'therapist'):
                    unique_therapists.add(note.therapist.id)
            
            # Calculate session frequency per patient
            patient_session_counts = Counter()
            for note in session_notes:
                if hasattr(note, 'patient'):
                    patient_session_counts[note.patient.id] += 1
            
            # Appointment completion analysis
            completed_appointments = sum(1 for apt in appointments if apt.status == 'completed')
            total_appointments = len(appointments)
            completion_rate = completed_appointments / max(1, total_appointments)
            
            # Session frequency analysis
            frequency_stats = {
                'avg_sessions_per_patient': np.mean(list(patient_session_counts.values())) if patient_session_counts else 0,
                'median_sessions_per_patient': np.median(list(patient_session_counts.values())) if patient_session_counts else 0,
                'max_sessions_per_patient': max(patient_session_counts.values()) if patient_session_counts else 0,
                'min_sessions_per_patient': min(patient_session_counts.values()) if patient_session_counts else 0,
                'patients_with_multiple_sessions': sum(1 for count in patient_session_counts.values() if count > 1)
            }
            
            # Duration analysis (if appointment data available)
            duration_stats = self._analyze_session_durations(appointments)
            
            return {
                'total_sessions': total_sessions,
                'total_notes': total_notes,
                'total_patients': len(unique_patients),
                'active_patients': len(patient_session_counts),
                'total_therapists': len(unique_therapists),
                'frequency_stats': frequency_stats,
                'duration_analysis': duration_stats,
                'completion_stats': {
                    'completion_rate': completion_rate,
                    'completed_appointments': completed_appointments,
                    'total_appointments': total_appointments,
                    'cancelled_appointments': sum(1 for apt in appointments if apt.status == 'cancelled'),
                    'missed_appointments': sum(1 for apt in appointments if apt.status == 'missed')
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating session statistics: {str(e)}")
            return {}

    def _analyze_session_durations(self, appointments: List) -> Dict[str, Any]:
        """Analyze session duration patterns"""
        try:
            durations = []
            for apt in appointments:
                if hasattr(apt, 'duration') and apt.duration:
                    durations.append(apt.duration.total_seconds() / 60)  # Convert to minutes
            
            if not durations:
                return {'avg_duration': 0, 'median_duration': 0, 'duration_variance': 0}
            
            return {
                'avg_duration': np.mean(durations),
                'median_duration': np.median(durations),
                'std_duration': np.std(durations),
                'duration_variance': np.var(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'total_durations_analyzed': len(durations)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing session durations: {str(e)}")
            return {}

    def _analyze_notes_content(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the content and quality of session notes"""
        try:
            session_notes = raw_data.get('session_notes', [])
            
            if not session_notes:
                return {'quality_metrics': {}, 'content_analysis': {}, 'progress_tracking': {}}
            
            # Quality metrics
            note_lengths = [len(note.notes) for note in session_notes if hasattr(note, 'notes')]
            quality_metrics = {
                'avg_note_length': np.mean(note_lengths) if note_lengths else 0,
                'median_note_length': np.median(note_lengths) if note_lengths else 0,
                'std_note_length': np.std(note_lengths) if note_lengths else 0,
                'total_notes_analyzed': len(note_lengths),
                'very_short_notes': sum(1 for length in note_lengths if length < 50),
                'comprehensive_notes': sum(1 for length in note_lengths if length > 500)
            }
            
            # Content analysis
            content_analysis = self._analyze_therapeutic_content(session_notes)
            
            # Progress tracking metrics
            progress_tracking = self._analyze_progress_tracking(session_notes)
            
            return {
                'quality_metrics': quality_metrics,
                'content_analysis': content_analysis,
                'progress_tracking': progress_tracking
            }
            
        except Exception as e:
            logger.error(f"Error analyzing notes content: {str(e)}")
            return {}

    def _analyze_therapeutic_content(self, session_notes: List) -> Dict[str, Any]:
        """Analyze therapeutic content and approaches in notes"""
        try:
            therapeutic_keywords = {
                'cbt': [r'\bcbt\b', r'cognitive.*behavior', r'thought.*record', r'behavioral.*activation'],
                'dbt': [r'\bdbt\b', r'dialectical.*behavior', r'mindfulness', r'distress.*tolerance'],
                'psychodynamic': [r'psychodynamic', r'transference', r'unconscious', r'defense.*mechanism'],
                'humanistic': [r'humanistic', r'person.*centered', r'unconditional.*positive.*regard'],
                'solution_focused': [r'solution.*focused', r'goal.*setting', r'scaling.*question'],
                'trauma': [r'trauma', r'ptsd', r'emdr', r'exposure.*therapy'],
                'family_therapy': [r'family.*therapy', r'systemic', r'family.*dynamic'],
                'group_therapy': [r'group.*therapy', r'group.*dynamic', r'peer.*support']
            }
            
            emotion_keywords = {
                'anxiety': [r'anxiety', r'anxious', r'worry', r'panic', r'nervous'],
                'depression': [r'depression', r'depressed', r'sad', r'hopeless', r'mood'],
                'anger': [r'anger', r'angry', r'rage', r'irritated', r'frustrated'],
                'grief': [r'grief', r'loss', r'bereaved', r'mourning'],
                'stress': [r'stress', r'stressed', r'overwhelmed', r'pressure']
            }
            
            progress_indicators = {
                'improvement': [r'improvement', r'better', r'progress', r'positive.*change'],
                'setback': [r'setback', r'regression', r'worse', r'decline'],
                'stable': [r'stable', r'maintaining', r'consistent', r'steady'],
                'breakthrough': [r'breakthrough', r'insight', r'realization', r'aha.*moment']
            }
            
            # Count keyword occurrences
            therapeutic_counts = defaultdict(int)
            emotion_counts = defaultdict(int)
            progress_counts = defaultdict(int)
            
            for note in session_notes:
                if hasattr(note, 'notes'):
                    note_text = note.notes.lower()
                    
                    # Count therapeutic approaches
                    for approach, patterns in therapeutic_keywords.items():
                        for pattern in patterns:
                            if re.search(pattern, note_text):
                                therapeutic_counts[approach] += 1
                    
                    # Count emotions discussed
                    for emotion, patterns in emotion_keywords.items():
                        for pattern in patterns:
                            if re.search(pattern, note_text):
                                emotion_counts[emotion] += 1
                    
                    # Count progress indicators
                    for indicator, patterns in progress_indicators.items():
                        for pattern in patterns:
                            if re.search(pattern, note_text):
                                progress_counts[indicator] += 1
            
            return {
                'therapeutic_approaches': dict(therapeutic_counts),
                'emotions_discussed': dict(emotion_counts),
                'progress_indicators': dict(progress_counts),
                'most_common_approach': max(therapeutic_counts.items(), key=lambda x: x[1])[0] if therapeutic_counts else None,
                'most_discussed_emotion': max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else None,
                'overall_progress_trend': max(progress_counts.items(), key=lambda x: x[1])[0] if progress_counts else None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing therapeutic content: {str(e)}")
            return {}

    def _analyze_progress_tracking(self, session_notes: List) -> Dict[str, Any]:
        """Analyze how well progress is being tracked across sessions"""
        try:
            # Group notes by patient
            patient_notes = defaultdict(list)
            for note in session_notes:
                if hasattr(note, 'patient') and hasattr(note, 'session_date'):
                    patient_notes[note.patient.id].append(note)
            
            # Sort notes by date for each patient
            for patient_id in patient_notes:
                patient_notes[patient_id].sort(key=lambda x: x.session_date or x.timestamp)
            
            # Analyze continuity and progress tracking
            continuity_scores = []
            goal_tracking_scores = []
            
            for patient_id, notes in patient_notes.items():
                if len(notes) > 1:
                    # Calculate continuity (how often previous sessions are referenced)
                    continuity_score = self._calculate_continuity_score(notes)
                    continuity_scores.append(continuity_score)
                    
                    # Calculate goal tracking (how often goals/progress is mentioned)
                    goal_score = self._calculate_goal_tracking_score(notes)
                    goal_tracking_scores.append(goal_score)
            
            return {
                'avg_continuity_score': np.mean(continuity_scores) if continuity_scores else 0,
                'avg_goal_tracking_score': np.mean(goal_tracking_scores) if goal_tracking_scores else 0,
                'patients_with_multiple_sessions': len(continuity_scores),
                'excellent_tracking': sum(1 for score in goal_tracking_scores if score > 0.7),
                'poor_tracking': sum(1 for score in goal_tracking_scores if score < 0.3)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing progress tracking: {str(e)}")
            return {}

    def _calculate_continuity_score(self, notes: List) -> float:
        """Calculate how well sessions reference previous sessions"""
        try:
            continuity_indicators = [
                r'last.*session', r'previous.*session', r'since.*last.*time',
                r'continued.*from', r'follow.*up', r'building.*on', r'as.*discussed'
            ]
            
            continuity_mentions = 0
            total_notes = len(notes)
            
            # Skip first note as it has no previous session to reference
            for note in notes[1:]:
                if hasattr(note, 'notes'):
                    note_text = note.notes.lower()
                    for pattern in continuity_indicators:
                        if re.search(pattern, note_text):
                            continuity_mentions += 1
                            break  # Count each note only once
            
            return continuity_mentions / max(1, total_notes - 1)
            
        except Exception as e:
            logger.error(f"Error calculating continuity score: {str(e)}")
            return 0.0

    def _calculate_goal_tracking_score(self, notes: List) -> float:
        """Calculate how well goals and progress are tracked"""
        try:
            goal_indicators = [
                r'goal', r'objective', r'target', r'aim', r'progress',
                r'improvement', r'achievement', r'milestone', r'outcome'
            ]
            
            goal_mentions = 0
            total_notes = len(notes)
            
            for note in notes:
                if hasattr(note, 'notes'):
                    note_text = note.notes.lower()
                    for pattern in goal_indicators:
                        if re.search(pattern, note_text):
                            goal_mentions += 1
                            break  # Count each note only once
            
            return goal_mentions / max(1, total_notes)
            
        except Exception as e:
            logger.error(f"Error calculating goal tracking score: {str(e)}")
            return 0.0

    def _analyze_patient_care_patterns(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze patterns in patient care and engagement"""
        try:
            session_notes = raw_data.get('session_notes', [])
            appointments = raw_data.get('appointments', [])
            
            # Group data by patient
            patient_data = defaultdict(lambda: {'notes': [], 'appointments': []})
            
            for note in session_notes:
                if hasattr(note, 'patient'):
                    patient_data[note.patient.id]['notes'].append(note)
            
            for apt in appointments:
                if hasattr(apt, 'patient'):
                    patient_data[apt.patient.id]['appointments'].append(apt)
            
            # Analyze engagement patterns
            engagement_patterns = self._analyze_engagement_patterns(patient_data)
            
            # Analyze therapeutic approaches per patient
            therapeutic_approaches = self._analyze_patient_therapeutic_approaches(patient_data)
            
            # Analyze session outcomes
            session_outcomes = self._analyze_session_outcomes(patient_data)
            
            return {
                'engagement_patterns': engagement_patterns,
                'therapeutic_approaches': therapeutic_approaches,
                'session_outcomes': session_outcomes
            }
            
        except Exception as e:
            logger.error(f"Error analyzing patient care patterns: {str(e)}")
            return {}

    def _analyze_engagement_patterns(self, patient_data: Dict) -> Dict[str, Any]:
        """Analyze patient engagement patterns"""
        try:
            high_engagement = 0
            medium_engagement = 0
            low_engagement = 0
            
            for patient_id, data in patient_data.items():
                notes = data['notes']
                appointments = data['appointments']
                
                # Calculate engagement score based on session frequency and note quality
                session_count = len(notes)
                avg_note_length = np.mean([len(note.notes) for note in notes if hasattr(note, 'notes')]) if notes else 0
                
                # Attendance rate
                completed_apts = sum(1 for apt in appointments if apt.status == 'completed')
                total_apts = len(appointments)
                attendance_rate = completed_apts / max(1, total_apts)
                
                # Engagement score calculation
                engagement_score = (
                    (session_count / 10) * 0.4 +  # Session frequency (normalized to 10)
                    (avg_note_length / 500) * 0.3 +  # Note quality (normalized to 500 chars)
                    attendance_rate * 0.3  # Attendance rate
                )
                
                if engagement_score > 0.7:
                    high_engagement += 1
                elif engagement_score > 0.4:
                    medium_engagement += 1
                else:
                    low_engagement += 1
            
            total_patients = len(patient_data)
            
            return {
                'high_engagement_patients': high_engagement,
                'medium_engagement_patients': medium_engagement,
                'low_engagement_patients': low_engagement,
                'high_engagement_percentage': (high_engagement / max(1, total_patients)) * 100,
                'medium_engagement_percentage': (medium_engagement / max(1, total_patients)) * 100,
                'low_engagement_percentage': (low_engagement / max(1, total_patients)) * 100,
                'total_patients_analyzed': total_patients
            }
            
        except Exception as e:
            logger.error(f"Error analyzing engagement patterns: {str(e)}")
            return {}

    def _analyze_patient_therapeutic_approaches(self, patient_data: Dict) -> Dict[str, Any]:
        """Analyze therapeutic approaches used for different patients"""
        try:
            approach_usage = defaultdict(int)
            patient_approach_diversity = []
            
            for patient_id, data in patient_data.items():
                notes = data['notes']
                patient_approaches = set()
                
                for note in notes:
                    if hasattr(note, 'notes'):
                        note_text = note.notes.lower()
                        
                        # Check for different therapeutic approaches
                        if re.search(r'\bcbt\b|cognitive.*behavior', note_text):
                            patient_approaches.add('CBT')
                        if re.search(r'\bdbt\b|dialectical.*behavior', note_text):
                            patient_approaches.add('DBT')
                        if re.search(r'psychodynamic', note_text):
                            patient_approaches.add('Psychodynamic')
                        if re.search(r'humanistic|person.*centered', note_text):
                            patient_approaches.add('Humanistic')
                        if re.search(r'solution.*focused', note_text):
                            patient_approaches.add('Solution-Focused')
                
                # Count approach usage
                for approach in patient_approaches:
                    approach_usage[approach] += 1
                
                # Track diversity of approaches per patient
                patient_approach_diversity.append(len(patient_approaches))
            
            return {
                'approach_usage': dict(approach_usage),
                'avg_approaches_per_patient': np.mean(patient_approach_diversity) if patient_approach_diversity else 0,
                'most_used_approach': max(approach_usage.items(), key=lambda x: x[1])[0] if approach_usage else None,
                'patients_with_multiple_approaches': sum(1 for count in patient_approach_diversity if count > 1),
                'approach_diversity_score': np.std(patient_approach_diversity) if patient_approach_diversity else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing therapeutic approaches: {str(e)}")
            return {}

    def _analyze_session_outcomes(self, patient_data: Dict) -> Dict[str, Any]:
        """Analyze session outcomes and effectiveness"""
        try:
            positive_outcomes = 0
            neutral_outcomes = 0
            concerning_outcomes = 0
            
            outcome_keywords = {
                'positive': [r'progress', r'improvement', r'better', r'breakthrough', r'success'],
                'neutral': [r'stable', r'maintaining', r'consistent', r'status.*quo'],
                'concerning': [r'setback', r'regression', r'worse', r'crisis', r'deterioration']
            }
            
            for patient_id, data in patient_data.items():
                notes = data['notes']
                
                patient_outcome_scores = {'positive': 0, 'neutral': 0, 'concerning': 0}
                
                for note in notes:
                    if hasattr(note, 'notes'):
                        note_text = note.notes.lower()
                        
                        for outcome_type, keywords in outcome_keywords.items():
                            for keyword in keywords:
                                if re.search(keyword, note_text):
                                    patient_outcome_scores[outcome_type] += 1
                
                # Determine overall patient outcome
                max_score_type = max(patient_outcome_scores.items(), key=lambda x: x[1])[0]
                
                if max_score_type == 'positive':
                    positive_outcomes += 1
                elif max_score_type == 'neutral':
                    neutral_outcomes += 1
                else:
                    concerning_outcomes += 1
            
            total_patients = len(patient_data)
            
            return {
                'positive_outcomes': positive_outcomes,
                'neutral_outcomes': neutral_outcomes,
                'concerning_outcomes': concerning_outcomes,
                'positive_outcome_percentage': (positive_outcomes / max(1, total_patients)) * 100,
                'neutral_outcome_percentage': (neutral_outcomes / max(1, total_patients)) * 100,
                'concerning_outcome_percentage': (concerning_outcomes / max(1, total_patients)) * 100,
                'total_patients_analyzed': total_patients
            }
            
        except Exception as e:
            logger.error(f"Error analyzing session outcomes: {str(e)}")
            return {}

    def _analyze_temporal_patterns(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze temporal patterns in session scheduling and notes"""
        try:
            session_notes = raw_data.get('session_notes', [])
            appointments = raw_data.get('appointments', [])
            
            # Analyze session timing patterns
            patterns = self._analyze_session_timing_patterns(session_notes, appointments)
            
            # Analyze workload distribution
            workload_analysis = self._analyze_workload_distribution(session_notes, appointments)
            
            # Analyze consistency metrics
            consistency_metrics = self._analyze_consistency_metrics(session_notes)
            
            return {
                'patterns': patterns,
                'workload_analysis': workload_analysis,
                'consistency_metrics': consistency_metrics
            }
            
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {}

    def _analyze_session_timing_patterns(self, session_notes: List, appointments: List) -> Dict[str, Any]:
        """Analyze when sessions typically occur"""
        try:
            # Analyze session notes timing
            note_hours = []
            note_days = []
            
            for note in session_notes:
                if hasattr(note, 'timestamp'):
                    note_hours.append(note.timestamp.hour)
                    note_days.append(note.timestamp.weekday())
            
            # Analyze appointment timing
            apt_hours = []
            apt_days = []
            
            for apt in appointments:
                if hasattr(apt, 'appointment_date'):
                    apt_hours.append(apt.appointment_date.hour)
                    apt_days.append(apt.appointment_date.weekday())
            
            # Day names for readability
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            return {
                'most_common_note_hour': max(set(note_hours), key=note_hours.count) if note_hours else None,
                'most_common_note_day': day_names[max(set(note_days), key=note_days.count)] if note_days else None,
                'most_common_appointment_hour': max(set(apt_hours), key=apt_hours.count) if apt_hours else None,
                'most_common_appointment_day': day_names[max(set(apt_days), key=apt_days.count)] if apt_days else None,
                'avg_note_hour': np.mean(note_hours) if note_hours else 0,
                'avg_appointment_hour': np.mean(apt_hours) if apt_hours else 0,
                'note_hour_distribution': Counter(note_hours),
                'note_day_distribution': Counter(note_days),
                'appointment_hour_distribution': Counter(apt_hours),
                'appointment_day_distribution': Counter(apt_days)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing session timing patterns: {str(e)}")
            return {}

    def _analyze_workload_distribution(self, session_notes: List, appointments: List) -> Dict[str, Any]:
        """Analyze workload distribution over time"""
        try:
            # Group by date
            daily_notes = defaultdict(int)
            daily_appointments = defaultdict(int)
            
            for note in session_notes:
                if hasattr(note, 'session_date') and note.session_date:
                    daily_notes[note.session_date] += 1
                elif hasattr(note, 'timestamp'):
                    daily_notes[note.timestamp.date()] += 1
            
            for apt in appointments:
                if hasattr(apt, 'appointment_date'):
                    daily_appointments[apt.appointment_date.date()] += 1
            
            # Calculate workload metrics
            daily_note_counts = list(daily_notes.values())
            daily_apt_counts = list(daily_appointments.values())
            
            return {
                'avg_daily_notes': np.mean(daily_note_counts) if daily_note_counts else 0,
                'max_daily_notes': max(daily_note_counts) if daily_note_counts else 0,
                'avg_daily_appointments': np.mean(daily_apt_counts) if daily_apt_counts else 0,
                'max_daily_appointments': max(daily_apt_counts) if daily_apt_counts else 0,
                'workload_variability_notes': np.std(daily_note_counts) if daily_note_counts else 0,
                'workload_variability_appointments': np.std(daily_apt_counts) if daily_apt_counts else 0,
                'high_workload_days': sum(1 for count in daily_note_counts if count > np.mean(daily_note_counts) + np.std(daily_note_counts)) if daily_note_counts else 0,
                'total_working_days': len(set(list(daily_notes.keys()) + list(daily_appointments.keys())))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing workload distribution: {str(e)}")
            return {}

    def _analyze_consistency_metrics(self, session_notes: List) -> Dict[str, Any]:
        """Analyze consistency in note-taking and session scheduling"""
        try:
            # Group by therapist
            therapist_data = defaultdict(list)
            
            for note in session_notes:
                if hasattr(note, 'therapist'):
                    therapist_data[note.therapist.id].append(note)
            
            # Calculate consistency metrics per therapist
            therapist_consistency_scores = []
            note_quality_consistency = []
            
            for therapist_id, notes in therapist_data.items():
                if len(notes) > 1:
                    # Time consistency (how regular are the sessions)
                    dates = [note.session_date or note.timestamp.date() for note in notes if hasattr(note, 'session_date') or hasattr(note, 'timestamp')]
                    if len(dates) > 1:
                        dates.sort()
                        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                        time_consistency = 1 / (1 + np.std(intervals)) if intervals else 0
                        therapist_consistency_scores.append(time_consistency)
                    
                    # Note quality consistency
                    note_lengths = [len(note.notes) for note in notes if hasattr(note, 'notes')]
                    if note_lengths:
                        quality_consistency = 1 / (1 + np.std(note_lengths) / max(1, np.mean(note_lengths)))
                        note_quality_consistency.append(quality_consistency)
            
            return {
                'avg_time_consistency': np.mean(therapist_consistency_scores) if therapist_consistency_scores else 0,
                'avg_quality_consistency': np.mean(note_quality_consistency) if note_quality_consistency else 0,
                'highly_consistent_therapists': sum(1 for score in therapist_consistency_scores if score > 0.7),
                'inconsistent_therapists': sum(1 for score in therapist_consistency_scores if score < 0.3),
                'total_therapists_analyzed': len(therapist_data)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing consistency metrics: {str(e)}")
            return {}

    def _calculate_data_quality_score(self, raw_data: Dict[str, Any]) -> float:
        """Calculate overall data quality score"""
        try:
            session_notes = raw_data.get('session_notes', [])
            appointments = raw_data.get('appointments', [])
            
            if not session_notes:
                return 0.0
            
            # Calculate quality factors
            completeness_score = 0.0
            consistency_score = 0.0
            richness_score = 0.0
            
            # Completeness: How many notes have all required fields
            complete_notes = 0
            for note in session_notes:
                if (hasattr(note, 'notes') and note.notes and 
                    hasattr(note, 'session_date') and note.session_date and
                    hasattr(note, 'patient') and note.patient and
                    hasattr(note, 'therapist') and note.therapist):
                    complete_notes += 1
            
            completeness_score = complete_notes / len(session_notes)
            
            # Consistency: Standard deviation of note lengths (lower is better)
            note_lengths = [len(note.notes) for note in session_notes if hasattr(note, 'notes')]
            if note_lengths:
                cv = np.std(note_lengths) / max(1, np.mean(note_lengths))
                consistency_score = max(0, 1 - cv)
            
            # Richness: Average note length and detail
            avg_length = np.mean(note_lengths) if note_lengths else 0
            richness_score = min(1.0, avg_length / 500)  # Normalize to 500 chars
            
            # Overall quality score
            overall_score = (completeness_score * 0.4 + consistency_score * 0.3 + richness_score * 0.3)
            
            return float(overall_score)
            
        except Exception as e:
            logger.error(f"Error calculating data quality score: {str(e)}")
            return 0.0

    def _calculate_performance_metrics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance metrics for the collection process"""
        try:
            session_notes = raw_data.get('session_notes', [])
            appointments = raw_data.get('appointments', [])
            
            return {
                'total_records_processed': len(session_notes) + len(appointments),
                'session_notes_processed': len(session_notes),
                'appointments_processed': len(appointments),
                'data_date_range': {
                    'start_date': raw_data.get('start_date'),
                    'end_date': raw_data.get('end_date')
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {}
