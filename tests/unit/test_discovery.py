import os

from session_snapshot.core.discovery import PsutilProcessSource


def test_psutil_source_sees_own_process():
    procs = PsutilProcessSource().snapshot()
    mine = [p for p in procs if p.pid == os.getpid()]
    assert len(mine) == 1
    assert mine[0].argv
