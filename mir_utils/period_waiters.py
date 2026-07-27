import time

class PeriodWaiterExact:
    """
    Boucle à période fixe, en privilégiant la moyenne
    Lorsque le temps de traitement dépasse parfois le temps de boucle
    la moyenne est bonne
    le jitter augmente
    """
    def __init__(self, period: float):
        self.period = period
        self.next_tick = 0.0
        self.start()

    def start(self):
        """Initialise le scheduler."""
        self.next_tick = time.perf_counter()

    def wait(self):
        """Attend jusqu'au prochain tick."""
        self.next_tick += self.period
        sleep_time = self.next_tick - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)
        # sinon : tick en retard → on ne corrige pas 

class PeriodWaiterSafeForJitter:
    """
    Boucle à période fixe, en privilégiant le jitter
    Lorsque le temps de traitement dépasse parfois le temps de boucle
    le jitter est réduit (pas de risque de deux exécutions rapprochées)
    la moyenne augmente
    """
    def __init__(self, period: float):
        self.period = period
        self.next_tick = 0.0

    def start(self):
        """Initialise le scheduler."""
        self.next_tick = time.perf_counter()

    def wait(self):
        """Attend jusqu'au prochain tick, corrige le retard si nécessaire."""
        self.next_tick += self.period
        sleep_time = self.next_tick - time.perf_counter()

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            # Tick en retard → on recale
            self.next_tick = time.perf_counter()

#tests.
#avec un temps de traitement toujours en dessous de la période:
#FixedRateLoopBetterAverage:  min=19.93ms  max=20.08ms  mean=20.00ms  std=23µs
#FixedRateLoopBetterJitter:   min=19.89ms  max=20.09ms  mean=20.00ms  std=36µs

#avec temps de traitement aléatoirement plus long:
#FixedRateLoopBetterAverage: min=0.55ms   max=30.54ms  mean=20.00ms  std=5480µs
#FixedRateLoopBetterJitter:  min=19.54ms  max=30.49ms  mean=21.79ms  std=2950µs
