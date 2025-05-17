from .views import (
    PlaybookViewSet,
    PlaybookSectionsViewSet,
    PlaybookSetViewSet,
    PlaybookAnswersViewSet,
    CreateProject,
    UpdateProject,
    AssignPlaybook
)
from django.urls import path

urlpatterns = [
    path("playbook/", PlaybookViewSet.as_view({"get": "list", "post": "create"})),
    path(
        "playbook/<int:pk>/",
        PlaybookViewSet.as_view(
            {"get": "retrieve", "put": "update", "delete": "destroy"}
        ),
    ),
    path(
        "playbook/sections/<int:playbook_id>/",
        PlaybookSectionsViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path("playbook/set/", PlaybookSetViewSet.as_view({"get": "list", "post": "create"})),
    path(
        "playbook/set/<int:pk>/",
        PlaybookSetViewSet.as_view(
            {"get": "retrieve", "put": "update", "delete": "destroy"}
        ),
    ),
    path(
        "playbook/answers/",
        PlaybookAnswersViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "playbook/answers/<int:pk>/",
        PlaybookAnswersViewSet.as_view(
            {"get": "retrieve", "put": "update", "delete": "destroy"}
        ),
    ),
    path("project/create/", CreateProject.as_view(), name="create_project"),
    path("project/update/<int:pk>/", UpdateProject.as_view(), name="update_project"),
    path("project/assign/", AssignPlaybook.as_view(), name="assign_playbook"),
]
