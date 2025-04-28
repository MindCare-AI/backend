# feeds/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from feeds.models import Post, Comment, Reaction, PollVote
from notifications.models import Notification, NotificationType
from django.core.cache import cache

import logging

logger = logging.getLogger(__name__)


def get_or_create_notification_type(type_id, type_name, description=""):
    """Helper function to get or create notification types with caching"""
    cache_key = f'notification_type_{type_id}'
    notification_type = cache.get(cache_key)
    
    if notification_type is None:
        notification_type, created = NotificationType.objects.get_or_create(
            id=type_id,
            defaults={
                'name': type_name,
                'description': description,
                'default_enabled': True,
                'is_global': True
            }
        )
        cache.set(cache_key, notification_type, timeout=3600)  # Cache for 1 hour
        
        if created:
            logger.info(f"Created new notification type: {type_name}")
            
    return notification_type


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
            # Here's the implementation with proper error handling for future use:
            # notification_type = get_or_create_notification_type(
            #     4, "new_post", "New post from followed user"
            # )
            # 
            # for follower in instance.author.followers.all():
            #     try:
            #         Notification.objects.create(
            #             user=follower,
            #             notification_type=notification_type,
            #             title=f"New post from {instance.author.get_full_name() or instance.author.username}",
            #             message=instance.content[:100],
            #             read=False,
            #         )
            #     except Exception as inner_e:
            #         logger.error(f"Error creating notification for follower {follower}: {str(inner_e)}")

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
                # Get or create notification type for comments
                comment_notification_type = get_or_create_notification_type(
                    2, "post_comment", "Comment on your post"
                )
                
                Notification.objects.create(
                    user=instance.post.author,
                    notification_type=comment_notification_type,
                    title=f"{instance.author.get_full_name() or instance.author.username} commented on your post",
                    message=instance.content[:100],  # Changed from 'content' to 'message'
                    read=False,  # Changed from 'is_read' to 'read'
                )
                
                # Clear cache for notification count
                cache.delete(f'user_notifications_{instance.post.author.id}')
                cache.delete(f'notification_count_{instance.post.author.id}')

            # If this is a reply, notify the parent comment author
            if instance.parent and instance.parent.author != instance.author:
                # Get or create notification type for replies
                reply_notification_type = get_or_create_notification_type(
                    3, "comment_reply", "Reply to your comment"
                )
                
                Notification.objects.create(
                    user=instance.parent.author,
                    notification_type=reply_notification_type,
                    title=f"{instance.author.get_full_name() or instance.author.username} replied to your comment",
                    message=instance.content[:100],  # Changed from 'content' to 'message'
                    read=False,  # Changed from 'is_read' to 'read'
                )
                
                # Clear cache for notification count
                cache.delete(f'user_notifications_{instance.parent.author.id}')
                cache.delete(f'notification_count_{instance.parent.author.id}')

        except Exception as e:
            logger.error(f"Error creating comment notification: {str(e)}", exc_info=True)


@receiver(post_save, sender=Reaction)
def notify_on_reaction(sender, instance, created, **kwargs):
    """
    Send notifications when a new reaction is added
    """
    try:
        content_object = instance.content_object

        # Skip if no content object or if user is reacting to their own content
        if not content_object or instance.user == getattr(
            content_object, "author", None
        ):
            return

        # Determine content type and create notification
        if hasattr(content_object, "author"):
            author = content_object.author

            # Determine if it's a post or comment
            is_post = hasattr(content_object, "post_type")
            content_type = "post" if is_post else "comment"

            # Get or create notification type for reactions
            reaction_notification_type = get_or_create_notification_type(
                1, "reaction", "Reaction to your content"
            )

            # Create notification only once per content and user
            Notification.objects.update_or_create(
                user=author,
                notification_type=reaction_notification_type,
                object_id=instance.object_id,
                content_type=instance.content_type,
                defaults={
                    "title": f"{instance.user.get_full_name() or instance.user.username} reacted to your {content_type}",
                    "message": f"{instance.user.get_full_name() or instance.user.username} reacted with {instance.reaction_type}",
                    "read": False,
                },
            )
            
            # Clear cache for notification count
            cache.delete(f'user_notifications_{author.id}')
            cache.delete(f'notification_count_{author.id}')
            
    except Exception as e:
        logger.error(f"Error creating reaction notification: {str(e)}", exc_info=True)


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

            # Get or create notification type for poll votes
            poll_notification_type = get_or_create_notification_type(
                5, "poll_vote", "Vote on your poll"
            )

            # Create notification
            Notification.objects.create(
                user=post.author,
                notification_type=poll_notification_type,
                title=f"{instance.user.get_full_name() or instance.user.username} voted on your poll",
                message=f"Option: {instance.poll_option.option_text[:50]}",
                read=False,
                metadata={
                    "poll_option_id": instance.poll_option.id,
                    "post_id": post.id
                }
            )
            
            # Clear cache for notification count
            cache.delete(f'user_notifications_{post.author.id}')
            cache.delete(f'notification_count_{post.author.id}')
            
        except Exception as e:
            logger.error(f"Error creating poll vote notification: {str(e)}", exc_info=True)
