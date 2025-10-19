
import os
import logging
import uuid
import json
import subprocess

from collections import defaultdict
from time import time
from random import randint

from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseNotAllowed, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _, get_language
from django.contrib import messages
from django.conf import settings
from django.views.i18n import set_language
from django.forms.formsets import formset_factory

from helios.view_utils import render_template
from django.contrib.auth.hashers import make_password
from helios.models import User, Election
from heliosauth.models import UserGroup
from zeus.models import Institution
from zeus.utils import email_is_valid
from zeus.auth import ZeusUser

from zeus.stv_count_reports import stv_count_and_report

logger = logging.getLogger(__name__)


def stv_count(request):

    context = {'menu_active': 'home'}
    session = request.session.get('stvcount', {})
    results_generated = context['results'] = session.get('results', {})
    el_data = None

    do_count = True
    if request.GET.get('form', None):
        do_count = False
        from zeus.forms import STVElectionForm, STVBallotForm
        form = STVElectionForm()

        ballots_form = None
        if request.method == "POST":
            form = STVElectionForm(request.POST, disabled=False)
            if form.is_valid():
                candidates = form.get_candidates()

                class F(STVBallotForm):
                    pass

                setattr(F, 'candidates', candidates)
                formset_count = int(form.cleaned_data.get('ballots_count'))
                if not request.POST.get('submit_ballots', False):
                    BallotsForm = formset_factory(F, extra=formset_count,
                                                max_num=formset_count)
                    ballots_form = BallotsForm()
                else:
                    BallotsForm = formset_factory(F, extra=0,
                                                max_num=formset_count)
                    ballots_form = BallotsForm(request.POST)
                    if ballots_form.is_valid():
                        el = form.get_data()
                        for i, b in enumerate(ballots_form):
                            choices = b.get_choices(i + 1)
                            if not choices.get('votes'):
                                continue
                            el['ballots'].append(b.get_choices(i + 1))
                        el_data = el
                        do_count = True
                    else:
                        context['error'] = _("Invalid ballot data")

        context['import'] = 1
        context['form'] = form
        context['ballots_form'] = ballots_form

    if request.GET.get('reset', None):
        del request.session['stvcount']
        return HttpResponseRedirect(reverse('stv_count'))

    if request.GET.get('download', None) and results_generated:
        filename = results_generated.get(request.GET.get('download', 'pdf'), '/nofile')
        if not os.path.exists(filename):
            return HttpResponseRedirect(reverse('stv_count') + "?reset=1")

        response = FileResponse(open(filename, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=%s' % os.path.basename(filename)
        response['Content-Length'] = os.path.getsize(filename)
        return response

    if request.method == "POST" and do_count:
        el_data = el_data or json.loads(request.FILES.get('data').read())
        _uuid = str(uuid.uuid4())
        files = stv_count_and_report(_uuid, el_data)
        json_file = os.path.join('/tmp', 'json-stv-results-%s' % _uuid)
        with open(json_file, 'w', encoding="utf-8") as f:
            f.write(json.dumps(el_data, ensure_ascii=False))
        files.append(('json', json_file))
        session['results'] = dict(files)
        request.session['stvcount'] = session
        return HttpResponseRedirect(reverse('stv_count'))

    request.session['stvcount'] = session
    return render_template(request, "zeus/stvcount", context)


def setlang(request):
    lang = request.POST.get('language')
    if lang not in [x[0] for x in settings.LANGUAGES]:
        return HttpResponseRedirect(reverse('home'))
    return set_language(request)


def home(request):
    user = request.zeususer
    bad_login = request.GET.get('bad_login')
    return render_template(request, "zeus/home", {
        'menu_active': 'home',
        'user': user,
        'bad_login': bad_login
    })


def terms(request):
    terms_file = getattr(settings, 'ZEUS_TERMS_FILE', None)
    if terms_file is None:
        return HttpResponseRedirect(reverse('home'))

    with open(terms_file % {'lang': get_language()}, "r") as terms_fd:
        terms_contents = terms_fd.read()

    return render_template(request, "zeus/terms", {
        'content': terms_contents
    })


def faqs_trustee(request):
    user = request.zeususer
    return render_template(request, "zeus/faqs_admin", {
        'menu_active': 'faqs',
        'submenu': 'admin',
        'user': user
    })


def faqs_voter(request):
    user = request.zeususer
    return render_template(request, "zeus/faqs_voter", {
      'menu_active': 'faqs',
      'submenu': 'voter',
      'user': user
    })


def resources(request):
    user = request.zeususer
    return render_template(request, "zeus/resources", {
        'menu_active': 'resources',
        'user': user
    })


def contact(request):
    user = request.zeususer
    return render_template(request, "zeus/contact", {
        'menu_active': 'contact',
        'user': user
    })


def stats(request):
    user = request.zeususer._user
    if not request.zeususer.is_admin:
        return HttpResponseRedirect(reverse('home'))
    uuid = request.GET.get('uuid', None)
    election = None

    elections = Election.objects.filter()
    if not (user and user.superadmin_p):
        elections = Election.objects.filter(canceled_at__isnull=True,
                                            completed_at__isnull=False,
                                            voting_ended_at__isnull=False,
                                            admins__in=[user],
                                            trial=False)

    elections = elections.order_by('-created_at')

    if uuid:
        try:
            election = elections.get(uuid=uuid)
        except Election.DoesNotExist:
            return HttpResponseRedirect(reverse('home'))

    return render_template(request, 'zeus/stats', {
        'menu_active': 'stats',
        'election': election,
        'uuid': uuid,
        'user': user,
        'elections': elections
    })


_demo_addresses = defaultdict(int)
_demo_emails_per_address = defaultdict(set)


def _get_demo_user(email_address):
    password = email_address

    try:
        user = User.objects.get(name=email_address)
    except User.DoesNotExist:
        pass
    else:
        if user.user_id.startswith("demo_"):
            user.info = {'name': email_address,
                         'password': make_password(password)}
            user.save()
            return user, password

    try:
        inst = Institution.objects.get(name="DEMO")
    except Institution.DoesNotExist:
        return None, ''

    tries = 10
    while tries > 0:
        user_id = "demo_%d" % randint(1000, 1000000)
        try:
            User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            break
        tries -= 1

    if tries <= 0:
        return None, ''

    demogroup = None
    try:
        demogroup = UserGroup.objects.get(name="demo")
    except UserGroup.DoesNotExist:
        pass
    newuser = User()
    newuser.user_type = "password"
    newuser.admin_p = True
    newuser.info = {'name': email_address,
                    'password': make_password(password)}
    newuser.name = email_address
    newuser.user_id = user_id
    newuser.superadmin_p = False
    newuser.institution = inst
    newuser.ecounting_account = False
    newuser.save()
    if demogroup:
        newuser.user_groups.add(demogroup)
        newuser.save()
    return newuser, password


@csrf_exempt
def demo(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    email_address = request.POST.get('email', '')

    if not email_is_valid(email_address):
        msg = _("Invalid email address")
        messages.error(request, msg)
        return HttpResponseRedirect(reverse('home'))

    remote_addr = request.META.get("REMOTE_ADDR", None)
    client_address = request.META.get('HTTP_X_FORWARDED_FOR', remote_addr)
    if not client_address:
        msg = _("Client address unavailable")
        messages.error(request, msg)
        return HttpResponseRedirect(reverse('home'))

    now_seconds = int(time())
    last_seconds = _demo_addresses[client_address]
    if now_seconds - last_seconds < settings.DEMO_SUBMIT_INTERVAL_SECONDS:
        msg = _("There are too many requests from your address")
        messages.error(request, msg)
        return HttpResponseRedirect(reverse('home'))

    emails = _demo_emails_per_address[client_address]
    if email_address not in emails and len(emails) >= settings.DEMO_EMAILS_PER_IP:
        msg = _("There are too many emails registered from your address")
        messages.error(request, msg)
        return HttpResponseRedirect(reverse('home'))

    demo_user, password = _get_demo_user(email_address)
    if demo_user is None:
        msg = _("Cannot create demo users right now. Sorry.")
        messages.error(request, msg)
        return HttpResponseRedirect(reverse('home'))

    emails.add(email_address)
    mail_subject = render_to_string('email/demo_email_subject.txt',
                                    {'settings': settings}).strip()
    mail_body = render_to_string('email/demo_email_body.txt',
                                 {'settings': settings,
                                  'username': demo_user.user_id,
                                  'password': password})
    mail_from = _(settings.DEFAULT_FROM_NAME)
    mail_from += ' <%s>' % settings.DEFAULT_FROM_EMAIL
    _demo_addresses[client_address] = now_seconds

    msg = _("An email with demo credentials has been sent to %s") % email_address
    messages.success(request, msg)
    logger.info("DEMO::%s::%s::%s" % (
                email_address, client_address, demo_user.user_id))
    send_mail(mail_subject, mail_body, mail_from, [email_address])
    return HttpResponseRedirect(reverse('home'))


def error(request, code=None, message=None, type='error'):
    user = getattr(request, 'zeususer', ZeusUser.from_request(request))
    messages_len = len(messages.get_messages(request))
    if not messages_len and not message:
        return HttpResponseRedirect(reverse('home'))

    response = render_template(request, "zeus/error", {
        'code': code,
        'error_message': message,
        'error_type': type,
        'user': user,
    })
    response.status_code = int(code)
    return response


def handler403(request, exception):
    msg = _("You do not have permission to access this page.")
    return error(request, 403, msg)


def handler500(request):
    msg = _("An error has been occured. Please notify the server admin.")
    return error(request, 500, msg)


def handler400(request, exception):
    msg = _("An error has been occured. Please notify the server admin.")
    return error(request, 400, msg)


def handler404(request, exception):
    msg = _("The requested page was not found.")
    return error(request, 404, msg)


def commit(request):
    output = subprocess.check_output(
        ['git', 'log', '-n1'],
        cwd=settings.ROOT_PATH,
        encoding='utf-8',
        errors='ignore'
    )
    return HttpResponse(output, content_type='text/plain; charset=utf-8')
