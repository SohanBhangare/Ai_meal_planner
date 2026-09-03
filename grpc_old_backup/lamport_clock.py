import threading


class LamportClock:

    def __init__(self, initial_time=0):
        self.time = initial_time
        self.lock = threading.Lock()

    def tick(self):
        """
        Increment Lamport clock for a local event.
        """
        with self.lock:
            self.time += 1
            return self.time

    def receive(self, received_time):
        """
        Update Lamport clock when a message is received.

        Rule:
        C = max(C, received_timestamp) + 1
        """
        with self.lock:
            self.time = max(
                self.time,
                int(received_time)
            ) + 1

            return self.time

    def now(self):
        """
        Return current Lamport clock value.
        """
        with self.lock:
            return self.time