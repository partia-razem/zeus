# -*- coding: utf-8 -*-

import os
from django.utils.translation import gettext_lazy as _

# go through environment variables and override them


def get_from_env(var, default):
    if var in os.environ:
        return os.environ[var]
    else:
        return default


ROOT_PATH = os.path.join(os.path.dirname(__file__), '..')

TESTING = False
DEBUG = False
ZEUS_TASK_DEBUG = False

ADMINS = [
    ('Zeus admin', 'zeus.admin@localhost'),
]

ELECTION_ADMINS = [
    ('Zeus election admin', 'zeus.election@localhost'),
]

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE', 'zeus'),
        'USER': os.environ.get('PGUSER', 'zeus'),
        'PASS': os.environ.get('PGPASSWORD', ''),
        'HOST': os.environ.get('PGHOST', ''),
        'PORT': os.environ.get('PGPORT', '5432'),
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Warsaw'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'
LANGUAGES = [('en', _('English')), ('el', _('Greek')), ('pl', _('Polish'))]

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = '/home/zeus/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
#ADMIN_MEDIA_PREFIX = '/media/'
STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(ROOT_PATH, 'sitestatic')

# Make this unique, and don't share it with anybody.
SECRET_KEY = get_from_env('SECRET_KEY', 'replaceme')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            ROOT_PATH,
            os.path.join(ROOT_PATH, 'templates')
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
                "zeus.context_processors.user",
                "zeus.context_processors.confirm_messages",
                "zeus.context_processors.theme",
                "zeus.context_processors.lang",
                "zeus.context_processors.prefix",
            ],
        },
    },
]


MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'dj_pagination.middleware.PaginationMiddleware',
    'zeus.middleware.AuthenticationMiddleware',
    'zeus.middleware.ExceptionsMiddleware',
]

ROOT_URLCONF = 'urls'

BOOTH_PATH = os.path.join('zeus', 'static', 'booth')

LOCALE_PATHS = (os.path.join(BOOTH_PATH, 'locale'),)

INSTALLED_APPS = [
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'dj_pagination',
    'heliosauth',
    'helios',
    'zeus',
    'server_ui',
    'account_administration',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

##
## HELIOS
##

MEDIA_ROOT = MEDIA_ROOT

# a relative path where voter upload files are stored
VOTER_UPLOAD_REL_PATH = "voters/%Y/%m/%d"

# Change your email settings
DEFAULT_FROM_EMAIL = get_from_env('DEFAULT_FROM_EMAIL', 'zeus.from@localhost')
DEFAULT_FROM_NAME = get_from_env('DEFAULT_FROM_NAME', 'Zeus admin')
SERVER_EMAIL = '%s <%s>' % (DEFAULT_FROM_NAME, DEFAULT_FROM_EMAIL)

LOGIN_URL = '/auth/'
LOGOUT_ON_CONFIRMATION = False

SITE_DOMAIN = "localhost"
# The two hosts are here so the main site can be over plain HTTP
# while the voting URLs are served over SSL.
URL_HOST = get_from_env("URL_HOST", "http://%s:8000" % SITE_DOMAIN)

# IMPORTANT: you should not change this setting once you've created
# elections, as your elections' cast_url will then be incorrect.
# SECURE_URL_HOST = "https://localhost:8443"
SECURE_URL_HOST = get_from_env("SECURE_URL_HOST", "http://%s:8000" % SITE_DOMAIN)

# this additional host is used to iframe-isolate the social buttons,
# which usually involve hooking in remote JavaScript, which could be
# a security issue. Plus, if there's a loading issue, it blocks the whole
# page. Not cool.
SOCIALBUTTONS_URL_HOST= get_from_env("SOCIALBUTTONS_URL_HOST", "http://%s:8000" % SITE_DOMAIN)

# election stuff
SITE_TITLE = get_from_env('SITE_TITLE', 'Zeus election server')

# FOOTER links
FOOTER_LINKS = []
FOOTER_LOGO = False

WELCOME_MESSAGE = get_from_env('WELCOME_MESSAGE', "This is the default message")

HELP_EMAIL_ADDRESS = get_from_env('HELP_EMAIL_ADDRESS', 'zeus.help@localhost')

AUTH_TEMPLATE_BASE = "server_ui/templates/base.html"
HELIOS_TEMPLATE_BASE = "server_ui/templates/base.html"
HELIOS_ADMIN_ONLY = False
HELIOS_VOTERS_UPLOAD = True
HELIOS_VOTERS_EMAIL = True

SHUFFLE_MODULE = 'zeus.zeus_sk'

# are elections private by default?
HELIOS_PRIVATE_DEFAULT = False

# authentication systems enabled
#AUTH_ENABLED_AUTH_SYSTEMS = ['password','facebook','twitter', 'google', 'yahoo']
AUTH_ENABLED_AUTH_SYSTEMS = ['google']
AUTH_DEFAULT_AUTH_SYSTEM = None

# facebook
FACEBOOK_APP_ID = ''
FACEBOOK_API_KEY = ''
FACEBOOK_API_SECRET = ''

# twitter
TWITTER_API_KEY = ''
TWITTER_API_SECRET = ''
TWITTER_USER_TO_FOLLOW = 'heliosvoting'
TWITTER_REASON_TO_FOLLOW = "we can direct-message you when the result has been computed in an election in which you participated"

# the token for Helios to do direct messaging
TWITTER_DM_TOKEN = {"oauth_token": "", "oauth_token_secret": "", "user_id": "", "screen_name": ""}

# LinkedIn
LINKEDIN_API_KEY = ''
LINKEDIN_API_SECRET = ''

# email server
EMAIL_SUBJECT_PREFIX = '[ZEUS] '
EMAIL_HOST = get_from_env('EMAIL_HOST', 'localhost')
EMAIL_PORT = 2525
EMAIL_HOST_USER = get_from_env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_from_env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = False

# set up logging
#import logging
#logging.basicConfig(
    #level = logging.INFO if DEBUG else logging.INFO,
    #format = '%(asctime)s %(levelname)s %(message)s'
#)

CELERY_BROKER_URL = 'redis://redis'
CELERY_RESULT_BACKEND = 'redis://broker'

BOOTH_STATIC_PATH = ROOT_PATH + '/zeus/static/booth/'

ECOUNTING_LOGIN_URL = "https://x.x.x.x/checkuser.php"
ECOUNTING_POST_URL = "https://x.x.x.x/newelection.php"
ECOUNTING_CHECK_URL = "https://x.x.x.x/newelection.php"
ECOUNTING_SECRET = "xxxxx"

ZEUS_VOTER_EMAIL_RATE = '30/m'

DATA_PATH = os.path.join(ROOT_PATH, 'data')

ZEUS_ELECTION_LOG_DIR = os.path.join(DATA_PATH, 'election_logs')
ZEUS_RESULTS_PATH = os.path.join(DATA_PATH, 'results')
ZEUS_PROOFS_PATH = os.path.join(DATA_PATH, 'proofs')
ZEUS_MIXES_PATH = os.path.join(DATA_PATH, 'mixes')
ZEUS_ALLOW_EARLY_ELECTION_CLOSE = True
ZEUS_CELERY_TEMPDIR = os.path.join('/', 'var', 'run', 'zeus-celery')
ZEUS_HEADER_BG_URL = '/static/zeus/images/logo_bg_nobrand'
ZEUS_TERMS_FILE = os.path.join(ROOT_PATH, 'terms/terms_%(lang)s.html.example')

SERVER_PREFIX = ''

CANDIDATES_CHANGE_TIME_MARGIN = 1

COLLATION_LOCALE = 'el_GR.UTF-8'

MIX_PART_SIZE = 104857600

USE_X_SENDFILE = False


# default sms credentials
ZEUS_SMS_API_USERNAME = ""
ZEUS_SMS_API_PASSWORD = ""
ZEUS_SMS_API_SENDER = "ZEUS"

# per election uuid sms api credentials
# '<election-uuid>': {
#   'username': '<username>',
#   'password': '<password>',
#   'sender': '<sender>'
# }
ZEUS_SMS_API_CREDENTIALS = {}


DEMO_MAX_ELECTIONS = 5
DEMO_MAX_VOTERS = 5
DEMO_SUBMIT_INTERVAL_SECONDS = 10
DEMO_EMAILS_PER_IP = 1

MAX_QUESTIONS_LIMIT = 20

PAGINATION_DEFAULT_WINDOW = 3

# apt-get install ttf-dejavu
DEFAULT_REGULAR_FONT = "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf"
DEFAULT_BOLD_FONT = "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf"

ZEUS_RESULTS_FONT_REGULAR_PATH = DEFAULT_REGULAR_FONT
ZEUS_RESULTS_FONT_BOLD_PATH = DEFAULT_BOLD_FONT

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Necessary for uploading decryption factors.
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024

TEST_RUNNER = "django.test.runner.DiscoverRunner"

SMS_BACKEND = "mybsms"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s [%(levelname)s] %(message)s'
        },
        'verbose': {
            'format': 'zeus: %(process)d [%(levelname)s] %(message)s'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': [],
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        # disabled under Docker
        #
        # 'syslog': {
        #    'level': 'INFO',
        #    'class': 'logging.handlers.SysLogHandler',
        #    'address': '/dev/log',
        #    'formatter': 'verbose'
        # },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'include_html': False,
        },
    },
    'loggers': {
        'django': {
            'propagate': True,
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': True,
    },
}


# Session age for users, in seconds.
VOTER_SESSION_AGE = 10 * 60
TRUSTEE_SESSION_AGE = 2 * 60 * 60
USER_SESSION_AGE = 14 * 24 * 60 * 60

SESSION_COOKIE_AGE = USER_SESSION_AGE
