# -*- coding: utf-8 -*-
"""
Forms for Zeus
"""

import copy
import json
import csv
from io import StringIO

from collections import defaultdict
from datetime import datetime

from django import forms
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib.auth.hashers import check_password, make_password
from django.forms.models import BaseModelFormSet
from django.forms.widgets import Select, MultiWidget, TextInput,\
    HiddenInput
from django.forms.formsets import BaseFormSet
from django.http import QueryDict

from helios.models import Election, Poll, Voter
from heliosauth.models import User

from zeus.utils import extract_trustees, election_trustees_to_text
from zeus.widgets import JqSplitDateTimeField, JqSplitDateTimeWidget
from zeus import help_texts as help
from zeus.utils import undecalize, ordered_dict_prepend

from django.core.validators import validate_email
from zeus.election_modules import ELECTION_MODULES_CHOICES


LOG_CHANGED_FIELDS = [
    "name",
    "voting_starts_at",
    "voting_ends_at",
    "voting_extended_until",
    "description",
    "help_email",
    "help_phone"
]

INVALID_CHAR_MSG = _("%s is not a valid character.") % "%"


def election_form_formfield_cb(f, **kwargs):
    if f.name in ['voting_starts_at', 'voting_ends_at',
                  'voting_extended_until']:
        widget = JqSplitDateTimeWidget(attrs={'date_class': 'datepicker',
                                              'time_class': 'timepicker'})
        return JqSplitDateTimeField(label=f.verbose_name,
                                    initial=f.default,
                                    widget=widget,
                                    required=not f.blank,
                                    help_text=f.help_text)
    return f.formfield()


class ElectionForm(forms.ModelForm):

    formfield_callback = election_form_formfield_cb

    trustees = forms.CharField(label=_('Trustees'), required=False,
                               widget=forms.Textarea,
                               help_text=help.trustees)

    remote_mixes = forms.BooleanField(label=_('Multiple mixnets'),
                                      required=False,
                                      help_text=help.remote_mixes)
    linked_polls = forms.BooleanField(label=_("Linked polls (experimental)"),
                                      required=False)

    FIELD_REQUIRED_FEATURES = {
        'trustees': ['edit_trustees'],
        'name': ['edit_name'],
        'description': ['edit_description'],
        'election_module': ['edit_type'],
        'voting_starts_at': ['edit_voting_starts_at'],
        'voting_ends_at': ['edit_voting_ends_at'],
        'voting_extended_until': ['edit_voting_extended_until'],
        'remote_mixes': ['edit_remote_mixes'],
        'trial': ['edit_trial'],
        'departments': ['edit_departments'],
        'linked_polls': ['edit_linked_polls'],
        'cast_consent_text': ['edit_cast_consent_text'],
    }

    class Meta:
        model = Election
        fields = ('trial', 'election_module', 'name', 'description',
                  'departments', 'voting_starts_at', 'voting_ends_at',
                  'voting_extended_until',
                  'trustees', 'help_email', 'help_phone',
                  'communication_language', 'linked_polls',
                  'sms_api_enabled', 'cast_consent_text')

    def __init__(self, owner, institution, *args, **kwargs):
        self.institution = institution
        self.owner = owner

        if kwargs.get('lang'):
            lang = kwargs.pop('lang')
        else:
            lang = None
        super(ElectionForm, self).__init__(*args, **kwargs)
        choices = settings.LANGUAGES
        help_text = _("Set the language that will be used for email messages")
        self.fields['communication_language'] = forms.ChoiceField(label=_("Communication language"),
                                                    choices=choices,
                                                    initial=lang,
                                                    help_text=help_text)
        self.fields['linked_polls'].widget = forms.HiddenInput()
        if owner.sms_data:
            help_text = _("Notify voters using SMS (%d deliveries available for your account)") % owner.sms_data.left
            self.fields['sms_api_enabled'] = forms.BooleanField(
                label=_("Mobile SMS notifications enabled"),
                initial=True,
                required=False,
                help_text=help_text)
        else:
            del self.fields['sms_api_enabled']

        self.creating = True
        self._initial_data = {}
        if self.instance and self.instance.pk:
            self._initial_data = {}
            for field in LOG_CHANGED_FIELDS:
                self._initial_data[field] = self.initial[field]
            self.creating = False

        eligible_types = owner.eligible_election_types
        if not self.creating and self.instance:
            eligible_types.add(self.instance.election_module)
        eligible_types_choices = [x for x in ELECTION_MODULES_CHOICES if x[0] in eligible_types]

        self.fields['election_module'].choices = eligible_types_choices

        self.fields['departments'].required = False
        if 'election_module' in self.data:
            if self.data['election_module'] == 'stv':
                self.fields['departments'].required = True

        if self.instance and self.instance.pk:
            self.fields.get('trustees').initial = \
                election_trustees_to_text(self.instance)
            self.fields.get('remote_mixes').initial = \
                bool(self.instance.mix_key)

        for field, features in self.FIELD_REQUIRED_FEATURES.items():
            editable = all([self.instance.check_feature(f) for
                            f in features])

            widget = self.fields.get(field).widget
            if not editable:
                self.fields.get(field).widget.attrs['readonly'] = True
                if isinstance(widget, forms.CheckboxInput):
                    self.fields.get(field).widget.attrs['disabled'] = True

        if not self.instance.frozen_at:
            self.fields.pop('voting_extended_until')

    def clean(self):
        data = super(ElectionForm, self).clean()
        self.clean_voting_dates(data.get('voting_starts_at'),
                                data.get('voting_ends_at'),
                                data.get('voting_extended_until'))
        for field, features in self.FIELD_REQUIRED_FEATURES.items():
            if not self.instance.pk:
                continue
            editable = all([self.instance.check_feature(f) for
                            f in features])
            if not editable and field in self.cleaned_data:
                if field == 'trustees':
                    self.cleaned_data[field] = \
                        election_trustees_to_text(self.instance)
                elif field == 'remote_mixes':
                    self.cleaned_data[field] = bool(self.instance.mix_key)
                else:
                    self.cleaned_data[field] = getattr(self.instance, field)

        return data

    def clean_departments(self):
        deps = self.cleaned_data.get('departments')
        deps_arr = deps.split('\n')
        cleaned_deps = []
        for item in deps_arr:
            item = item.strip()
            item = item.lstrip()
            if item:
                cleaned_deps.append(item)
        cleaned_deps = '\n'.join(cleaned_deps)
        return cleaned_deps

    def clean_voting_dates(self, starts, ends, extension):
        if starts and ends:
            if ends < datetime.now() and self.instance.feature_edit_voting_ends_at:
                raise forms.ValidationError(_("Invalid voting end date"))
            if starts >= ends:
                raise forms.ValidationError(_("Invalid voting dates"))
        if extension and extension <= ends:
            raise forms.ValidationError(_("Invalid voting extension date"))

    def clean_trustees(self):
        trustees = self.cleaned_data.get('trustees')
        try:
            for tname, temail in extract_trustees(trustees):
                validate_email(temail)
        except ValueError:
            raise forms.ValidationError(_("Invalid trustees format"))
        return trustees

    def log_changed_fields(self, instance):
        for field in LOG_CHANGED_FIELDS:
            if field in self.changed_data:
                inital = self._initial_data[field]
                newvalue = self.cleaned_data[field]
                instance.logger.info("Field '%s' changed from %r to %r", field,
                                    inital, newvalue)

    def save(self, *args, **kwargs):
        remote_mixes = self.cleaned_data.get('remote_mixes')
        if remote_mixes:
            self.instance.generate_mix_key()
        else:
            self.instance.mix_key = None
        saved = super(ElectionForm, self).save(*args, **kwargs)
        trustees = extract_trustees(self.cleaned_data.get('trustees'))
        saved.institution = self.institution
        if saved.sms_api_enabled:
            saved.sms_data = self.owner.sms_data

        saved.save()
        if saved.feature_edit_trustees:
            saved.update_trustees(trustees)
        else:
            saved.logger.info("Election updated %r", self.changed_data)
            self.log_changed_fields(saved)
        return saved


class AnswerWidget(forms.TextInput):

    def render(self, *args, **kwargs):
        html = super(AnswerWidget, self).render(*args, **kwargs)
        html = """
        <div class="row">
        <div class="columns eleven">
        %s
        </div>
        <div class="columns one">
        <a href="#" style="font-weight: bold; color:red"
        class="remove_answer">X</a>
        </div>
        </div>
        """ % html
        return mark_safe(html)


DEFAULT_ANSWERS_COUNT = 2
MAX_QUESTIONS_LIMIT = getattr(settings, 'MAX_QUESTIONS_LIMIT', 1)


class QuestionBaseForm(forms.Form):
    choice_type = forms.ChoiceField(choices=(
        ('choice', _('Choice')),
    ))
    question = forms.CharField(label=_("Question"), max_length=5000,
                               required=True,
                               widget=forms.Textarea(attrs={
                                'rows': 4,
                                'class': 'textarea'
                               }))

    answers_file = forms.FileField(
        label=_('CSV file with answers'),
        help_text=_('Attach a UTF-8 encoded file. Answers will replace the current list.'),
        required=False)

    def __init__(self, *args, **kwargs):
        super(QuestionBaseForm, self).__init__(*args, **kwargs)
        if len(self.fields['choice_type'].choices) == 1:
            self.fields['choice_type'].widget = forms.HiddenInput()
            self.fields['choice_type'].initial = 'choice'

        self.answers_file_errors = []
        self.update_answers_from_file()

        answers = len([k for k in self.data if k.startswith("%s-answer_" %
                                                self.prefix)])
        if not answers:
            answers = len([k for k in list(self.initial.keys()) if k.startswith("answer_") and "indexes" not in k])

        if answers == 0:
            answers = DEFAULT_ANSWERS_COUNT

        for ans in range(answers):
            field_key = 'answer_%d' % ans
            self.fields[field_key] = forms.CharField(max_length=300,
                                              required=True,
                                              widget=AnswerWidget)
            self.fields[field_key].widget.attrs.update({'class': 'answer_input'})

        self._answers = answers

    def update_answers_from_file(self):
        file_key = self.add_prefix('answers_file')
        if not (self.files and file_key in self.files):
            return

        content = self.files[file_key].read()
        del self.files[file_key]

        try:
            s = content.decode()
        except UnicodeDecodeError as e:
            self.answers_file_errors.append(str(e))
            return

        self.data = self.data.copy()
        reader = csv.reader(StringIO(s))
        self.clear_answers()
        i = 0
        for row in reader:
            try:
                if self.add_answer_from_row(i, row):
                    i += 1
            except forms.ValidationError as e:
                self.answers_file_errors.append(e)

    def clean(self):
        data = super().clean()
        for e in self.answers_file_errors:
            self.add_error('answers_file', e)
        return data

    def clear_answers(self):
        for k in list(self.data.keys()):
            if k.startswith(self.add_prefix('answer_')):
                del self.data[k]

    def add_answer_from_row(self, i, row):
        if len(row) == 0:
            return False
        if len(row) > 1:
            raise forms.ValidationError(f'too many columns: {row}')
        self.data[self.add_prefix(f'answer_{i}')] = row[0]
        return True

    def clean_question(self):
        q = self.cleaned_data.get('question', '')
        if '%' in q:
            raise forms.ValidationError(INVALID_CHAR_MSG)
        return q.replace(": ", ":\t")


class QuestionForm(QuestionBaseForm):
    min_answers = forms.ChoiceField(label=_("Min answers"))
    max_answers = forms.ChoiceField(label=_("Max answers"))

    min_limit = None
    max_limit = None

    def __init__(self, *args, **kwargs):
        super(QuestionForm, self).__init__(*args, **kwargs)
        answers = self._answers
        max_choices = [(x, x) for x in range(1, self.max_limit or answers+1)]

        self.fields['max_answers'].choices = max_choices
        self.fields['max_answers'].initial = min([x[1] for x in max_choices])
        self.fields['min_answers'].choices = max_choices
        self.fields['min_answers'].initial = 0

    def clean(self):
        cleaned_data = super().clean()

        max_answers = int(cleaned_data.get('max_answers'))
        min_answers = int(cleaned_data.get('min_answers'))
        if min_answers > max_answers:
            raise forms.ValidationError(_("Max answers should be greater "
                                          "or equal to min answers"))
        answer_list = []
        for key in self.cleaned_data:
            if key.startswith('answer_'):
                if '%' in self.cleaned_data[key]:
                    raise forms.ValidationError(INVALID_CHAR_MSG)
                answer_list.append(self.cleaned_data[key])
        if len(answer_list) > len(set(answer_list)):
            raise forms.ValidationError(_("No duplicate choices allowed"))
        return cleaned_data


class PartyForm(QuestionForm):
    question = forms.CharField(label=_("Party name"), max_length=255,
                               required=True)


SCORES_DEFAULT_LEN = 2
SCORES_CHOICES = [(x, x) for x in range(1, 10)]


class ScoresForm(QuestionBaseForm):
    scores = forms.MultipleChoiceField(required=True,
                                       widget=forms.CheckboxSelectMultiple,
                                       choices=SCORES_CHOICES,
                                       label=_('Scores'))

    scores.initial = (1, 2)

    min_answers = forms.ChoiceField(label=_("Min answers"), required=True)
    max_answers = forms.ChoiceField(label=_("Max answers"), required=True)

    def __init__(self, *args, **kwargs):
        super(ScoresForm, self).__init__(*args, **kwargs)
        if isinstance(self.data, QueryDict):
            myDict = dict(self.data.lists())
        else:
            myDict = self.data

        if 'form-0-scores' in myDict:
            self._scores_len = len(myDict['form-0-scores'])
        elif 'scores' in self.initial:
            self._scores_len = len(self.initial['scores'])
        else:
            self._scores_len = SCORES_DEFAULT_LEN
        max_choices = [(x, x) for x in range(1, self._scores_len + 1)]
        self.fields['max_answers'].choices = max_choices
        self.fields['max_answers'].initial = self._scores_len
        self.fields['min_answers'].choices = max_choices

    def clean(self):
        super(ScoresForm, self).clean()
        max_answers = int(self.cleaned_data.get('max_answers', 0))
        min_answers = int(self.cleaned_data.get('min_answers', 0))
        if (min_answers and max_answers) and min_answers > max_answers:
            raise forms.ValidationError(_("Max answers should be greater "
                                          "or equal to min answers"))
        answer_list = []
        for key in self.cleaned_data:
            if key.startswith('answer_'):
                if '%' in self.cleaned_data[key]:
                    raise forms.ValidationError(INVALID_CHAR_MSG)
                answer_list.append(self.cleaned_data[key])
        if len(answer_list) > len(set(answer_list)):
            raise forms.ValidationError(_("No duplicate choices allowed"))
        if 'scores' in self.cleaned_data:
            if (len(answer_list) < max_answers):
                m = _("Number of answers must be equal or bigger than max answers")
                raise forms.ValidationError(m)
        return self.cleaned_data


class RequiredFormset(BaseFormSet):

    def __init__(self, *args, **kwargs):
        super(RequiredFormset, self).__init__(*args, **kwargs)
        try:
            self.forms[0].empty_permitted = False
        except IndexError:
            pass


class CandidateWidget(MultiWidget):
    template_name = 'election_modules/stv/candidate_widget.html'

    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        widgets = (TextInput(),
                   Select(choices=departments))
        super(CandidateWidget, self).__init__(widgets, *args, **kwargs)

    def decompress(self, value):
        if not value:
            return [None, None]

        return json.loads(value)

    def value_from_datadict(self, data, files, name):
        datalist = [
            widget.value_from_datadict(data, files, name + '_%s' % i)
            for i, widget in enumerate(self.widgets)]
        return json.dumps(datalist)


class SavForm(QuestionBaseForm):
    min_votes = forms.IntegerField(
        label=_("Min votes"),
        help_text=_("Shorter ballots will be accepted, but the votes will not be counted any higher."),
        min_value=1,
        required=False)

    def __init__(self, *args, **kwargs):

        super(SavForm, self).__init__(*args, **kwargs)

        self.fields.pop('question')
        self.fields.pop('choice_type')

    def clean(self):
        super().clean()

        from django.forms.utils import ErrorList
        message = _("This field is required.")
        answers = len([k for k in self.data if k.startswith("%s-answer_" %
                                                self.prefix)])

        #list used for checking duplicate candidates
        candidates_list = []

        for ans in range(0, answers):
            field_key = 'answer_%d' % ans
            answer = self.cleaned_data[field_key]
            if not answer:
                self._errors[field_key] = ErrorList([message])
            if '%' in answer:
                raise forms.ValidationError(INVALID_CHAR_MSG)
            candidates_list.append(answer)

        if len(candidates_list) > len(set(candidates_list)):
            raise forms.ValidationError(_("No duplicate choices allowed"))

        return self.cleaned_data


class StvForm(QuestionBaseForm):

    def __init__(self, *args, **kwargs):
        deps = kwargs['initial']['departments_data'].split('\n')
        self.department_choices = []
        for dep in deps:
            self.department_choices.append((dep.strip(), dep.strip()))

        super(StvForm, self).__init__(*args, **kwargs)

        self.fields.pop('question')
        self.fields.pop('choice_type')
        answers = len([k for k in self.data if k.startswith("%s-answer_" %
                                                self.prefix)]) // 2
        if not answers:
            answers = len([k for k in self.initial if k.startswith("answer_")])
        if answers == 0:
            answers = DEFAULT_ANSWERS_COUNT

        for k in list(self.fields.keys()):
            if k.startswith('answer_'):
                del self.fields[k]
        for ans in range(answers):
            field_key = 'answer_%d' % ans
            self.fields[field_key] = forms.CharField(max_length=600,
                                              required=True,
                                              widget=CandidateWidget(departments=self.department_choices),
                                              label=('Candidate'))
        widget=forms.TextInput(attrs={'hidden': 'True'})
        dep_lim_help_text = _("maximum number of elected from the same constituency")
        dep_lim_label = _("Constituency limit")
        ordered_dict_prepend(self.fields, 'department_limit',
                             forms.CharField(
                                 help_text=dep_lim_help_text,
                                 label=dep_lim_label,
                                 widget=widget,
                                 required=False))

        widget=forms.CheckboxInput(attrs={'onclick': 'enable_limit()'})
        limit_help_text = _("enable limiting the elections from the same constituency")
        limit_label = _("Limit elected per constituency")
        ordered_dict_prepend(self.fields, 'has_department_limit',
                             forms.BooleanField(
                                 widget=widget,
                                 help_text=limit_help_text,
                                 label=limit_label,
                                 required=False))

        elig_help_text = _("set the eligibles count of the election")
        label_text = _("Eligibles count")
        ordered_dict_prepend(self.fields, 'eligibles',
                             forms.CharField(
                                 label=label_text,
                                 help_text=elig_help_text))

        ordered_dict_prepend(self.fields, 'shuffle_answers',
                             forms.BooleanField(
                                 required=False,
                                 label=_('Shuffle answers'),
                                 help_text=_('Reorder answers when voting')))

    min_answers = None
    max_answers = None

    def add_answer_from_row(self, i, row):
        if len(row) == 0:
            return False
        if len(row) < 2:
            raise forms.ValidationError(f'too few columns: {row}')
        if len(row) > 2:
            raise forms.ValidationError(f'too many columns: {row}')

        dep = None
        for value, label in self.department_choices:
            if row[1] == label:
                dep = value
                break
        else:
            raise forms.ValidationError(f'department not found: {row[1]}')

        self.data[self.add_prefix(f'answer_{i}_0')] = row[0]
        self.data[self.add_prefix(f'answer_{i}_1')] = dep
        return True

    def clean(self):
        super().clean()

        from django.forms.utils import ErrorList
        message = _("This field is required.")

        answers = len([k for k in self.data if k.startswith("%s-answer_" %
                                                self.prefix)]) // 2

        #list used for checking duplicate candidates
        candidates_list = []

        for ans in range(answers):
            field_key = 'answer_%d' % ans
            answer = self.cleaned_data[field_key]
            answer_lst = json.loads(answer)
            if '%' in answer_lst[0]:
                raise forms.ValidationError(INVALID_CHAR_MSG)
            candidates_list.append(answer_lst[0])
            if not answer_lst[0]:
                self._errors[field_key] = ErrorList([message])
            answer_lst[0] = answer_lst[0].strip()
            self.cleaned_data[field_key] = json.dumps(answer_lst)

        if len(candidates_list) > len(set(candidates_list)):
            raise forms.ValidationError(_("No duplicate choices allowed"))

        return self.cleaned_data

    def clean_eligibles(self):
        message = _("Value must be a positive integer")
        eligibles = self.cleaned_data.get('eligibles')
        try:
            eligibles = int(eligibles)
            if eligibles > 0:
                return eligibles
            else:
                raise forms.ValidationError(message)
        except ValueError:
            raise forms.ValidationError(message)

    def clean_department_limit(self):
        message = _("Value must be a positive integer")
        dep_limit = self.cleaned_data.get('department_limit')
        if self.cleaned_data.get('has_department_limit'):
            if not dep_limit:
                raise forms.ValidationError(message)
        else:
            return 0
        try:
            dep_limit = int(dep_limit)
            if dep_limit > 0:
                return dep_limit
            else:
                raise forms.ValidationError(message)
        except ValueError:
            raise forms.ValidationError(message)


class LoginForm(forms.Form):
    username = forms.CharField(label=_('Username'),
                               max_length=50)
    password = forms.CharField(label=_('Password'),
                               widget=forms.PasswordInput(),
                               max_length=100)

    def clean(self):
        self._user_cache = None
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        try:
            user = User.objects.get(user_id=username)
        except User.DoesNotExist:
            raise forms.ValidationError(_("Invalid username or password"))

        if user.is_disabled:
            raise forms.ValidationError(_("Your account is disabled"))

        if check_password(password, user.info['password']):
            self._user_cache = user
            return self.cleaned_data
        else:
            raise forms.ValidationError(_("Invalid username or password"))


class PollForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.election = kwargs.pop('election', None)
        super(PollForm, self).__init__(*args, **kwargs)
        CHOICES = (
            ('public', 'public'),
            ('confidential', 'confidential'),
        )

        TYPES = (
            ('google', 'google'),
            ('facebook', 'facfebook'),
            ('other', 'other')
        )

        ordered_dict_prepend(self.fields, 'jwt_file',
                             forms.FileField(
                                 label="JWT public keyfile",
                                 required=False))
        self.fields['jwt_file'].widget.attrs['accept'] = '.pem'
        self.fields['jwt_public_key'] = forms.CharField(required=False,
                                                        widget=forms.Textarea)
        self.fields['oauth2_type'] = forms.ChoiceField(required=False,
                                                       choices=TYPES)
        self.fields['oauth2_client_type'] = forms.ChoiceField(required=False,
                                                              choices=CHOICES)
        self.fields['google_code_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://accounts.google.com/o/oauth2/auth",
                                    required=False)
        self.fields['google_exchange_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://accounts.google.com/o/oauth2/token",
                                    required=False)
        self.fields['google_confirmation_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://www.googleapis.com/oauth2/v1/userinfo",
                                    required=False)
        self.fields['facebook_code_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://www.facebook.com/dialog/oauth",
                                    required=False)
        self.fields['facebook_exchange_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://graph.facebook.com/oauth/access_token",
                                    required=False)
        self.fields['facebook_confirmation_url'] = forms.CharField(
                                    widget=HiddenInput,
                                    initial="https://graph.facebook.com/v2.2/me",
                                    required=False)

        if self.initial:
            shib = self.initial.get('shibboleth_constraints', None)
            if shib is not None and isinstance(shib, dict):
                self.initial['shibboleth_constraints'] = json.dumps(shib)
        if self.election.feature_frozen:
            self.fields['name'].widget.attrs['readonly'] = True

        auth_title = _('2-factor authentication')
        auth_help = _('2-factor authentication help text')
        self.fieldsets = {'auth': [auth_title, auth_help, []]}
        self.fieldset_fields = []

        auth_fields = ['jwt', 'google', 'facebook', 'shibboleth', 'oauth2']
        for name, field in list(self.fields.items()):
            if name.split("_")[0] in auth_fields:
                self.fieldsets['auth'][2].append(name)
                self.fieldset_fields.append(field)

        keyOrder = self.fieldsets['auth'][2]
        for field in ['jwt_auth', 'oauth2_thirdparty', 'shibboleth_auth']:
            prev_index = keyOrder.index(field)
            item = keyOrder.pop(prev_index)
            keyOrder.insert(0, item)
            self.fields[field].widget.attrs['field_class'] = 'fieldset-auth'
            if field == 'jwt_auth':
                self.fields[field].widget.attrs['field_class'] = 'clearfix last'

    class Meta:
        model = Poll
        fields = ('name',
                  'jwt_auth', 'jwt_issuer', 'jwt_public_key',
                  'oauth2_thirdparty', 'oauth2_type',
                  'oauth2_client_type', 'oauth2_client_id',
                  'oauth2_client_secret', 'oauth2_code_url',
                  'oauth2_exchange_url', 'oauth2_confirmation_url',
                  'shibboleth_auth', 'shibboleth_constraints')

    def iter_fieldset(self, name):
        for field in self.fieldsets[name][2]:
            yield self[field]

    def clean_shibboleth_constraints(self):
        value = self.cleaned_data.get('shibboleth_constraints', None)
        if value == "None":
            return None
        return value

    def clean(self):

        data = self.cleaned_data
        election_polls = self.election.polls.all()
        for poll in election_polls:
            if (data.get('name') == poll.name and
                    ((not self.instance.pk) or
                    (self.instance.pk and self.instance.name!=data.get('name')))):
                message = _("Duplicate poll names are not allowed")
                raise forms.ValidationError(message)
        if self.election.feature_frozen and\
            (self.cleaned_data['name'] != self.instance.name):
            raise forms.ValidationError(_("Poll name cannot be changed\
                                               after freeze"))

        oauth2_field_names = ['type', 'client_type', 'client_id', 'client_secret',
                       'code_url', 'exchange_url', 'confirmation_url']
        oauth2_field_names = ['oauth2_' + x for x in oauth2_field_names]
        jwt_field_names = ['jwt_issuer', 'jwt_public_key']
        url_validate = URLValidator()
        if data['oauth2_thirdparty']:
            for field_name in oauth2_field_names:
                if not data[field_name]:
                    self._errors[field_name] = _('This field is required.'),
            url_types = ['code', 'exchange', 'confirmation']
            for url_type in url_types:
                try:
                    url_validate(data['oauth2_{}_url'.format(url_type)])
                except ValidationError:
                    self._errors['oauth2_{}_url'.format(url_type)] =\
                        ((_("This URL is invalid"),))
        else:
            for field_name in oauth2_field_names:
                data[field_name] = ''

        shibboleth_field_names = []
        if data['shibboleth_auth']:
            for field_name in shibboleth_field_names:
                if not data[field_name]:
                    self._errors[field_name] = _('This field is required.'),

        if data['jwt_auth']:
            for field_name in jwt_field_names:
                if not data[field_name]:
                    self._errors[field_name] = _('This field is required.'),
        else:
            for field_name in jwt_field_names:
                data[field_name]=''
        return data

    def save(self, *args, **kwargs):
        commit = kwargs.pop('commit', True)
        instance = super(PollForm, self).save(commit=False, *args, **kwargs)
        instance.election = self.election
        if commit:
            instance.save()
        return instance


class PollFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        self.election = kwargs.pop('election', None)
        super(PollFormSet, self).__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['election'] = kwargs.get('election', self.election)
        return super(PollFormSet, self)._construct_form(i, **kwargs)

    def clean(self):
        forms_data = self.cleaned_data
        form_poll_names = []
        for form_data in forms_data:
            form_poll_names.append(form_data['name'])
            poll_name = form_data['name']
            e = Election.objects.get(id=self.election.id)
            election_polls = e.polls.all()
            for poll in election_polls:
                if poll_name == poll.name:
                    message = _("Duplicate poll names are not allowed")
                    raise forms.ValidationError(message)
        if len(form_poll_names) > len(set(form_poll_names)):
            message = _("Duplicate poll names are not allowed")
            raise forms.ValidationError(message)

    def save(self, election, *args, **kwargs):
        commit = kwargs.pop('commit', True)
        instances = super(PollFormSet, self).save(commit=False, *args,
                                                  **kwargs)
        if commit:
            for instance in instances:
                instance.election = election
                instance.save()

        return instances


SEND_TO_CHOICES = [
    ('all', _('all selected voters')),
    ('voted', _('selected voters who have cast a ballot')),
    ('not-voted', _('selected voters who have not yet cast a ballot'))
]

CONTACT_CHOICES = [
    ('email', _('Email only')),
    ('sms', _('SMS only')),
    ('email:sms', _('Email and SMS')),
]


class EmailVotersForm(forms.Form):
    email_subject = forms.CharField(label=_('Email subject'), max_length=80,
                              required=False)
    email_body = forms.CharField(label=_('In place of BODY'), max_length=30000,
                           widget=forms.Textarea, required=False)
    sms_body = forms.CharField(label=_('In place of SMS_BODY'), max_length=30000,
                           widget=forms.Textarea, required=False)
    contact_method = forms.ChoiceField(label=_("Contact method"), initial="email:sms",
                                choices=CONTACT_CHOICES)
    notify_once = forms.BooleanField(initial=True, label=_("Do not send sms if voter email is set"), required=False)
    send_to = forms.ChoiceField(label=_("Send To"), initial="all",
                                choices=SEND_TO_CHOICES)

    def __init__(self, election, template, *args, **kwargs):
        super(EmailVotersForm, self).__init__(*args, **kwargs)
        self.election = election
        self.template = template

        if not election.sms_enabled:
            self.fields['sms_body'].widget = forms.HiddenInput()
            self.fields['contact_method'].widget = forms.HiddenInput()
            self.fields['contact_method'].choices = [('email', _('Email'))]
            self.fields['contact_method'].initial = 'email'
            self.fields['notify_once'].widget = forms.HiddenInput()
            self.fields['notify_once'].initial = False
        else:
            choices = copy.copy(CONTACT_CHOICES)
            choices[1] = list(choices[1])
            choices[1][1] = "%s (%s)" % (str(choices[1][1]), _("%d deliveries available") % election.sms_data.left)
            self.fields['contact_method'].choices = choices

    def clean(self):
        super(EmailVotersForm, self).clean()
        data = self.cleaned_data
        if 'sms' in data.get('contact_method', []) and self.template == 'info':
            if data.get('sms_body').strip() == '':
                raise ValidationError(_("Please provide SMS body"))
        return data


class ChangePasswordForm(forms.Form):
    password = forms.CharField(label=_('Current password'), widget=forms.PasswordInput)
    new_password = forms.CharField(label=_('New password'), widget=forms.PasswordInput)
    new_password_confirm = forms.CharField(label=_('New password confirm'), widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    def save(self):
        user = self.user
        pwd = make_password(self.cleaned_data['new_password'].strip())
        user.info['password'] = pwd
        user.save()

    def clean(self):
        cl = super(ChangePasswordForm, self).clean()
        pwd = self.cleaned_data['password'].strip()
        if not check_password(pwd, self.user.info['password']):
            raise forms.ValidationError(_('Invalid password'))
        if not self.cleaned_data.get('new_password') == \
           self.cleaned_data.get('new_password_confirm'):
            raise forms.ValidationError(_('Passwords don\'t match'))
        return cl


class VoterLoginForm(forms.Form):

    login_id = forms.CharField(label=_('Login password'), required=True)

    def __init__(self, *args, **kwargs):
        self._voter = None
        super(VoterLoginForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(VoterLoginForm, self).clean()

        login_id = self.cleaned_data.get('login_id')

        invalid_login_id_error = _("Invalid login code")
        if not login_id:
            raise forms.ValidationError(invalid_login_id_error)

        try:
            poll_id, secret = login_id.split("-", 1)
            secret = undecalize(secret)
        except ValueError:
            raise forms.ValidationError(invalid_login_id_error)

        poll = None
        try:
            poll = Poll.objects.get(pk=poll_id)
        except Poll.DoesNotExist:
            raise forms.ValidationError(invalid_login_id_error)

        try:
            self._voter = poll.voters.get(voter_password=secret)
        except Voter.DoesNotExist:
            raise forms.ValidationError(_("Invalid email or password"))

        return cleaned_data


class STVBallotForm(forms.Form):

    def __init__(self, *args, **kwargs):
        candidates = self.candidates
        super(STVBallotForm, self).__init__(*args, **kwargs)
        choices = [('', '')]
        for i, c in enumerate(candidates):
            choices.append((str(i), c))
        for i, c in enumerate(candidates):
            self.fields['choice_%d' % (i + 1)] = forms.ChoiceField(choices=choices, initial='', required=False, label=_("Ballot choice %s") % str(i + 1))

    def get_choices(self, serial):
        vote = {'votes': [], "ballotSerialNumber": serial}
        for i, c in enumerate(self.candidates):
            val = self.cleaned_data.get('choice_%d' % (i + 1), '')
            if not val:
                break
            vote['votes'].append({'rank': (i + 1), "candidateTmpId": val})
        return vote

    def clean(self):
        data = self.cleaned_data
        empty = False
        choices = []
        for i, c in enumerate(self.candidates):
            val = self.cleaned_data.get('choice_%d' % (i + 1), '')
            if val == "":
                empty = True
            if val and empty:
                raise ValidationError(_("Invalid ballot"))
            if val:
                choices.append(val)

        if len(choices) != len(set(choices)):
            raise ValidationError(_("Invalid ballot"))
        return data


candidates_help_text = _("""Candidates list. e.g., <br/><br/>
FirstName, LastName, SchoolA<br />
FirstName, LastName, SchoolB<br />
""")

limit_choices = [(x, str(x)) for x in range(2)]
eligibles_choices = [(x, str(x)) for x in range(1, 20)]


class STVElectionForm(forms.Form):
    name = forms.CharField(label=_("Election name"), required=True)
    voting_starts = forms.CharField(label=_("Voting start date"), required=True, help_text=_("e.g. 25/01/2015 07:00"))
    voting_ends = forms.CharField(label=_("Voting end date"), required=True, help_text=_("e.g. 25/01/2015 19:00"))
    institution = forms.CharField(label=_("Institution name"))
    candidates = forms.CharField(label=_("Candidates"), widget=forms.Textarea, help_text=candidates_help_text)
    eligibles_count = forms.ChoiceField(label=_("Eligibles count"), choices=eligibles_choices)
    elected_limit = forms.IntegerField(label=_("Maximum elected per department"), required=False)
    ballots_count = forms.CharField(label=_("Ballots count"))

    def __init__(self, *args, **kwargs):
        kwargs.pop('disabled', False)
        super(STVElectionForm, self).__init__(*args, **kwargs)

    def clean_voting_starts(self):
        d = self.cleaned_data.get('voting_starts') or ''
        d = d.strip()
        try:
            datetime.strptime(d, "%d/%m/%Y %H:%M")
        except ValueError:
            raise ValidationError(_("Invalid date format"))
        return d

    def clean_voting_ends(self):
        d = self.cleaned_data.get('voting_ends') or ''
        d = d.strip()
        try:
            datetime.strptime(d, "%d/%m/%Y %H:%M")
        except ValueError:
            raise ValidationError(_("Invalid date format"))
        return d

    def clean_candidates(self):
        candidates = self.cleaned_data.get('candidates').strip()
        candidates = [x.strip() for x in candidates.split("\n")]
        for c in candidates:
            if len(c.split(",")) != 3:
                raise ValidationError(_("Candidate %s is invalid") % c)

        return candidates

    def get_candidates(self):
        if not hasattr(self, 'cleaned_data'):
            return []

        cs = self.cleaned_data.get('candidates')[:]
        for i, c in enumerate(cs):
            cs[i] = [x.strip().replace(" ", "-") for x in c.split(",")]
            cs[i] = "{} {}:{}".format(*cs[i])
        return cs

    def get_data(self):
        data = self.cleaned_data
        ret = {}
        ret['elName'] = data.get('name')
        ret['electedLimit'] = data.get('elected_limit') or 0
        ret["votingStarts"] = data.get('voting_starts')
        ret["votingEnds"] = data.get('voting_ends')
        ret["institution"] = data.get('institution')
        ret["numOfEligibles"] = int(data.get('eligibles_count'))
        cands = self.get_candidates()
        schools = defaultdict(lambda: [])
        for i, c in enumerate(cands):
            name, school = c.split(":")
            name, surname, fathername = name.split(" ")
            entry = {'lastName': surname,
                     'candidateTmpId': i,
                     'firstName': name}
            schools[school].append(entry)

        _schools = []
        for school, cands in schools.items():
            _schools.append({'candidates': cands, 'Name': school})

        ret['schools'] = _schools
        ret['ballots'] = []
        return ret
