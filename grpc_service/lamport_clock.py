"""
grpc_service/lamport_clock.py
==============================
Lamport Logical Clock — Experiment 3: Distributed Computing

A Lamport clock assigns a monotonically increasing integer timestamp
to every event in a distributed system. It obeys two rules:

  Rule 1 (Local event):
      Before any local event, increment: C = C + 1

  Rule 2 (Message receive):
      On receiving a message with timestamp T:
      C = max(C, T) + 1

This ensures: if event A causally precedes event B, then
timestamp(A) < timestamp(B). It does NOT guarantee the converse,
but it does establish a consistent global ordering of events.

Thread-safety: threading.Lock ensures concurrent gRPC calls
(which use a thread pool) never corrupt the clock value.
"""

import threading


class LamportClock:
    """
    Thread-safe Lamport logical clock.

    Usage:
        clock = LamportClock()
        t = clock.tick()          # local event → increment
        t = clock.receive(msg_t)  # receive message → update
        t = clock.now()           # read current value
    """

    def __init__(self, initial_time: int = 0):
        self.time = initial_time
        self.lock = threading.Lock()          # Protect concurrent access

    # ------------------------------------------------------------------
    # Rule 1 — Local event
    # ------------------------------------------------------------------
    def tick(self) -> int:
        """
        Increment the clock for a local send or internal event.
        Returns the new timestamp.
        """
        with self.lock:
            self.time += 1
            return self.time

    # ------------------------------------------------------------------
    # Rule 2 — Message receive
    # ------------------------------------------------------------------
    def receive(self, received_time) -> int:
        """
        Update the clock upon receiving a message with 'received_time'.

        Formula:  C = max(C, received_time) + 1

        This guarantees the local clock is always strictly greater than
        the sender's clock at the moment the message was sent.
        Returns the new timestamp.
        """
        with self.lock:
            self.time = max(self.time, int(received_time)) + 1
            return self.time

    # ------------------------------------------------------------------
    # Read current value (no side effect)
    # ------------------------------------------------------------------
    def now(self) -> int:
        """Return the current clock value without modifying it."""
        with self.lock:
            return self.time
