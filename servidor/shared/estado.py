import multiprocessing as mp


class EstadoServidor:
    """Estado compartido del servidor: estructuras Manager + locks reales."""

    def __init__(self, manager=None):
        self._manager = manager or mp.Manager()
        self.registro = self._manager.dict()        # id -> {"tipo":..., "estado":...}
        self.contador = self._manager.Value("i", 0)  # total de tareas registradas
        self.metricas = self._manager.dict()        # {"cpu_pct":..., "rss_kb":..., "hilos":...}
        self.eventos = self._manager.list()         # log compartido
        self.lock_registro = mp.Lock()
        self.lock_metricas = mp.Lock()


def crear_estado():
    return EstadoServidor()