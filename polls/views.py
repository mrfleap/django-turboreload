from django.shortcuts import render
from django.http import HttpResponse

from . import slow_import

print("def")


def index(request):
    return HttpResponse("Hello, world2!")
