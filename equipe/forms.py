from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q

from catalogo.models import Procedimento
from core.forms import EstiloMixin

from .models import Convite, Profissional

User = get_user_model()


def usuarios_com_email(email):
    return User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))


def _procedimentos(estabelecimento, vinculados=()):
    """Procedimentos ativos do estabelecimento; inativos só aparecem se já estavam vinculados."""
    return Procedimento.objects.filter(estabelecimento=estabelecimento).filter(
        Q(ativo=True) | Q(pk__in=vinculados)
    )


class ConviteForm(EstiloMixin, forms.ModelForm):
    """Cadastro de um novo profissional: gera um convite que vai por e-mail."""

    class Meta:
        model = Convite
        fields = ["nome", "email", "gerente", "procedimentos"]
        widgets = {"procedimentos": forms.CheckboxSelectMultiple}
        help_texts = {
            "email": "O convite vai para este e-mail. Com ele, o profissional cria a senha ou usa o login que já tem.",
            "gerente": "Com o mesmo login, escolhe ao entrar se quer usar a área do gerente ou a de profissional.",
        }

    def __init__(self, *args, estabelecimento, usuario_logado, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.estabelecimento = estabelecimento
        self.instance.criado_por = usuario_logado
        self.usuario_logado = usuario_logado
        self.fields["procedimentos"].queryset = _procedimentos(estabelecimento)
        if not self.fields["procedimentos"].queryset.exists():
            self.fields["procedimentos"].help_text = "Nenhum procedimento ativo cadastrado ainda."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        estabelecimento = self.instance.estabelecimento
        mesmo_email = Q(usuario__username__iexact=email) | Q(usuario__email__iexact=email)
        if estabelecimento.profissionais.filter(mesmo_email).exists():
            raise forms.ValidationError("Este e-mail já é de um profissional deste estabelecimento.")
        if estabelecimento.convites.filter(email=email, aceito_em__isnull=True).exists():
            raise forms.ValidationError(
                "Já existe um convite pendente para este e-mail. Reenvie-o na lista de profissionais."
            )
        return email

    @property
    def para_si_mesmo(self):
        """O gerente cadastrando a si mesmo como profissional: não precisa de convite."""
        return usuarios_com_email(self.cleaned_data["email"]).filter(pk=self.usuario_logado.pk).exists()


class ProfissionalForm(EstiloMixin, forms.ModelForm):
    """Edição de um profissional do estabelecimento. Login e senha são de cada um."""

    gerente = forms.BooleanField(
        label="Também é gerente",
        required=False,
        help_text="Com o mesmo login, escolhe ao entrar se quer usar a área do gerente ou a de profissional.",
    )

    class Meta:
        model = Profissional
        fields = ["nome", "gerente", "procedimentos"]
        widgets = {"procedimentos": forms.CheckboxSelectMultiple}

    def __init__(self, *args, usuario_logado, **kwargs):
        super().__init__(*args, **kwargs)
        estabelecimento, usuario = self.instance.estabelecimento, self.instance.usuario
        self.fields["nome"].help_text = f"Login: {usuario.email or usuario.username}"
        self.fields["gerente"].initial = estabelecimento.gerentes.filter(pk=usuario.pk).exists()
        if usuario == usuario_logado:
            self.fields["gerente"].disabled = True
            self.fields["gerente"].help_text = "Você não pode remover o seu próprio acesso de gerente."
        self.fields["procedimentos"].queryset = _procedimentos(estabelecimento, self.instance.procedimentos.all())
        if not self.fields["procedimentos"].queryset.exists():
            self.fields["procedimentos"].help_text = "Nenhum procedimento ativo cadastrado ainda."

    def save(self, commit=True):
        with transaction.atomic():
            profissional = super().save(commit=True)
            if not self.fields["gerente"].disabled:
                gerentes = profissional.estabelecimento.gerentes
                if self.cleaned_data["gerente"]:
                    gerentes.add(profissional.usuario)
                else:
                    gerentes.remove(profissional.usuario)
        return profissional


class CadastroConviteForm(EstiloMixin, forms.Form):
    """Quem recebeu o convite e ainda não tem login cria a senha."""

    nome = forms.CharField(label="Seu nome", max_length=150)
    senha = forms.CharField(
        label="Senha", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    confirmacao = forms.CharField(
        label="Repita a senha", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def __init__(self, *args, email, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email

    def clean(self):
        dados = super().clean()
        senha, confirmacao = dados.get("senha"), dados.get("confirmacao")
        if senha and confirmacao:
            if senha != confirmacao:
                self.add_error("confirmacao", "As senhas não conferem.")
            else:
                try:
                    validate_password(
                        senha, User(username=self.email, email=self.email, first_name=dados.get("nome", ""))
                    )
                except forms.ValidationError as erro:
                    self.add_error("senha", erro)
        return dados

    def criar_usuario(self):
        return User.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.cleaned_data["senha"],
            first_name=self.cleaned_data["nome"],
        )
