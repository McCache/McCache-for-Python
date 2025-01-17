import os
import sys

# The purpose of this script is to be used primarily for development testing.

print("Hello. This is McCache.")

filepath = f"{__file__[:__file__.find('src')-1]}{os.sep}tests{os.sep}unit{os.sep}start_mccache.py"  #   C:\Work\Me\McCache-for-Python\tests\unit\start_mccache.py
if  os.path.isfile( filepath ):
    # ONLY used during development testing.
    sys.path.append(__file__[:__file__.find('src')-1])  #   C:\Work\Me\McCache-for-Python
    sys.path.append(__file__[:__file__.find('src')+3])  #   C:\Work\Me\McCache-for-Python\src

    print("Running the test file 'start_mccache.py' in the development environment.")
    import tests.unit.start_mccache # noqa: F401 I001
else:
    print("The test file 'start_mccache.py' is NOT found.  You need to be in the development environment.")
