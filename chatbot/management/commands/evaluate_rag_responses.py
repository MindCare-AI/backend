from django.core.management.base import BaseCommand
from chatbot.models import ChatMessage
from django.db.models import Q
import json

class Command(BaseCommand):
    help = "Evaluate RAG response quality and provide metrics"

    def handle(self, *args, **kwargs):
        # Get recent RAG responses
        rag_messages = ChatMessage.objects.filter(
            is_bot=True,
            metadata__rag_used=True
        ).order_by('-timestamp')[:20]

        total_responses = rag_messages.count()
        cbt_responses = rag_messages.filter(metadata__therapy_recommendation__approach='cbt').count()
        dbt_responses = rag_messages.filter(metadata__therapy_recommendation__approach='dbt').count()
        
        avg_confidence = sum([
            msg.metadata.get('therapy_recommendation', {}).get('confidence', 0)
            for msg in rag_messages
        ]) / total_responses if total_responses > 0 else 0

        self.stdout.write(self.style.SUCCESS(f"✅ RAG System Performance:"))
        self.stdout.write(f"  Total RAG responses: {total_responses}")
        self.stdout.write(f"  CBT responses: {cbt_responses}")
        self.stdout.write(f"  DBT responses: {dbt_responses}")
        self.stdout.write(f"  Average confidence: {avg_confidence:.3f}")
        
        if avg_confidence > 0.7:
            self.stdout.write(self.style.SUCCESS("🎯 HIGH QUALITY responses detected"))
        elif avg_confidence > 0.5:
            self.stdout.write(self.style.WARNING("⚠️ MODERATE QUALITY responses"))
        else:
            self.stdout.write(self.style.ERROR("❌ LOW QUALITY responses - consider retraining"))
