from django.urls import reverse


def test_home(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200


def test_health_consulta_banco(client, db):
    response = client.get(reverse("core:health"))
    assert response.json() == {"status": "ok"}
