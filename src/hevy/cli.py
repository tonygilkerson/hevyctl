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
    workout_ls_parser.add_argument("--page-size", dest="page_size", type=parse_page_size, default=7, help="Number of workouts to fetch")
    workout_ls_parser.add_argument(
        "--check-routine",
        action="store_true",
        help="Compare workout exercises to a routine with the same title",
    )
    workout_ls_parser.add_argument(
        "--no-exercises",
        action="store_true",
        help="List workouts without printing exercises",
    )
    workout_ls_parser.add_argument("--with-notes", dest="with_notes", action="store_true", help="Include exercise notes")

    routine_parser = subparsers.add_parser("routine", help="Routine commands")
    routine_subparsers = routine_parser.add_subparsers(dest="routine_command")

    routine_ls_parser = routine_subparsers.add_parser("ls", help="List routines")
    routine_ls_parser.add_argument("--page-size", dest="page_size", type=parse_page_size, default=10, help="Number of routines to fetch")
    routine_ls_parser.add_argument("--with-notes", dest="with_notes", action="store_true", help="Include notes")

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

    all_routines: list[dict] = []
    page = 1
    page_count: int | None = None

    while True:
        query = parse.urlencode({"page": page, "pageSize": page_size})
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

        response_page_count = payload.get("page_count")
        if isinstance(response_page_count, int) and response_page_count > 0:
            page_count = response_page_count

        if not routines:
            break

        all_routines.extend(routines)

        # When fewer than page_size are returned, we reached the last page.
        if len(routines) < page_size:
            break

        if page_count is not None and page >= page_count:
            break

        page += 1

    return all_routines


def build_routine_lookup(routines: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for routine in routines:
        if not isinstance(routine, dict):
            continue

        title = routine.get("title")
        if isinstance(title, str) and title:
            lookup[title] = routine

    return lookup


def print_workouts(
    workouts: list[dict],
    check_routine: bool = False,
    routines: list[dict] | None = None,
    include_exercises: bool = True,
    include_notes: bool = False,
) -> None:
    if not workouts:
        print("No workouts found.")
        return

    routine_lookup = build_routine_lookup(routines or []) if check_routine else {}

    print(f"\nWorkouts:\n")
    for index, workout in enumerate(workouts, start=1):
        title = workout.get("title") or "(untitled)"
        description = workout.get("description") or ""
        print(f"{title}")
        for description_line in description.strip().splitlines():
            print(f"  ( {description_line}")

        if not include_exercises:
            continue

        exercises = workout.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            continue

        routine_exercise_titles: set[str] = set()
        if check_routine:
            routine = routine_lookup.get(title)
            if isinstance(routine, dict):
                routine_exercises = routine.get("exercises")
                if isinstance(routine_exercises, list):
                    for routine_exercise in routine_exercises:
                        if not isinstance(routine_exercise, dict):
                            continue
                        routine_exercise_title = routine_exercise.get("title")
                        if isinstance(routine_exercise_title, str) and routine_exercise_title:
                            routine_exercise_titles.add(routine_exercise_title)

        workout_exercise_titles: set[str] = set()
        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue

            exercise_title = exercise.get("title") or "(untitled exercise)"
            if isinstance(exercise_title, str):
                workout_exercise_titles.add(exercise_title)

            # Add "| " prefix if exercise is part of a superset
            superset_id = exercise.get("superset_id")
            title_with_superset = f"| {exercise_title}" if superset_id is not None else exercise_title

            if not check_routine or not routine_exercise_titles:
                print(f"\n    - {title_with_superset}")
                if include_notes:
                    notes = exercise.get("notes")
                    if isinstance(notes, str) and notes.strip():
                        for note_line in notes.strip().splitlines():
                            print(f"      ( {note_line}")
                continue

            if exercise_title in routine_exercise_titles:
                print(f"\n  ✅ - {title_with_superset}")
            else:
                print(f"\n  ➕ - {title_with_superset}")

            if include_notes:
                notes = exercise.get("notes")
                if isinstance(notes, str) and notes.strip():
                    for note_line in notes.strip().splitlines():
                        print(f"      ( {note_line}")

        if check_routine and routine_exercise_titles:
            for routine_exercise_title in sorted(routine_exercise_titles):
                if routine_exercise_title not in workout_exercise_titles:
                    print(f"\n  ❌ - {routine_exercise_title}")
        print(f"\n")


def print_routines(routines: list[dict], include_notes: bool = False) -> None:
    if not routines:
        print("No routines found.")
        return

    print(f"\nRoutines:\n")
    for index, routine in enumerate(routines, start=1):
        title = routine.get("title") or "(untitled)"
        print(f"{title}")

        exercises = routine.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            continue

        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue

            exercise_title = exercise.get("title") or "(untitled exercise)"
            print(f"\n    - {exercise_title}")

            if include_notes:
                notes = exercise.get("notes")
                if isinstance(notes, str) and notes.strip():
                    for note_line in notes.strip().splitlines():
                        print(f"      ( {note_line}")
        print(f"\n")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "workout" and args.workout_command == "ls":
        try:
            workouts = fetch_workouts(args.page_size)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        routines: list[dict] | None = None
        if args.check_routine and not args.no_exercises:
            try:
                routines = fetch_routines(args.page_size)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                raise SystemExit(1) from exc

        print_workouts(
            workouts,
            check_routine=args.check_routine,
            routines=routines,
            include_exercises=not args.no_exercises,
            include_notes=args.with_notes,
        )
        return

    if args.command == "workout":
        parser.parse_args(["workout", "--help"])
        return

    if args.command == "routine" and args.routine_command == "ls":
        try:
            routines = fetch_routines(args.page_size)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        print_routines(routines, include_notes=args.with_notes)
        return

    if args.command == "routine":
        parser.parse_args(["routine", "--help"])
        return

    parser.print_help()


if __name__ == "__main__":
    main()