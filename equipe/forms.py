from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q

from catalogo.models import Procedimento
from core.forms import EstiloMixin
from core.permissions import GRUPO_GERENTE, eh_gerente

from .models import Profissional

User = get_user_model()


class ProfissionalForm(EstiloMixin, forms.ModelForm):
    """Cria/edita o profissional junto com o usuário de login (e-mail + senha).

    O e-mail de um gerente que ainda não é profissional reaproveita o login dele: um só cadastro, dois perfis.
    """

    email = forms.EmailField(label="E-mail", help_text="Usado pelo profissional para entrar no sistema.")
    senha = forms.CharField(
        label="Senha inicial",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    gerente = forms.BooleanField(
        label="Também é gerente",
        required=False,
        help_text="Com o mesmo login, escolhe ao entrar se quer usar a área do gerente ou a de profissional.",
    )

    class Meta:
        model = Profissional
        fields = ["nome", "email", "senha", "gerente", "procedimentos"]
        widgets = {"procedimentos": forms.CheckboxSelectMultiple}

    def __init__(self, *args, usuario_logado=None, **kwargs):
        super().__init__(*args, **kwargs)
        editando = self.instance.pk is not None
        self.usuario_existente = None

        if editando:
            usuario = self.instance.usuario
            self.fields["gerente"].initial = eh_gerente(usuario)
            if usuario.is_superuser:
                self.fields["gerente"].disabled = True
                self.fields["gerente"].help_text = "Administrador do sistema: é sempre gerente."
            elif usuario == usuario_logado:
                self.fields["gerente"].disabled = True
                self.fields["gerente"].help_text = "Você não pode remover o seu próprio acesso de gerente."

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
            self.fields["senha"].help_text = (
                "Repasse ao profissional para o primeiro acesso. "
                "Se o e-mail for de um gerente já cadastrado, deixe em branco: ele continua com a mesma senha."
            )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existentes = User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.usuario_id)
        existente = existentes.first()
        if existente is None:
            return email
        if self.instance.pk or existentes.count() > 1 or hasattr(existente, "profissional"):
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        # Gerente que passa a atender também: usa o mesmo login
        self.usuario_existente = existente
        return email

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        if senha:
            validate_password(senha)
        return senha

    def clean(self):
        dados = super().clean()
        if self.instance.pk:
            return dados
        if self.usuario_existente is not None:
            if dados.get("senha"):
                self.add_error("senha", "Este e-mail já tem login. Deixe em branco para manter a senha atual.")
        elif "senha" in dados and not dados["senha"]:
            self.add_error("senha", forms.Field.default_error_messages["required"])
        return dados

    def save(self, commit=True):
        email, senha = self.cleaned_data["email"], self.cleaned_data["senha"]
        with transaction.atomic():
            if self.instance.pk:
                usuario = self.instance.usuario
            else:
                usuario = self.usuario_existente or User(is_active=True)
            usuario.username = email
            usuario.email = email
            usuario.first_name = self.cleaned_data["nome"][:150]
            if senha:
                usuario.set_password(senha)
            usuario.save()
            if not self.fields["gerente"].disabled:
                grupo = Group.objects.get(name=GRUPO_GERENTE)
                if self.cleaned_data["gerente"]:
                    usuario.groups.add(grupo)
                elif self.usuario_existente is None:  # vincular um gerente não tira o acesso dele
                    usuario.groups.remove(grupo)
            self.instance.usuario = usuario
            profissional = super().save(commit=True)
        return profissional
