# See MIT license at the bottom of this script.
#
# Pytest script template.
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html

import pytest
import unittest.mock    as  mock
#mport MyClassToTest

#   Fixture are global external resource for all your tests.
#   Defining it in this script will only be scoped in this script.
#   To be scoped for all test scripts, place the fixture defs into a special script called "conftest.py"
#
@pytest.fixture(scope='session')
def database():
    return None


#   How to use skip and xfail to deal with tests that cannot succeed
#   SEE:    https://docs.pytest.org/en/7.4.x/how-to/skipping.html#skip
#
#   @pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10 or higher" )
#   @pytest.mark.xfail( sys.platform == "win32", reason="bug in a 3rd party library" )
#

#   Use marker to annotate groups to allow specific test run.  This one is mark as 'change'.
#   Your can run this specific group of test as follows:
#       $ py.test -m unit
@pytest.mark.unit
#   Use Python class to group similar tests together.
class   TestClass:
    """Test `Class`
    """

    #   Per test setup and tear down.  To display output use: "-s" CLI option
    #
    def setup_method(self ,method: callable):
        pass

    def teardown_method(self ,method: callable):
        pass


    @pytest.mark.skip(reason="Skip 'test_init_00()' test for it is an example of a failure.")
    def test_unit_00(self):
        assert  0 == 1  ,"Expect value is 0 but Actual value is 1."

    def test_unit_01(self):
        assert  1 == 1

    #   Parameterized test with different input values to tests.  Much cleaner than for loops.
    @pytest.mark.parametrize("input1 ,expect" ,[(1 ,1) ,(2 ,2) ,(3 ,3)] )
    def test_unit_02(self ,input1 ,expect):
        def fn( var ):
            return var

        assert  fn( input1 ) == expect

    def test_unit_exception_01(self):
        with pytest.raises(Exception ,match=r"err"):   # Check message with regex.
            raise Exception("Test err text.")

    #   Mock the original method call with ours.
    #   TODO: Try out Monkey Patch.  https://docs.pytest.org/en/latest/how-to/monkeypatch.html#monkeypatching
    @pytest.mark.xfail(reason="This is just an example.")
    @mock.patch("socket.recvfrom")
    def test_unit_extapi_name( mock_socket_recvfrom ):      # Mock reference to the original method.
        mock_socket_recvfrom.return_value = "Mock value"    # Setup the mock returned value.
        actual = socket.recvfrom()                          # Call the actual external service but it is mocked.

        assert actual is not None


# The MIT License (MIT)
# Copyright (c) 2023 Edward Lau.
#
# Permission is hereby granted ,free of charge ,to any person obtaining a copy
# of this software and associated documentation files (the "Software") ,to deal
# in the Software without restriction ,including without limitation the rights
# to use ,copy ,modify ,merge ,publish ,distribute ,sublicense ,and/or sell
# copies of the Software ,and to permit persons to whom the Software is
# furnished to do so ,subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS" ,WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED ,INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY ,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY ,WHETHER IN AN ACTION OF CONTRACT ,TORT OR
# OTHERWISE ,ARISING FROM ,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.
