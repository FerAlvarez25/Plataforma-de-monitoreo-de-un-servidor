import re


def parsear_pid_stat(contenido):
    partes = contenido.split(") ", 1)          # comm puede contener paréntesis
    if len(partes) != 2:
        return {}
    numeros = partes[1].split()
    # tras ')' los campos numéricos empiezan en field 3 (state) -> índice 0
    # field 14 utime -> índice 11 ; field 15 stime -> índice 12
    try:
        return {"utime": int(numeros[11]), "stime": int(numeros[12])}
    except (IndexError, ValueError):
        return {}


def parsear_status(contenido):
    m_rss = re.search(r"VmRSS:\s*(\d+)\s*kB", contenido)
    m_thr = re.search(r"Threads:\s*(\d+)", contenido)
    return {
        "rss_kb": int(m_rss.group(1)) if m_rss else None,
        "hilos": int(m_thr.group(1)) if m_thr else None,
    }


def muestrear_proceso(pid):
    with open(f"/proc/{pid}/stat") as f:
        stat = parsear_pid_stat(f.read())
    with open(f"/proc/{pid}/status") as f:
        status = parsear_status(f.read())
    return {**stat, **status}


def monitoreo_main(estado, paro, intervalo=1.0):
    while not paro.is_set():
        pids = set()
        for ev in estado.eventos:
            m = re.search(r"pid=(\d+)", ev)
            if m:
                pids.add(int(m.group(1)))
        for pid in list(pids)[:8]:
            try:
                estado.metricas[f"pid_{pid}"] = muestrear_proceso(pid)
            except FileNotFoundError:
                pass
        paro.wait(intervalo)