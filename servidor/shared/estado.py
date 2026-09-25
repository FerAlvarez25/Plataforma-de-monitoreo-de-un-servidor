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

    def __getstate__(self):
        # El objeto SyncManager no es picklable bajo spawn: se viaja con las
        # proxies (registro, contador, ...) que sí lo son. `_manager` solo lo
        # necesita main.py antes de lanzar los procesos hijos.
        state = self.__dict__.copy()
        state.pop("_manager", None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._manager = None


def crear_estado():
    return EstadoServidor()