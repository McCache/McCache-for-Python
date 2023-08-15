# TODO: Fix the path.
#import mccache as mc
#import tests.unit.start_mccache

# In the above McCache is also imported in the `tests.unit.start_mccache` package.
# Just to make sure we can see that McCache is initialize only once.

_mcCacheDict = {}   # Private dict to segeregate the cache namespace.

# os.environ['MCCACHE_DEBUG_FILE']'

def initialize( logfile: str ):
    with open( logfile, 'r') as fn:
        for ln in fn.readline():
            pass

def test_always_pass():
    assert True

def test_always_fail():
    assert False
