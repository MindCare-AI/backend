# feeds/serializers.py
from rest_framework import serializers
from feeds.models import (
    Post, 
    Comment, 
    Topic, 
    Reaction, 
    PollOption, 
    PollVote
)
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
from media_handler.models import MediaFile
from media_handler.serializers import MediaFileSerializer


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for post topics"""
    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'icon', 'color', 'is_active', 'created_at']
        read_only_fields = ['created_at', 'created_by']

    def create(self, validated_data):
        """Associate the topic with the authenticated user"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ReactionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Reaction
        fields = ['id', 'user', 'reaction_type', 'created_at']
        read_only_fields = ['user', 'created_at']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'full_name': obj.user.get_full_name()
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
            ('like', 'Like 👍'),
            ('love', 'Love ❤️'),
            ('support', 'Support 🤝'),
            ('insightful', 'Insightful 💡'),
            ('celebrate', 'Celebrate 🎉')
        ],
        required=True,
        help_text="Type of reaction to add"
    )


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comments on posts"""
    author_name = serializers.SerializerMethodField()
    author_profile_pic = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    replies_count = serializers.IntegerField(source='replies.count', read_only=True)
    current_user_reaction = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'author', 'author_name', 'author_profile_pic',
            'content', 'parent', 'created_at', 'updated_at', 
            'is_edited', 'reactions_count', 'replies_count',
            'current_user_reaction'
        ]
        read_only_fields = ['author', 'created_at', 'updated_at', 'is_edited']

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username
    
    def get_author_profile_pic(self, obj):
        if hasattr(obj.author, 'profile') and hasattr(obj.author.profile, 'profile_image'):
            if obj.author.profile.profile_image:
                return obj.author.profile.profile_image.url
        return None
        
    def get_reactions_count(self, obj):
        return obj.reactions_count
        
    def get_current_user_reaction(self, obj):
        """Get the current user's reaction to this comment if any"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Comment)
            try:
                reaction = Reaction.objects.get(
                    content_type=content_type,
                    object_id=obj.id,
                    user=request.user
                )
                return reaction.reaction_type
            except Reaction.DoesNotExist:
                return None
        return None

    def create(self, validated_data):
        """Associate the comment with the authenticated user"""
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class PollOptionSerializer(serializers.ModelSerializer):
    """Serializer for poll options"""
    votes_count = serializers.IntegerField(source='votes.count', read_only=True)
    user_has_voted = serializers.SerializerMethodField()
    
    class Meta:
        model = PollOption
        fields = ['id', 'post', 'option_text', 'votes_count', 'user_has_voted']
        read_only_fields = ['votes_count']
        
    def get_user_has_voted(self, obj):
        """Check if current user has voted for this option"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.votes.filter(user=request.user).exists()
        return False


class PostSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=False)
    media_files = MediaFileSerializer(many=True, read_only=True)
    reactions_summary = serializers.SerializerMethodField()
    current_user_reaction = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True)
    author_name = serializers.SerializerMethodField()
    author_profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_name', 'author_profile_pic', 
            'content', 'post_type', 'topics', 'visibility', 
            'created_at', 'updated_at', 'file', 'media_files',
            'link_url', 'views_count', 'tags', 'reactions_summary',
            'current_user_reaction', 'comments_count'
        ]
        read_only_fields = ['author', 'visibility', 'created_at', 'updated_at']

    def get_reactions_summary(self, obj):
        return obj.get_reactions_summary()

    def get_current_user_reaction(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Post)
            try:
                reaction = Reaction.objects.get(
                    content_type=content_type,
                    object_id=obj.id,
                    user=request.user
                )
                return reaction.reaction_type
            except Reaction.DoesNotExist:
                return None
        return None

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_author_profile_pic(self, obj):
        if hasattr(obj.author, 'profile') and hasattr(obj.author.profile, 'profile_image'):
            if obj.author.profile.profile_image:
                return obj.author.profile.profile_image.url
        return None

    def create(self, validated_data):
        file = validated_data.pop('file', None)
        post = super().create(validated_data)

        if file:
            media_file = MediaFile.objects.create(
                file=file,
                uploaded_by=post.author,
                media_type=self._determine_media_type(file)
            )
            post.media_files.add(media_file)

        return post

    def _determine_media_type(self, file):
        content_type = getattr(file, 'content_type', '')
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type.startswith('audio/'):
            return 'audio'
        return 'document'


class PostDetailSerializer(PostSerializer):
    """Serializer for post detail view with comments"""
    comments = serializers.SerializerMethodField()
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['comments']
        
    def get_comments(self, obj):
        """Get top-level comments on the post"""
        comments = obj.comments.filter(parent=None).order_by('-created_at')[:5]
        return CommentSerializer(
            comments, 
            many=True, 
            context=self.context
        ).data


class PollVoteSerializer(serializers.ModelSerializer):
    """Serializer for poll votes"""
    
    class Meta:
        model = PollVote
        fields = ['id', 'poll_option', 'user', 'voted_at']
        read_only_fields = ['user', 'voted_at']
        
    def create(self, validated_data):
        """Associate the vote with the authenticated user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
        
    def validate(self, data):
        """Validate that the user hasn't already voted on this poll"""
        user = self.context['request'].user
        poll_option = data['poll_option']
        post = poll_option.post
        
        existing_votes = PollVote.objects.filter(
            poll_option__post=post,
            user=user
        )
        
        if existing_votes.exists():
            raise serializers.ValidationError("You have already voted on this poll")
            
        return data


class UserProfileMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for user profiles in feed responses"""
    name = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'name', 'profile_pic', 'user_type']
        
    def get_name(self, obj):
        return obj.get_full_name() or obj.username
        
    def get_profile_pic(self, obj):
        if hasattr(obj, 'profile') and hasattr(obj.profile, 'profile_image'):
            if obj.profile.profile_image:
                return obj.profile.profile_image.url
        return None