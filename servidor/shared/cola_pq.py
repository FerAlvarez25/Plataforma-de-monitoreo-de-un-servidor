import multiprocessing as mp


class ColaProductorConsumidor:
    """Cola acotada compartible entre procesos: semáforos empty/full + mutex."""

    def __init__(self, capacidad, manager):
        self._capacidad = capacidad
        self._buffer = manager.list()
        self._libre = mp.BoundedSemaphore(capacidad)   # huecos disponibles
        self._lleno = mp.Semaphore(0)                  # ítems disponibles
        self._mutex = mp.Lock()

    def put(self, item):
        self._libre.acquire()
        with self._mutex:
            self._buffer.append(item)
        self._lleno.release()

    def get(self):
        self._lleno.acquire()
        with self._mutex:
            item = self._buffer.pop(0)
        self._libre.release()
        return item

    def size(self):
        return len(self._buffer)