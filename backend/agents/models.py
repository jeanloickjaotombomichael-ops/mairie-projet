"""Rôle des agents municipaux (un compte, un guichet) et documents officiels établis aux guichets."""
import datetime
import decimal
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.text import slugify

from .guichets import GUICHET_CHOICES, GUICHETS


class AgentProfile(models.Model):
    """Rattache un compte (non staff) à son guichet ; attribué par l'administrateur."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_profile', verbose_name=_('compte'),
    )
    guichet = models.PositiveSmallIntegerField(_('guichet'), choices=GUICHET_CHOICES)
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    # Dernière consultation des notifications : les demandes reçues après sont « nouvelles ».
    notifications_seen_at = models.DateTimeField(_('notifications vues le'), null=True, blank=True, editable=False)

    class Meta:
        ordering = ['guichet', 'user__last_name']
        verbose_name = _('agent municipal')
        verbose_name_plural = _('agents municipaux')

    def __str__(self):
        name = self.user.get_full_name() or self.user.get_username()
        return f'{name} — Guichet {self.guichet}'

    @property
    def guichet_info(self):
        return GUICHETS[self.guichet]


DEFAULT_MARGINAL_NOTES = (
    'Sans objet. (Aucune mention ultérieure enregistrée à la date de délivrance de la présente copie).'
)


class OfficialDocument(models.Model):
    """
    Socle commun des documents officiels établis aux guichets.

    Le document est « scellé » à sa création : empreinte SHA-256 de son contenu
    (SEALED_FIELDS) + signature HMAC (clé du serveur). Il n'est plus modifiable
    ensuite ; toute altération en base est détectée à la vérification
    (QR code → /verifier/<id> sur le site). L'agent peut l'envoyer à l'usager de
    la demande d'origine ; la suppression est demandée par l'agent et décidée
    par l'administrateur.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Valide')
        REVOKED = 'REVOKED', _('Révoqué')
    # À définir par chaque document.
    PREFIX = ''            # numéro : « 2026-<PREFIX>-00001 »
    DOCUMENT_CODE = ''     # type renvoyé par la vérification publique
    SEALED_FIELDS = ()     # contenu propre au document (s'ajoute à COMMON_SEALED_FIELDS)
    # Champs ajoutés après la mise en service : scellés seulement s'ils sont remplis, pour que
    # l'empreinte des documents établis avant leur ajout reste valide.
    LATE_SEALED_FIELDS = ()
    COMMON_SEALED_FIELDS = ('act_number', 'region', 'district', 'commune', 'act_datetime')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    act_number = models.CharField(_("numéro d'acte"), max_length=30, unique=True, editable=False)

    # Lieu et date d'établissement
    region = models.CharField(_('région'), max_length=150, default='Boeny')
    district = models.CharField(_('district'), max_length=150, default='Mahajanga I')
    commune = models.CharField(_('commune'), max_length=150, default='Commune Urbaine de Mahajanga')
    act_datetime = models.DateTimeField(_("date et heure de l'acte"), default=timezone.now)

    # Traçabilité
    request = models.ForeignKey(
        'espace.DossierRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_("demande d'origine"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('établi par'),
    )
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    status = models.CharField(_('statut'), max_length=10, choices=Status.choices, default=Status.ACTIVE)
    # Envoi à l'usager : le document devient téléchargeable depuis ses notifications (espace usager).
    sent_at = models.DateTimeField(_("envoyé à l'usager le"), null=True, blank=True, editable=False)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('envoyé par'), editable=False,
    )
    # Retrait au guichet : l'agent a scanné le bon de retrait et remis le document officiel.
    # Le bon ne sert alors plus (son QR code n'est plus affiché ni téléchargeable).
    retrieved_at = models.DateTimeField(_('remis au guichet le'), null=True, blank=True, editable=False)
    retrieved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('remis par'), editable=False,
    )
    # Suppression : l'agent la demande (avec un motif), l'administrateur l'accepte ou la refuse.
    deletion_requested_at = models.DateTimeField(_('suppression demandée le'), null=True, blank=True, editable=False)
    deletion_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('suppression demandée par'), editable=False,
    )
    deletion_reason = models.TextField(_('motif de la suppression'), blank=True, editable=False)
    # Suppression acceptée par l'administrateur : le document est masqué mais conservé (numéro jamais
    # réattribué, le QR code d'une copie déjà imprimée indique « révoqué »).
    deleted_at = models.DateTimeField(_('supprimé le'), null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('supprimé par'), editable=False,
    )

    # Sécurité
    content_hash = models.CharField(_('empreinte SHA-256'), max_length=64, editable=False)
    signature = models.CharField(_('signature HMAC-SHA256'), max_length=64, editable=False)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return f'{self._meta.verbose_name.capitalize()} N° {self.act_number} — {self.holder_name}'

    # -- À définir par chaque document --------------------------------------

    @property
    def holder_name(self):
        """Personne (ou objet) principale du document, pour les listes et la vérification."""
        raise NotImplementedError

    @property
    def main_date(self):
        """Date principale (naissance, mariage, décès, texte…), pour les listes."""
        return self.act_datetime

    @property
    def document_title(self):
        """Titre imprimé en tête du PDF."""
        return self._meta.verbose_name.upper()

    # -- États ----------------------------------------------------------------

    @property
    def place_name(self):
        for prefix in ('Commune Urbaine de ', 'Commune Rurale de ', 'Commune de '):
            if self.commune.startswith(prefix):
                return self.commune[len(prefix):]
        return self.commune

    @property
    def label(self):
        return f'{self._meta.verbose_name.capitalize()} N° {self.act_number}'

    @property
    def filename(self):
        return f'{slugify(self._meta.verbose_name)}-{self.act_number}.pdf'

    @property
    def downloadable_by_requester(self):
        """L'usager peut télécharger son bon de retrait (envoyé, pas encore retiré, ni supprimé ni révoqué)."""
        return (
            self.request_id is not None and self.sent_at is not None and self.retrieved_at is None
            and self.deleted_at is None and self.status == self.Status.ACTIVE
        )

    @property
    def ticket_filename(self):
        return f'bon-de-retrait-{self.act_number}.pdf'

    @property
    def deletion_pending(self):
        return self.deletion_requested_at is not None and self.deleted_at is None

    # -- Sécurité ---------------------------------------------------------------

    def sealed_fields(self):
        return self.COMMON_SEALED_FIELDS + tuple(self.SEALED_FIELDS)

    def canonical_payload(self):
        """Contenu du document sous une forme stable (clés triées, dates ISO en UTC)."""
        data = {'id': str(self.id)}
        names = list(self.sealed_fields())
        names += [name for name in self.LATE_SEALED_FIELDS if getattr(self, name) not in (None, '', False)]
        for name in names:
            value = getattr(self, name)
            if isinstance(value, datetime.datetime):
                value = value.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat()
            elif isinstance(value, datetime.date):
                value = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                value = f'{value:.2f}'
            data[name] = value if value is not None else ''
        return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

    def compute_hash(self):
        return hashlib.sha256(self.canonical_payload().encode('utf-8')).hexdigest()

    @staticmethod
    def compute_signature(content_hash):
        key = settings.DOCUMENT_SIGNING_KEY.encode('utf-8')
        return hmac.new(key, (content_hash or '').encode('utf-8'), hashlib.sha256).hexdigest()

    @classmethod
    def next_act_number(cls, year):
        prefix = f'{year}-{cls.PREFIX}-'
        last = (
            cls.objects.filter(act_number__startswith=prefix)
            .order_by('-act_number').values_list('act_number', flat=True).first()
        )
        sequence = int(last.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{sequence:05d}'

    def save(self, *args, **kwargs):
        if self._state.adding and not self.content_hash:
            # Secondes seulement : l'empreinte doit être recalculable à l'identique.
            for name in self.sealed_fields():
                value = getattr(self, name)
                if isinstance(value, datetime.datetime):
                    setattr(self, name, value.replace(microsecond=0))
            if not self.act_number:
                self.act_number = self.next_act_number(timezone.localtime(self.act_datetime).year)
            self.content_hash = self.compute_hash()
            self.signature = self.compute_signature(self.content_hash)
        super().save(*args, **kwargs)

    def verify(self):
        """Même résultat que Document.verify_authenticity() (utilisé par la vérification publique)."""
        hash_matches = hmac.compare_digest(self.compute_hash(), self.content_hash or '')
        signature_valid = hmac.compare_digest(
            self.compute_signature(self.content_hash), self.signature or '',
        )
        if self.status == self.Status.REVOKED or self.deleted_at is not None:
            status = 'REVOKED'
        elif not (hash_matches and signature_valid):
            status = 'INVALID'
        else:
            status = 'VALID'
        return {
            'is_authentic': status == 'VALID',
            'hash_matches': hash_matches,
            'signature_valid': signature_valid,
            'status': status,
        }

    @property
    def verification_url(self):
        """Adresse du QR code du bon de retrait : page de vérification réservée aux agents."""
        return f'{settings.BACKEND_URL}/verifier/{self.id}/'


class Sex(models.TextChoices):
    MALE = 'M', _('Masculin')
    FEMALE = 'F', _('Féminin')
# ---------------------------------------------------------------------------
# Guichet 1 — Actes de naissance
# ---------------------------------------------------------------------------

class BirthCertificate(OfficialDocument):
    PREFIX = 'NAI'
    DOCUMENT_CODE = 'BIRTH_CERTIFICATE'
    Sex = Sex

    child_last_name = models.CharField(_("nom de famille de l'enfant"), max_length=150)
    child_first_names = models.CharField(_("prénoms de l'enfant"), max_length=200)
    child_sex = models.CharField(_('sexe'), max_length=1, choices=Sex.choices)
    birth_datetime = models.DateTimeField(_('date et heure de naissance'))
    birth_place = models.CharField(_('lieu de naissance'), max_length=200)

    # Père (facultatif : filiation paternelle non établie)
    father_full_name = models.CharField(_('nom complet du père'), max_length=200, blank=True)
    father_birth_date = models.DateField(_('date de naissance du père'), null=True, blank=True)
    father_birth_place = models.CharField(_('lieu de naissance du père'), max_length=200, blank=True)
    father_profession = models.CharField(_('profession du père'), max_length=150, blank=True)
    father_address = models.CharField(_('domicile du père'), max_length=255, blank=True)

    # Mère
    mother_full_name = models.CharField(_('nom complet de la mère'), max_length=200)
    mother_birth_date = models.DateField(_('date de naissance de la mère'))
    mother_birth_place = models.CharField(_('lieu de naissance de la mère'), max_length=200)
    mother_profession = models.CharField(_('profession de la mère'), max_length=150, blank=True)
    mother_address = models.CharField(_('domicile de la mère'), max_length=255)

    # Déclaration et délivrance
    declarant_name = models.CharField(_('nom du déclarant'), max_length=200)
    declarant_relationship = models.CharField(
        _('qualité du déclarant'), max_length=150, help_text=_("Ex. : le père de l'enfant, la sage-femme…"),
    )
    registrar_name = models.CharField(_("nom de l'officier d'état civil"), max_length=200)
    registrar_title = models.CharField(
        _("qualité de l'officier"), max_length=200, default="Officier de l'état civil",
    )
    marginal_notes = models.TextField(_('mentions marginales'), blank=True, default=DEFAULT_MARGINAL_NOTES)

    SEALED_FIELDS = (
        'child_last_name', 'child_first_names', 'child_sex', 'birth_datetime', 'birth_place',
        'father_full_name', 'father_birth_date', 'father_birth_place', 'father_profession', 'father_address',
        'mother_full_name', 'mother_birth_date', 'mother_birth_place', 'mother_profession', 'mother_address',
        'declarant_name', 'declarant_relationship', 'registrar_name', 'registrar_title', 'marginal_notes',
    )

    class Meta(OfficialDocument.Meta):
        verbose_name = _('acte de naissance')
        verbose_name_plural = _('actes de naissance')

    @property
    def holder_name(self):
        return f'{self.child_last_name.upper()} {self.child_first_names}'

    @property
    def main_date(self):
        return self.birth_datetime

    @property
    def document_title(self):
        return "EXTRAIT D'ACTE DE NAISSANCE"


# ---------------------------------------------------------------------------
# Guichet 2 — Actes de mariage
# ---------------------------------------------------------------------------

class MarriageCertificate(OfficialDocument):
    PREFIX = 'MAR'
    DOCUMENT_CODE = 'MARRIAGE_CERTIFICATE'

    marriage_datetime = models.DateTimeField(_('date et heure du mariage'))
    marriage_place = models.CharField(_('lieu de célébration'), max_length=200)

    husband_last_name = models.CharField(_("nom de l'époux"), max_length=150)
    husband_first_names = models.CharField(_("prénoms de l'époux"), max_length=200)
    husband_birth_date = models.DateField(_("date de naissance de l'époux"))
    husband_birth_place = models.CharField(_("lieu de naissance de l'époux"), max_length=200)
    husband_profession = models.CharField(_("profession de l'époux"), max_length=150, blank=True)
    husband_address = models.CharField(_("domicile de l'époux"), max_length=255)
    husband_father_name = models.CharField(_("père de l'époux"), max_length=200, blank=True)
    husband_father_profession = models.CharField(_("profession du père de l'époux"), max_length=150, blank=True)
    husband_mother_name = models.CharField(_("mère de l'époux"), max_length=200, blank=True)
    husband_mother_profession = models.CharField(_("profession de la mère de l'époux"), max_length=150, blank=True)

    wife_last_name = models.CharField(_("nom de l'épouse"), max_length=150)
    wife_first_names = models.CharField(_("prénoms de l'épouse"), max_length=200)
    wife_birth_date = models.DateField(_("date de naissance de l'épouse"))
    wife_birth_place = models.CharField(_("lieu de naissance de l'épouse"), max_length=200)
    wife_profession = models.CharField(_("profession de l'épouse"), max_length=150, blank=True)
    wife_address = models.CharField(_("domicile de l'épouse"), max_length=255)
    wife_father_name = models.CharField(_("père de l'épouse"), max_length=200, blank=True)
    wife_father_profession = models.CharField(_("profession du père de l'épouse"), max_length=150, blank=True)
    wife_mother_name = models.CharField(_("mère de l'épouse"), max_length=200, blank=True)
    wife_mother_profession = models.CharField(_("profession de la mère de l'épouse"), max_length=150, blank=True)

    matrimonial_regime = models.CharField(
        _('régime matrimonial'), max_length=500, default='Régime de droit commun (communauté de biens)',
        help_text=_('Ex. : contrat de mariage reçu le … par Maître …, notaire à Mahajanga.'),
    )
    witness1_name = models.CharField(_('premier témoin'), max_length=200)
    witness1_details = models.CharField(
        _('premier témoin — qualité / domicile'), max_length=255, blank=True,
    )
    witness2_name = models.CharField(_('second témoin'), max_length=200)
    witness2_details = models.CharField(
        _('second témoin — qualité / domicile'), max_length=255, blank=True,
    )
    registrar_name = models.CharField(_("nom de l'officier d'état civil"), max_length=200)
    registrar_title = models.CharField(_("qualité de l'officier"), max_length=200, default="Officier de l'état civil")
    marginal_notes = models.TextField(_('mentions marginales'), blank=True, default=DEFAULT_MARGINAL_NOTES)

    SEALED_FIELDS = (
        'marriage_datetime', 'marriage_place',
        'husband_last_name', 'husband_first_names', 'husband_birth_date', 'husband_birth_place',
        'husband_profession', 'husband_address', 'husband_father_name', 'husband_mother_name',
        'wife_last_name', 'wife_first_names', 'wife_birth_date', 'wife_birth_place',
        'wife_profession', 'wife_address', 'wife_father_name', 'wife_mother_name',
        'matrimonial_regime', 'witness1_name', 'witness1_details', 'witness2_name', 'witness2_details',
        'registrar_name', 'registrar_title', 'marginal_notes',
    )
    LATE_SEALED_FIELDS = (
        'husband_father_profession', 'husband_mother_profession', 'wife_father_profession', 'wife_mother_profession',
    )

    class Meta(OfficialDocument.Meta):
        verbose_name = _('acte de mariage')
        verbose_name_plural = _('actes de mariage')

    @property
    def holder_name(self):
        return f'{self.husband_last_name.upper()} {self.husband_first_names} & {self.wife_last_name.upper()} {self.wife_first_names}'

    @property
    def main_date(self):
        return self.marriage_datetime

    @property
    def document_title(self):
        return 'ACTE DE MARIAGE (COPIE INTÉGRALE)'


# ---------------------------------------------------------------------------
# Guichet 3 — Actes de décès
# ---------------------------------------------------------------------------

class DeathCertificate(OfficialDocument):
    PREFIX = 'DEC'
    DOCUMENT_CODE = 'DEATH_CERTIFICATE'
    Sex = Sex

    class MaritalStatus(models.TextChoices):
        SINGLE = 'SINGLE', _('Célibataire')
        MARRIED = 'MARRIED', _('Marié(e)')
        WIDOWED = 'WIDOWED', _('Veuf / veuve')
        DIVORCED = 'DIVORCED', _('Divorcé(e)')
    deceased_last_name = models.CharField(_('nom du défunt'), max_length=150)
    deceased_first_names = models.CharField(_('prénoms du défunt'), max_length=200)
    deceased_sex = models.CharField(_('sexe'), max_length=1, choices=Sex.choices)
    deceased_birth_date = models.DateField(_('date de naissance du défunt'), null=True, blank=True)
    deceased_birth_place = models.CharField(_('lieu de naissance du défunt'), max_length=200, blank=True)
    deceased_profession = models.CharField(_('profession du défunt'), max_length=150, blank=True)
    deceased_address = models.CharField(_('domicile du défunt'), max_length=255)
    marital_status = models.CharField(_('situation matrimoniale'), max_length=10, choices=MaritalStatus.choices, blank=True)
    spouse_name = models.CharField(_('nom du conjoint'), max_length=200, blank=True)
    father_name = models.CharField(_('nom du père'), max_length=200, blank=True)
    father_deceased = models.BooleanField(_('père décédé (« feu »)'), default=False)
    mother_name = models.CharField(_('nom de la mère'), max_length=200, blank=True)
    mother_deceased = models.BooleanField(_('mère décédée (« feue »)'), default=False)

    death_datetime = models.DateTimeField(_('date et heure du décès'))
    death_place = models.CharField(_('lieu du décès'), max_length=200)

    declarant_name = models.CharField(_('nom du déclarant'), max_length=200)
    declarant_relationship = models.CharField(
        _('qualité du déclarant'), max_length=150, help_text=_('Ex. : fils du défunt, voisin, médecin…'),
    )
    declarant_age = models.PositiveSmallIntegerField(_('âge du déclarant'), null=True, blank=True)
    declarant_profession = models.CharField(_('profession du déclarant'), max_length=150, blank=True)
    declarant_address = models.CharField(_('domicile du déclarant'), max_length=255, blank=True)
    registrar_name = models.CharField(_("nom de l'officier d'état civil"), max_length=200)
    registrar_title = models.CharField(_("qualité de l'officier"), max_length=200, default="Officier de l'état civil")
    marginal_notes = models.TextField(_('mentions marginales'), blank=True, default='Néant.')

    SEALED_FIELDS = (
        'deceased_last_name', 'deceased_first_names', 'deceased_sex', 'deceased_birth_date',
        'deceased_birth_place', 'deceased_profession', 'deceased_address', 'marital_status', 'spouse_name',
        'father_name', 'mother_name', 'death_datetime', 'death_place',
        'declarant_name', 'declarant_relationship', 'declarant_address',
        'registrar_name', 'registrar_title', 'marginal_notes',
    )
    LATE_SEALED_FIELDS = ('father_deceased', 'mother_deceased', 'declarant_age', 'declarant_profession')

    class Meta(OfficialDocument.Meta):
        verbose_name = _('acte de décès')
        verbose_name_plural = _('actes de décès')

    @property
    def holder_name(self):
        return f'{self.deceased_last_name.upper()} {self.deceased_first_names}'

    @property
    def age_at_death(self):
        if not self.deceased_birth_date:
            return None
        died = timezone.localtime(self.death_datetime).date()
        born = self.deceased_birth_date
        return died.year - born.year - ((died.month, died.day) < (born.month, born.day))

    @property
    def main_date(self):
        return self.death_datetime

    @property
    def document_title(self):
        return "COPIE INTÉGRALE D'ACTE DE DÉCÈS"


# ---------------------------------------------------------------------------
# Guichet 4 — Législation (extraits certifiés conformes)
# ---------------------------------------------------------------------------

class LegislationExtract(OfficialDocument):
    PREFIX = 'LEG'
    DOCUMENT_CODE = 'LEGISLATION_EXTRACT'

    class TextType(models.TextChoices):
        ARRETE = 'arrete', _('Arrêté')
        DELIBERATION = 'deliberation', _('Délibération')
        REGLEMENT = 'reglement', _('Règlement')
        DECISION = 'decision', _('Décision')
        OTHER = 'other', _('Autre texte')
    text_type = models.CharField(_('type de texte'), max_length=20, choices=TextType.choices)
    text_number = models.CharField(_('numéro du texte'), max_length=100)
    text_date = models.DateField(_('date du texte'))
    subject = models.CharField(_('objet'), max_length=255)
    content = models.TextField(_('extrait certifié'), help_text=_('Dispositif ou articles reproduits.'))
    recipient_name = models.CharField(_('délivré à'), max_length=200, blank=True)
    registrar_name = models.CharField(_('nom du signataire'), max_length=200)
    registrar_title = models.CharField(_('qualité du signataire'), max_length=200, default='Le Maire')

    SEALED_FIELDS = (
        'text_type', 'text_number', 'text_date', 'subject', 'content', 'recipient_name',
        'registrar_name', 'registrar_title',
    )

    class Meta(OfficialDocument.Meta):
        verbose_name = _('extrait de texte')
        verbose_name_plural = _('extraits de textes (législation)')

    @property
    def holder_name(self):
        return f'{self.get_text_type_display()} N° {self.text_number} — {self.subject}'

    @property
    def main_date(self):
        return self.text_date

    @property
    def document_title(self):
        return 'EXTRAIT CERTIFIÉ CONFORME'


# ---------------------------------------------------------------------------
# Guichet 5 — Attestations des services (recette, transport, marché…)
# ---------------------------------------------------------------------------

class ServiceCertificate(OfficialDocument):
    PREFIX = 'ATT'
    DOCUMENT_CODE = 'SERVICE_CERTIFICATE'

    class Service(models.TextChoices):
        RECETTE = 'recette', _('Recette')
        TRANSPORT = 'transport', _('Transport')
        URBANISME = 'urbanisme', _('Urbanisme')
        MARCHE = 'marche', _('Marché')
        CADASTRE = 'cadastre', _('Cadastre')
        IMPOT_FONCIER = 'impot_foncier', _('Impôt foncier')
        ACTES_DIVERS = 'actes_divers', _('Actes divers')
    # Titre imprimé selon le service.
    TITLES = {
        'recette': 'ATTESTATION DE PAIEMENT',
        'transport': 'AUTORISATION DE TRANSPORT',
        'urbanisme': "AUTORISATION D'URBANISME",
        'marche': "ATTESTATION D'EMPLACEMENT DE MARCHÉ",
        'cadastre': 'EXTRAIT CADASTRAL',
        'impot_foncier': "ATTESTATION D'IMPÔT FONCIER",
        'actes_divers': 'ATTESTATION ADMINISTRATIVE',
    }

    service = models.CharField(_('service'), max_length=20, choices=Service.choices)
    nature = models.CharField(
        _("nature de l'acte"), max_length=150,
        help_text=_('Ex. : licence de taxi, permis de construire, attestation de paiement…'),
    )
    holder_full_name = models.CharField(_('bénéficiaire (nom et prénoms)'), max_length=200)
    holder_national_id = models.CharField(_('N° de CIN du bénéficiaire'), max_length=50, blank=True)
    holder_address = models.CharField(_('adresse du bénéficiaire'), max_length=255, blank=True)
    reference = models.CharField(
        _('référence'), max_length=150, blank=True,
        help_text=_("Immatriculation, référence de parcelle, N° d'emplacement, référence fiscale…"),
    )
    location = models.CharField(
        _('lieu / bien concerné'), max_length=255, blank=True,
        help_text=_('Adresse du terrain ou du bien, nom du marché, quartier…'),
    )
    subject = models.TextField(_('objet'), help_text=_("Ce que la Commune atteste ou autorise."))
    amount = models.DecimalField(_('montant (Ar)'), max_digits=14, decimal_places=2, null=True, blank=True)
    valid_until = models.DateField(_("valable jusqu'au"), null=True, blank=True)
    registrar_name = models.CharField(_('nom du signataire'), max_length=200)
    registrar_title = models.CharField(_('qualité du signataire'), max_length=200, default='Le Chef de service')
    observations = models.TextField(_('observations'), blank=True)

    SEALED_FIELDS = (
        'service', 'nature', 'holder_full_name', 'holder_national_id', 'holder_address', 'reference',
        'location', 'subject', 'amount', 'valid_until', 'registrar_name', 'registrar_title', 'observations',
    )

    class Meta(OfficialDocument.Meta):
        verbose_name = _('attestation de service')
        verbose_name_plural = _('attestations de services (guichet 5)')

    @property
    def holder_name(self):
        return f'{self.holder_full_name} — {self.get_service_display()} ({self.nature})'

    @property
    def document_title(self):
        return self.TITLES.get(self.service, 'ATTESTATION')
