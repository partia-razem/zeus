# -*- coding: utf-8 -*-


import six
from codecs import BOM_LE, BOM_BE, getreader
from collections import OrderedDict

from django.db.models import Q
from django.urls import reverse
from django.shortcuts import render
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email, ValidationError
if six.PY2:
    from backports.csv import (Sniffer, excel, Error as csvError,
                               reader as imported_csv_reader)
else:
    from csv import (Sniffer, excel, Error as csvError,
                     reader as imported_csv_reader)


def election_trustees_to_text(election):
    content = ""
    for trustee in election.trustees.filter(secret_key__isnull=True):
        content += "%s, %s\n" % (trustee.name, trustee.email)
    return content


def append_ballot_to_msg(election, msg):
    if msg[-1] != '\n':
        msg += '\n'
    el_type_str = "\nElection type: {}\n\n".format(election.election_module)
    msg += el_type_str
    msg += "Ballot info\n***********************\n"
    for poll in election.polls.all():
        msg += "- Poll name: {}\n".format(poll.name)
        for ballot in poll.questions_data:
            question = ballot.get('question', None)
            if question:
                msg += "- Question: {}\n".format(question)
            answers = ballot.get('answers', None)
            if answers:
                msg += "- Answers\n"
                for answer in answers:
                    msg += "  * {}\n".format(answer)
            scores = ballot.get('scores', None)
            if scores:
                msg += "- Scores: "
                for score in scores:
                    msg += '[{}] '.format(str(score))
                msg += '\n'
            min_ans = ballot.get('min_answers', None)
            max_ans = ballot.get('max_answers', None)
            if min_ans and max_ans:
                msg += "- Min answers: {}\n- Max answers: {}\n".format(min_ans,
                                                                   max_ans)
            eligibles = ballot.get('eligibles', None)
            if eligibles:
                msg += "- Eligibles: {}\n".format(eligibles)
            has_limit = ballot.get('has_department_limit', None)
            if has_limit:
                department_limit = ballot.get('department_limit', None)
                msg += "- Poll has department limit of:{}\n".format(str(department_limit))
        candidates = poll.zeus.do_get_candidates()
        candidates = [str(x) for x in candidates]
        candidates = str(candidates)
        msg += "- do_get_candidates:\n{}\n\n".format(candidates)
    return msg


def election_reverse(election, view, **extra):
    kwargs = {'election_uuid': election.uuid}
    kwargs.update(extra)
    return reverse('election_%s' % view, kwargs=kwargs)


def poll_reverse(poll, view, **extra):
    kwargs = {'election_uuid': poll.election.uuid, 'poll_uuid': poll.uuid}
    kwargs.update(extra)
    return reverse('election_poll_%s' % view, kwargs=kwargs)


def extract_trustees(content):
    trustees = []
    rows = [x.strip() for x in content.strip().split("\n")]
    for trustee in rows:
        if not trustee:
            continue
        trustee = [x.strip() for x in trustee.split(",")]
        trustees.append(trustee)
    return trustees


def render_template(request, template_name, vars={}):
    vars_with_user = vars.copy()
    vars_with_user['user'] = request.zeususer
    vars_with_user['settings'] = settings
    vars_with_user['CURRENT_URL'] = request.path

    # csrf protection
    if 'csrf_token' in request.session:
        vars_with_user['csrf_token'] = request.session['csrf_token']

    return render(request, 'server_ui/templates/%s.html' % template_name,
                  vars_with_user)


def sanitize_mobile_number(num):
    size = len(num)
    if size == 12:
        return num
    if size == 10:
        return "30%s" % str(num)
    if size > 12:
        return num[-12:]
    raise Exception("Invalid number")


def decalize(string, sep='-', chunk=2):
    if not isinstance(string, str):
        m = "argument must be an 'str', not %r" % type(string)
        raise ValueError(m)
    slist = []
    s = ''
    i = 0
    for z, c in enumerate(string):
        o = ord(c)
        if o < 32 or o > 127:
            m = ("index %d: Can only decalize printable ASCII characters "
                 "in range 32-127, not character %d(\\x%x)")
            m = m % (z, o, o)
            raise ValueError(m)
        s += "%02d" % (ord(c) - 32)
        i += 1
        if i == chunk:
            slist.append(s)
            s = ''
            i = 0

    if s:
        slist.append(s)

    return sep.join(slist)


def undecalize(string):
    i = 2
    s = ''
    d = 0
    for z, c in enumerate(string):
        if not c.isdigit():
            continue
        i -= 1
        d *= 10
        d += int(c, 10)
        if not i:
            d += 32
            if d > 127:
                m = "index %d: invalid ASCII code %d > 127" % (z, d)
                raise ValueError(m)
            s += chr(d)
            d = 0
            i = 2

    if i != 2:
        m = "Input has an odd number of decimal digits: %d" % (z + 1)
        raise ValueError(m)

    return s


VOTER_TABLE_HEADERS = OrderedDict([
    ('voter_login_id', _('Registration ID')),
    ('voter_email', _('Email')),
    ('voter_surname', _('Surname')),
    ('voter_name', _('Given name')),
    ('voter_fathername', _('Middle name')),
    ('voter_mobile', _('Mobile phone')),
    ('voter_weight', _('Vote weight')),
    ('cast_votes__id', _('Has voted')),
    ('last_booth_invitation_send_at', _('Booth invitation sent at')),
    ('last_visit', _('Last visit')),
    ('actions', _('Actions'))
    ])

ELECTION_TABLE_HEADERS = OrderedDict([
    ('name', _('Name')),
    ('institution', _('Institution')),
    ('admins', _('Administrator')),
    ('created_at', _('Creation')),
    ('voting_starts_at', _('Start')),
    ('voting_ends_at', _('End')),
    ('status_display', _('Election status')),
    ('trial', _('Trial')),
    ('official', _('Official'))
    ])

REPORT_TABLE_HEADERS = OrderedDict([
    ('institution', _('Institution')),
    ('voters', _('Voters')),
    ('voters_voted', _('Voters Voted')),
    ('voting_starts_at', _('Start')),
    ('completed_at', _('End')),
    ('name', _('Name')),
    ('polls_count', _('Number of Polls')),
    ('admins', _('Administrators')),
    ('official', _('Official'))
    ])

VOTER_SEARCH_FIELDS = ['voter_login_id', 'voter_name', 'voter_surname', 'voter_email']
VOTER_EXTRA_HEADERS = ['excluded_at']
VOTER_BOOL_KEYS_MAP = {
        'voted': ('cast_votes__id', 'nullcheck'),
        'email': ('voter_email', 'nullcheck'),
        'mobile': ('voter_mobile', 'nullcheck'),
        'invited': ('last_booth_invitation_send_at', 'nullcheck'),
        'excluded': ('excluded_at', 'nullcheck'),
     }

ELECTION_SEARCH_FIELDS = ['name', 'description', 'institution__name', 'admins__user_id', ]
ELECTION_EXTRA_HEADERS = []
ELECTION_BOOL_KEYS_MAP = {'trial': 'trial'}

REPORT_SEARCH_FIELDS = ['name', 'institution__name', 'admins__user_id', ]
REPORT_EXTRA_HEADERS = []
REPORT_BOOL_KEYS_MAP = {}


def parse_q_param(q):
    args = []
    for special_arg in q.split(" "):
        if special_arg.startswith("+") or special_arg.startswith("-"):
            q = q.replace(" " + special_arg, "")
            q = q.replace(special_arg, "")
            args.append(special_arg)
    return q, args


def get_filters(q_param, table_headers, search_fields, bool_keys_map, extra_headers=[], exclude_fields=[]):

    q = Q()
    if q_param != '':
        q_parsed, extra_filters = parse_q_param(q_param)
        for search_field in search_fields:
            if search_field in exclude_fields:
                continue
            kwargs = {'%s__icontains' % search_field: q_parsed.strip()}
            q = q | Q(**kwargs)
        for arg in extra_filters:
            arg_type = False if arg[0] == "-" else True
            key = bool_keys_map.get(arg[1:], arg[1:])
            nullcheck = False
            if type(key) == tuple:
                nullcheck = key[1] == 'nullcheck'
                key = key[0]
            if key in (list(table_headers.keys()) + extra_headers):
                flt = ''
                if nullcheck:
                    flt = '__isnull'
                    arg_type = not arg_type
                q = q & Q(**{'%s%s' % (key, flt): arg_type})
    return q


def get_voters_filters_with_constraints(q_param=None, constraints_include=None,
                                        constraints_exclude=None):
    q = Q()
    if q_param:
        q = q & get_filters(q_param, VOTER_TABLE_HEADERS, VOTER_SEARCH_FIELDS,
                            VOTER_BOOL_KEYS_MAP, VOTER_EXTRA_HEADERS)
    if constraints_include:
        q = q & Q(**constraints_include)
    if constraints_exclude:
        q = q & ~Q(**constraints_exclude)
    return q


class CSVReader(object):

    def __init__(self, csv_data, min_fields=2, max_fields=6, **kwargs):

        if hasattr(csv_data, 'read') and hasattr(csv_data, 'seek'):
            f = csv_data
        elif isinstance(csv_data, six.binary_type):
            f = six.BytesIO(csv_data)
        elif isinstance(csv_data, six.text_type):
            f = six.StringIO(csv_data)
        else:
            m = "Please provide str or file to csv_data, not {type}"
            m = m.format(type=type(csv_data))
            raise ValueError(m)
        if min_fields == 0 or max_fields == 0:
            m = "Invalid arguments, min_fields or max_fields can't be 0"
            raise ValueError(m)
        if min_fields > max_fields:
            m = "Invalid arguments, min_fields must be less than max_fields"
            raise ValueError(m)

        encodings = DEFAULT_ENCODINGS[:]
        preferred_encoding = kwargs.get('preferred_encoding', None)
        if preferred_encoding is not None:
            encodings.insert(1, preferred_encoding)

        self.min_fields = min_fields
        self.max_fields = max_fields

        sample = pick_sample(f.read(65536))
        f.seek(0)
        if isinstance(sample, six.binary_type):
            encoding = get_encoding(sample.strip(), encodings=encodings)
            f = getreader(encoding)(f)
            sample = pick_sample(f.read(65536))
            f.seek(0)

        dialect = kwargs.get('dialect', get_dialect(sample))
        self.reader = imported_csv_reader(f, dialect)

    def __next__(self):
        row = next(self.reader)
        if len(row) < self.min_fields or len(row) > self.max_fields:
            raise CSVCellError(len(row), self.min_fields, self.max_fields)
        row += [''] * (self.max_fields - len(row))
        return row

    def __iter__(self):
        return self


class CSVCellError(Exception):

    def __init__(self, cell_num, min_fields, max_fields):
        if cell_num < min_fields:
            self.m = ("CSV cells(" + str(cell_num) +
                      ") < min_fields(" + str(min_fields)+")")
        if cell_num > max_fields:
            self.m = ("CSV cells(" + str(cell_num) +
                      ") > max_fields("+str(max_fields)+")")

    def __str__(self):
        return self.m


DEFAULT_ENCODINGS = ['utf-8', 'utf-16', 'utf-16le', 'utf-16be']


def get_encoding(csv_data, encodings=DEFAULT_ENCODINGS):
    encodings = encodings[:]
    encodings.reverse()
    while 1:
        m = "Cannot decode csv data! Please choose another encoding."
        if not encodings:
            raise ValueError(m)
        encoding = encodings[-1]
        try:
            if (encoding == "utf-16" and
                    (not csv_data or csv_data[0:2] not in (BOM_LE, BOM_BE))):
                raise ValueError
            data = csv_data.decode(encoding)
            if (encoding in ('utf-16be', 'utf-16le')
                    and data and data[0] == '\ufffe'):
                data = data[1:]
            if data.count('\x00') > 0:
                m = "Wrong encoding detected (heuristic)"
                raise ValueError(m)
            if data.count('\u0A00') > data.count('\u000A'):
                m = "Wrong endianess (heuristic)"
                raise ValueError(m)
            break
        except (UnicodeDecodeError, ValueError):
            encodings.pop()
            continue
    return encoding


def pick_sample(part):
    nl = b'\x0a' if isinstance(part, six.binary_type) else '\x0a'
    sample, sep, junk = part.rpartition(nl)
    if len(sample) & 1:
        sample += sep
    return sample


def get_dialect(sample):
    try:
        dialect = Sniffer().sniff(sample, (',', ':', ' ', '\t', ';'))
    except (csvError):
        dialect = excel
    return dialect


def email_is_valid(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def ordered_dict_prepend(dct, key, value):
    if key in dct:
        del dct[key]

    items = list(dct.items())
    dct.clear()
    dct[key] = value
    dct.update(items)
