import subprocess
import sys


def test_smoke_servidor_modo_fix():
    cmd = [
        sys.executable, "-m", "servidor.main",
        "--total", "20", "--intensidad", "5",
        "--cargadores", "2", "--hilos-escritores", "2",
        "--capacidad", "8", "--tiempo-max", "20",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    assert res.returncode == 0, res.stderr
    assert "RESUMEN registrados=20 esperados=20 sync=mutex" in res.stdout