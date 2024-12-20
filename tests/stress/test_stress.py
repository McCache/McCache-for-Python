# See MIT license at the bottom of this script.
#
# Pytest script template.
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html

import base64
import hashlib
import json
import logging
import os
import re
import time

from datetime import timedelta


#   Use Python class to group similar tests together.
class   TestClass:
    """Test `Class`
    """

    def get_result(self ,caplog) -> dict:
        logger = logging.getLogger()
        chksums= dict()
        endtsm: str = None  # Done testing time.
        exttsm: str = None  # Exit testing time.
        member: str = None

        with open("./log/result.txt") as fn:
            for ln in fn:
                if 'Done testing' in ln:
                    # Not dependent on the debug format.
                    tokens  = ln.split('\t')        # Tokenize the the entire log line.
                    if 'Im:' in tokens[0]:
                        # Debug format.
                        strMrk = tokens[0].index('Im:')+3
                        member = tokens[0][ strMrk: ]   # Source IP address.

                    logmsg  = tokens[-1]            # Last token is the message.
                    tokens  = logmsg.split(' ')     # Tokenize the message portion of the line. e.g. "172.18.0.1 Done testing at 04:00:03.472051929"
                    if 'Im:' in tokens[0]:
                        # Debug format.
                        strMrk = tokens[0].index('Im:')+3
                        member = tokens[0][ strMrk: ].split(' ')[0] # Source IP address.

                    tokens  = logmsg[ logmsg.index('at ')+3: ].strip().split(' ')
                    endtsm  = tokens[0].strip()     # Timestamp.

                    if  member not in chksums:
                        chksums[ member ] = {'endtsm': endtsm ,'exttsm': None ,'crc': None ,'data': {}}
                elif "'crc':" in ln  and "'tsm':" in ln:
                    # Example:
                    # 'K000-003': {'crc': 'fkU4sT6XTwQhLQT6ZvUb3w', 'tsm': '07:47:33.89543949'}
                    sts = json.loads( '{' + ln.replace('}}' ,'}').replace("'" ,'"') + '}')
                    chksums[ member ]['data'].update( sts )
                elif 'Exiting test' in ln:
                    # Not dependent on the debug format.
                    tokens  = ln.split('\t')        # Tokenize the the entire log line.
                    logmsg  = tokens[-1]            # Last token is the message.
                    tokens  = logmsg[ logmsg.index('at ')+3: ].strip().split(' ') # Tokenize the message portion of the line. e.g. "Exiting test at 04:00:03.510304783."
                    exttsm  = tokens[0].strip()     # Timestamp.
                    chksums[ member ]['exttsm'] = exttsm
                    chksums[ member ]['crc'] = hashlib.md5( bytearray(str( chksums[ member ]['data'] ) ,encoding='utf-8') ).digest()

        # First remove all members that have identical checksums so we have fewer entries to compare.
        #
#       for i ,prv  in enumerate(list(chksums.items())):
#           if  i > 0:
#               for _ ,cur  in enumerate(list(chksums.items())):
#                   if  prv[0] != cur[0]:
#                       if  prv[0] in chksums and prv[1]['crc'] == cur[1]['crc']:
#                           _ = chksums.pop(prv[0])

        return  chksums

    def test_stress_00(self ,caplog):
        logger = logging.getLogger()
        with caplog.at_level(logging.INFO):
            logger.info(f"In test_stress_00 ...")

        assert  os.path.exists( "./log/result.txt")     ,"File not found: ./log/result.txt"
        assert  os.path.getsize("./log/result.txt") > 0 ,"File size zero: ./log/result.txt"

    def test_stress_01(self ,caplog):
        logger = logging.getLogger()
        with caplog.at_level(logging.INFO):
            logger.info(f"In test_stress_01 ...")

        chksums = self.get_result( caplog )

        with caplog.at_level(logging.INFO):
            for node in chksums.keys():
                endtsm  = chksums[node]['endtsm']
                exttsm  = chksums[node]['exttsm']
                md5     = base64.b64encode( chksums[node]['crc'] ).decode()[:-2]
                logger.info(f"{node:11}: Done at {endtsm} ,existed at {exttsm} with CRC: {md5} ...")

        # Any entry timestamp that older than the compared to endings (endtsm) timestamp is discarded
        # for compared to member is done with its test while this member is still running.
        #
        for _  ,prv in enumerate(list(chksums.items())):
            if  prv[0]  in  chksums:
                for _  ,cur in  enumerate(list(chksums.items())):
                    if  cur[0]  in  chksums and prv[0] != cur[0]:   # Different IP address.
                        # Compare previous to current.
                        #
                        for k   in  prv[1]['data'].keys():
                            if  k   in cur[1]['data']:
                                # NOTE: If we have 2 values with different CRC then something got change and we need to validate the timestamp.
                                #       Only validate if:
                                #           The previous entry timestamp is less than the current  node completion timestamp, and
                                #           the current  entry timestamp is less than the previous node completion timestamp.
                                if  prv[1]['data'][ k ]['crc'] != cur[1]['data'][ k ]['crc']:
                                    if  prv[1]['data'][ k ]['tsm'] < cur[1]['endtsm'] and\
                                        cur[1]['data'][ k ]['tsm'] < prv[1]['endtsm']:
                                        # TODO: Refactor into a method.
                                        #   Convert the previous entries formatted time string into a float value.
                                        ttk = prv[1]['data'][ k ]['tsm'].split('.')
                                        tsm = time.strptime( ttk[0] ,'%H:%M:%S' )
                                        sec = timedelta( hours=tsm.tm_hour ,minutes=tsm.tm_min ,seconds=tsm.tm_sec ).total_seconds()
                                        psc = float(f'{int(sec)}.{ttk[1]}')
                                        #   Convert the current  entries formatted time string into a float value.
                                        ttk = cur[1]['data'][ k ]['tsm'].split('.')
                                        tsm = time.strptime( ttk[0] ,'%H:%M:%S' )
                                        sec = timedelta( hours=tsm.tm_hour ,minutes=tsm.tm_min ,seconds=tsm.tm_sec ).total_seconds()
                                        csc = float(f'{int(sec)}.{ttk[1]}')
                                        #   The time difference between the previous and current entries.
                                        dff = psc - csc

                                        msg =   f"Key: {k} ,Nodes: {prv[0]} & {cur[0]} ,Var: {dff:0.4f} PrvTsm: {prv[1]['data'][ k ]['tsm']} CurTsm: {cur[1]['data'][ k ]['tsm']} ,PrvEnd: {prv[1]['endtsm']} CurEnd: {cur[1]['endtsm']} ,PrvCRC: {prv[1]['data'][ k ]['crc']} CurCRC: {cur[1]['data'][ k ]['crc']}"
                                        assert  prv[1]['data'][ k ]['tsm'] ==  cur[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the previous key tsm is before the current  node exit time than assert it.
                                    #if  prv[1]['data'][ k ]['tsm'] < cur[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {prv[0]} {cur[0]} ,PrvTsm: {prv[1]['data'][ k ]['tsm']} CurEnd: {cur[1]['endtsm']} ,CRC: {prv[1]['data'][ k ]['crc']} != {cur[1]['data'][ k ]['crc']}"
                                    #    assert  prv[1]['data'][ k ]['tsm'] == cur[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the current  key tsm is before the previous node exit time than assert it.
                                    #if  cur[1]['data'][ k ]['tsm'] < prv[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {cur[0]} {prv[0]} ,CurTsm: {cur[1]['data'][ k ]['tsm']} PrvEnd: {prv[1]['endtsm']} ,CRC: {cur[1]['data'][ k ]['crc']} != {prv[1]['data'][ k ]['crc']}"
                                    #    assert  cur[1]['data'][ k ]['tsm'] == prv[1]['data'][ k ]['tsm'] ,msg

                        # Compare current to previous.
                        #
                        for k   in  cur[1]['data'].keys():
                            if  k   in prv[1]['data']:
                                if  cur[1]['data'][ k ]['crc'] != prv[1]['data'][ k ]['crc']:
                                    if  cur[1]['data'][ k ]['tsm'] < prv[1]['endtsm'] and\
                                        prv[1]['data'][ k ]['tsm'] < cur[1]['endtsm']:
                                        # TODO: Refactor into a method.
                                        #   Convert the current  entries formatted time string into a float value.
                                        ttk = cur[1]['data'][ k ]['tsm'].split('.')
                                        tsm = time.strptime( ttk[0] ,'%H:%M:%S' )
                                        sec = timedelta( hours=tsm.tm_hour ,minutes=tsm.tm_min ,seconds=tsm.tm_sec ).total_seconds()
                                        csc = float(f'{int(sec)}.{ttk[1]}')
                                        #   Convert the previous entries formatted time string into a float value.
                                        ttk = prv[1]['data'][ k ]['tsm'].split('.')
                                        tsm = time.strptime( ttk[0] ,'%H:%M:%S' )
                                        sec = timedelta( hours=tsm.tm_hour ,minutes=tsm.tm_min ,seconds=tsm.tm_sec ).total_seconds()
                                        psc = float(f'{int(sec)}.{ttk[1]}')
                                        #   The time difference between the previous and current entries.
                                        dff = csc - psc

                                        msg =   f"Key: {k} ,Nodes: {cur[0]} & {prv[0]} ,Var: {dff:0.4f} ,CurTsm: {cur[1]['data'][ k ]['tsm']} PrvTsm: {prv[1]['data'][ k ]['tsm']} ,CurEnd: {cur[1]['endtsm']} PrvEnd: {prv[1]['endtsm']} ,CurCRC: {cur[1]['data'][ k ]['crc']} PrvCRC: {prv[1]['data'][ k ]['crc']}"
                                        assert  cur[1]['data'][ k ]['tsm'] ==  prv[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the current  key tsm is before the previous node exit time than assert it.
                                    #if  cur[1]['data'][ k ]['tsm'] < prv[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {cur[0]} {prv[0]} ,CurTsm: {cur[1]['data'][ k ]['tsm']} PrvEnd: {prv[1]['endtsm']} ,CRC: {cur[1]['data'][ k ]['crc']} != {prv[1]['data'][ k ]['crc']}"
                                    #    assert  prv[1]['data'][ k ]['tsm'] == cur[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the previous key tsm is before the current  node exit time than assert it.
                                    #if  prv[1]['data'][ k ]['tsm'] < cur[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {prv[0]} {cur[0]} ,PrvTsm: {prv[1]['data'][ k ]['tsm']} CurEnd: {cur[1]['endtsm']} ,CRC: {prv[1]['data'][ k ]['crc']} != {cur[1]['data'][ k ]['crc']}"
                                    #    assert  cur[1]['data'][ k ]['tsm'] == prv[1]['data'][ k ]['tsm'] ,msg
        #
        # Assert the incoherence count.
        pass

    def test_stress_02(self ,caplog):
        logger = logging.getLogger()
        with caplog.at_level(logging.INFO):
            logger.info(f"In test_stress_02 ...")

        chksums = self.get_result( caplog )

        if 'TEST_CLUSTER_SIZE' in os.environ:
            _cs = int( os.environ['TEST_CLUSTER_SIZE'] )
            _ls = len(chksums)
            assert  _cs == _ls ,f"Expecting {_cs} INQ results but got {_ls}."

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
