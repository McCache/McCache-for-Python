# See MIT license at the bottom of this script.
#
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html
# SEE:  https://realpython.com/pytest-python-testing

import hashlib
import logging
import queue
import time

import pytest

from collections import OrderedDict
from datetime import datetime
from mccache.pycache import Cache

# SEE: https://docs.python.org/3/library/stdtypes.html#dict
#
#   When started, I had a different implementation and was testing alot of the overwrote methods.
#   Since, I have change my implementation BUT I am keeping the original test so more testing is better.

class   TestCache:
    """Test Cache
    """
#   Don't define a constructor.  You will get the following error:
#       PytestCollectionWarning: cannot collect test class 'TestCache' because it has a __init__ constructor
#   def __init__(self): ...

    def test_init_00(self):
        """Test basic initialization
        """
        c = Cache()
        assert  c.name  == 'default'    ,f"Expect   'name'      should be 'default' ,but actual is {c.name}"
        assert  c.maxlen    == 256      ,f"Expect   'max'       should be 256       ,but actual is {c.maxlen}"
        assert  c.maxsize   == 256*1024 ,f"Expect   'size'      should be 65536     ,but actual is {c.maxsize}"
        assert  c.ttl       == 0        ,f"Expect   'ttl'       should be 0         ,but actual is {c.ttl}"
        assert  c.msgbdy    is not None ,f"Expect   'msgbdy'    should NOT be None  ,but actual is {c.msgbdy}"
        assert  c.logger    is not None ,f"Expect   'logger'    should NOT be None  ,but actual is {c.logger}"
        assert  c.queue     is None     ,f"Expect   'queue'     should be None      ,but actual is {c.queue}"
        assert  c.metadata  == {}       ,f"Expect   'metadata'  should be dict      ,but actual is {c.metadata}"

    def test_init_01(self):
        """Test parameterized initialization
        """
        l = logging.getLogger()
        q = queue.Queue()

        c = Cache( name='test' ,max=16 ,size=256 ,ttl=3 ,msgbdy='log formatted txt' ,logger=l ,queue=q )
        assert  c.name  == 'test'       ,f"Expect   'name'      should be 'test'    ,but actual is {c.name}"
        assert  c.maxlen    == 16       ,f"Expect   'max'       should be 16        ,but actual is {c.maxlen}"
        assert  c.maxsize   == 256      ,f"Expect   'size'      should be 256       ,but actual is {c.maxsize}"
        assert  c.ttl       == 3        ,f"Expect   'ttl'       should be 3         ,but actual is {c.ttl}"
        assert  c.msgbdy is not None    ,f"Expect   'msgbdy'    should NOT be None  ,but actual is {c.msgbdy}"
        assert  c.logger    == l        ,f"Expect   'logger'    should NOT be None  ,but actual is {c.logger}"
        assert  c.queue     == q        ,f"Expect   'queue'     should NOT be None  ,but actual is {c.queue}"
        assert  c.metadata  == {}       ,f"Expect   'metadata'  should be dict      ,but actual is {c.metadata}"

    #@pytest.mark.xfail(reason="Not done implementing the dunder methods.")
    def test_init_02(self):
        e  = {'three': 3, 'one': 1, 'two': 2}

        c1 = Cache({'three': 3, 'one': 1, 'two': 2})        # Mapping type
        assert  e == c1                 ,f"Expect   {e} ,but actual is {c1}"

        c2 = Cache([('two', 2), ('one', 1), ('three', 3)])  # Iterable
        assert  e == c2                 ,f"Expect   {e} ,but actual is {c2}"

        c3 = Cache(one=1, two=2, three=3)                   # Positional
        assert  e == c3                 ,f"Expect   {e} ,but actual is {c3}"

        c4 = Cache({'one': 1, 'three': 3}, two=2)           # Mapping
        assert  e == c4                 ,f"Expect   {e} ,but actual is {c4}"

        c5 = Cache(zip(['one', 'two', 'three'], [1, 2, 3])) # Iterable
        assert  e == c5                 ,f"Expect   {e} ,but actual is {c5}"

    def test_init_exception_01(self):
        with pytest.raises(Exception ,match=r'An instance of "logging.Logger" is required!'):
            c = Cache( logger=datetime.now() )

        with pytest.raises(Exception ,match=r'An instance of "queue.Queue" is required!'):
            c = Cache( queue=datetime.now() )

    def test_setgetitem_01(self):   # NOTE: Dunder __setitem__() and __getitem__()
        d = {'a': 1 ,'b': '2' ,'c': True ,'d': [{'e': datetime.now()}] }
        s = 'string value'
        t = datetime.now()
        c = Cache()

        # Setting section.
        #
        c['k1'] = True
        v =     c['k1']
        assert  v == True           ,f"Expect   True ,but actual is {c['k1']}"
        v =     c.get('k1')
        assert  v == True           ,f"Expect   True ,but actual is {c['k1']}"
        v =     c.get('k1_' ,False)
        assert  v       ==   False  ,f"Expect  False ,but actual is {v}"

        c['k2'] = 7
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c['k2']
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c.get('k2')
        assert  c['k2'] == 7        ,f"Expect   7    ,but actual is {c['k2']}"
        v =     c.get('k2_' ,9)
        assert  v       ==   9      ,f"Expect   9    ,but actual is {v}"

        c['k3'] = 3.14
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c['k3']
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c.get('k3')
        assert  c['k3'] == 3.14     ,f"Expect   3.14 ,but actual is {c['k3']}"
        v =     c.get('k3_' ,4.13)
        assert  v       ==   4.13   ,f"Expect   4.13 ,but actual is {v}"

        c['k4'] = t
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c['k4']
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c.get('k4')
        assert  c['k4'] == t        ,f"Expect   {t}   ,but actual is {c['k4']}"
        v =     c.get('k4_' ,t)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {v}"#

        c['k5'] = s
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c['k5']
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c.get('k5')
        assert  c['k5'] == s        ,f"Expect   {s}   ,but actual is {c['k5']}"
        v =     c.get('k5_' ,s)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {v}"

        c['k6'] = d
        assert  c['k6'] == d        ,f"Expe6t   {d}   ,but actual is {c['k6']}"
        v =     c['k6']
        assert  c['k6'] == d        ,f"Expect   {d}   ,but actual is {c['k6']}"
        v =     c.get('k6')
        assert  c['k6'] == d        ,f"Expect   {d}   ,but actual is {c['k6']}"
        v =     c.get('k6_' ,d)
        assert  v       ==   d      ,f"Expect   {d}   ,but actual is {v}"

    def test_setdefault_01(self):
        d = {'a': 1 ,'b': '2' ,'c': True ,'d': [{'e': datetime.now()}] }
        s = 'string value'
        t = datetime.now()
        c = Cache()

        v =     c.setdefault('k1__',True)
        assert  c['k1__'] == True   ,f"Expect   True ,but actual is {c['k1__']}"
        v =     c.setdefault('k1__',False)
        assert  c['k1__'] == True   ,f"Expect   True ,but actual is {c['k1__']}"
        v =     c.setdefault('k2__',3)
        assert  c['k2__'] == 3      ,f"Expect   3    ,but actual is {c['k2__']}"
        v =     c.setdefault('k2__',5)
        assert  c['k2__'] == 3      ,f"Expect   3    ,but actual is {c['k2__']}"
        v =     c.setdefault('k3__',1.23)
        assert  v       ==   1.23   ,f"Expect   1.23 ,but actual is {c['k3__']}"
        v =     c.setdefault('k3__',7.89)
        assert  v       ==   1.23   ,f"Expect   1.23 ,but actual is {c['k3__']}"
        v =     c.setdefault('k4__',t)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {c['K4__']}"
        v =     c.setdefault('k4__',d)
        assert  v       ==   t      ,f"Expect   {t}   ,but actual is {c['K4__']}"
        v =     c.setdefault('k5__',s)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {c['k5__']}"
        v =     c.setdefault('k5__',d)
        assert  v       ==   s      ,f"Expect   {s}   ,but actual is {c['k5__']}"
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
        e = {'k1': True ,'k2': 7 ,'k3': 3.14}
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14

        v = c.copy()
        assert  v == e      ,f"Expect   {e}     ,but actual is {v}"

    def test_fromkeys_01(self):
        k = {'k1', 'k2', 'k3'}
        e = {'k1': 5 ,'k2': 5 ,'k3': 5}
        c = Cache()

        v = {k: v for k ,v in c.fromkeys( k ,5 ).items()}
        assert  v == e                      ,f"Expect   {e}         ,but actual is {v}"
        assert  v.keys()    == e.keys()     ,f"Expect   {e.keys()}     ,but actual is {v.keys()}"

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

    def test_popitem_01(self):
        c = Cache()

        with pytest.raises(KeyError ,match=r'k1'):
            _ = c['k1']

        c.update({'k1': 123})
        k ,v = c.popitem()
        assert  k == 'k1'   ,f"Expect    k1     ,but actual is {k}"
        assert  v ==  123   ,f"Expect    123    ,but actual is {v}"

        c.update({'k1': 456})
        k ,v = c.popitem()
        assert  k == 'k1'   ,f"Expect    k1     ,but actual is {k}"
        assert  v ==  456   ,f"Expect    456    ,but actual is {v}"


    @pytest.mark.xfail(reason="Don't know why it fail when they both expect and actual look identical. SEE: test_values_02()")
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

    # Test my cache very specific enhancements.
    #

    def test_meta_01(self):
        e = {   'k1': hashlib.md5( bytearray(str( True ) ,encoding='utf-8') ).digest(),
                'k2': hashlib.md5( bytearray(str( 7    ) ,encoding='utf-8') ).digest(),
                'k3': hashlib.md5( bytearray(str( 3.14 ) ,encoding='utf-8') ).digest(),
             }
        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"

        c = Cache({ 'k3': 3.14, 'k1': True  , 'k2': 7})         # Mapping type
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"
        c = Cache([('k2', 7), ('k1', True)  ,('k3', 3.14)])     # Iterable
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"
        c = Cache(k1=True, k2=7, k3=3.14)                       # Positional
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"
        c = Cache({ 'k1': True, 'k3': 3.14} ,k2=7)              # Mapping
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"
        c = Cache(zip(['k1', 'k2', 'k3'], [True, 7, 3.14]))     # Iterable
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"

        c = Cache()
        c.update({'k1': True ,'k2': 7 ,'k3': 3.14})
        v = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"

        c = Cache()
        _ =     c.setdefault('k1'   ,True   )
        _ =     c.setdefault('k1'   ,False  )
        _ =     c.setdefault('k2'   ,7      )
        _ =     c.setdefault('k2'   ,3      )
        _ =     c.setdefault('k3'   ,3.14   )
        _ =     c.setdefault('k3'   ,1.23   )
        _ = {k: v['crc'] for k ,v in c.metadata.items()}
        assert  v == e      ,f"Expect   {e}    ,but actual is {v}"

        c = Cache()
        c['k1'] = True
        c['k2'] = 7
        c['k3'] = 3.14
        v = c.inserts
        assert  v == 3      ,f"Expect   3       ,but actual is {v}"

        c['k3'] = 1.23
        v = c.updates
        assert  v == 1      ,f"Expect   1       ,but actual is {v}"

        v = c.lookups
        assert  v == 0      ,f"Expect   0       ,but actual is {v}"

        del c['k2']
        del c['k3']
        v = c.deletes
        assert  v == 2      ,f"Expect   2       ,but actual is {v}"

    def test_eviction_01(self):
        c = Cache( max=3 )
        c['k1'] = 1
        c['k2'] = 2
        c['k3'] = 3

        a = len(c)
        assert  a == 3      ,f"Expect   3       ,but actual is {a}"

        c['k4'] = 4
        a = len(c)
        assert  a == 3      ,f"Expect   3       ,but actual is {a}"

        with pytest.raises(KeyError ,match=r'k1'):
            _ = c['k1'] # Should be evicted.

        c = Cache( size=360 )
        c['k1'] = 1
        c['k2'] = 2
        a = len(c)
        assert  a == 2      ,f"Expect   2       ,but actual is {a}"

        c['k3'] = 3
        a = len(c)
        assert  a == 2      ,f"Expect   2       ,but actual is {a}"

        with pytest.raises(KeyError ,match=r'k1'):
            _ = c['k1'] # Should be evicted.

        c = Cache( ttl=1 )   # ttl initialized to 1 second.
        a = c.ttl
        assert  a == 1      ,f"Expect   2       ,but actual is {a}"

        c['k1'] = 1
        c['k2'] = 2
        c['k3'] = 3
        a = len(c)
        assert  a == 3      ,f"Expect   3       ,but actual is {a}"

        time.sleep(3)       # 3 seconds
        c['k4'] = 4
        a = len(c)
        assert  1 == a      ,f"Expect   1       ,but actual is {a}"

        with pytest.raises(KeyError ,match=r'k1'):
            _ = c['k1'] # Should be evicted.

    def test_queue(self):
        q = queue.Queue()
        c = Cache( queue=q )
        t = Cache.tsm_version()
        c['k1'] = True
        c['k2'] = 3
        c['k3'] = 3.14
        c['k3'] = 1.23
        del c['k3']

        a = q.get()
        h = hashlib.md5( bytearray(str( True)  ,encoding='utf-8') ).digest()
        assert  a[0] == 'INS'       ,f"Expect   INS     ,but actual is {a[0]}"
        assert  a[1] >=  t          ,f"Expect   >={t}   ,but actual is {a[1]}"
        assert  a[2] == 'default'   ,f"Expect   default ,but actual is {a[2]}"
        assert  a[3] == 'k1'        ,f"Expect   k1      ,but actual is {a[3]}"
        assert  a[4] ==  h          ,f"Expect   {h}     ,but actual is {a[4]}"
        assert  a[5] ==  True       ,f"Expect   True    ,but actual is {a[5]}"

        a = q.get()
        h = hashlib.md5( bytearray(str( 3   )  ,encoding='utf-8') ).digest()
        assert  a[0] == 'INS'       ,f"Expect   INS     ,but actual is {a[0]}"
        assert  a[1] >=  t          ,f"Expect   >={t}   ,but actual is {a[1]}"
        assert  a[2] == 'default'   ,f"Expect   default ,but actual is {a[2]}"
        assert  a[3] == 'k2'        ,f"Expect   k2      ,but actual is {a[3]}"
        assert  a[4] ==  h          ,f"Expect   {h}     ,but actual is {a[4]}"
        assert  a[5] ==  3          ,f"Expect   3       ,but actual is {a[5]}"

        a = q.get()
        h = hashlib.md5( bytearray(str( 3.14)  ,encoding='utf-8') ).digest()
        assert  a[0] == 'INS'       ,f"Expect   INS     ,but actual is {a[0]}"
        assert  a[1] >=  t          ,f"Expect   >={t}   ,but actual is {a[1]}"
        assert  a[2] == 'default'   ,f"Expect   default ,but actual is {a[2]}"
        assert  a[3] == 'k3'        ,f"Expect   k3      ,but actual is {a[3]}"
        assert  a[4] ==  h          ,f"Expect   {h}     ,but actual is {a[4]}"
        assert  a[5] ==  3.14       ,f"Expect   3.14    ,but actual is {a[5]}"

        a = q.get()
        h = hashlib.md5( bytearray(str( 1.23)  ,encoding='utf-8') ).digest()
        assert  a[0] == 'UPD'       ,f"Expect   INS     ,but actual is {a[0]}"
        assert  a[1] >=  t          ,f"Expect   >={t}   ,but actual is {a[1]}"
        assert  a[2] == 'default'   ,f"Expect   default ,but actual is {a[2]}"
        assert  a[3] == 'k3'        ,f"Expect   k3      ,but actual is {a[3]}"
        assert  a[4] ==  h          ,f"Expect   {h}     ,but actual is {a[4]}"
        assert  a[5] ==  1.23       ,f"Expect   1.23    ,but actual is {a[5]}"

        a = q.get()
        h = hashlib.md5( bytearray(str( 1.23)  ,encoding='utf-8') ).digest()
        assert  a[0] == 'DEL'       ,f"Expect   INS     ,but actual is {a[0]}"
        assert  a[1] >=  t          ,f"Expect   >={t}   ,but actual is {a[1]}"
        assert  a[2] == 'default'   ,f"Expect   default ,but actual is {a[2]}"
        assert  a[3] == 'k3'        ,f"Expect   k3      ,but actual is {a[3]}"
        assert  a[4] ==  h          ,f"Expect   {h}     ,but actual is {a[4]}"
        assert  a[5] is  None       ,f"Expect   None    ,but actual is {a[5]}"

    def test_callback(self):
        def callback(ctx: dict):
            assert  ctx  is not None
            assert 'key'    in  ctx
            assert 'tsm'    in  ctx
            assert 'lkp'    in  ctx
            assert 'prvcrc' in  ctx
            assert 'newcrc' in  ctx

        c = Cache( callback=callback )
        c['k1'] = True
        time.sleep(0.5)
        c['k1'] = False


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
