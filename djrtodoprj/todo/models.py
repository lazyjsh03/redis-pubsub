from django.db import models


class Todo(models.Model):
    work: models.CharField(max_length=100)
    done: models.BooleanField(default=False)
