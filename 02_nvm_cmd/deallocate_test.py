import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_and_write(nvme0, nvme0n1, repeat,
                              lba_start=1, lba_step=3, lba_count=3):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    pattern = repeat + (repeat<<8) + (repeat<<16) + (repeat<<24)
    write_buf = Buffer(4096, "write", pattern, 32)
    read_buf = Buffer(4096, "read")
    q = Qpair(nvme0, 8)
    
    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(q, buf, 1).waitdone()
    nvme0n1.write(q, write_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    nvme0n1.read(q, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    for i in range(lba_count):
        assert read_buf[i*512 + 10] == repeat
        

@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_and_read(nvme0, nvme0n1, repeat, 
                             lba_start=1, lba_step=3, lba_count=3):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    read_buf = Buffer(4096, "read")
    q = Qpair(nvme0, 8)
    
    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(q, buf, 1).waitdone()
    nvme0n1.read(q, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()


def test_deallocate_out_of_range(nvme0, nvme0n1):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    ncap = nvme0n1.id_data(15, 8)
    buf = Buffer(4096)
    q = Qpair(nvme0, 8)

    buf.set_dsm_range(0, ncap-1, 1)
    nvme0n1.dsm(q, buf, 1).waitdone()
    
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        buf.set_dsm_range(0, ncap, 1)
        nvme0n1.dsm(q, buf, 1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        buf.set_dsm_range(0, ncap-1, 2)
        nvme0n1.dsm(q, buf, 1).waitdone()


def test_deallocate_nr_maximum(nvme0, nvme0n1):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    q = Qpair(nvme0, 8)

    for i in range(256):
        buf.set_dsm_range(i, i, 1)
    nvme0n1.dsm(q, buf, 256).waitdone()

    with pytest.raises(IndexError):
        for i in range(257):
            buf.set_dsm_range(i, i, 1)
    nvme0n1.dsm(q, buf, 257).waitdone()
    

def test_deallocate_correct_range(nvme0, nvme0n1):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    q = Qpair(nvme0, 8)
    nvme0n1.write(q, buf, 1, 3).waitdone()
    
    buf.set_dsm_range(0, 2, 1)
    nvme0n1.dsm(q, buf, 1).waitdone()

    nvme0n1.read(q, buf, 1, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 1
    nvme0n1.read(q, buf, 2, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(q, buf, 3, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 3

    
def test_deallocate_multiple_range(nvme0, nvme0n1):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    q = Qpair(nvme0, 8)
    nvme0n1.write(q, buf, 1, 4).waitdone()
    
    buf.set_dsm_range(0, 1, 1)
    buf.set_dsm_range(1, 2, 1)
    buf.set_dsm_range(2, 3, 1)
    nvme0n1.dsm(q, buf, 3).waitdone()

    nvme0n1.read(q, buf, 1, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(q, buf, 2, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(q, buf, 3, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(q, buf, 4, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 4
    
    nvme0n1.write(q, buf, 1, 4).waitdone()
    nvme0n1.read(q, buf, 1, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 1
    nvme0n1.read(q, buf, 2, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 2
    nvme0n1.read(q, buf, 3, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 3
    nvme0n1.read(q, buf, 4, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 4
