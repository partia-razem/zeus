import logging
import urllib2 
import urllib
import json

from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest

from zeus import auth
from zeus.utils import *
from zeus.forms import ChangePasswordForm, VoterLoginForm

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_http_methods

from helios.view_utils import render_template
from helios.models import Voter, Poll
from zeus.forms import LoginForm
from zeus import auth


logger = logging.getLogger(__name__)


@auth.unauthenticated_user_required
@require_http_methods(["POST", "GET"])
def voter_login(request):
    form_cls = VoterLoginForm
    form = VoterLoginForm()
    if request.method == 'POST':
        form = VoterLoginForm(request.POST)
        if form.is_valid():
            poll = form._voter.poll
            user = auth.ZeusUser(form._voter)
            user.authenticate(request)
            poll.logger.info("Poll voter '%s' logged in (global login view)",
                             form._voter.voter_login_id)
            return HttpResponseRedirect(poll_reverse(poll, 'index'))

    cxt = {'form': form}
    return render_template(request, 'voter_login', cxt)


@auth.unauthenticated_user_required
@require_http_methods(["POST", "GET"])
def password_login_view(request):
    error = None
    if request.method == "GET":
        form = LoginForm()
    else:
        form = LoginForm(request.POST)

    request.session['auth_system_name'] = 'password'

    if request.method == "POST":
        if form.is_valid():
            request.session[auth.USER_SESSION_KEY] = form._user_cache.pk
            logger.info("User %s logged in", form._user_cache.user_id)
            return HttpResponseRedirect(reverse('admin_home'))

    return render_template(request,
                           'login',
                           {'form': form, 'error': error})


def logout(request):
    return_url = request.GET.get('next', reverse('home'))
    logger.info("User %s logged out", request.zeususer.user_id)
    request.zeususer.logout(request)
    return HttpResponseRedirect(return_url)


@auth.user_required
def change_password(request):
    user = request.zeususer

    # only admin users can change password
    if not user.is_admin:
        raise PermissionDenied('32')

    password_changed = request.GET.get('password_changed', None)
    form = ChangePasswordForm(user)
    if request.method == "POST":
        form = ChangePasswordForm(user._user, request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(
                reverse('change_password') + '?password_changed=1')
    return render_template(request, 'change_password',
                           {'form': form,
                            'password_changed': password_changed})

def oauth2_login(request):
    # bad request if not session keus
    # remove session keys after 
    token = None
    code = request.GET.get('code')
    poll_uuid = request.GET.get('state')
    oauth2_voter_uuid = request.session.get('oauth2_voter_uuid')
    oauth2_voter_email = request.session.get('oauth2_voter_email')
    if code and poll_uuid and oauth2_voter_uuid and oauth2_voter_email:
        poll = Poll.objects.get(uuid = poll_uuid)
        data = {
                'client_id': poll.oauth2_client_id,
                'client_secret': poll.oauth2_client_secret,
                'redirect_uri': 'http://zeus-dev.grnet.gr:8081/auth/auth/oauth2',
                'code': code,
                'grant_type': 'authorization_code',
                }
        data = urllib.urlencode(data)
        url = 'https://accounts.google.com/o/oauth2/token'
        r = urllib2.urlopen(url, data=data)
        a = json.loads(r.read())
        token = a.get('access_token')
        if token:
            url="https://www.googleapis.com/plus/v1/people/me?access_token={}".format(token)
            r = urllib2.urlopen(url)
            a = json.loads(r.read())
            response_mail = a['emails'][0]['value']
            if response_mail == request.session['oauth2_voter_email']:
                voter = Voter.objects.get(poll__uuid=poll_uuid,
                    uuid=request.session['oauth2_voter_uuid'])
                poll = Poll.objects.get(uuid=poll_uuid)
                user = auth.ZeusUser(voter)
                user.authenticate(request)
                poll.logger.info("Poll voter '%s' logged in", voter.voter_login_id)
                del request.session['oauth2_voter_uuid']
                del request.session['oauth2_voter_email']
                return HttpResponseRedirect(poll_reverse(poll, 'index'))
            else:
                from django.contrib import messages
                messages.error(request, 'oauth2 user does not match voter')
                return HttpResponseRedirect(reverse("home"))

    else:
        return HttpResponseBadRequest(400)
