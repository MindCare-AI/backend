from django.contrib import admin
from .models.one_to_one import OneToOneConversation, OneToOneMessage
from .models.group import GroupConversation, GroupMessage

admin.site.register(OneToOneConversation)
admin.site.register(OneToOneMessage)
admin.site.register(GroupConversation)
admin.site.register(GroupMessage)
