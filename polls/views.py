from django.shortcuts import render
from django.http import HttpResponse

from polls.constants import HELLO_MARK

from . import slow_import

CONSTANT = "Test!3"


def index(request):
    return HttpResponse(HELLO_MARK)


print("hi")
