from django.db import models
from django.contrib.auth.models import User


class Playbook(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PlaybookSections(models.Model):
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE)
    step_number = models.IntegerField()
    section_name = models.CharField(max_length=255, null=False, blank=False)
    section_category = models.CharField(max_length=255, null=False, blank=False)
    section_question = models.TextField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.playbook.name} - Step {self.section_name} ({self.step_number})"


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class PlaybookSet(models.Model):
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PlaybookAnswers(models.Model):
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    playbook_set = models.ForeignKey(PlaybookSet, on_delete=models.CASCADE)
    section = models.ForeignKey(PlaybookSections, on_delete=models.CASCADE)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.playbook.name} - {self.section.section_name} ({self.section.step_number})"
