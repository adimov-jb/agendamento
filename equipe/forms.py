from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q

from catalogo.models import Procedimento
from core.forms import EstiloMixin

from .models import Profissional

User = get_user_model()


class ProfissionalForm(EstiloMixin, forms.ModelForm):
    """Cria/edita o profissional junto com o usuário de login (e-mail + senha)."""

    email = forms.EmailField(label="E-mail", help_text="Usado pelo profissional para entrar no sistema.")
    senha = forms.CharField(
        label="Senha inicial",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Profissional
        fields = ["nome", "email", "senha", "procedimentos"]
        widgets = {"procedimentos": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        editando = self.instance.pk is not None

        # Procedimentos inativos só aparecem se já estavam vinculados
        disponiveis = Q(ativo=True)
        if editando:
            self.fields["email"].initial = self.instance.usuario.email
            disponiveis |= Q(pk__in=self.instance.procedimentos.all())
        self.fields["procedimentos"].queryset = Procedimento.objects.filter(disponiveis)
        if not self.fields["procedimentos"].queryset.exists():
            self.fields["procedimentos"].help_text = "Nenhum procedimento ativo cadastrado ainda."

        if editando:
            self.fields["senha"].label = "Nova senha"
            self.fields["senha"].help_text = "Deixe em branco para manter a senha atual."
        else:
            self.fields["senha"].required = True
            self.fields["senha"].help_text = "Repasse ao profissional para o primeiro acesso."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existentes = User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.usuario_id)
        if existentes.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        if senha:
            validate_password(senha)
        return senha

    def save(self, commit=True):
        email, senha = self.cleaned_data["email"], self.cleaned_data["senha"]
        with transaction.atomic():
            usuario = self.instance.usuario if self.instance.pk else User(is_active=True)
            usuario.username = email
            usuario.email = email
            usuario.first_name = self.cleaned_data["nome"][:150]
            if senha:
                usuario.set_password(senha)
            usuario.save()
            self.instance.usuario = usuario
            profissional = super().save(commit=True)
        return profissional
