import datetime

from django import forms
from django.db import models
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from documents.models import AgentAccessRequest
from espace.models import DossierRequest

from .access import home_url_for
from .models import (
    BirthCertificate,
    DeathCertificate,
    LegislationExtract,
    MarriageCertificate,
    ServiceCertificate,
)

class AgentProfileForm(forms.ModelForm):
    """Nom affiché de l'agent. L'e-mail reste géré par l'administrateur : il sert à la connexion et au courrier."""

    first_name = forms.CharField(label=_('Prénom'), max_length=150)
    last_name = forms.CharField(label=_('Nom'), max_length=150)

    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name')


# Statuts pour lesquels l'usager doit recevoir une explication.
FINAL_STATUSES = {
    DossierRequest.Status.APPROVED,
    DossierRequest.Status.REJECTED,
    DossierRequest.Status.COMPLETED,
}


class ConnexionForm(AuthenticationForm):
    """Connexion commune : seuls les administrateurs et les agents (avec un guichet) peuvent entrer."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': _('Identifiant ou mot de passe incorrect.'),
        'no_role': _(
            "Ce compte n'a pas encore de rôle. Attendez que l'administrateur valide "
            "votre demande d'accès et vous attribue un guichet."
        ),
        'pending': _(
            "Votre demande d'accès est en attente de validation par l'administrateur. "
            "Vous pourrez vous connecter dès qu'elle sera acceptée."
        ),
        'rejected': _("Votre demande d'accès a été refusée par l'administrateur."),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].label = _("E-mail ou nom d'utilisateur")

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as error:
            # Identifiants refusés : si c'est l'e-mail d'une demande d'accès, on explique où elle en est.
            if getattr(error, 'code', None) == 'invalid_login':
                identifier = (self.cleaned_data.get('username') or '').strip()
                latest = (
                    AgentAccessRequest.objects.filter(email__iexact=identifier, agent_user=None)
                    .order_by('-created_at').first()
                    if identifier else None
                )
                if latest and latest.status == AgentAccessRequest.Status.PENDING:
                    raise forms.ValidationError(self.error_messages['pending'], code='pending') from error
                if latest and latest.status == AgentAccessRequest.Status.REJECTED:
                    raise forms.ValidationError(self.error_messages['rejected'], code='rejected') from error
            raise

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if home_url_for(user) is None:
            raise forms.ValidationError(self.error_messages['no_role'], code='no_role')


class DecisionForm(forms.ModelForm):
    """Traitement d'une demande par l'agent : statut et réponse à l'usager."""

    class Meta:
        model = DossierRequest
        fields = ['status', 'response_message']
        widgets = {
            'response_message': forms.Textarea(attrs={'rows': 6, 'maxlength': 4000}),
        }
        labels = {
            'status': _('Statut de la demande'),
            'response_message': _("Réponse à l'usager"),
        }
        help_texts = {
            'response_message': _("Elle apparaît dans les notifications de l'usager."),
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        message = (cleaned.get('response_message') or '').strip()
        cleaned['response_message'] = message
        if status in FINAL_STATUSES and not message:
            self.add_error(
                'response_message',
                "Écrivez une réponse à l'usager pour une demande approuvée, refusée ou terminée.",
            )
        return cleaned


class AgentSignupForm(forms.Form):
    """Demande d'accès d'un agent : il choisit ses identifiants ; l'administrateur valide et attribue le guichet."""

    last_name = forms.CharField(label=_('Nom'), max_length=100)
    first_name = forms.CharField(label=_('Prénom'), max_length=100)
    email = forms.EmailField(label='E-mail', max_length=150, help_text=_('Ce sera votre identifiant de connexion.'))
    password1 = forms.CharField(label=_('Mot de passe'), strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label=_('Confirmer le mot de passe'), strip=False, widget=forms.PasswordInput)

    AUTOCOMPLETE = {
        'last_name': 'family-name', 'first_name': 'given-name', 'email': 'email',
        'password1': 'new-password', 'password2': 'new-password',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['placeholder'] = field.label
            if name in self.AUTOCOMPLETE:
                field.widget.attrs['autocomplete'] = self.AUTOCOMPLETE[name]

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        User = get_user_model()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('Un compte existe déjà avec cet e-mail.'))
        pending = AgentAccessRequest.objects.filter(
            email__iexact=email, status=AgentAccessRequest.Status.PENDING,
        )
        if pending.exists():
            raise forms.ValidationError(_('Une demande avec cet e-mail attend déjà la validation.'))
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', _('Les deux mots de passe ne correspondent pas.'))
        elif password1:
            candidate = get_user_model()(
                username=cleaned.get('email', ''), email=cleaned.get('email', ''),
                first_name=cleaned.get('first_name', ''), last_name=cleaned.get('last_name', ''),
            )
            try:
                password_validation.validate_password(password1, candidate)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        return cleaned

    def save(self):
        data = self.cleaned_data
        return AgentAccessRequest.objects.create(
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            email=data['email'],
            phone_number='',
            request_type='AGENT_ACCESS',
            password_hash=make_password(data['password1']),
        )


# ---------------------------------------------------------------------------
# Documents officiels (un formulaire par guichet, même socle)
# ---------------------------------------------------------------------------

REGISTRATION_SECTION = (_('Enregistrement'), ('region', 'district', 'commune', 'act_datetime'))


def _fields(sections):
    return [name for _, names in sections for name in names]


class OfficialDocumentForm(forms.ModelForm):
    """
    Socle des formulaires de documents : champs regroupés par rubrique (SECTIONS),
    dates au format des champs HTML (date, datetime-local), choix courts en boutons radio.
    """

    SECTIONS = ()
    RADIO_FIELDS = ()
    TEXTAREA_ROWS = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            model_field = self._meta.model._meta.get_field(name)
            if isinstance(model_field, models.DateTimeField):
                field.widget = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
                field.input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S']
            elif isinstance(model_field, models.DateField):
                field.widget = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
            elif isinstance(model_field, models.TextField):
                field.widget = forms.Textarea(attrs={'rows': self.TEXTAREA_ROWS})
            if name in self.RADIO_FIELDS:
                field.widget = forms.RadioSelect(choices=[c for c in field.choices if c[0] != ''])

    def sections(self):
        return [(title, [self[name] for name in names]) for title, names in self.SECTIONS]

    # Contrôles communs
    def _not_future(self, cleaned, name, message):
        value = cleaned.get(name)
        if value is None:
            return
        now = timezone.now() if isinstance(value, datetime.datetime) else timezone.localdate()
        limit = now + datetime.timedelta(minutes=5) if isinstance(value, datetime.datetime) else now
        if value > limit:
            self.add_error(name, message)

    def _before(self, cleaned, earlier, later, message, error_on=None):
        """`earlier` doit précéder `later` (dates ou dates-heures) ; l'erreur s'affiche sous `error_on`."""
        first, second = cleaned.get(earlier), cleaned.get(later)
        if first is None or second is None:
            return
        target = error_on or earlier
        if isinstance(first, datetime.datetime) != isinstance(second, datetime.datetime):
            first = first.date() if isinstance(first, datetime.datetime) else first
            second = second.date() if isinstance(second, datetime.datetime) else second
            if first >= second:
                self.add_error(target, message)
        elif first > second:
            self.add_error(target, message)

    def clean(self):
        cleaned = super().clean()
        self._not_future(cleaned, 'act_datetime', _("La date de l'acte ne peut pas être dans le futur."))
        return cleaned


# Guichet 1 -----------------------------------------------------------------

BIRTH_SECTIONS = (
    REGISTRATION_SECTION,
    (_("Informations sur l'enfant"), ('child_last_name', 'child_first_names', 'child_sex', 'birth_datetime', 'birth_place')),
    (_('Père'), ('father_full_name', 'father_birth_date', 'father_birth_place', 'father_profession', 'father_address')),
    (_('Mère'), ('mother_full_name', 'mother_birth_date', 'mother_birth_place', 'mother_profession', 'mother_address')),
    (_('Déclaration et délivrance'), (
        'declarant_name', 'declarant_relationship', 'registrar_name', 'registrar_title', 'marginal_notes',
    )),
)


class BirthCertificateForm(OfficialDocumentForm):
    SECTIONS = BIRTH_SECTIONS
    RADIO_FIELDS = ('child_sex',)

    class Meta:
        model = BirthCertificate
        fields = _fields(BIRTH_SECTIONS)
        help_texts = {
            'father_full_name': _("Laissez vide si la filiation paternelle n'est pas établie."),
            'child_first_names': _('Séparez les prénoms par une virgule : « Lucas, Alexandre ».'),
        }

    def clean(self):
        cleaned = super().clean()
        self._not_future(cleaned, 'birth_datetime', _('La date de naissance ne peut pas être dans le futur.'))
        self._before(cleaned, 'birth_datetime', 'act_datetime', _("L'acte ne peut pas être dressé avant la naissance."), error_on='act_datetime')
        for parent in ('father', 'mother'):
            self._before(cleaned, f'{parent}_birth_date', 'birth_datetime',
                         "Doit être antérieure à la naissance de l'enfant.")
        father_details = any(cleaned.get(f'father_{f}') for f in ('birth_date', 'birth_place', 'profession', 'address'))
        if father_details and not cleaned.get('father_full_name'):
            self.add_error('father_full_name', _('Indiquez le nom du père (ou videz ses autres champs).'))
        return cleaned


# Guichet 2 -----------------------------------------------------------------

MARRIAGE_SECTIONS = (
    REGISTRATION_SECTION,
    (_('Célébration'), ('marriage_datetime', 'marriage_place', 'matrimonial_regime')),
    (_("L'époux"), (
        'husband_last_name', 'husband_first_names', 'husband_birth_date', 'husband_birth_place',
        'husband_profession', 'husband_address',
        'husband_father_name', 'husband_father_profession', 'husband_mother_name', 'husband_mother_profession',
    )),
    (_("L'épouse"), (
        'wife_last_name', 'wife_first_names', 'wife_birth_date', 'wife_birth_place',
        'wife_profession', 'wife_address',
        'wife_father_name', 'wife_father_profession', 'wife_mother_name', 'wife_mother_profession',
    )),
    (_('Témoins'), ('witness1_name', 'witness1_details', 'witness2_name', 'witness2_details')),
    (_('Délivrance'), ('registrar_name', 'registrar_title', 'marginal_notes')),
)


class MarriageCertificateForm(OfficialDocumentForm):
    SECTIONS = MARRIAGE_SECTIONS

    class Meta:
        model = MarriageCertificate
        fields = _fields(MARRIAGE_SECTIONS)
        widgets = {'matrimonial_regime': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cleaned = super().clean()
        self._not_future(cleaned, 'marriage_datetime', _('La date du mariage ne peut pas être dans le futur.'))
        self._before(cleaned, 'marriage_datetime', 'act_datetime', _("L'acte ne peut pas être dressé avant le mariage."), error_on='act_datetime')
        for spouse in ('husband', 'wife'):
            self._before(cleaned, f'{spouse}_birth_date', 'marriage_datetime',
                         _('Doit être antérieure à la date du mariage.'))
        return cleaned


# Guichet 3 -----------------------------------------------------------------

DEATH_SECTIONS = (
    REGISTRATION_SECTION,
    (_('Le défunt'), (
        'deceased_last_name', 'deceased_first_names', 'deceased_sex', 'deceased_birth_date',
        'deceased_birth_place', 'deceased_profession', 'deceased_address',
    )),
    (_('Situation familiale'), (
        'marital_status', 'spouse_name', 'father_name', 'father_deceased', 'mother_name', 'mother_deceased',
    )),
    (_('Décès'), ('death_datetime', 'death_place')),
    (_('Déclaration et délivrance'), (
        'declarant_name', 'declarant_age', 'declarant_profession', 'declarant_relationship', 'declarant_address',
        'registrar_name', 'registrar_title', 'marginal_notes',
    )),
)


class DeathCertificateForm(OfficialDocumentForm):
    SECTIONS = DEATH_SECTIONS
    RADIO_FIELDS = ('deceased_sex',)

    class Meta:
        model = DeathCertificate
        fields = _fields(DEATH_SECTIONS)

    def clean(self):
        cleaned = super().clean()
        self._not_future(cleaned, 'death_datetime', _('La date du décès ne peut pas être dans le futur.'))
        self._before(cleaned, 'death_datetime', 'act_datetime', _("L'acte ne peut pas être dressé avant le décès."), error_on='act_datetime')
        self._before(cleaned, 'deceased_birth_date', 'death_datetime', _('Doit être antérieure à la date du décès.'))
        age = cleaned.get('declarant_age')
        if age is not None and not 10 <= age <= 120:
            self.add_error('declarant_age', _('Âge invalide.'))
        return cleaned


# Guichet 4 -----------------------------------------------------------------

LEGISLATION_SECTIONS = (
    REGISTRATION_SECTION,
    (_('Texte'), ('text_type', 'text_number', 'text_date', 'subject')),
    (_('Extrait certifié'), ('content',)),
    (_('Délivrance'), ('recipient_name', 'registrar_name', 'registrar_title')),
)


class LegislationExtractForm(OfficialDocumentForm):
    SECTIONS = LEGISLATION_SECTIONS
    TEXTAREA_ROWS = 8

    class Meta:
        model = LegislationExtract
        fields = _fields(LEGISLATION_SECTIONS)

    def clean(self):
        cleaned = super().clean()
        self._not_future(cleaned, 'text_date', _('La date du texte ne peut pas être dans le futur.'))
        self._before(cleaned, 'text_date', 'act_datetime', _("L'extrait ne peut pas précéder le texte."), error_on='act_datetime')
        return cleaned


# Guichet 5 -----------------------------------------------------------------

SERVICE_SECTIONS = (
    REGISTRATION_SECTION,
    (_('Service'), ('service', 'nature')),
    (_('Bénéficiaire'), ('holder_full_name', 'holder_national_id', 'holder_address')),
    (_('Objet'), ('subject', 'reference', 'location', 'amount', 'valid_until')),
    (_('Délivrance'), ('registrar_name', 'registrar_title', 'observations')),
)


class ServiceCertificateForm(OfficialDocumentForm):
    SECTIONS = SERVICE_SECTIONS

    class Meta:
        model = ServiceCertificate
        fields = _fields(SERVICE_SECTIONS)

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount')
        if amount is not None and amount < 0:
            self.add_error('amount', _('Le montant ne peut pas être négatif.'))
        self._before(cleaned, 'act_datetime', 'valid_until', _("La date de validité doit suivre la date de l'acte."),
                     error_on='valid_until')
        return cleaned
