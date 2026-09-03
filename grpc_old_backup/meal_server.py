from concurrent import futures
import os
import sys

import grpc
import pandas as pd


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORT GENERATED gRPC FILES
# ============================================================

from grpc.generated import meal_service_pb2
from grpc.generated import meal_service_pb2_grpc

from grpc.lamport_clock import LamportClock


# ============================================================
# LAMPORT CLOCK
# ============================================================

server_clock = LamportClock()


# ============================================================
# DATASET PATH
# ============================================================

DATASET_DIR = os.path.join(
    PROJECT_ROOT,
    "Dataset"
)


# ============================================================
# LOAD DATA
# ============================================================

def load_food_data():

    dataframes = []

    files = [
        "Breakfast.csv",
        "Lunch.csv",
        "Dinner.csv"
    ]

    for filename in files:

        filepath = os.path.join(
            DATASET_DIR,
            filename
        )

        if os.path.exists(filepath):

            try:

                df = pd.read_csv(filepath)

                if not df.empty:
                    dataframes.append(df)

                print(
                    f"[SERVER] Loaded {filename}"
                )

            except Exception as e:

                print(
                    f"[SERVER] Error loading "
                    f"{filename}: {e}"
                )

        else:

            print(
                f"[SERVER] File not found: "
                f"{filepath}"
            )

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(
        dataframes,
        ignore_index=True
    )


FOOD_DATA = load_food_data()


# ============================================================
# FIND COLUMN
# ============================================================

def find_column(df, possible_names):

    if df.empty:
        return None

    columns = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:

        if name.lower() in columns:
            return columns[name.lower()]

    return None


# ============================================================
# GET FOOD INFORMATION
# ============================================================

def get_food_information(meal_name):

    if FOOD_DATA.empty:
        return None

    name_column = find_column(
        FOOD_DATA,
        [
            "name",
            "food",
            "food_name",
            "dish",
            "item",
            "recipe"
        ]
    )

    if name_column is None:
        return None

    search_name = meal_name.strip().lower()

    matches = FOOD_DATA[
        FOOD_DATA[name_column]
        .astype(str)
        .str.lower()
        .str.contains(
            search_name,
            na=False
        )
    ]

    if matches.empty:
        return None

    row = matches.iloc[0]

    calories_column = find_column(
        FOOD_DATA,
        [
            "calories",
            "calorie",
            "energy",
            "kcal"
        ]
    )

    protein_column = find_column(
        FOOD_DATA,
        [
            "protein",
            "protein_g"
        ]
    )

    carbs_column = find_column(
        FOOD_DATA,
        [
            "carbs",
            "carbohydrates",
            "carbohydrate"
        ]
    )

    fat_column = find_column(
        FOOD_DATA,
        [
            "fat",
            "fats",
            "total_fat"
        ]
    )

    def get_value(column):

        if column is None:
            return 0

        try:

            value = row[column]

            if pd.isna(value):
                return 0

            return float(value)

        except Exception:

            return 0

    return {
        "calories": get_value(calories_column),
        "protein": get_value(protein_column),
        "carbs": get_value(carbs_column),
        "fat": get_value(fat_column)
    }


# ============================================================
# gRPC SERVICE
# ============================================================

class MealService(
    meal_service_pb2_grpc.MealServiceServicer
):

    def GetMealNutrition(
        self,
        request,
        context
    ):

        # ----------------------------------------------------
        # RECEIVE EVENT
        # ----------------------------------------------------

        server_receive_time = server_clock.receive(
            request.lamport_timestamp
        )

        print()
        print(
            "[SERVER] Request received"
        )

        print(
            f"[SERVER] Meal: "
            f"{request.meal_name}"
        )

        print(
            f"[SERVER] Client Lamport: "
            f"{request.lamport_timestamp}"
        )

        print(
            f"[SERVER] Server Lamport: "
            f"{server_receive_time}"
        )

        # ----------------------------------------------------
        # SEARCH DATASET
        # ----------------------------------------------------

        food = get_food_information(
            request.meal_name
        )

        if food is None:

            response_time = server_clock.tick()

            print(
                "[SERVER] Meal not found"
            )

            print(
                f"[SERVER] Response Lamport: "
                f"{response_time}"
            )

            return meal_service_pb2.MealResponse(
                meal_name=request.meal_name,
                calories=0,
                protein=0,
                carbs=0,
                fat=0,
                lamport_timestamp=response_time,
                status="NOT_FOUND"
            )

        # ----------------------------------------------------
        # SEND RESPONSE
        # ----------------------------------------------------

        response_time = server_clock.tick()

        print()
        print(
            "[SERVER] Sending response"
        )

        print(
            f"[SERVER] Response Lamport: "
            f"{response_time}"
        )

        return meal_service_pb2.MealResponse(

            meal_name=request.meal_name,

            calories=food["calories"],

            protein=food["protein"],

            carbs=food["carbs"],

            fat=food["fat"],

            lamport_timestamp=response_time,

            status="SUCCESS"
        )


# ============================================================
# START gRPC SERVER
# ============================================================

def serve():

    print()
    print("=" * 70)
    print("STARTING MEAL PLANNER gRPC SERVER")
    print("=" * 70)

    server = grpc.server(
        futures.ThreadPoolExecutor(
            max_workers=10
        )
    )

    meal_service_pb2_grpc.add_MealServiceServicer_to_server(
        MealService(),
        server
    )

    port = server.add_insecure_port(
        "[::]:50051"
    )

    print(
        f"[SERVER] Port configured: {port}"
    )

    server.start()

    print(
        "[SERVER] Server started successfully"
    )

    print(
        "[SERVER] Running on port 50051"
    )

    print(
        f"[SERVER] Initial Lamport Clock: "
        f"{server_clock.now()}"
    )

    print("=" * 70)

    # Keep server alive
    server.wait_for_termination()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    serve()