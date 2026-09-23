from django.conf import settings


def app(request):
    return {"APP_NAME": settings.APP_NAME}
