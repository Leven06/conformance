#
#  BSD LICENSE
#
#  Copyright (c) Crane Chu <cranechu@gmail.com>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#    * Neither the name of Intel Corporation nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# -*- coding: utf-8 -*-


import time
import pytest
import random
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem, __version__
from scripts.zns import Zone


@pytest.fixture()
def nvme0n1(nvme0):
    # only verify data in zone 0
    ret = Namespace(nvme0, 1, 0x8000)
    yield ret
    ret.close()


@pytest.fixture()
def zone(nvme0n1, qpair):
    slba = 0x8000*int(random.random()*100)
    ret = Zone(qpair, nvme0n1, slba)
    if ret.state == 'Full':
        ret.reset()
    if ret.state == 'Empty':
        ret.open()
    assert ret.state == 'Explicitly Opened'
    assert ret.wpointer == ret.slba
    return ret


def test_dut_firmware_and_model_name(nvme0):
    logging.info(nvme0.id_data(63, 24, str))
    logging.info(nvme0.id_data(71, 64, str))
    logging.info("testing conformance with pynvme " + __version__)

    
def test_zns_identify_namespace(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=1).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=5).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=6).waitdone()
    logging.info(buf.dump(64))
    

def test_zns_management_receive(nvme0n1, qpair, buf):
    zone_size = 0x8000
    nvme0n1.zns_mgmt_receive(qpair, buf).waitdone()
    nzones = buf.data(7, 0)
    logging.info("number of zones: %d" % nzones)

    for i in range(10):
        base = 64
        nvme0n1.zns_mgmt_receive(qpair, buf, slba=i*zone_size).waitdone()
        zone_type = buf.data(base)
        assert zone_type == 2

        zone = Zone(qpair, nvme0n1, i*zone_size)
        assert buf.data(base+1)>>4 == 14
        assert buf.data(base+15, base+8) == zone.capacity
        logging.info(zone)
    

def test_zns_management_send(nvme0n1, qpair):
    z0 = Zone(qpair, nvme0n1, 0)
    z0.action(2)
    assert z0.state == 'Full'


@pytest.mark.parametrize("slba", [0, 0x8000, 0x10000, 0x80000, 0x100000])
def test_zns_state_machine(nvme0n1, qpair, slba):
    z0 = Zone(qpair, nvme0n1, slba)
    assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'
    
    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.finish()
    assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.reset()
    assert z0.state == 'Empty'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.reset()
    assert z0.state == 'Empty'
    
    z0.finish()
    assert z0.state == 'Full'
    

def test_zns_show_zone(nvme0n1, qpair, slba=0):
    z0 = Zone(qpair, nvme0n1, slba)
    logging.info(z0)

    
def test_zns_write_full_zone(nvme0n1, qpair, slba=0):
    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    assert z0.state == 'Full'

    with pytest.warns(UserWarning, match="ERROR status: 01/"):
        z0.write(qpair, buf, 0, 96//4).waitdone()

    z0.reset()
    z0.finish()
    assert z0.state == 'Full'


def test_zns_write_1(nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'

    
def test_zns_write_2(nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 12)
    zone.write(qpair, buf, 12, 12)
    zone.close()
    zone.finish()
    qpair.waitdone(2)
    assert zone.state == 'Full'

    
def test_zns_write_192k(nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 24, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'


def test_zns_write_twice(nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 0, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'    


def _test_zns_write_48k_and_96k(nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 12)
    zone.write(qpair, buf, 0, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'    
    
    
@pytest.mark.parametrize("repeat", range(100)) #100
@pytest.mark.parametrize("slba", [0, 0x8000, 0x100000])
def test_zns_write_implicitly_open(nvme0n1, qpair, slba, repeat):
    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'
    assert z0.wpointer == slba

    z0.write(qpair, buf, 0, 96//4)
    time.sleep(1)
    assert z0.state == 'Implicitly Opened'
    assert z0.wpointer == slba+0x18

    z0.close()
    #logging.info(z0)
    assert z0.state == 'Closed'
    assert z0.wpointer == slba+0x18
    
    z0.finish()
    qpair.waitdone()
    logging.info(z0)
    assert z0.state == 'Full'
    assert z0.wpointer == slba+0x4800

