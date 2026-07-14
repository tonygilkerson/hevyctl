import argparse
import json
import os
import sys
from typing import Optional
from urllib import error, parse, request


API_URL = "https://api.hevyapp.com/v1/workouts"
ROUTINES_API_URL = "https://api.hevyapp.com/v1/routines"
ROUTINE_FOLDERS_API_URL = "https://api.hevyapp.com/v1/routine_folders"
POUNDS_PER_KILOGRAM = 2.20462


def parse_page_size(value: str) -> int:
    try:
        page_size = int(value)
    except ValueError:
        return 7

    return page_size if page_size > 0 else 5


def format_weight_lbs(weight_kg: object) -> str:
    if not isinstance(weight_kg, (int, float)) or isinstance(weight_kg, bool):
        return ""

    weight_lbs = round(weight_kg * POUNDS_PER_KILOGRAM, 1)
    if weight_lbs.is_integer():
        return str(int(weight_lbs))

    return f"{weight_lbs:.1f}"


def format_set_weight_and_reps(exercise_set: dict) -> str:
    set_type = exercise_set.get("type")
    if set_type == "normal":
        set_index = exercise_set.get("index")
        set_text = str(set_index + 1) if isinstance(set_index, int) else "?"
    elif set_type == "failure":
        set_text = "F"
    elif set_type == "warmup":
        set_text = "W"
    else:
        set_text = "?"

    weight = format_weight_lbs(exercise_set.get("weight_kg"))
    weight_text = f"{weight:>4} lbs" if weight else ""

    reps = exercise_set.get("reps")
    reps_text = f"X {reps:>2} reps" if isinstance(reps, int) and not isinstance(reps, bool) else ""

    if not weight_text and not reps_text:
        return ""

    return f"{set_text} {weight_text} {reps_text}".rstrip()


def print_exercise_details(
    exercise: dict,
    include_notes: bool = False,
    include_sets: bool = False,
    indent: str = "      ",
) -> None:
    if include_notes:
        notes = exercise.get("notes")
        if isinstance(notes, str) and notes.strip():
            for note_line in notes.strip().splitlines():
                print(f"{indent}( {note_line}")

    if not include_sets:
        return

    sets = exercise.get("sets")
    if not isinstance(sets, list) or not sets:
        return

    for exercise_set in sets:
        if not isinstance(exercise_set, dict):
            continue

        set_text = format_set_weight_and_reps(exercise_set)
        if set_text:
            print(f"{indent}{set_text}")
        else:
            print(f"{indent}...")


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
    workout_ls_parser.add_argument("--with-sets", dest="with_sets", action="store_true", help="Include exercise sets")
    workout_ls_parser.add_argument("--exercise", dest="exercise_filter", type=str, default="", help="Only show exercises whose name contains this string")

    routine_parser = subparsers.add_parser("routine", help="Routine commands")
    routine_subparsers = routine_parser.add_subparsers(dest="routine_command")

    routine_ls_parser = routine_subparsers.add_parser("ls", help="List routines")
    routine_ls_parser.add_argument("--page-size", dest="page_size", type=parse_page_size, default=10, help="Number of routines to fetch")
    routine_ls_parser.add_argument("--with-notes", dest="with_notes", action="store_true", help="Include notes")
    routine_ls_parser.add_argument("--with-sets", dest="with_sets", action="store_true", help="Include exercise sets")
    routine_ls_parser.add_argument("--exercise", dest="exercise_filter", type=str, default="", help="Only show exercises whose name contains this string")
    routine_ls_parser.add_argument("--name", dest="name_filter", type=str, default="", help="Only show routines whose name contains this string")
    routine_ls_parser.add_argument("--folder", dest="folder_filter", type=str, default="", help="Only show routines whose folder title contains this string")

    folder_parser = subparsers.add_parser("folder", help="Routine folder commands")
    folder_subparsers = folder_parser.add_subparsers(dest="folder_command")

    folder_ls_parser = folder_subparsers.add_parser("ls", help="List routine folders")
    folder_ls_parser.add_argument("--page-size", dest="page_size", type=parse_page_size, default=10, help="Number of routine folders to fetch")

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
    page_count: Optional[int] = None

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


def fetch_folders(page_size: int) -> list[dict]:
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY environment variable is not set")

    folders: list[dict] = []
    page = 1
    page_count: Optional[int] = None

    while True:
        query = parse.urlencode({"page": page, "pageSize": page_size})
        req = request.Request(
            f"{ROUTINE_FOLDERS_API_URL}?{query}",
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

        page_folders = payload.get("routine_folders")
        if not isinstance(page_folders, list):
            raise RuntimeError("Hevy API response did not contain a routine_folders list")

        response_page_count = payload.get("page_count")
        if isinstance(response_page_count, int) and response_page_count > 0:
            page_count = response_page_count

        if not page_folders:
            break

        folders.extend(page_folders)

        if len(page_folders) < page_size:
            break

        if page_count is not None and page >= page_count:
            break

        page += 1

    return folders


def build_folder_title_lookup(folders: list[dict]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for folder in folders:
        if not isinstance(folder, dict):
            continue

        folder_id = folder.get("id")
        folder_title = folder.get("title")
        if isinstance(folder_id, int) and isinstance(folder_title, str) and folder_title:
            lookup[folder_id] = folder_title

    return lookup


def build_routine_lookup(routines: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for routine in routines:
        if not isinstance(routine, dict):
            continue

        title = routine.get("title")
        if isinstance(title, str) and title:
            lookup[title] = routine

    return lookup


def title_matches_exercise_filter(title: object, exercise_filter_text: str) -> bool:
    return isinstance(title, str) and (not exercise_filter_text or exercise_filter_text in title.lower())


def filter_exercises(exercises: object, exercise_filter_text: str) -> list[dict]:
    if not isinstance(exercises, list):
        return []

    matching_exercises: list[dict] = []
    for exercise in exercises:
        if not isinstance(exercise, dict):
            continue

        if title_matches_exercise_filter(exercise.get("title"), exercise_filter_text):
            matching_exercises.append(exercise)

    return matching_exercises


def print_workouts(
    workouts: list[dict],
    check_routine: bool = False,
    routines: Optional[list[dict]] = None,
    include_exercises: bool = True,
    include_notes: bool = False,
    include_sets: bool = False,
    exercise_filter: str = "",
) -> None:
    if not workouts:
        print("No workouts found.")
        return

    routine_lookup = build_routine_lookup(routines or []) if check_routine else {}
    exercise_filter_text = exercise_filter.lower()

    print(f"\n🏋️ Workouts:\n")
    for index, workout in enumerate(workouts, start=1):
        matching_exercises = filter_exercises(workout.get("exercises"), exercise_filter_text)

        if exercise_filter_text and not matching_exercises:
            continue

        title = workout.get("title") or "(untitled)"
        description = workout.get("description") or ""
        print(f"{title}")
        for description_line in description.strip().splitlines():
            print(f"  ( {description_line}")

        if not include_exercises:
            print(f"\n")
            continue

        if not matching_exercises:
            print(f"\n")
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
                        if title_matches_exercise_filter(routine_exercise_title, exercise_filter_text):
                            routine_exercise_titles.add(routine_exercise_title)

        workout_exercise_titles: set[str] = set()
        for exercise in matching_exercises:
            exercise_title = exercise.get("title") or "(untitled exercise)"
            if isinstance(exercise_title, str):
                workout_exercise_titles.add(exercise_title)

            # Add "| " prefix if exercise is part of a superset
            superset_id = exercise.get("superset_id")
            title_with_superset = f"| {exercise_title}" if superset_id is not None else exercise_title

            if not check_routine or not routine_exercise_titles:
                print(f"  - {title_with_superset}")
                print_exercise_details(
                    exercise,
                    include_notes=include_notes,
                    include_sets=include_sets,
                    indent="    ",
                )
                continue

            if exercise_title in routine_exercise_titles:
                print(f"  ✅ - {title_with_superset}")
            else:
                print(f"  ➕ - {title_with_superset}")

            print_exercise_details(
                exercise,
                include_notes=include_notes,
                include_sets=include_sets,
                indent="    ",
            )

        if check_routine and routine_exercise_titles:
            for routine_exercise_title in sorted(routine_exercise_titles):
                if routine_exercise_title not in workout_exercise_titles:
                    print(f"  ❌ - {routine_exercise_title}")
        print(f"\n")


def print_routines(
    routines: list[dict],
    include_notes: bool = False,
    include_sets: bool = False,
    exercise_filter: str = "",
    folder_title_lookup: Optional[dict[int, str]] = None,
    group_by_folder: bool = False,
) -> None:
    if not routines:
        print("No routines found.")
        return

    folder_title_lookup = folder_title_lookup or {}
    previous_folder_title: Optional[str] = None
    exercise_filter_text = exercise_filter.lower()

    print(f"\nRoutines:\n")
    for index, routine in enumerate(routines, start=1):
        matching_exercises = filter_exercises(routine.get("exercises"), exercise_filter_text)

        if exercise_filter_text and not matching_exercises:
            continue

        title = routine.get("title") or "(untitled)"
        folder_title = ""
        folder_id = routine.get("folder_id")
        if isinstance(folder_id, int):
            folder_title = folder_title_lookup.get(folder_id, "")
        folder_label = folder_title or "My Routines"

        if group_by_folder and folder_title:
            if folder_title != previous_folder_title:
                print(f"🗂️ {folder_title}")
                previous_folder_title = folder_title
            print(f"{title}")
        elif group_by_folder and not folder_title:
            if folder_label != previous_folder_title:
                print(f"🗂️ {folder_label}")
                previous_folder_title = folder_label
            print(f"{title}")
        else:
            print(f"🗂️ {folder_label}\n{title}")

        if not matching_exercises:
            continue

        for exercise in matching_exercises:
            exercise_title = exercise.get("title") or "(untitled exercise)"

            # Add "| " prefix if exercise is part of a superset
            superset_id = exercise.get("superset_id")
            title_with_superset = f"| {exercise_title}" if superset_id is not None else exercise_title

            print(f"  - {title_with_superset}")

            print_exercise_details(exercise, include_notes=include_notes, include_sets=include_sets, indent="    ")
        print(f"\n")


def print_folders(folders: list[dict]) -> None:
    if not folders:
        print("No routine folders found.")
        return

    print(f"\nRoutine Folders:\n")
    for folder in folders:
        if not isinstance(folder, dict):
            continue

        title = folder.get("title") or "(untitled)"
        print(f"- {title}")

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

        routines: Optional[list[dict]] = None
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
            include_sets=args.with_sets,
            exercise_filter=args.exercise_filter,
        )
        return

    if args.command == "workout":
        parser.parse_args(["workout", "--help"])
        return

    if args.command == "routine" and args.routine_command == "ls":
        try:
            routines = fetch_routines(args.page_size)
            folders = fetch_folders(args.page_size)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        folder_title_lookup = build_folder_title_lookup(folders)

        if args.name_filter:
            filter_text = args.name_filter.lower()
            routines = [
                routine
                for routine in routines
                if isinstance(routine.get("title"), str) and filter_text in routine.get("title", "").lower()
            ]

        if args.folder_filter:
            folder_filter_text = args.folder_filter.lower()
            routines = [
                routine
                for routine in routines
                if folder_filter_text in folder_title_lookup.get(routine.get("folder_id"), "").lower()
            ]

        print_routines(
            routines,
            include_notes=args.with_notes,
            include_sets=args.with_sets,
            exercise_filter=args.exercise_filter,
            folder_title_lookup=folder_title_lookup,
            group_by_folder=bool(args.folder_filter),
        )
        return

    if args.command == "folder" and args.folder_command == "ls":
        try:
            folders = fetch_folders(args.page_size)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        print_folders(folders)
        return

    if args.command == "routine":
        parser.parse_args(["routine", "--help"])
        return

    if args.command == "folder":
        parser.parse_args(["folder", "--help"])
        return

    parser.print_help()


if __name__ == "__main__":
    main()