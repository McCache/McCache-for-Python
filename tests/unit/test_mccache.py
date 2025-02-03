# See MIT license at the bottom of this script.
#
# Pytest script template.
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html
# SEE:  https://realpython.com/pytest-python-testing

import  hashlib
import  os
import  pickle
import  sys
import  pytest
import  queue
import  struct
import  threading
import  unittest.mock   as  mock

from    collections.abc     import Callable
from    cryptography.fernet import Fernet
from    logging.handlers    import QueueListener

from    pycache import Cache as PyCache


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

    def test_init_00(self):
        """Test basic default initialization
        """
        threading.RLock().acquire()

        import mccache

        # Make sure the internal objects are inituialize correctly with the correct types.
        assert isinstance( mccache._mcCache     ,dict         ) ,f'Expect mccache._mcCache   to be type dict    ,but actual is {type(mccache._mcCache       )}'  
        assert isinstance( mccache._mcArrived   ,dict         ) ,f'Expect mccache._mcArrived to be type dict    ,but actual is {type(mccache._mcArrived     )}'
        assert isinstance( mccache._mcPending   ,dict         ) ,f'Expect mccache._mcPending to be type dict    ,but actual is {type(mccache._mcPending     )}'
        assert isinstance( mccache._mcMember    ,dict         ) ,f'Expect mccache._mcMember  to be type dict    ,but actual is {type(mccache._mcMember      )}'
        assert isinstance( mccache._mcLgLsnr    ,QueueListener) ,f'Expect mccache._mcLgLsnr  to be type QueueListener, but actual is {type(mccache._mcLgLsnr)}'
        assert isinstance( mccache._mcIBQueue   ,queue.Queue  ) ,f'Expect mccache._mcIBQueue to be type Queue   ,but actual is {type(mccache._mcIBQueue     )}'
        assert isinstance( mccache._mcOBQueue   ,queue.Queue  ) ,f'Expect mccache._mcOBQueue to be type Queue   ,but actual is {type(mccache._mcOBQueue     )}'
        assert isinstance( mccache._mcQueueStats,dict         ) ,f'Expect mccache._mcQueueStats to be type dict ,but actual is {type(mccache._mcQueueStats  )}'

        # Assert default configuration was not changed.
        assert mccache._mcConfig.cache_ttl      == 3600         ,f'Expect mccache.cache_ttl      == 3600        ,but actual is{mccache._mcConfig.cache_ttl      }'
        assert mccache._mcConfig.cache_max      == 256          ,f'Expect mccache.cache_max      == 256         ,but actual is{mccache._mcConfig.cache_max      }'
        assert mccache._mcConfig.cache_size     == 8388608      ,f'Expect mccache.cache_size     == 8388608     ,but actual is{mccache._mcConfig.cache_size     }'
        assert mccache._mcConfig.cache_pulse    == 5            ,f'Expect mccache.cache_pulse    == 5           ,but actual is{mccache._mcConfig.cache_pulse    }'
        assert mccache._mcConfig.cache_mode     == 1            ,f'Expect mccache.cache_mode     == 1           ,but actual is{mccache._mcConfig.cache_mode     }'
        assert mccache._mcConfig.cache_sync_on  == 0.0          ,f'Expect mccache.cache_sync_on  == 0.0         ,but actual is{mccache._mcConfig.cache_sync_on  }'
        assert mccache._mcConfig.congestion     == 25           ,f'Expect mccache.congestion     == 25          ,but actual is{mccache._mcConfig.congestion     }'
        assert mccache._mcConfig.crypto_key     == None         ,f'Expect mccache.crypto_key     is None        ,but actual is{mccache._mcConfig.crypto_key     }'
        assert mccache._mcConfig.packet_mtu     == 1472         ,f'Expect mccache.packet_mtu     == 1472        ,but actual is{mccache._mcConfig.packet_mtu     }'
        assert mccache._mcConfig.packet_pace    == 0.1          ,f'Expect mccache.packet_pace    == 0.1         ,but actual is{mccache._mcConfig.packet_pace    }'
        assert mccache._mcConfig.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip   == 224.0.0.3   ,but actual is{mccache._mcConfig.multicast_ip   }'
        assert mccache._mcConfig.multicast_port == 4000         ,f'Expect mccache.multicast_port == 4000        ,but actual is{mccache._mcConfig.multicast_port }'
        assert mccache._mcConfig.multicast_hops == 3            ,f'Expect mccache.multicast_hops == 3           ,but actual is{mccache._mcConfig.multicast_hops }'
        assert mccache._mcConfig.callback_win   == 5            ,f'Expect mccache.callback_win   == 5           ,but actual is{mccache._mcConfig.callback_win   }'
        assert mccache._mcConfig.monkey_tantrum == 0            ,f'Expect mccache.monkey_tantrum == 0           ,but actual is{mccache._mcConfig.monkey_tantrum }'
        assert mccache._mcConfig.daemon_sleep   == 1.00         ,f'Expect mccache.daemon_sleep   == 1.00        ,but actual is{mccache._mcConfig.daemon_sleep   }'


    def test_init_01(self):
        """Test instantiated internal objects using pyproject.toml and env var.
        """
        threading.RLock().acquire()

        os.environ['MCCACHE_CACHE_TTL']     = '3000'
        os.environ['MCCACHE_CACHE_MAX']     = '128'
        os.environ['MCCACHE_CACHE_MODE']    = '0'
        os.environ['MCCACHE_CACHE_SIZE']    = '1048576'
        os.environ['MCCACHE_CACHE_PULSE']   = '2'
        os.environ['MCCACHE_CONGESTION']    = '20'
        os.environ['MCCACHE_CRYPTO_KEY']    = 'sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc='
        os.environ['MCCACHE_PACKET_MTU']    = '1470'
        os.environ['MCCACHE_MULTICAST_IP']  = '224.0.0.26'
        os.environ['MCCACHE_MULTICAST_PORT']= '4001'
        os.environ['MCCACHE_MULTICAST_HOPS']= '5'

        # The following are loaded from pyproject.toml
        if  os.path.exists('pyproject.toml'):
            os.rename('pyproject.toml' ,'pyproject.toml.orig')

        with open('pyproject.toml' ,'w') as fp:
            fp.write("[tool.mccache]\n")
            fp.write('callback_win   = 7\n')
            fp.write('monkey_tantrum = 2\n')
            fp.write('daemon_sleep   = 1.23\n')
            fp.write('\n')

        import mccache
        mccache._mcConfig = mccache._load_config()

        os.remove('pyproject.toml')
        if  os.path.exists('pyproject.toml.orig'):
            os.rename('pyproject.toml.orig' ,'pyproject.toml')

        assert isinstance( mccache._mcConfig    ,mccache.McCacheConfig  )   ,'Expect mccache._mcConfig  to be type mccache.McCacheConfig.'
#           assert isinstance( mccache._mcCrypto    ,Fernet                 )   ,'Expect mccache._mcCrypto  to be type Fernet.'

        cfg = mccache._mcConfig
        # Assert default configuration was not changed.
        assert cfg.cache_ttl      == 3000         ,f'Expect mccache.cache_ttl     == 3000         ,but actual is {cfg.cache_ttl     }'
        assert cfg.cache_max      == 128          ,f'Expect mccache.cache_max     == 128          ,but actual is {cfg.cache_max     }'
        assert cfg.cache_size     == 1048576      ,f'Expect mccache.cache_size    == 1048576      ,but actual is {cfg.cache_size    }'
        assert cfg.cache_pulse    == 2            ,f'Expect mccache.cache_pulse   == 2            ,but actual is {cfg.cache_pulse   }'
        assert cfg.cache_mode     == 0            ,f'Expect mccache.cache_mode    == 0            ,but actual is {cfg.cache_mode    }'
        assert cfg.congestion     == 20           ,f'Expect mccache.congestion    == 20           ,but actual is {cfg.congestion    }'
        assert cfg.crypto_key     =='sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc='\
                                                ,f'Expect mccache.crypto_key    == sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc='
        assert cfg.packet_mtu     == 1470         ,f'Expect mccache.packet_mtu    == 1470         ,but actual is {cfg.packet_mtu    }'
        assert cfg.multicast_ip   =='224.0.0.26'  ,f'Expect mccache.multicast_ip  == 224.0.0.26   ,but actual is {cfg.multicast_ip  }'
        assert cfg.multicast_port == 4001         ,f'Expect mccache.multicast_port== 4001         ,but actual is {cfg.multicast_port}'
        assert cfg.multicast_hops == 5            ,f'Expect mccache.multicast_hops== 5            ,but actual is {cfg.multicast_hops}'
        assert cfg.callback_win   == 7            ,f'Expect mccache.callback_win  == 7            ,but actual is {cfg.callback_win  }'
        assert cfg.monkey_tantrum == 2            ,f'Expect mccache.monkey_tantrum== 2            ,but actual is {cfg.monkey_tantrum}'
        assert cfg.daemon_sleep   == 1.23         ,f'Expect mccache.daemon_sleep  == 1.23         ,but actual is {cfg.daemon_sleep  }'

        # Test validity of the multicast IP address.
        os.environ['MCCACHE_MULTICAST_IP']  = '224.0.0.3'       # Valid
        cfg =  mccache._mcConfig = mccache._load_config()
        assert mccache._mcConfig.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip  == 224.0.0.3    ,but actual is {mccache._mcConfig.multicast_ip}'

        os.environ['MCCACHE_MULTICAST_IP']  = '223.0.0.3'       # Invalid
        cfg =  mccache._mcConfig = mccache._load_config()
        assert cfg.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip  == 224.0.0.3    ,but actual is {cfg.multicast_ip}'

        os.environ['MCCACHE_MULTICAST_IP']  = '224.1.0.3'       # Invalid
        cfg =  mccache._mcConfig = mccache._load_config()
        assert cfg.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip  == 224.0.0.3    ,but actual is {cfg.multicast_ip}'

        os.environ['MCCACHE_MULTICAST_IP']  = '224.0.1.3'       # Invalid
        cfg =  mccache._mcConfig = mccache._load_config()
        assert cfg.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip  == 224.0.0.3    ,but actual is {cfg.multicast_ip}'

        os.environ['MCCACHE_MULTICAST_IP']  = '224.0.0.4'       # Invalid
        cfg =  mccache._mcConfig = mccache._load_config()
        assert cfg.multicast_ip   =='224.0.0.3'   ,f'Expect mccache.multicast_ip  == 224.0.0.3    ,but actual is {cfg.multicast_ip}'

        # Clean up the environment.
        del os.environ['MCCACHE_CACHE_TTL']
        del os.environ['MCCACHE_CACHE_MAX']
        del os.environ['MCCACHE_CACHE_MODE']
        del os.environ['MCCACHE_CACHE_SIZE']
        del os.environ['MCCACHE_CACHE_PULSE']
        del os.environ['MCCACHE_CONGESTION']
        del os.environ['MCCACHE_CRYPTO_KEY']
        del os.environ['MCCACHE_PACKET_MTU']
        del os.environ['MCCACHE_MULTICAST_IP']
        del os.environ['MCCACHE_MULTICAST_PORT']
        del os.environ['MCCACHE_MULTICAST_HOPS']


    def test_public_methods_01(self):
        """Test public factory methods.
        """
        threading.RLock().acquire()
        import  mccache
        mccache._mcConfig = mccache._load_config()

        # Test this factory method.
        c = mccache.get_cache()

        assert  c.name      == 'mccache'    ,f'Expect cache.name    == mccache  ,but actual is {c.name}'
        assert  c.maxlen    ==  256         ,f'Expect cache.maxlen  == 256      ,but actual is {c.maxlen}'
        assert  c.maxsize   ==  8388608     ,f'Expect cache.maxsize == 8388608  ,but actual is {c.maxsize}'
        assert  c.ttl       ==  3600        ,f'Expect cache.ttl     == 3600     ,but actual is {c.ttl}'

        c = mccache.get_cache( name='test_factory'  )
        assert  c.name      == 'test_factory'       ,f'Expect cache.name    == test_factory  ,but actual is {c.name}'
        assert  isinstance(c.callback ,Callable)    ,f'Expect cache.callable of type Callable,but actual is {type(c.callback)}'

        # TODO:  Add callback tests.

        # Test exception thrown by factory object.
        with pytest.raises(TypeError ,match=r'The cache name must be a string!'):
            c = mccache.get_cache( 1234 )
        with pytest.raises(TypeError ,match=r'The cache name must be a string!'):
            c = mccache.get_cache( True )

    def test_public_methods_02(self):
        """Test public methods.
        """
        threading.RLock().acquire()
        import  mccache
        mccache._mcConfig = mccache._load_config()

        c = mccache.get_cache()

        # Test missing node.
#       with pytest.raises(TypeError   ,match=r'Node: N/A does not exist in the cluster.'):
#           mccache.clear_cache(        name='mccache' ,node='N/A')
#       with pytest.raises(TypeError   ,match=r'Node: N/A does not exist in the cluster.'):
#           mccache.get_cluster_metrics(name='mccache' ,node='N/A')
    
        # Test local metrics.  This also call the private '_get_local_metrics()' method.
        met = mccache.get_local_metrics(name='mccache' )
        assert  c.name      == 'mccache'    ,f'Expect cache.name    == mccache  ,but actual is {c.name}'
        assert 'process'    in  met         ,'Expect "process" in metric   ,but it is missing'
        assert 'mqueue'     in  met         ,'Expect "mqueue"  in metric   ,but it is missing'
        assert 'mccache'    in  met         ,'Expect "mccache" in metric   ,but it is missing'

        # Test local checksum. This also call the private '_get_local_checksum()' method.
        c['k1'] = 'v1'
        c['k2'] = 'v2'
        crc = mccache.get_local_checksum( name='mccache' )   #,key: str | None = None ) -> dict:
        assert 'k1'             in  crc                     ,f'Expect key "k1" in crc  ,but it is missing'
        assert 'k2'             in  crc                     ,f'Expect key "k2" in crc  ,but it is missing'
        assert  crc['k1']['crc']== 'ZlTHNMyrj0QP8IJetEPcfw' ,f'Expect crc["k1"] == "ZlTHNMyrj0QP8IJetEPcfw" ,but actual is {crc["k1"]['crc']}'
        assert  crc['k2']['crc']== 'GyZ2GcSBLMRu4oF0eITKUA' ,f'Expect crc["k2"] == "GyZ2GcSBLMRu4oF0eITKUA" ,but actual is {crc["k2"]['crc']}'


    def test_private_methods_01(self):
        """Test private methods.
        """
        os.environ['MCCACHE_CRYPTO_KEY'] = 'sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc='
        os.environ['MCCACHE_PACKET_MTU'] = '1489'   # Arbitrary
        import  mccache
        cfg =   mccache._mcConfig = mccache._load_config()
        del os.environ['MCCACHE_CRYPTO_KEY']
        del os.environ['MCCACHE_PACKET_MTU']
        assert mccache._mcConfig.crypto_key ==  'sjQNjXGt_AygJrrFUu7C5hN6voq9a9WBBorVXkuD3Xc='
        if not mccache._mcCrypto:
            mccache._mcCrypto = Fernet( str( mccache._mcConfig.crypto_key ))

        # Test the chunking into pending acknowledgements.
        val     = 'The test value!'*555
        crc     =  hashlib.md5( bytearray(str( val ) ,encoding='utf-8') ).digest()  # noqa: S324   New crc value.
        tsm     =  PyCache.tsm_version()
        key     =  'key'
        key_t   = ('mccache'    , key       ,tsm)
        val_t   = ('TST'        , crc       ,val)
        members = {'mbr1':None  ,'mbr2':None,'mbr3':None}
        key_s   = len( pickle.dumps( key_t ))
        val_s   = len( mccache._mcCrypto.encrypt( pickle.dumps( val_t )))

        # Test the pending acknowledgments.
        ack = mccache._make_pending_ack( key_t ,val_t ,members ,cfg.packet_mtu )

        assert 'tsm'        in  ack             ,f'Expect  "tsm"    in  ack         ,but it is missing'
        assert  ack['tsm']  ==  tsm             ,f'Expect   tsm     == {tsm}        ,but actual is {ack["tsm"]}'   
        assert 'opc'        in  ack             ,f'Expect  "opc"    in  ack         ,but it is missing'
        assert  ack['opc']  == 'TST'            ,f'Expect   opc     ==  TST         ,but actual is {ack["opc"]}'   
        assert 'crc'        in  ack             ,f'Expect  "crc"    in  ack         ,but it is missing'
        assert  ack['crc']  ==  crc             ,f'Expect   crc     == {crc}        ,but actual is {ack["crc"]}'   
        assert 'members'    in  ack             ,f'Expect  "member" in  ack         ,but it is missing'
        assert len(ack['members']) == 3         ,f'Expect 3 members in  ack         ,but actual is {len(ack['members'])}'
        assert 'mbr1'       in  ack['members']  ,f'Expect  "mbr1"   in  ack.members ,but it is missing'
        assert 'mbr2'       in  ack['members']  ,f'Expect  "mbr2"   in  ack.members ,but it is missing'
        assert 'mbr3'       in  ack['members']  ,f'Expect  "mbr3"   in  ack.members ,but it is missing'

        # Test the message fragments.
        assert 'message'    in  ack             ,f'Expect  "message" in ack         ,but it is missing'
        assert len(ack['message']   ) == 8      ,f'Expect 8 fragments  ,but actual is {len(ack['message'])}'
        assert len(ack['message'][7]) == 1017   ,f'Expect   fragment 36 length to be 182  ,but actual is {len(ack['message'][i])}'
        for i  in  range(8-1):
            assert len(ack['message'][i]) == cfg.packet_mtu\
                                                ,f'Expect   fragment {i:2} length to be 1489,but actual is {len(ack['message'][i])}'
        for i  in  range(8):
            hdr_b = ack['message'][i][ 0 : mccache.HEADER_SIZE ]    # Fix size 16 bytes of packet header.
            _mgc ,_ ,_fsq ,_fct ,_ksz ,_vsz ,_tsm ,_ = struct.unpack('@BBBBHHQH' ,hdr_b)    # Unpack the fragment header.
            assert  _mgc  == mccache.MAGIC_BYTE ,f'Expect magic byte to be {mccache.MAGIC_BYTE} ,but actual is {_mgc}'
            assert  _fsq  == i                  ,f'Expect fragment sequence to be {i},but actual is {_fsq}'
            assert  _fct  == 8                  ,f'Expect fragment count to be 8    ,but actual is {_fct}'
            assert  _ksz  == key_s              ,f'Expect key size to be {key_s}    ,but actual is {_ksz}'
            assert  _vsz  == val_s              ,f'Expect key size to be {val_s}    ,but actual is {_vsz}'
            assert  _tsm  == tsm                ,f'Expect tsm == {tsm}              ,but actual is {_tsm}'

#       val_b = []
#       for i in range(8):
#           val_b.extend( ack['message'][i][ mccache.HEADER_SIZE : ])
#       val_b = mccache._mcCrypto.decrypt( bytes( val_b ))
#       key_b = pickle.loads(bytes( val_b[ 0 : key_s ]  ))
#       val_o = pickle.loads(bytes( val_b[ key_s :   ]  ))


    def test_private_opcode_01(self):
        """Test the individual Op Code.
        """
        # This should be all tested in teh stress test.

        import  mccache
        cfg =   mccache._mcConfig = mccache._load_config()
        c   =   mccache.get_cache()

        mccache._mcMember = { 'mbr1' : None , 'mbr2' : None }   # Simulate a cluster of me + 2 members.
        nms =   c.name
        val =  'value1'*10
        key =  'key'

#       # Test the ACK processing.
#       opc =   mccache.OpCode.ACK
#       mccache._process_ACK(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the BYE processing.
#       opc =   mccache.OpCode.BYE
#       lts =   None
#       lcs =   None
#       mccache._process_BYE(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the DEL processing.
#       opc =   mccache.OpCode.DEL
#       lts =   None
#       lcs =   None
#       mccache._process_DEL(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the NEW processing.
#       opc =   mccache.OpCode.NEW
#       lts =   None
#       lcs =   None
#       mccache._process_NEW(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the RAK processing.
#       opc =   mccache.OpCode.RAK
#       lts =   None
#       lcs =   None
#       mccache._process_RAK(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr ,aky_t )
#
#       # Test the REQ processing.
#       opc =   mccache.OpCode.REQ
#       lts =   None
#       lcs =   None
#       mccache._process_REQ(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the RST processing.
#       opc =   mccache.OpCode.RST
#       lts =   None
#       lcs =   None
#       mccache._process_RST(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the SYC processing.
#       opc =   mccache.OpCode.SYC
#       lts =   None
#       lcs =   None
#       mccache._process_SYC(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )
#
#       # Test the UPD processing.
#       opc =   mccache.OpCode.UPD
#       lts =   None
#       lcs =   None
#       mccache._process_UPD(   nms ,key ,tsm ,lts ,opc ,crc ,lcs ,val ,sdr )


    #   Parameterized test with different input values to tests.  Much cleaner than for loops.
    @pytest.mark.parametrize("input1 ,expect" ,[(1 ,1) ,(2 ,2) ,(3 ,3)] )
    def test_unit_02(self ,input1 ,expect):
        def fn( var ):
            return var

        assert  fn( input1 ) == expect

    def test_unit_exception_01(self):
        with pytest.raises(Exception ,match=r"err"):   # Check message with regex.
            raise Exception("Test err text.")



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
