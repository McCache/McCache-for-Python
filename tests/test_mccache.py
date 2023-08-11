# TODO: Fix the path.
#import mccache as mc
#import tests.unit.start_mccache

# In the above McCache is also imported in the `tests.unit.start_mccache` package.
# Just to make sure we can see that McCache is initialize only once.


def test_always_pass():
    assert True

def test_always_fail():
    assert False
