import pytest

from servidor.componentes.monitoreo import (
    muestrear_proceso,
    parsear_pid_stat,
    parsear_status,
)

STAT_FIXTURE = (
    "1234 (servidor) S 1 1234 1234 0 -1 4194560 100 0 0 0 120 80 0 0 "
    "20 0 1 0 100 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
)
STAT_FIXTURE_ALIAS = (
    "5678 (bash (deleted)) S 1 5678 5678 0 -1 4194560 100 0 0 0 55 44 0 0 "
    "20 0 1 0 100 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
)
STATUS_FIXTURE = "Name:\tservidor\nThreads:\t4\nVmRSS:\t      123456 kB\n"


def test_parsear_pid_stat():
    assert parsear_pid_stat(STAT_FIXTURE) == {"utime": 120, "stime": 80}


def test_parsear_pid_stat_con_parentesis():
    assert parsear_pid_stat(STAT_FIXTURE_ALIAS) == {"utime": 55, "stime": 44}


def test_parsear_status():
    assert parsear_status(STATUS_FIXTURE) == {"rss_kb": 123456, "hilos": 4}


@pytest.mark.skipif(not __import__("os").path.exists("/proc"), reason="requiere Linux")
def test_muestreo_real_en_linux():
    datos = muestrear_proceso(1)  # PID 1 (init/systemd) en Linux
    assert "utime" in datos and "rss_kb" in datos