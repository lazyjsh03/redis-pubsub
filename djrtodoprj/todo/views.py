from django.shortcuts import render
from .tasks import get, add, update, remove
from rest_framework.response import Response
from .cache_function import getAllKey, getKey
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from django.http import HttpResponse
from rest_framework import status, viewsets


class TodoViewSet(viewsets.ViewSet):
    def get(self, request):
        data = get()
        return Response(data)

    def add(self, request):
        data = add(request)
        return Response(data)

    def update(self, request, pk=None):
        data = update(request, pk)
        return Response(data)

    def remove(self, request, pk=None):
        data = remove(request, pk)
        return Response(data)

    def getCache(self, request, key="*"):
        return Response(getAllKey(key))

    def getKey(self, request, key="*"):
        return Response(getKey(key))
