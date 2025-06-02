# MindCare Mental Health Platform - Class Diagrams

## Overview
This document provides comprehensive class diagrams for the MindCare mental health platform, illustrating the object-oriented architecture, inheritance hierarchies, and relationships between different components of the Django-based backend system.

## Architecture Layers

### 1. User Management Layer
The foundation layer handling user authentication, profiles, and preferences.

#### Core Classes:
- **CustomUser**: Extended Django user model with mental health specific fields
- **BaseProfile**: Abstract base class for user profiles
- **PatientProfile**: Specialized profile for patients with medical information
- **TherapistProfile**: Specialized profile for therapists with professional credentials
- **UserPreferences**: User notification and display preferences
- **UserSettings**: Privacy and data sharing settings

#### Key Patterns:
- **Inheritance**: `BaseProfile` → `PatientProfile` / `TherapistProfile`
- **Composition**: `CustomUser` has `UserPreferences` and `UserSettings`
- **Polymorphism**: Different user types with specialized behaviors

### 2. Serializers Layer
Django REST Framework serializers for API data validation and transformation.

#### Core Classes:
- **CustomUserSerializer**: Handles user creation and type assignment
- **PatientProfileSerializer**: Validates medical information
- **TherapistProfileSerializer**: Validates professional credentials
- **UserPreferencesSerializer**: Manages user preferences
- **UserSettingsSerializer**: Handles privacy settings

#### Key Features:
- Data validation and transformation
- Nested serialization for related objects
- Custom validation methods for business rules

### 3. Views Layer
API endpoints and business logic controllers.

#### Core Classes:
- **CustomUserViewSet**: User CRUD operations and profile management
- **PatientProfileViewSet**: Patient-specific operations
- **TherapistProfileViewSet**: Therapist verification and availability

#### Key Features:
- RESTful API endpoints
- Permission-based access control
- Custom actions for specialized operations

### 4. Permissions Layer
Security and access control classes.

#### Core Classes:
- **IsSuperUserOrSelf**: Allows access to own data or admin
- **IsPatientOrTherapist**: Role-based access control
- **IsVerifiedTherapist**: Ensures only verified therapists access certain features

### 5. Healthcare Layer
Mental health specific domain models.

#### Core Classes:
- **Appointment**: Therapy session scheduling
- **WaitingListEntry**: Queue management for appointments
- **MoodLog**: Daily mood tracking
- **JournalEntry**: Therapeutic journaling
- **HealthMetric**: Quantified health measurements

#### Key Features:
- Healthcare-specific business logic
- Data analytics capabilities
- Privacy and confidentiality controls

### 6. Messaging Layer
Real-time communication system.

#### Core Classes:
- **BaseConversation**: Abstract conversation model
- **BaseMessage**: Abstract message model
- **OneToOneConversation**: Private messaging
- **GroupConversation**: Group therapy sessions
- **OneToOneMessage**: Private messages
- **GroupMessage**: Group messages with mentions

#### Key Patterns:
- **Template Method**: Base classes define conversation structure
- **Strategy Pattern**: Different message types with specialized behavior

### 7. AI Services Layer
Artificial intelligence and machine learning services.

#### Core Classes:
- **ChatbotService**: AI-powered mental health chatbot
- **AIAnalysisService**: User data analysis and insights
- **ConversationSummaryService**: Therapy session summaries
- **CrisisMonitoringService**: Risk assessment and intervention
- **TherapyRAGService**: Retrieval-augmented therapy recommendations

#### Key Features:
- Integration with external AI APIs (Gemini, Ollama)
- Real-time crisis detection
- Evidence-based therapy recommendations

### 8. Notification Services
Real-time notification and alert system.

#### Core Classes:
- **UnifiedNotificationService**: Central notification management
- **Notification**: Individual notification instances
- **NotificationType**: Categorization of notifications

#### Key Features:
- Multi-channel delivery (push, email, in-app)
- User preference management
- Real-time WebSocket integration

### 9. Media & Files
File upload and management system.

#### Core Classes:
- **MediaFile**: Generic file storage with content type relations

#### Key Features:
- Generic foreign key relationships
- File type validation
- Image compression and optimization

### 10. Core Utilities
Cross-cutting concerns and infrastructure.

#### Core Classes:
- **RequestMiddleware**: Thread-local request storage
- **UnifiedWebSocketAuthMiddleware**: WebSocket authentication
- **PatientProfileFilter**: Django filter for patient searches

## Design Patterns Used

### 1. Inheritance Patterns
```
BaseProfile
├── PatientProfile
└── TherapistProfile

BaseConversation
├── OneToOneConversation
└── GroupConversation

BaseMessage
├── OneToOneMessage
└── GroupMessage
```

### 2. Composition Patterns
- User-Profile relationship (OneToOne)
- User-Preferences relationship (OneToOne)
- Conversation-Message relationship (OneToMany)

### 3. Service Layer Pattern
- **ChatbotService**: Encapsulates AI chatbot logic
- **AIAnalysisService**: Handles data analysis
- **UnifiedNotificationService**: Manages notifications

### 4. Repository Pattern
- Django ORM acts as repository layer
- Custom managers for complex queries
- QuerySet methods for business logic

### 5. Observer Pattern
- Django signals for model events
- Real-time notifications via WebSockets
- Cache invalidation on model changes

## Relationships Overview

### One-to-One Relationships
- `CustomUser` ↔ `UserPreferences`
- `CustomUser` ↔ `UserSettings`
- `CustomUser` ↔ `PatientProfile`
- `CustomUser` ↔ `TherapistProfile`

### One-to-Many Relationships
- `PatientProfile` → `Appointment`
- `TherapistProfile` → `Appointment`
- `CustomUser` → `MoodLog`
- `CustomUser` → `JournalEntry`
- `CustomUser` → `Notification`

### Many-to-Many Relationships
- `BaseConversation` ↔ `CustomUser` (participants)
- `GroupMessage` ↔ `CustomUser` (mentions)

### Generic Foreign Key Relationships
- `MediaFile` → Any model (content_object)

## Key Business Rules

### User Management
1. Users must have either 'patient' or 'therapist' type
2. Profile creation is automatic based on user type
3. User preferences are created with sensible defaults

### Healthcare Operations
1. Only verified therapists can provide services
2. Patients can only book with available therapists
3. Appointments have status workflow (pending → confirmed → completed)

### Privacy and Security
1. Patient data is protected by privacy levels
2. Therapist-patient confidentiality is enforced
3. Crisis situations trigger immediate alerts

### AI and Analytics
1. AI analysis requires minimum data points
2. Crisis detection has escalation procedures
3. All AI interactions are logged for audit

## Usage Instructions

### For PlantUML (class_diagrams.puml)
1. **Local Rendering**:
   ```bash
   java -jar plantuml.jar class_diagrams.puml
   ```

2. **Online Tools**:
   - [PlantUML Online Server](http://www.plantuml.com/plantuml/)
   - [PlantText](https://www.planttext.com/)

### For Mermaid (class_diagrams.mermaid)
1. **Online Editors**:
   - [Mermaid Live Editor](https://mermaid.live/)
   - [Mermaid Chart](https://www.mermaidchart.com/)

2. **VS Code Extensions**:
   - Mermaid Markdown Syntax Highlighting
   - Markdown Preview Mermaid Support

3. **Command Line**:
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   mmdc -i class_diagrams.mermaid -o class_diagrams.png
   ```

### Integration with Development Workflow
1. **Documentation**: Include diagrams in technical documentation
2. **Code Reviews**: Reference class relationships during reviews
3. **Onboarding**: Use diagrams to explain system architecture
4. **Planning**: Visualize impact of new features on existing classes

## File Structure
```
/home/siaziz/Desktop/backend/
├── class_diagrams.puml          # PlantUML class diagrams
├── class_diagrams.mermaid       # Mermaid class diagrams
├── CLASS_DIAGRAMS.md           # This documentation file
├── database_relationships.puml  # Database ERD (PlantUML)
├── database_relationships.mermaid # Database ERD (Mermaid)
└── DATABASE_SCHEMA.md          # Database documentation
```

## Next Steps
1. **Sequence Diagrams**: Create interaction diagrams for key workflows
2. **Component Diagrams**: Show deployment and module relationships  
3. **State Diagrams**: Model appointment and user status workflows
4. **Activity Diagrams**: Document complex business processes

## Maintenance
- Update diagrams when adding new classes or relationships
- Validate diagrams against actual code during refactoring
- Use automated tools to generate diagrams from code when possible
- Keep documentation synchronized with code changes
