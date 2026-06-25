import argparse
import json
import os
import sys
from urllib import error, parse, request


API_URL = "https://api.hevyapp.com/v1/workouts"
ROUTINES_API_URL = "https://api.hevyapp.com/v1/routines"


def parse_page_size(value: str) -> int:
    try:
        page_size = int(value)
    except ValueError:
        return 7

    return page_size if page_size > 0 else 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hevyctl")
    parser.add_argument("--version", action="version", version="0.1.0")

    subparsers = parser.add_subparsers(dest="command")

    workout_parser = subparsers.add_parser("workout", help="Workout commands")
    workout_subparsers = workout_parser.add_subparsers(dest="workout_command")

    workout_ls_parser = workout_subparsers.add_parser("ls", help="List workouts")
    workout_ls_parser.add_argument("--pageSize", type=parse_page_size, default=7, help="Number of workouts to fetch")

    routine_parser = subparsers.add_parser("routine", help="Routine commands")
    routine_subparsers = routine_parser.add_subparsers(dest="routine_command")

    routine_ls_parser = routine_subparsers.add_parser("ls", help="List routines")
    routine_ls_parser.add_argument("--pageSize", type=parse_page_size, default=7, help="Number of routines to fetch")

    return parser


def fetch_workouts(page_size: int) -> list[dict]:
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY environment variable is not set")

    query = parse.urlencode({"page": 1, "pageSize": page_size})
    req = request.Request(
        f"{API_URL}?{query}",
        headers={
            "accept": "application/json",
            "api-key": api_key,
        },
        method="GET",
    )

    try:
        with request.urlopen(req) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hevy API request failed: {exc.code} {exc.reason}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Hevy API: {exc.reason}") from exc

    workouts = payload.get("workouts")
    if not isinstance(workouts, list):
        raise RuntimeError("Hevy API response did not contain a workouts list")

    return workouts


def fetch_routines(page_size: int) -> list[dict]:
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY environment variable is not set")

    query = parse.urlencode({"page": 1, "pageSize": page_size})
    req = request.Request(
        f"{ROUTINES_API_URL}?{query}",
        headers={
            "accept": "application/json",
            "api-key": api_key,
        },
        method="GET",
    )

    try:
        with request.urlopen(req) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hevy API request failed: {exc.code} {exc.reason}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Hevy API: {exc.reason}") from exc

    routines = payload.get("routines")
    if not isinstance(routines, list):
        raise RuntimeError("Hevy API response did not contain a routines list")

    return routines


def print_workouts(workouts: list[dict]) -> None:
    if not workouts:
        print("No workouts found.")
        return


    print(f"\nWorkouts:")
    for index, workout in enumerate(workouts, start=1):
        title = workout.get("title") or "(untitled)"
        description = workout.get("description") or ""
        print(f"\n{title} {description}")

        exercises = workout.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            continue

        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue

            exercise_title = exercise.get("title") or "(untitled exercise)"
            # notes = exercise.get("notes") or ""
            print(f"    - {exercise_title}")
    print(f"\n")


def print_routines(routines: list[dict]) -> None:
    if not routines:
        print("No routines found.")
        return

    print(f"\nRoutines:")
    for index, routine in enumerate(routines, start=1):
        title = routine.get("title") or "(untitled)"
        description = routine.get("description") or ""
        print(f"\n{title} {description}")

        exercises = routine.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            continue

        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue

            exercise_title = exercise.get("title") or "(untitled exercise)"
            # notes = exercise.get("notes") or ""
            print(f"    - {exercise_title}")
    print(f"\n")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "workout" and args.workout_command == "ls":
        try:
            workouts = fetch_workouts(args.pageSize)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        print_workouts(workouts)
        return

    if args.command == "workout":
        parser.parse_args(["workout", "--help"])
        return

    if args.command == "routine" and args.routine_command == "ls":
        try:
            routines = fetch_routines(args.pageSize)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        print_routines(routines)
        return

    if args.command == "routine":
        parser.parse_args(["routine", "--help"])
        return

    parser.print_help()


if __name__ == "__main__":
    main()