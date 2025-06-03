# datawarehouse/services/realtime_analytics.py
"""
Real-time Analytics and Streaming Data Processing Service
Provides live data processing and real-time insights for the MindCare platform
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import redis
from django.conf import settings
from django.utils import timezone

from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from journal.models import JournalEntry
from mood.models import MoodLog

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Represents a streaming data event"""
    
    event_type: str
    user_id: int
    timestamp: datetime
    data: Dict[str, Any]
    source: str
    priority: str = "normal"  # low, normal, high, critical


@dataclass
class RealTimeMetrics:
    """Real-time metrics container"""
    
    active_users: int = 0
    events_per_minute: float = 0.0
    avg_mood_score: float = 0.0
    crisis_alerts: int = 0
    system_load: float = 0.0
    last_updated: datetime = field(default_factory=timezone.now)


class StreamProcessor:
    """Processes streaming events with configurable handlers"""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_buffer = deque(maxlen=10000)
        self.metrics_window = timedelta(minutes=5)
        
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for specific event types"""
        self.handlers[event_type].append(handler)
        
    async def process_event(self, event: StreamEvent):
        """Process a single streaming event"""
        try:
            # Add to buffer for metrics
            self.event_buffer.append(event)
            
            # Process with registered handlers
            for handler in self.handlers.get(event.event_type, []):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")
                    
            # Handle high priority events immediately
            if event.priority in ["high", "critical"]:
                await self._handle_priority_event(event)
                
        except Exception as e:
            logger.error(f"Error processing stream event: {e}")
            
    async def _handle_priority_event(self, event: StreamEvent):
        """Handle high-priority events immediately"""
        if event.event_type == "crisis_indicator":
            await self._trigger_crisis_alert(event)
        elif event.event_type == "mood_severe_decline":
            await self._trigger_mood_alert(event)


class RealTimeAnalyticsService:
    """
    Real-time analytics service for live data processing and insights
    
    Features:
    - Live event streaming and processing
    - Real-time dashboard metrics
    - Crisis detection and alerting
    - Live user activity monitoring
    - Performance metrics tracking
    - WebSocket-based live updates
    """
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        )
        self.channel_layer = get_channel_layer()
        self.stream_processor = StreamProcessor()
        self.metrics = RealTimeMetrics()
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup event handlers for different data types"""
        self.stream_processor.register_handler("mood_entry", self._handle_mood_event)
        self.stream_processor.register_handler("journal_entry", self._handle_journal_event)
        self.stream_processor.register_handler("message", self._handle_message_event)
        self.stream_processor.register_handler("user_login", self._handle_user_activity)
        self.stream_processor.register_handler("crisis_indicator", self._handle_crisis_event)
        
    async def publish_event(self, event: StreamEvent):
        """Publish event to the streaming pipeline"""
        try:
            # Store in Redis stream
            stream_key = f"events:{event.event_type}"
            event_data = {
                'user_id': event.user_id,
                'timestamp': event.timestamp.isoformat(),
                'data': json.dumps(event.data),
                'source': event.source,
                'priority': event.priority
            }
            
            self.redis_client.xadd(stream_key, event_data)
            
            # Process immediately
            await self.stream_processor.process_event(event)
            
            # Broadcast to WebSocket consumers
            await self._broadcast_event(event)
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            
    async def _broadcast_event(self, event: StreamEvent):
        """Broadcast event to WebSocket consumers"""
        try:
            if self.channel_layer:
                await self.channel_layer.group_send(
                    f"user_{event.user_id}",
                    {
                        "type": "realtime_update",
                        "event_type": event.event_type,
                        "data": event.data,
                        "timestamp": event.timestamp.isoformat()
                    }
                )
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")
            
    async def _handle_mood_event(self, event: StreamEvent):
        """Handle mood-related events"""
        mood_score = event.data.get('mood_score', 0)
        
        # Update real-time mood metrics
        current_avg = self.metrics.avg_mood_score
        self.metrics.avg_mood_score = (current_avg + mood_score) / 2
        
        # Check for severe mood decline
        if mood_score <= 2:  # Assuming 1-10 scale
            crisis_event = StreamEvent(
                event_type="mood_severe_decline",
                user_id=event.user_id,
                timestamp=event.timestamp,
                data={"mood_score": mood_score, "alert_level": "high"},
                source="mood_monitor",
                priority="high"
            )
            await self.publish_event(crisis_event)
            
    async def _handle_journal_event(self, event: StreamEvent):
        """Handle journal-related events"""
        sentiment = event.data.get('sentiment_score', 0)
        
        # Check for concerning content
        if sentiment < -0.7:  # Very negative sentiment
            crisis_event = StreamEvent(
                event_type="negative_journal_content",
                user_id=event.user_id,
                timestamp=event.timestamp,
                data={"sentiment": sentiment, "alert_level": "medium"},
                source="journal_monitor",
                priority="high"
            )
            await self.publish_event(crisis_event)
            
    async def _handle_message_event(self, event: StreamEvent):
        """Handle messaging events"""
        # Track communication patterns in real-time
        await self._update_communication_metrics(event)
        
    async def _handle_user_activity(self, event: StreamEvent):
        """Handle user activity events"""
        # Update active users count
        self.redis_client.setex(f"user_active:{event.user_id}", 300, 1)  # 5 min TTL
        
        # Count current active users
        active_count = len(self.redis_client.keys("user_active:*"))
        self.metrics.active_users = active_count
        
    async def _handle_crisis_event(self, event: StreamEvent):
        """Handle crisis indicator events"""
        self.metrics.crisis_alerts += 1
        
        # Trigger immediate notifications
        await self._trigger_crisis_alert(event)
        
    async def _trigger_crisis_alert(self, event: StreamEvent):
        """Trigger crisis alert notifications"""
        try:
            # Send to crisis response team
            if self.channel_layer:
                await self.channel_layer.group_send(
                    "crisis_team",
                    {
                        "type": "crisis_alert",
                        "user_id": event.user_id,
                        "event_data": event.data,
                        "timestamp": event.timestamp.isoformat(),
                        "priority": "critical"
                    }
                )
                
            # Log for audit trail
            logger.critical(f"Crisis alert for user {event.user_id}: {event.data}")
            
        except Exception as e:
            logger.error(f"Error triggering crisis alert: {e}")
            
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """Get current real-time metrics"""
        # Calculate events per minute
        now = timezone.now()
        recent_events = [
            e for e in self.stream_processor.event_buffer
            if (now - e.timestamp) <= self.stream_processor.metrics_window
        ]
        
        events_per_minute = len(recent_events) / self.stream_processor.metrics_window.total_seconds() * 60
        self.metrics.events_per_minute = events_per_minute
        self.metrics.last_updated = now
        
        return {
            "active_users": self.metrics.active_users,
            "events_per_minute": round(self.metrics.events_per_minute, 2),
            "avg_mood_score": round(self.metrics.avg_mood_score, 2),
            "crisis_alerts": self.metrics.crisis_alerts,
            "system_load": self.metrics.system_load,
            "last_updated": self.metrics.last_updated.isoformat(),
            "total_events_buffered": len(self.stream_processor.event_buffer)
        }
    
    def get_mood_monitoring_data(self, user_id: str) -> Dict[str, Any]:
        """Get real-time mood monitoring data for a specific user"""
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return {"error": "Invalid user_id format"}
            
        now = timezone.now()
        
        # Get recent mood events for this user from event buffer
        user_events = [
            e for e in self.stream_processor.event_buffer 
            if e.user_id == user_id and e.event_type == "mood_entry"
            and (now - e.timestamp).total_seconds() <= 86400  # Last 24 hours
        ]
        
        # If no recent events in buffer, get data from database
        if not user_events:
            try:
                # Fallback to database query for recent mood logs
                from mood.models import MoodLog
                twenty_four_hours_ago = now - timedelta(hours=24)
                
                recent_mood_logs = MoodLog.objects.filter(
                    user_id=user_id,
                    logged_at__gte=twenty_four_hours_ago
                ).order_by('-logged_at')[:10]
                
                if not recent_mood_logs.exists():
                    return {
                        "user_id": user_id,
                        "recent_mood_data": [],
                        "avg_mood_24h": None,
                        "mood_trend": "no_data",
                        "last_entry": None,
                        "entries_count": 0
                    }
                
                # Convert database records to the same format as events
                mood_scores = []
                recent_mood_data = []
                
                for log in recent_mood_logs:
                    mood_score = log.mood_rating  # Use mood_rating from database
                    mood_scores.append(mood_score)
                    recent_mood_data.append({
                        "timestamp": log.logged_at.isoformat(),
                        "mood_score": mood_score,
                        "notes": log.notes or ""
                    })
                
                # Calculate average mood
                avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 0
                
                # Simple trend calculation
                if len(mood_scores) >= 2:
                    recent_half = mood_scores[:len(mood_scores)//2]  # Recent logs first due to ordering
                    earlier_half = mood_scores[len(mood_scores)//2:]
                    if sum(recent_half)/len(recent_half) > sum(earlier_half)/len(earlier_half):
                        trend = "improving"
                    elif sum(recent_half)/len(recent_half) < sum(earlier_half)/len(earlier_half):
                        trend = "declining"
                    else:
                        trend = "stable"
                else:
                    trend = "insufficient_data"
                
                return {
                    "user_id": user_id,
                    "recent_mood_data": recent_mood_data,
                    "avg_mood_24h": round(avg_mood, 2),
                    "mood_trend": trend,
                    "last_entry": recent_mood_data[0]["timestamp"] if recent_mood_data else None,
                    "entries_count": len(recent_mood_data)
                }
                
            except Exception as e:
                logger.error(f"Error querying mood logs from database: {e}")
                return {
                    "user_id": user_id,
                    "recent_mood_data": [],
                    "avg_mood_24h": None,
                    "mood_trend": "no_data",
                    "last_entry": None,
                    "entries_count": 0
                }
        
        
        # Calculate metrics from event buffer
        mood_scores = [e.data.get("mood_score", 5) for e in user_events]
        avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 0
        
        # Simple trend calculation
        if len(mood_scores) >= 2:
            recent_half = mood_scores[len(mood_scores)//2:]
            earlier_half = mood_scores[:len(mood_scores)//2]
            if sum(recent_half)/len(recent_half) > sum(earlier_half)/len(earlier_half):
                trend = "improving"
            elif sum(recent_half)/len(recent_half) < sum(earlier_half)/len(earlier_half):
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            
        return {
            "user_id": user_id,
            "recent_mood_data": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "mood_score": e.data.get("mood_score", 5),
                    "notes": e.data.get("notes", "")
                } for e in sorted(user_events, key=lambda x: x.timestamp, reverse=True)[:10]
            ],
            "avg_mood_24h": round(avg_mood, 2),
            "mood_trend": trend,
            "last_entry": user_events[-1].timestamp.isoformat() if user_events else None,
            "entries_count": len(user_events)
        }
    
    def get_crisis_alerts(self) -> List[Dict[str, Any]]:
        """Get current crisis detection alerts"""
        now = timezone.now()
        
        # Get recent crisis events
        crisis_events = [
            e for e in self.stream_processor.event_buffer 
            if e.priority == "critical" and (now - e.timestamp).total_seconds() <= 3600  # Last hour
        ]
        
        alerts = []
        for event in crisis_events:
            alerts.append({
                "alert_id": f"crisis_{event.user_id}_{int(event.timestamp.timestamp())}",
                "user_id": event.user_id,
                "timestamp": event.timestamp.isoformat(),
                "severity": "high",
                "type": event.event_type,
                "description": f"Crisis detected in {event.event_type}",
                "data": event.data
            })
            
        return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get real-time system metrics"""
        return self.get_realtime_metrics()
    
    def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a real-time event from API request"""
        try:
            # Create event from incoming data
            event = StreamEvent(
                event_type=event_data.get("event_type", "custom"),
                user_id=int(event_data.get("user_id", 0)),
                timestamp=timezone.now(),
                data=event_data.get("data", {}),
                source=event_data.get("source", "api"),
                priority=event_data.get("priority", "normal")
            )
            
            # Process event asynchronously
            async_to_sync(self.stream_processor.process_event)(event)
            
            return {
                "event_id": f"{event.event_type}_{event.user_id}_{int(event.timestamp.timestamp())}",
                "processed_at": timezone.now().isoformat(),
                "event_type": event.event_type,
                "user_id": event.user_id
            }
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return {"error": str(e)}
        
    async def start_stream_consumer(self):
        """Start consuming events from Redis streams"""
        while True:
            try:
                # Consume from multiple streams
                streams = ["events:mood_entry", "events:journal_entry", "events:message"]
                for stream in streams:
                    messages = self.redis_client.xread({stream: '$'}, count=10, block=1000)
                    
                    for stream_name, msgs in messages:
                        for msg_id, fields in msgs:
                            await self._process_redis_message(fields)
                            
            except Exception as e:
                logger.error(f"Error in stream consumer: {e}")
                await asyncio.sleep(5)  # Wait before retrying
                
    async def _process_redis_message(self, fields: Dict[bytes, bytes]):
        """Process message from Redis stream"""
        try:
            # Convert bytes to strings
            data = {k.decode(): v.decode() for k, v in fields.items()}
            
            event = StreamEvent(
                event_type=data.get('event_type', 'unknown'),
                user_id=int(data.get('user_id', 0)),
                timestamp=datetime.fromisoformat(data.get('timestamp')),
                data=json.loads(data.get('data', '{}')),
                source=data.get('source', 'unknown'),
                priority=data.get('priority', 'normal')
            )
            
            await self.stream_processor.process_event(event)
            
        except Exception as e:
            logger.error(f"Error processing Redis message: {e}")


# Global service instance
realtime_service = RealTimeAnalyticsService()


# Django signal receivers for automatic event generation
@receiver(post_save, sender=MoodLog)
def mood_entry_saved(sender, instance, created, **kwargs):
    """Automatically publish mood events to real-time stream"""
    if created:
        event = StreamEvent(
            event_type="mood_entry",
            user_id=instance.user.id,
            timestamp=instance.logged_at,
            data={
                "mood_score": instance.mood_rating,  # Use mood_rating from the model
                "notes": instance.notes[:100] if instance.notes else "",
                "tags": getattr(instance, 'tags', [])
            },
            source="mood_tracker"
        )
        async_to_sync(realtime_service.publish_event)(event)


@receiver(post_save, sender=JournalEntry)
def journal_entry_saved(sender, instance, created, **kwargs):
    """Automatically publish journal events to real-time stream"""
    if created:
        event = StreamEvent(
            event_type="journal_entry",
            user_id=instance.user.id,
            timestamp=instance.created_at,
            data={
                "content_length": len(instance.content),
                "sentiment_score": getattr(instance, 'sentiment_score', 0),
                "emotion_tags": getattr(instance, 'emotion_tags', [])
            },
            source="journal"
        )
        async_to_sync(realtime_service.publish_event)(event)
