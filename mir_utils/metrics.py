import threading
import math
import numpy as np

#moyenne glissante
class SimpleMovingAverage:
    def __init__(self, window_size: int):
        if window_size <= 0:
            raise ValueError("window_size must be > 0")

        self.window_size = window_size
        self.buffer = [0.0] * window_size
        self.index = 0
        self.count = 0
        self.sum = 0.0

        self._lock = threading.Lock()

    def add(self, value: float):
        with self._lock:
            # Retirer l’ancienne valeur si la fenêtre est pleine
            if self.count == self.window_size:
                old = self.buffer[self.index]
                self.sum -= old
            else:
                self.count += 1

            # Ajouter la nouvelle valeur
            self.buffer[self.index] = value
            self.sum += value

            # Avancer l’index circulaire
            self.index = (self.index + 1) % self.window_size

    def average(self) -> float:
        with self._lock:
            if self.count == 0:
                return 0.0
            return self.sum / self.count

#classe de statistiques qui met à jour à chaque ajout de valeur (add) :
#min, max, moyenne, ecart-type, total échantillons
#les données statistiques sont fournies sous forme de dictionnaire (get)
class Stats:
    """
    Accumulateur statistique temps réel, thread-safe.
    Calcule min, max, moyenne, variance, écart-type en O(1).
    Peut ignorer les N premières valeurs ajoutées.
    """
    def __init__(self, num_values_to_ignore=0):
        self._ignore_left = num_values_to_ignore

        self._count = 0
        self._sum = 0.0
        self._sum_sq = 0.0
        self._min = float('inf')
        self._max = float('-inf')

        self._lock = threading.Lock()

    def add(self, value: float):
        """Ajoute une valeur et met à jour les stats en O(1)."""
        with self._lock:

            # Phase d'ignorés
            if self._ignore_left > 0:
                self._ignore_left -= 1
                return

            # Phase normale
            self._count += 1
            self._sum += value
            self._sum_sq += value * value

            if value < self._min:
                self._min = value
            if value > self._max:
                self._max = value

    def reset(self):
        """Réinitialise toutes les statistiques."""
        with self._lock:
            self._count = 0
            self._sum = 0.0
            self._sum_sq = 0.0
            self._min = float('inf')
            self._max = float('-inf')
            # On ne réinitialise PAS _ignore_left volontairement
            # (comportement classique). Si tu veux le réinitialiser,
            # je peux te faire une version alternative.

    def get(self):
        """
        Retourne un dictionnaire :
        - count
        - min
        - max
        - mean
        - variance
        - std
        """
        with self._lock:
            if self._count == 0:
                return {
                    "count": 0,
                    "min": 0,
                    "max": 0,
                    "mean": 0,
                    "variance": 0,
                    "std": 0
                }

            mean = self._sum / self._count
            variance = (self._sum_sq / self._count) - (mean * mean)
            variance = max(variance, 0.0)  # protection flottants

            return {
                "count": self._count,
                "min": self._min,
                "max": self._max,
                "mean": mean,
                "variance": variance,
                "std": math.sqrt(variance)
            }

#tableau de données rempli par la droite
#utilisable pour une vue à la façon d'un oscilloscope en mode rolling
class RollingArray:
    def __init__(self, size=1000):
        self._buffer = np.zeros(size)
        self._end_index = size-1
        self._samples_count = 0
        self._lock = threading.Lock()

    def add(self, value):
        with self._lock:
            self._buffer[0:self._end_index] = self._buffer[1:]
            self._buffer[self._end_index] = value
            if self._samples_count < self._buffer.size:
                self._samples_count += 1

    def get_array(self):
        with self._lock:
            return self._samples_count, self._buffer.copy()