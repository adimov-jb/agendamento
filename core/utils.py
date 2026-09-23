from django.shortcuts import redirect, render


def responder_linha(request, template, contexto, url_lista):
    """Em requisições HTMX devolve só a linha atualizada; sem HTMX volta para a lista."""
    if request.htmx:
        return render(request, template, contexto)
    return redirect(url_lista)
