"""
grpc_service/meal_client.py
============================
gRPC Client -- Experiment 3: Distributed Computing

This client connects to the MealService gRPC server running on
localhost:50051 and queries nutrition data for multiple food items.

It maintains its own Lamport logical clock to demonstrate
distributed event ordering between two separate processes.

Distributed Computing Concepts demonstrated:
  - gRPC Stub: the client calls GetMealNutrition() just like a
    local function, but it executes remotely on the server.
  - Protocol Buffers: requests/responses are efficiently serialized.
  - Lamport Clock: client and server exchange timestamps, allowing
    a global ordering of events across both processes to be inferred.

Run from project root:
    python -m grpc_service.meal_client

(Server must already be running on port 50051)
"""

import os
import sys

# ============================================================
# RESOLVE PROJECT ROOT (same pattern as meal_server.py)
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)
sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# IMPORTS
# ============================================================

import grpc

from grpc_service.generated import meal_service_pb2
from grpc_service.generated import meal_service_pb2_grpc
from grpc_service.lamport_clock import LamportClock


# ============================================================
# CLIENT LAMPORT CLOCK
# ============================================================

client_clock = LamportClock(initial_time=0)


# ============================================================
# HELPER -- single RPC call with Lamport clock management
# ============================================================

def query_meal(stub, meal_name):
    """
    Send one GetMealNutrition RPC request and print the full
    distributed event trace including Lamport timestamps.

    Lamport Clock sequence per call:
      1. client_clock.tick()            -> send event  (C_client = C+1)
      2. Send MealRequest with that timestamp.
      3. Server receives -> max(C_server, C_client) + 1
      4. Server sends response with its updated timestamp.
      5. client_clock.receive(server_t) -> max(C_client, server_t) + 1
    """

    # --------------------------------------------------------
    # STEP 1 - Client local SEND event
    # Lamport Rule 1: increment before sending
    # --------------------------------------------------------
    send_time = client_clock.tick()

    print()
    print("-" * 60)
    print(f"[CLIENT] -> Sending request")
    print(f"[CLIENT]   Meal      : {meal_name}")
    print(f"[CLIENT]   Lamport   : {send_time}  (tick before send)")

    # --------------------------------------------------------
    # STEP 2 - Build and send the RPC request
    # Protocol Buffers serialize this message automatically
    # --------------------------------------------------------
    request = meal_service_pb2.MealRequest(
        meal_name         = meal_name,
        lamport_timestamp = send_time,
    )

    try:
        response = stub.GetMealNutrition(request, timeout=10)
    except grpc.RpcError as rpc_err:
        print(f"[CLIENT] X RPC ERROR: {rpc_err.code()} - {rpc_err.details()}")
        print("-" * 60)
        return

    # --------------------------------------------------------
    # STEP 5 - Update client Lamport clock on RECEIVE
    # Lamport Rule 2: C_client = max(C_client, C_server) + 1
    # --------------------------------------------------------
    updated_time = client_clock.receive(response.lamport_timestamp)

    print(f"[CLIENT] <- Response received")
    print(f"[CLIENT]   Server Lamport  : {response.lamport_timestamp}")
    print(f"[CLIENT]   Updated Lamport : {updated_time}  "
          f"(= max(prev, {response.lamport_timestamp}) + 1)")
    print()

    # --------------------------------------------------------
    # Print nutrition result
    # --------------------------------------------------------
    if response.status == "SUCCESS":
        print(f"  Meal          : {response.meal_name}")
        print(f"  Calories      : {response.calories:.1f} kcal")
        print(f"  Protein       : {response.protein:.1f} g")
        print(f"  Carbohydrates : {response.carbs:.1f} g")
        print(f"  Fat           : {response.fat:.1f} g")
        print(f"  Status        : [SUCCESS]")
    else:
        print(f"  Meal          : {response.meal_name}")
        print(f"  Status        : [NOT_FOUND]  (food not in Dataset)")

    print("-" * 60)


# ============================================================
# MAIN - connect to server and run test queries
# ============================================================

def run():
    """
    Open a gRPC channel to the server, create a stub, and
    send multiple meal queries to demonstrate:
      - Valid food lookups (SUCCESS)
      - An invalid food lookup (NOT_FOUND)
      - Correct Lamport timestamp progression across events
    """

    print()
    print("=" * 70)
    print("  MEAL PLANNER gRPC CLIENT  --  Experiment 3")
    print("=" * 70)
    print(f"[CLIENT] Connecting to localhost:50051 ...")

    # Open an insecure channel (no TLS - lab environment)
    with grpc.insecure_channel("localhost:50051") as channel:

        # Create the stub (client-side proxy for MealService)
        stub = meal_service_pb2_grpc.MealServiceStub(channel)

        print(f"[CLIENT] Connected. Initial Lamport Clock: {client_clock.now()}")
        print()
        print("  Testing 4 meal queries (3 valid + 1 invalid)")
        print("=" * 70)

        # --------------------------------------------------------
        # TEST 1 - Valid food (exists in Breakfast.csv)
        # --------------------------------------------------------
        query_meal(stub, "Idli (2 pcs)")

        # --------------------------------------------------------
        # TEST 2 - Valid food (exists in Lunch.csv)
        # --------------------------------------------------------
        query_meal(stub, "Dal Makhani")

        # --------------------------------------------------------
        # TEST 3 - Valid food (exists in Dinner.csv)
        # --------------------------------------------------------
        query_meal(stub, "Palak Paneer")

        # --------------------------------------------------------
        # TEST 4 - Invalid food -> demonstrates NOT_FOUND
        # --------------------------------------------------------
        query_meal(stub, "PizzaBurger9000")

    # --------------------------------------------------------
    # Final Lamport clock state
    # --------------------------------------------------------
    print()
    print("=" * 70)
    print(f"[CLIENT] All queries complete.")
    print(f"[CLIENT] Final Lamport Clock: {client_clock.now()}")
    print()
    print("  Distributed Event Ordering Summary")
    print("  -----------------------------------")
    print("  Every send/receive updated the Lamport clock so that")
    print("  events are globally ordered across client and server.")
    print("  If event A causally precedes B -> timestamp(A) < timestamp(B)")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()
