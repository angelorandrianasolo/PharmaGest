"""Pages communes (accueil et healthcheck)."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


@login_required
def home(request):
    return render(request, "home.html")


def health(request):
    """Endpoint simple utilisable par un monitoring ou un healthcheck Docker."""
    return JsonResponse({"statut": "ok", "application": "PharmaGest"})
