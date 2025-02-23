# -*- coding: utf-8 -*-

from django.urls import include, re_path
from django.conf import settings
import django.views.i18n
import django.views.static

from zeus.views import auth, admin, poll, site, shared

SERVER_PREFIX = getattr(settings, 'SERVER_PREFIX', '')
if SERVER_PREFIX:
    SERVER_PREFIX = SERVER_PREFIX.rstrip('/') + '/'

app_patterns = []

auth_urls = [
    re_path(r'^auth/logout', auth.logout, name='logout'),
    re_path(r'^auth/login', auth.password_login_view, name='login'),
    re_path(r'^auth/change_password', auth.change_password, name='change_password'),
    re_path(r'^voter-login$', auth.voter_login, name="voter_login"),
    re_path(r'^auth/oauth2$', auth.oauth2_login, name="oauth2_login"),
    re_path(r'^auth/jwt$', auth.jwt_login, name="jwt_login"),
    re_path(r'^auth/shibboleth/(?P<endpoint>.*)$', auth.shibboleth_login, name="shibboleth_login"),
]

admin_urls = [
    re_path(r'^$', admin.HomeView.as_view(), name='admin_home'),
    re_path(r'^reports$', admin.elections_report, name='elections_report'),
    re_path(r'^reports/csv$', admin.elections_report_csv, name='elections_report_csv'),
]

app_patterns += [
    re_path(r'^vote', auth.voter_login, name='voter_quick_login'),
    re_path(r'^f/(?P<fingerprint>.*)', poll.download_signature_short, name='download_signature_short'),
    re_path(r'^', include('zeus.urls.site')),
    re_path(r'^elections/', include('zeus.urls.election')),
    re_path(r'^auth/', include(auth_urls)),
    re_path(r'^admin/', include(admin_urls)),
    re_path(r'^get-randomness/', shared.get_randomness,
        name="get_randomness"),
    re_path(r'^i18n/js', django.views.i18n.JavaScriptCatalog.as_view(),
        name='js_messages', kwargs={'packages': None}),
    re_path(r'^i18n/setlang', site.setlang),
    re_path(r'^i18n/', include('django.conf.urls.i18n')),
    re_path(r'^account_administration/', include('account_administration.urls')),
    re_path(r'^robots\.txt$', django.views.static.serve, {'document_root': settings.STATIC_ROOT, 'path': 'zeus/robots.txt'})
]

urlpatterns = [
    re_path(r'^' + SERVER_PREFIX, include(app_patterns)),
]


# For simplicity of setup, we removed external file server (apache/nginx), and
# static files are now handled by WhiteNoiseMiddleware. This takes care of
# serving STATIC_ROOT (`sitestatic` folder) under STATIC_URL (`/static/`). It
# should be fast enough.
#
# However, there is also `/booth/`, which cannot be served this way, since it's
# outside of STATIC_URL. We currently serve it using Django's `static.serve`,
# which is probably less efficient. Ideally, it should be served under
# `/static/booth` and handled using WhiteNoise a well.
static_urls = [
    # not necessary (handled by WhiteNoise as part of STATIC_URL):
    # re_path(r'static/(?P<path>.*)$', django.views.static.serve,

    # necessary for now (outside of STATIC_URL):
    re_path(r'booth/(?P<path>.*)$', django.views.static.serve, {
        'document_root': settings.BOOTH_STATIC_PATH
    }),
]

urlpatterns += static_urls

'''
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        re_path(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
'''

handler500 = 'zeus.views.site.handler500'
handler400 = 'zeus.views.site.handler400'
handler403 = 'zeus.views.site.handler403'
handler404 = 'zeus.views.site.handler404'
