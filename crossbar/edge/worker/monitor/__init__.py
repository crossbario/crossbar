##############################################################################
#
#                        Crossbar.io FX
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from crossbarfx.edge.worker.monitor._self import SelfMonitor
from crossbarfx.edge.worker.monitor._hardware import HWMonitor
from crossbarfx.edge.worker.monitor._network import NetMonitor
from crossbarfx.edge.worker.monitor._storage import StorageMonitor
from crossbarfx.edge.worker.monitor._system import SystemMonitor
from crossbarfx.edge.worker.monitor._memory import MemoryMonitor
from crossbarfx.edge.worker.monitor._cpu import CPUMonitor
from crossbarfx.edge.worker.monitor._disk import IOMonitor
from crossbarfx.edge.worker.monitor._process import ProcessMonitor

__all__ = ('MONITORS', )

# class map: monitor name -> monitor class
MONITORS = {
    SelfMonitor.ID: SelfMonitor,
    HWMonitor.ID: HWMonitor,
    NetMonitor.ID: NetMonitor,
    StorageMonitor.ID: StorageMonitor,
    SystemMonitor.ID: SystemMonitor,
    MemoryMonitor.ID: MemoryMonitor,
    CPUMonitor.ID: CPUMonitor,
    IOMonitor.ID: IOMonitor,
    ProcessMonitor.ID: ProcessMonitor,
}
