from playbook.models import Playbook, PlaybookSections, PlaybookSet, PlaybookAnswers, Project
from rest_framework import serializers


class PlaybookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playbook
        fields = "__all__"


class PlaybookSectionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookSections
        fields = "__all__"


class PlaybookSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookSet
        fields = "__all__"


class PlaybookAnswersSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookAnswers
        fields = "__all__"


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"
        