from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from messaging.models.one_to_one import OneToOneConversation
from messaging.models.group import GroupConversation
from messaging.serializers.one_to_one import OneToOneConversationSerializer
from messaging.serializers.group import GroupConversationSerializer


class AllConversationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        one_to_one = OneToOneConversation.objects.filter(participants=user)
        groups = GroupConversation.objects.filter(participants=user)
        one_to_one_data = OneToOneConversationSerializer(
            one_to_one, many=True, context={"request": request}
        ).data
        groups_data = GroupConversationSerializer(
            groups, many=True, context={"request": request}
        ).data
        return Response({"one_to_one": one_to_one_data, "groups": groups_data})
