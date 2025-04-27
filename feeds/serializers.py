# feeds/serializers.py
from rest_framework import serializers
from feeds.models import (
    Post, 
    Comment, 
    Topic, 
    Reaction, 
    SavedPost, 
    HiddenPost, 
    PollOption, 
    PollVote
)
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
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
    """Serializer for reactions to posts or comments"""
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Reaction
        fields = ['id', 'user', 'user_name', 'reaction_type', 'created_at']
        read_only_fields = ['user', 'created_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def create(self, validated_data):
        """Associate the reaction with the authenticated user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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
        # Try to get profile image URL through the user's profile
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
    """Serializer for feed posts"""
    author_name = serializers.SerializerMethodField()
    author_profile_pic = serializers.SerializerMethodField()
    topics_data = TopicSerializer(source='topics', many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    reactions_summary = serializers.SerializerMethodField()
    current_user_reaction = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    media_files_data = MediaFileSerializer(source='media_files', many=True, read_only=True)
    poll_options = PollOptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_name', 'author_profile_pic', 'content',
            'post_type', 'topics', 'topics_data', 'visibility', 'created_at',
            'updated_at', 'is_edited', 'is_pinned', 'is_featured', 'is_archived',
            'media_files', 'media_files_data', 'views_count', 'tags',
            'comments_count', 'reactions_count', 'reactions_summary',
            'current_user_reaction', 'is_saved', 'link_url', 'link_title',
            'link_description', 'link_image', 'poll_options'
        ]
        read_only_fields = [
            'author', 'created_at', 'updated_at', 'is_edited',
            'views_count', 'reactions_count', 'comments_count',
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username
    
    def get_author_profile_pic(self, obj):
        # Try to get profile image URL through the user's profile
        if hasattr(obj.author, 'profile') and hasattr(obj.author.profile, 'profile_image'):
            if obj.author.profile.profile_image:
                return obj.author.profile.profile_image.url
        return None
    
    def get_comments_count(self, obj):
        return obj.comments_count
    
    def get_reactions_count(self, obj):
        return obj.reactions_count
    
    def get_reactions_summary(self, obj):
        return obj.get_reactions_summary()
    
    def get_current_user_reaction(self, obj):
        """Get the current user's reaction to this post if any"""
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
    
    def get_is_saved(self, obj):
        """Check if the post is saved by the current user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedPost.objects.filter(user=request.user, post=obj).exists()
        return False

    def create(self, validated_data):
        """Create a post with related topics and poll options"""
        topics_data = validated_data.pop('topics', [])
        media_files_data = validated_data.pop('media_files', [])
        poll_options_data = self.context.get('request').data.get('poll_options', [])
        
        # Create the post
        post = Post.objects.create(
            author=self.context['request'].user,
            **validated_data
        )
        
        # Add topics
        if topics_data:
            post.topics.set(topics_data)
            
        # Add media files
        if media_files_data:
            post.media_files.set(media_files_data)
            
        # Create poll options if post_type is poll
        if post.post_type == 'poll' and poll_options_data:
            for option_text in poll_options_data:
                PollOption.objects.create(
                    post=post,
                    option_text=option_text
                )
                
        return post
        
    def update(self, instance, validated_data):
        """Update a post with related topics and poll options"""
        topics_data = validated_data.pop('topics', None)
        media_files_data = validated_data.pop('media_files', None)
        
        # Update the post fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Mark as edited
        instance.is_edited = True
        instance.save()
        
        # Update topics if provided
        if topics_data is not None:
            instance.topics.set(topics_data)
            
        # Update media files if provided
        if media_files_data is not None:
            instance.media_files.set(media_files_data)
            
        return instance


class PostDetailSerializer(PostSerializer):
    """Serializer for post detail view with comments"""
    comments = serializers.SerializerMethodField()
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['comments']
        
    def get_comments(self, obj):
        """Get top-level comments on the post"""
        # Get top-level comments (no parent)
        comments = obj.comments.filter(parent=None).order_by('-created_at')[:5]
        return CommentSerializer(
            comments, 
            many=True, 
            context=self.context
        ).data


class SavedPostSerializer(serializers.ModelSerializer):
    """Serializer for saved posts"""
    post_data = PostSerializer(source='post', read_only=True)
    
    class Meta:
        model = SavedPost
        fields = ['id', 'user', 'post', 'post_data', 'saved_at']
        read_only_fields = ['user', 'saved_at']

    def create(self, validated_data):
        """Associate the saved post with the authenticated user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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
        
        # Check if user has already voted on this poll
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
        # Try to get profile image URL through the user's profile
        if hasattr(obj, 'profile') and hasattr(obj.profile, 'profile_image'):
            if obj.profile.profile_image:
                return obj.profile.profile_image.url
        return None