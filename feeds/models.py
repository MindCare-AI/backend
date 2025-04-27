from django.db import models
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

POST_TYPES = [("text", "Text"), ("image", "Image"), ("video", "Video")]

# Topics choices for better organization
TOPIC_CHOICES = [
    ("mental_health", "Mental Health"),
    ("therapy", "Therapy"),
    ("self_care", "Self Care"),
    ("mindfulness", "Mindfulness"),
    ("stress_management", "Stress Management"),
    ("relationships", "Relationships"),
    ("personal_growth", "Personal Growth"),
    ("anxiety", "Anxiety"),
    ("depression", "Depression"),
    ("wellness", "Wellness"),
]

TAG_CHOICES = [
    ("mental_health", "Mental Health"),
    ("therapy", "Therapy"),
    ("self_care", "Self Care"),
    ("mindfulness", "Mindfulness"),
    ("stress_management", "Stress Management"),
    ("relationships", "Relationships"),
    ("personal_growth", "Personal Growth"),
    ("anxiety", "Anxiety"),
    ("depression", "Depression"),
    ("wellness", "Wellness"),
]


class Topic(models.Model):
    """Topics for posts categorization"""

    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_topics",
    )
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, default="#3498DB")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Reaction(models.Model):
    """Model for storing reactions to posts and comments"""

    REACTION_TYPES = [
        ("like", "Like 👍"),
        ("love", "Love ❤️"),
        ("support", "Support 🤝"),
        ("insightful", "Insightful 💡"),
        ("celebrate", "Celebrate 🎉"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=20, choices=REACTION_TYPES)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "content_type", "object_id"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.reaction_type}"


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    content = models.TextField()
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default="text")
    topics = models.CharField(
        max_length=20, choices=TOPIC_CHOICES, blank=True, null=True
    )
    visibility = models.CharField(max_length=20, default="public", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    media_files = models.ManyToManyField(
        "media_handler.MediaFile", related_name="posts", blank=True
    )
    link_url = models.URLField(blank=True, null=True)
    views_count = models.PositiveIntegerField(default=0)
    tags = models.CharField(max_length=50, choices=TAG_CHOICES)

    # Generic relations
    reactions = GenericRelation(Reaction)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["visibility"]),
        ]

    def __str__(self):
        return f"{self.author.username}'s post: {self.content[:50]}"

    @property
    def comments_count(self):
        return self.comments.count()

    @property
    def reactions_count(self):
        return self.reactions.count()

    def get_reactions_summary(self):
        """Get summary of reactions by type"""
        reactions = self.reactions.values("reaction_type").annotate(
            count=models.Count("reaction_type")
        )
        return {item["reaction_type"]: item["count"] for item in reactions}

    def increment_views(self):
        """Increment the view count"""
        self.views_count += 1
        self.save(update_fields=["views_count"])


class Comment(models.Model):
    """Comments on posts"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    # Generic relations
    reactions = GenericRelation(Reaction)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username}: {self.content[:50]}"

    @property
    def replies_count(self):
        return self.replies.count()

    @property
    def reactions_count(self):
        return self.reactions.count()


class PollOption(models.Model):
    """Options for poll posts"""

    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="poll_options"
    )
    option_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.option_text


class PollVote(models.Model):
    """User votes on poll options"""

    poll_option = models.ForeignKey(
        PollOption, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["poll_option", "user"]

    def __str__(self):
        return f"{self.user.username} voted for {self.poll_option.option_text}"
