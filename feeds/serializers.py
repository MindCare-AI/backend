# feeds/serializers.py
from rest_framework import serializers
from feeds.models import Post, Comment, Topic, Reaction, PollOption, PollVote
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
from media_handler.models import MediaFile
from media_handler.serializers import MediaFileSerializer


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for post topics"""

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "description",
            "icon",
            "color",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at", "created_by"]

    def create(self, validated_data):
        """Associate the topic with the authenticated user"""
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ReactionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Reaction
        fields = ["id", "user", "reaction_type", "created_at"]
        read_only_fields = ["user", "created_at"]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "full_name": obj.user.get_full_name(),
        }

    def validate_reaction_type(self, value):
        valid_types = dict(Reaction.REACTION_TYPES).keys()
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid reaction type. Must be one of: {', '.join(valid_types)}"
            )
        return value


class ReactionActionSerializer(serializers.Serializer):
    """Dedicated serializer for reaction actions"""

    reaction_type = serializers.ChoiceField(
        choices=[
            ("like", "Like 👍"),
            ("love", "Love ❤️"),
            ("support", "Support 🤝"),
            ("insightful", "Insightful 💡"),
            ("celebrate", "Celebrate 🎉"),
        ],
        required=True,
        help_text="Type of reaction to add",
    )


class LikeToggleSerializer(serializers.Serializer):
    """Serializer for toggling like action. No input is required."""

    pass


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comments on posts"""

    author_name = serializers.SerializerMethodField()
    author_profile_pic = serializers.SerializerMethodField()
    author_user_type = serializers.CharField(source='author.user_type', read_only=True)
    reactions_count = serializers.SerializerMethodField()
    replies_count = serializers.IntegerField(source="replies.count", read_only=True)
    current_user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "author",
            "author_name",
            "author_profile_pic",
            "author_user_type",
            "content",
            "parent",
            "created_at",
            "updated_at",
            "is_edited",
            "reactions_count",
            "replies_count",
            "current_user_reaction",
        ]
        read_only_fields = ["author", "created_at", "updated_at", "is_edited"]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_author_profile_pic(self, obj):
        user = obj.author
        url = None
        if hasattr(user, "patient_profile") and getattr(
            user.patient_profile, "profile_pic", None
        ):
            url = user.patient_profile.profile_pic.url
        elif hasattr(user, "profile") and getattr(user.profile, "profile_image", None):
            url = user.profile.profile_image.url
        elif hasattr(user, "therapist_profile") and getattr(
            user.therapist_profile, "profile_picture", None
        ):
            url = user.therapist_profile.profile_picture.url
        elif hasattr(user, "profile_picture") and user.profile_picture:
            url = user.profile_picture.url
        if url and self.context.get("request"):
            url = self.context["request"].build_absolute_uri(url)
        return url

    def get_reactions_count(self, obj):
        return obj.reactions_count

    def get_current_user_reaction(self, obj):
        """Get the current user's reaction to this comment if any"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Comment)
            try:
                reaction = Reaction.objects.get(
                    content_type=content_type, object_id=obj.id, user=request.user
                )
                return reaction.reaction_type
            except Reaction.DoesNotExist:
                return None
        return None

    def create(self, validated_data):
        """Associate the comment with the authenticated user"""
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class PollOptionSerializer(serializers.ModelSerializer):
    """Serializer for poll options"""

    votes_count = serializers.IntegerField(source="votes.count", read_only=True)
    user_has_voted = serializers.SerializerMethodField()

    class Meta:
        model = PollOption
        fields = ["id", "post", "option_text", "votes_count", "user_has_voted"]
        read_only_fields = ["votes_count"]

    def get_user_has_voted(self, obj):
        """Check if current user has voted for this option"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.votes.filter(user=request.user).exists()
        return False


class PostSerializer(serializers.ModelSerializer):
    """Enhanced Post serializer with complete data exposure"""

    file = serializers.FileField(required=False, write_only=True)
    media_files = MediaFileSerializer(many=True, read_only=True)
    reactions_summary = serializers.SerializerMethodField()
    current_user_reaction = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    author_profile_pic = serializers.SerializerMethodField()
    author_user_type = serializers.CharField(source='author.user_type', read_only=True)
    author_details = serializers.SerializerMethodField()
    poll_options = PollOptionSerializer(many=True, read_only=True)
    total_reactions = serializers.SerializerMethodField()
    is_liked_by_user = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "author_name",
            "author_profile_pic",
            "author_user_type",
            "author_details",
            "content",
            "post_type",
            "topics",
            "visibility",
            "created_at",
            "updated_at",
            "file",
            "media_files",
            "link_url",
            "views_count",
            "tags",
            "reactions_summary",
            "current_user_reaction",
            "total_reactions",
            "is_liked_by_user",
            "comments_count",
            "poll_options",
        ]
        read_only_fields = ["author", "visibility", "created_at", "updated_at", "views_count"]

    def get_reactions_summary(self, obj):
        """Get detailed reactions summary"""
        return obj.get_reactions_summary()

    def get_current_user_reaction(self, obj):
        """Get current user's reaction to this post"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Post)
            try:
                reaction = Reaction.objects.get(
                    content_type=content_type, object_id=obj.id, user=request.user
                )
                return reaction.reaction_type
            except Reaction.DoesNotExist:
                return None
        return None

    def get_total_reactions(self, obj):
        """Get total reaction count"""
        return obj.reactions.count()

    def get_is_liked_by_user(self, obj):
        """Check if current user liked this post"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Post)
            return obj.reactions.filter(
                user=request.user, reaction_type="like"
            ).exists()
        return False

    def get_comments_count(self, obj):
        """Get total comments count"""
        return obj.comments.count()

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_author_details(self, obj):
        """Get detailed author information"""
        user = obj.author
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.get_full_name(),
            "user_type": user.user_type,
            "email": user.email if self.context.get("request") and self.context["request"].user == user else None,
        }

    def get_author_profile_pic(self, obj):
        user = obj.author
        url = None
        if hasattr(user, "patient_profile") and getattr(
            user.patient_profile, "profile_pic", None
        ):
            url = user.patient_profile.profile_pic.url
        elif hasattr(user, "profile") and getattr(user.profile, "profile_image", None):
            url = user.profile.profile_image.url
        elif hasattr(user, "therapist_profile") and getattr(
            user.therapist_profile, "profile_picture", None
        ):
            url = user.therapist_profile.profile_picture.url
        elif hasattr(user, "profile_picture") and user.profile_picture:
            url = user.profile_picture.url
        if url and self.context.get("request"):
            url = self.context["request"].build_absolute_uri(url)
        return url

    def create(self, validated_data):
        file = validated_data.pop("file", None)
        post = super().create(validated_data)

        if file:
            media_file = MediaFile.objects.create(
                file=file,
                uploaded_by=post.author,
                media_type=self._determine_media_type(file),
            )
            post.media_files.add(media_file)

        return post

    def _determine_media_type(self, file):
        content_type = getattr(file, "content_type", "")
        if content_type.startswith("image/"):
            return "image"
        elif content_type.startswith("video/"):
            return "video"
        elif content_type.startswith("audio/"):
            return "audio"
        return "document"

    def to_representation(self, instance):
        """Ensure all data is properly serialized"""
        data = super().to_representation(instance)

        # Ensure all computed fields are included
        request = self.context.get("request")
        if request:
            # Add extra debugging info in development
            if hasattr(request, "user") and request.user.is_authenticated:
                data["_debug_info"] = {
                    "user_id": request.user.id,
                    "is_authenticated": True,
                    "timestamp": instance.created_at.isoformat() if instance.created_at else None,
                }

        return data


class PostDetailSerializer(PostSerializer):
    """Serializer for post detail view with comments"""

    comments = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ["comments", "reactions"]

    def get_comments(self, obj):
        """Get top-level comments on the post"""
        comments = obj.comments.filter(parent=None).order_by("-created_at")[:10]
        return CommentSerializer(comments, many=True, context=self.context).data

    def get_reactions(self, obj):
        """Get all reactions on the post"""
        reactions = obj.reactions.all().order_by("-created_at")[:20]
        return ReactionSerializer(reactions, many=True, context=self.context).data
