# feeds/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from feeds.models import Post, Comment, Reaction, PollVote
from notifications.models import Notification

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Post)
def notify_on_new_post(sender, instance, created, **kwargs):
    """
    Send notifications when a new post is created that might be relevant to users
    such as tagged users or followers of the topics
    """
    # Only process if this is a new post
    if created:
        try:
            logger.debug(f"New post created by {instance.author} (ID: {instance.id})")
            
            # TODO: Implement notifications when user connections are implemented
            # Notify followers of the post author
            # for follower in instance.author.followers.all():
            #     Notification.objects.create(
            #         user=follower,
            #         notification_type_id=4,  # New post from followed user
            #         title=f"New post from {instance.author.get_full_name() or instance.author.username}",
            #         content=instance.content[:100],
            #         is_read=False
            #     )
            
        except Exception as e:
            logger.error(f"Error creating post notification: {str(e)}")


@receiver(post_save, sender=Comment)
def notify_on_comment(sender, instance, created, **kwargs):
    """
    Send notifications when a new comment is created
    """
    if created:
        try:
            # Notify the post author if someone else commented
            if instance.post.author != instance.author:
                Notification.objects.create(
                    user=instance.post.author,
                    notification_type_id=2,  # Comment notification
                    title=f"{instance.author.get_full_name() or instance.author.username} commented on your post",
                    content=instance.content[:100],
                    is_read=False
                )
                
            # If this is a reply, notify the parent comment author
            if instance.parent and instance.parent.author != instance.author:
                Notification.objects.create(
                    user=instance.parent.author,
                    notification_type_id=3,  # Reply notification
                    title=f"{instance.author.get_full_name() or instance.author.username} replied to your comment",
                    content=instance.content[:100],
                    is_read=False
                )
                
        except Exception as e:
            logger.error(f"Error creating comment notification: {str(e)}")


@receiver(post_save, sender=Reaction)
def notify_on_reaction(sender, instance, created, **kwargs):
    """
    Send notifications when a new reaction is added
    """
    # Get the related object (post or comment)
    try:
        content_object = instance.content_object
        
        # Skip if no content object or if user is reacting to their own content
        if not content_object or instance.user == getattr(content_object, 'author', None):
            return
            
        # Determine content type and create notification
        if hasattr(content_object, 'author'):
            author = content_object.author
            
            # Determine if it's a post or comment
            is_post = hasattr(content_object, 'post_type')
            content_type = 'post' if is_post else 'comment'
            
            # Create notification only once per content and user
            Notification.objects.update_or_create(
                user=author,
                notification_type_id=1,  # Reaction notification
                defaults={
                    'title': f"{instance.user.get_full_name() or instance.user.username} reacted to your {content_type}",
                    'content': f"{instance.user.get_full_name() or instance.user.username} reacted with {instance.reaction_type}",
                    'is_read': False
                }
            )
    except Exception as e:
        logger.error(f"Error creating reaction notification: {str(e)}")


@receiver(post_save, sender=PollVote)
def notify_on_poll_vote(sender, instance, created, **kwargs):
    """
    Send notifications when a user votes on a poll
    """
    if created:
        try:
            post = instance.poll_option.post
            
            # Skip if user is voting on their own poll
            if instance.user == post.author:
                return
                
            # Create notification
            Notification.objects.create(
                user=post.author,
                notification_type_id=5,  # Poll vote notification
                title=f"{instance.user.get_full_name() or instance.user.username} voted on your poll",
                content=f"Option: {instance.poll_option.option_text[:50]}",
                is_read=False
            )
        except Exception as e:
            logger.error(f"Error creating poll vote notification: {str(e)}")