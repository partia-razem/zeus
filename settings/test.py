try:
    from .local import *  # noqa
except ImportError:
    from .dev import *  # noqa

import os
import errno
import datetime
import multiprocessing

DEBUG = False
TEMPLATE_DEBUG = True

LANGUAGES = (('en', 'EN'), ('el', 'EL'))
LANGUAGE_CODE = 'en'

ZEUS_TESTS_ELECTION_PARAMS = {}

ZEUS_TEST_DB = os.environ.get('ZEUS_DB')
if os.environ.get('ZEUS_TEST_DATABASE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': os.environ.get('ZEUS_DB', 'zeus_test'),
            'USER': os.environ.get('ZEUS_DB_USER', 'zeus_test'),
            'PASSWORD': os.environ.get('ZEUS_DB_PASSWORD', 'zeus_test'),
            'HOST': os.environ.get('ZEUS_DB_HOST', 'localhost'),
            'PORT': 5432 # in memory post
        }
    }

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

SOUTH_TESTS_MIGRATE = False
#DATABASES = {
    #'default': {
        #'ENGINE': 'django.db.backends.sqlite3',
        #'NAME': ':memory:'
    #}
#}

ZEUS_MIXNET_NR_PARALLEL = multiprocessing.cpu_count()
ZEUS_MIXNET_NR_ROUNDS = 16

ZEUS_ELECTION_STREAM_HANDLER = os.environ.get("ZEUS_TESTS_VERBOSE", False)

EMAIL_SUBJECT_PREFIX = 'Zeus System Message: '

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

TESTS_DIR = os.environ.get('ZEUS_TESTS_DIR', '/tmp/zeus-tests')
PROJECT_ROOT = '%s/%s' % (TESTS_DIR, datetime.datetime.now())
ZEUS_ELECTION_LOG_DIR = os.path.join(PROJECT_ROOT, 'election_logs')
ZEUS_PROOFS_PATH = os.path.join(PROJECT_ROOT, 'proofs')
ZEUS_RESULTS_PATH = os.path.join(PROJECT_ROOT, 'results')
ZEUS_MIXES_PATH = os.path.join(PROJECT_ROOT, 'mixes')

dirs = [ZEUS_ELECTION_LOG_DIR, ZEUS_PROOFS_PATH,
        ZEUS_RESULTS_PATH, ZEUS_MIXES_PATH]
for dir in dirs:
    mkdir_p(dir)

ZEUS_ELECTION_FREEZE_DELAY = 0

HELIOS_CRYPTOSYSTEM_PARAMS = {}
HELIOS_CRYPTOSYSTEM_PARAMS['p'] = 19936216778566278769000253703181821530777724513886984297472278095277636456087690955868900309738872419217596317525891498128424073395840060513894962337598264322558055230566786268714502738012916669517912719860309819086261817093999047426105645828097562635912023767088410684153615689914052935698627462693772783508681806906452733153116119222181911280990397752728529137894709311659730447623090500459340155653968608895572426146788021409657502780399150625362771073012861137005134355305397837208305921803153308069591184864176876279550962831273252563865904505239163777934648725590326075580394712644972925907314817076990800469107L
HELIOS_CRYPTOSYSTEM_PARAMS['q'] = 9968108389283139384500126851590910765388862256943492148736139047638818228043845477934450154869436209608798158762945749064212036697920030256947481168799132161279027615283393134357251369006458334758956359930154909543130908546999523713052822914048781317956011883544205342076807844957026467849313731346886391754340903453226366576558059611090955640495198876364264568947354655829865223811545250229670077826984304447786213073394010704828751390199575312681385536506430568502567177652698918604152960901576654034795592432088438139775481415636626281932952252619581888967324362795163037790197356322486462953657408538495400234553L
HELIOS_CRYPTOSYSTEM_PARAMS['g'] = 19167066187022047436478413372880824313438678797887170030948364708695623454002582820938932961803261022277829853214287063757589819807116677650566996585535208649540448432196806454948132946013329765141883558367653598679571199251774119976449205171262636938096065535299103638890429717713646407483320109071252653916730386204380996827449178389044942428078669947938163252615751345293014449317883432900504074626873215717661648356281447274508124643639202368368971023489627632546277201661921395442643626191532112873763159722062406562807440086883536046720111922074921528340803081581395273135050422967787911879683841394288935013751L


if os.path.exists("/usr/share/fonts/truetype/ubuntu-font-family/"):
    ZEUS_RESULTS_FONT_REGULAR_PATH = '/usr/share/fonts/truetype/ubuntu-font-family/Ubuntu-R.ttf'
    ZEUS_RESULTS_FONT_BOLD_PATH = '/usr/share/fonts/truetype/ubuntu-font-family/Ubuntu-B.ttf'

USE_X_SENDFILE = False
SERVER_PREFIX = ''
