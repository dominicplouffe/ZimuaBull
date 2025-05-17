from rest_framework import viewsets
from playbook.models import (
    Playbook,
    PlaybookSections,
    PlaybookSet,
    PlaybookAnswers,
    Project,
)
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from playbook.serializers import (
    PlaybookSerializer,
    PlaybookSectionsSerializer,
    PlaybookSetSerializer,
    PlaybookAnswersSerializer,
    ProjectSerializer,
)


class PlaybookViewSet(viewsets.ModelViewSet):
    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer
    permission_classes = [IsAuthenticated]


class PlaybookSectionsViewSet(viewsets.ModelViewSet):
    queryset = PlaybookSections.objects.all()
    serializer_class = PlaybookSectionsSerializer
    permission_classes = [IsAuthenticated]

    # Create filter for sections on playbook_id from URL path i.e. /playbook/sections/<int:playbook_id>/
    def get_queryset(self):
        queryset = PlaybookSections.objects.all()
        playbook_id = self.kwargs.get("playbook_id")
        if playbook_id:
            return queryset.filter(playbook=playbook_id)

        return queryset.none()


class PlaybookSetViewSet(viewsets.ModelViewSet):
    queryset = PlaybookSet.objects.all()
    serializer_class = PlaybookSetSerializer
    permission_classes = [IsAuthenticated]


class PlaybookAnswersViewSet(viewsets.ModelViewSet):
    queryset = PlaybookAnswers.objects.all()
    serializer_class = PlaybookAnswersSerializer
    permission_classes = [IsAuthenticated]


class CreateProject(APIView):
    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        project_name = request.data.get("project_name")
        project_description = request.data.get("project_name")

        project, _ = Project.objects.create(
            name=project_name, description=project_description, user=user
        )

        serializer = ProjectSerializer(project)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class UpdateProject(APIView):
    @method_decorator(login_required)
    def put(self, request, pk):
        project = Project.objects.get(pk=pk)
        project_name = request.data.get("project_name")
        project_description = request.data.get("project_name")

        project.name = project_name
        project.description = project_description
        project.save()

        serializer = ProjectSerializer(project)

        return Response(serializer.data, status=status.HTTP_200_OK)
    

class AssignPlaybook(APIView):
    @method_decorator(login_required)
    def post(self, request):
        project_id = request.data.get("project_id")
        playbook_id = request.data.get("playbook_id")
        playbook_set_name = request.data.get("playbook_set_name")
        playbook_set_description = request.data.get("playbook_set_description")

        project = Project.objects.get(pk=project_id)
        playbook = Playbook.objects.get(pk=playbook_id)

        playbook_set, _ = PlaybookSet.objects.create(
            project=project,
            playbook=playbook,
            name=playbook_set_name,
            description=playbook_set_description,
        )

        sections = PlaybookSections.objects.filter(playbook=playbook)
        for section in sections:
            PlaybookAnswers.objects.create(
                playbook=playbook,
                playbook_set=playbook_set,
                project=project,
                section=section,
            )
