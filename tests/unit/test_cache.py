# See MIT license at the bottom of this script.
#
# Pytest script template.
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html
# SEE:  https://realpython.com/pytest-python-testing

import logging
import queue

import pytest

from collections import OrderedDict
from datetime import datetime
from pycache.cache import Cache

# SEE: https://docs.python.org/3/library/stdtypes.html#dict
#
class   TestCache:
    def test_init_00(self):
        """Test basic initialization
        """
        c = Cache()
        assert  c.name  == 'default'    ,f"Expect   'name'      should be 'default' ,but actual is {c.name}"
        assert  c.maxlen    == 256      ,f"Expect   'max'       should be 256       ,but actual is {c.maxlen}"
        assert  c.maxsize   == 65536    ,f"Expect   'size'      should be 65536     ,but actual is {c.maxsize}"
        assert  c.ttl       == 0        ,f"Expect   'ttl'       should be 0         ,but actual is {c.ttl}"
        assert  c.logmsg    is not None ,f"Expect   'logmsg'    should NOT be None  ,but actual is {c.logmsg}"
        assert  c.logger    is not None ,f"Expect   'logger'    should NOT be None  ,but actual is {c.logger}"
        assert  c.queue     is None     ,f"Expect   'queue'     should be None      ,but actual is {c.queue}"

    def test_init_01(self):
        """Test parameterized initialization
        """
        l = logging.getLogger()
        q = queue.Queue()

        c = Cache( name='test' ,max=16 ,size=256 ,ttl=3 ,logmsg='log formatted txt' ,logger=l ,queue=q )
        assert  c.name  == 'test'       ,f"Expect   'name'      should be 'test'    ,but actual is {c.name}"
        assert  c.maxlen    == 16       ,f"Expect   'max'       should be 16        ,but actual is {c.maxlen}"
        assert  c.maxsize   == 256      ,f"Expect   'size'      should be 256       ,but actual is {c.maxsize}"
        assert  c.ttl       == 3        ,f"Expect   'ttl'       should be 3         ,but actual is {c.ttl}"
        assert  c.logmsg is not None    ,f"Expect   'logmsg'    should NOT be None  ,but actual is {c.logmsg}"
        assert  c.logger    == l        ,f"Expect   'logger'    should NOT be None  ,but actual is {c.logger}"
        assert  c.queue     == q        ,f"Expect   'queue'     should NOT be None  ,but actual is {c.queue}"

    @pytest.mark.xfail(reason="Not done implementing the dunder methods.")
    def test_init_02(self):
        e  = {'three': 3, 'one': 1, 'two': 2}

        c1 = Cache({'three': 3, 'one': 1, 'two': 2})        # Mapping type
        assert  e == c1                 ,f"Expect   {e} ,but actual is {c1}"

        c2 = Cache([('two', 2), ('one', 1), ('three', 3)])  # Iterable
        c3 = Cache(one=1, two=2, three=3)
        c4 = Cache({'one': 1, 'three': 3}, two=2)
        c5 = Cache(zip(['one', 'two', 'three'], [1, 2, 3]))


    def test_init_exception_01(self):
        with pytest.raises(Exception ,match=r'An instance of "logging.Logger" is required!'):
            c = Cache( logger=datetime.now() )

        with pytest.raises(Exception ,match=r'An instance of "queue.Queue" is required!'):
            c = Cache( queue=datetime.now() )

    def test_setget_01(self):
        d = {'a': 1 ,'b': '2' ,'c': True ,'d': [{'e': datetime.now()}] }
        s = 'string value'
        t = datetime.now()
        c = Cache()

        # Setting section.
        #
        c['k1'] = True
        assert  c['k1'] == True     ,f"Expect   True ,but actual is {c['k1']}"
        v =     c['k1']
        assert  c['k1'] == True     ,f"Expect   True ,but actual is {c['k1']}"
        v =     c.get('k1')
        assert  c['k1'] == True     ,f"Expect   True ,but actual is {c['k1']}"
        v =     c.get('k1_' ,False)
        assert  v       ==   False  ,f"Expect  False ,but actual is {v}"
        v =     c.setdefault('k1__',True)
        assert  c['k1__'] == True   ,f"Expect   True ,but actual is {c['k1__']}"
        v =     c.setdefault('k1__',False)
        assert  c['k1__'] == True   ,f"Expect   True ,but actual is {c['k1__']}"

        c['k2'] = 7
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c['k2']
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c.get('k2')
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c.get('k2_' ,9)
        assert  v       ==   9      ,f"Expect   9    ,but actual is {v}"
        v =     c.setdefault('k2__',3)
        assert  c['k2__'] == 3      ,f"Expect   3    ,but actual is {c['k2__']}"
        v =     c.setdefault('k2__',5)
        assert  c['k2__'] == 3      ,f"Expect   3    ,but actual is {c['k2__']}"

        c['k3'] = 3.14
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c['k3']
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c.get('k3')
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c.get('k3_' ,4.13)
        assert  v       ==   4.13   ,f"Expect   4.13 ,but actual is {v}"
        v =     c.setdefault('k3__',1.23)
        assert  v       ==   1.23   ,f"Expect   1.23 ,but actual is {c['k3__']}"
        v =     c.setdefault('k3__',7.89)
        assert  v       ==   1.23   ,f"Expect   1.23 ,but actual is {c['k3__']}"

        c['k4'] = t
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c['k4']
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c.get('k4')
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c.get('k4_' ,t)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {v}"
        v =     c.setdefault('k4__',t)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {c['K4__']}"
        v =     c.setdefault('k4__',d)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {c['K4__']}"

        c['k5'] = s
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c['k5']
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c.get('k5')
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c.get('k5_' ,s)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {v}"
        v =     c.setdefault('k5__',s)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {c['k5__']}"
        v =     c.setdefault('k5__',d)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {c['k5__']}"

        c['k6'] = d
        assert  c['k6'] == d        ,f"Expe6t   {d}   ,but actual is {c['k6']}"
        v =     c['k6']
        assert  c['k6'] == d        ,f"Expect   {d}   ,but actual is {c['k6']}"
        v =     c.get('k6')
        assert  c['k6'] == d        ,f"Expect   {d}   ,but actual is {c['k6']}"
        v =     c.get('k6_' ,d)
        assert  v       ==   d      ,f"Expect   {d}   ,but actual is {v}"
        v =     c.setdefault('k6__',d)
        assert  v       ==   d      ,f"Expect   {d}   ,but actual is {c['k6__']}"
        v =     c.setdefault('k6__',t)
        assert  v       ==   d      ,f"Expect   {d}   ,but actual is {c['k6__']}"

    def test_delete_01(self):
        d = {'a': 1 ,'b': '2' ,'c': True ,'d': [{'e': datetime.now()}] }
        s = 'string value'
        t = datetime.now()
        c = Cache()

        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        c['k4'] = t
        c['k5'] = s
        c['k6'] = d

        del c['k6']
        with pytest.raises(KeyError ,match=r'k6'):
            del c['k6']

        v = c.pop('k5')
        assert  v == s              ,f"Expect   {s}   ,but actual is {v}"
        with pytest.raises(KeyError ,match=r'k5'):
            _ = c['k5']

        v = c.pop('k5')
        assert  v is None           ,f"Expect   None  ,but actual is {c['k5']}"

        k ,v = c.popitem( last=True )
        assert  k == 'k4'           ,f"Expect   k4    ,but actual is {k}"
        assert  v == t              ,f"Expect   {t}   ,but actual is {v}"
        with pytest.raises(KeyError ,match=r'k4'):
            _ = c['k4']

        k ,v = c.popitem( last=False )
        assert  k == 'k1'           ,f"Expect   k1    ,but actual is {k}"
        assert  v == True           ,f"Expect   True  ,but actual is {v}"
        with pytest.raises(KeyError ,match=r'k1'):
            _ = c['k1']

    # Public dictionary methods
    #
    def test_clear_01(self):
        d = {'a': 1 ,'b': '2' ,'c': True ,'d': [{'e': datetime.now()}] }
        s = 'string value'
        t = datetime.now()
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        c['k4'] = t
        c['k5'] = s
        c['k6'] = d

        l = len(c)
        assert  len(c)  == 6        ,f"Expect   6      ,but actual is {len(c)}"

        c.clear()
        assert  len(c)  == 0        ,f"Expect   0      ,but actual is {len(c)}"

    def test_copy_01(self):
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        with pytest.raises(NotImplementedError ,match=r'Cache should NOT be shallow copied.'):
            _ = c.copy()

    def test_fromkeys_01(self):
        k = ('key1', 'key2', 'key3')
        v = 0
        c = Cache()
        with pytest.raises(NotImplementedError ,match=r'Use dict.fromkeys method instead.'):
            _ = Cache.fromkeys( k ,v )

    def test_items_01(self):
        e = {'k1': True ,'k2': 7 ,'k3': 3.14}.items()
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14

        v = c.items()
        assert  v == e      ,f"Expect   {e}     ,but actual is {v}"

    def test_keys_01(self):
        e = {'k1': True ,'k2': 7 ,'k3': 3.14}.keys()
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = c.keys()
        assert  v == e      ,f"Expect   {e}     ,but actual is {v}"

    def test_update_01(self):
        c = Cache()
        with pytest.raises(NotImplementedError ,match=r'Cache entry cannot be set this way.'):
            c.update({'k1' ,123})

    @pytest.mark.xfail(reason="Don't know why it fail when they both expect and actual look identical")
    def test_values_01(self):
        e = OrderedDict({'k1': True ,'k2': 7 ,'k3': 3.14}).values()
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = c.values()
        assert  v == e      ,f"Expect   {e}     ,but actual is {v}"

    def test_values_02(self):
        e = OrderedDict({'k1': True ,'k2': 7 ,'k3': 3.14}).values()
        e = [i for i in e]
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = c.values()
        v = [i for i in v]
        assert  v == e      ,f"Expect   {e}     ,but actual is {v}"

    def test_misc_01(self):
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = len(c)
        assert  v == 3      ,f"Expect   3      ,but actual is {v}"


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
