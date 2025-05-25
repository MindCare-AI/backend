from rest_framework import serializers


class OneToOneConversationMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField(default="one_to_one")


class GroupConversationMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField(default="group")


class AllConversationsSerializer(serializers.Serializer):
    one_to_one = OneToOneConversationMinimalSerializer(many=True)
    groups = GroupConversationMinimalSerializer(many=True)
