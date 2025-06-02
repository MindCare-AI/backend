# MindCare Database Schema Documentation

## Overview
This document describes the comprehensive database schema for the MindCare mental health platform, designed to support a React Native client application with Django backend.

## Core Entities

### User Management
- **CustomUser**: Central user model with patient/therapist distinction
- **PatientProfile**: Extended profile for patients with health-specific fields
- **TherapistProfile**: Extended profile for therapists with professional credentials

### Healthcare Services
- **Appointment**: Scheduling system for therapy sessions
- **SessionNote**: Therapist notes for each session
- **HealthMetric**: Patient health tracking data
- **MedicalHistoryEntry**: Patient medical history records

### Messaging System
- **OneToOneConversation/OneToOneMessage**: Private messaging between users
- **GroupConversation/GroupMessage**: Group chat functionality
- **ChatbotConversation/ChatMessage**: AI chatbot interactions

### Mental Health Tracking
- **JournalEntry/JournalCategory**: User journaling system
- **MoodLog**: Daily mood and energy tracking

### Social Features
- **Post**: Social feed posts for community support
- **Reaction**: User reactions to posts and content
- **Topic**: Content categorization system

### System Features
- **Notification/NotificationType**: User notification system
- **MediaFile**: File upload and management
- **UserAnalysis/AIInsight/TherapyRecommendation**: AI-powered analytics

## Key Relationships

### User-Centric Design
All major entities relate back to CustomUser, creating user-specific data silos for privacy and security.

### Appointment Workflow
```
Patient → Appointment ← Therapist
     ↓
SessionNote (created by therapist)
```

### Mental Health Tracking Pipeline
```
User → JournalEntry → MoodLog → UserAnalysis → AIInsight → TherapyRecommendation
```

### Messaging Ecosystem
```
User ↔ OneToOneConversation ↔ OneToOneMessage
User ↔ GroupConversation ↔ GroupMessage  
User ↔ ChatbotConversation ↔ ChatMessage
```

## Database Features

### Scalability
- Indexed foreign keys for performance
- JSON fields for flexible metadata storage
- Pagination-friendly timestamp ordering

### Security & Privacy
- User-based data isolation
- Soft deletion for sensitive data
- Encrypted storage capabilities

### AI Integration
- Structured data for ML analysis
- Real-time insight generation
- Recommendation tracking and effectiveness

### Mobile Optimization
- Offline-capable data structures
- Efficient caching mechanisms
- Minimal data transfer requirements

## Usage for AI Diagram Generation

### Supported Formats
1. **PlantUML** (`database_relationships.puml`): Use with PlantUML online editors
2. **Mermaid** (`database_relationships.mermaid`): Use with Mermaid live editor
3. **Documentation** (this file): Human-readable reference

### Recommended Tools
- **PlantUML Online**: https://www.plantuml.com/plantuml/
- **Mermaid Live Editor**: https://mermaid.live/
- **Draw.io**: Import PlantUML or create manually
- **Lucidchart**: Professional diagramming with database templates

### AI Prompt Suggestions
When using AI tools to generate or modify diagrams:

1. "Create an ERD from this PlantUML schema focusing on [specific subsystem]"
2. "Generate a simplified view showing only user-related tables"
3. "Create a data flow diagram showing the appointment booking process"
4. "Show the messaging system relationships in a clean format"

## Notes for Development
- All timestamps use Django's timezone-aware datetime
- Foreign keys include proper CASCADE/SET_NULL behaviors
- JSON fields provide flexibility for evolving requirements
- Generic foreign keys enable polymorphic relationships
