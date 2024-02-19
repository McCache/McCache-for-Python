# See MIT license at the bottom of this script.
#
# Pytest script template.
# SEE:  https://docs.pytest.org/en/7.4.x/explanation/anatomy.html

import hashlib
import json
import time

from datetime import timedelta


#   Use Python class to group similar tests together.
class   TestClass:
    """Test `Class`
    """

    def get_result(self) -> dict:
        chksums= dict()
        endtsm: str = None
        exttsm: str = None
        member: str = None

        with open("./log/result.txt") as fn:
            for ln in fn:
                if 'Done' in ln:
                    # Example:
                    # 1706831937.173151 Done at 23:49:31.73074860. Querying final cache checksum.
                    tks     = ln.split(' ')         # Tokenize the line.
                    endtsm  = tks[3][ :-1]          # Strip the trailing period.
                elif 'Exiting' in ln:
                    # Example:
                    # 1706834869.792038 Exiting at 07:58:17.91994199.
                    tks     = ln.split(' ')         # Tokenize the line.
                    exttsm  = tks[3][ :-1]          # Strip the trailing period.

                    chksums[ member ]['crc'] = hashlib.md5( bytearray(str( chksums[ member ]['data'] ) ,encoding='utf-8') ).digest()
                elif 'INQ' in ln:
                    # Example
                    # 1706834856.017798 L#1145 Im:10.89.2.71
                    tks     = ln.split(' ')         # Tokenize the line.
                    member  = tks[2][3: ].strip()   # Strip away 'Im:'
                elif 'crc' in ln and 'tsm' in ln:
                    if  member not in chksums:
                        chksums[ member ] = {'endtsm': endtsm ,'exttsm': exttsm ,'crc': None ,'data': {}}

                    # Example:
                    # 'K000-003': {'crc': 'fkU4sT6XTwQhLQT6ZvUb3w', 'tsm': '07:47:33.89543949'}
                    sts = json.loads( '{' + ln.replace("'" ,'"') + '}')
                    chksums[ member ]['data'].update( sts )

        # First remove all members that have identical checksums using nested loop iteration.
        #
        for i ,prv  in enumerate(list(chksums.items())):
            if  i > 0:
                for _ ,cur  in enumerate(list(chksums.items())):
                    if  prv[0] != cur[0]:
                        if  prv[0] in chksums and prv[1]['crc'] == cur[1]['crc']:
                            _ = chksums.pop(prv[0])

        return  chksums

    def test_stress_01(self):
        chksums = self.get_result()

        # Compare the remainder members.
        # Any entry timestamp that older than the compared to endings (endtsm) timestamp is discarded
        # for compared to member is done with its test while this member is still running.
        #
        for _  ,prv in enumerate(list(chksums.items())):
            if  prv[0]  in  chksums:
                for _  ,cur in  enumerate(list(chksums.items())):
                    if  cur[0]  in  chksums and prv[0] != cur[0]:
                        # Compare previous to current.
                        #
                        for k   in  prv[1]['data'].keys():
                            if  k   in cur[1]['data']:
                                # NOTE: If we have 2 values with different CRC then something got change and we need to validate the  timestamp.
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

                                        msg =   f"Key: {k} ,Nodes: {prv[0]} & {cur[0]} ,Var: {dff:0.4f} PrvTsm: {prv[1]['data'][ k ]['tsm']} CurEnd: {cur[1]['endtsm']} ,CRC: {prv[1]['data'][ k ]['crc']} != {cur[1]['data'][ k ]['crc']}"
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

                                        msg =   f"Key: {k} ,Nodes: {cur[0]} & {prv[0]} ,Var: {dff:0.4f} ,CurTsm: {cur[1]['data'][ k ]['tsm']} PrvEnd: {prv[1]['endtsm']} ,CRC: {cur[1]['data'][ k ]['crc']} != {prv[1]['data'][ k ]['crc']}"
                                        assert  cur[1]['data'][ k ]['tsm'] ==  prv[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the current  key tsm is before the previous node exit time than assert it.
                                    #if  cur[1]['data'][ k ]['tsm'] < prv[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {cur[0]} {prv[0]} ,CurTsm: {cur[1]['data'][ k ]['tsm']} PrvEnd: {prv[1]['endtsm']} ,CRC: {cur[1]['data'][ k ]['crc']} != {prv[1]['data'][ k ]['crc']}"
                                    #    assert  prv[1]['data'][ k ]['tsm'] == cur[1]['data'][ k ]['tsm'] ,msg

                                    ##   If the previous key tsm is before the current  node exit time than assert it.
                                    #if  prv[1]['data'][ k ]['tsm'] < cur[1]['endtsm']:
                                    #    msg =   f"Key: {k} ,Nodes: {prv[0]} {cur[0]} ,PrvTsm: {prv[1]['data'][ k ]['tsm']} CurEnd: {cur[1]['endtsm']} ,CRC: {prv[1]['data'][ k ]['crc']} != {cur[1]['data'][ k ]['crc']}"
                                    #    assert  cur[1]['data'][ k ]['tsm'] == prv[1]['data'][ k ]['tsm'] ,msg


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
