import argparse
import json
import os
import sys
from urllib import error, parse, request


API_URL = "https://api.hevyapp.com/v1/workouts"


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

    workouts_parser = subparsers.add_parser("workouts", help="List workouts")
    workouts_parser.add_argument("--pageSize", type=parse_page_size, default=7, help="Number of workouts to fetch")

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


def get_exercise_title(exercise: dict) -> str:
    title = exercise.get("title") or exercise.get("name")
    if isinstance(title, str) and title:
        return title

    template = exercise.get("exercise_template") or exercise.get("exerciseTemplate")
    if isinstance(template, dict):
        template_title = template.get("title") or template.get("name")
        if isinstance(template_title, str) and template_title:
            return template_title

    return "(untitled exercise)"


def print_workouts(workouts: list[dict]) -> None:
    if not workouts:
        print("No workouts found.")
        return

    for index, workout in enumerate(workouts, start=1):
        title = workout.get("title") or "(untitled)"
        description = workout.get("description") or ""
        print(f"\nWorkout: {title} {description}")

        exercises = workout.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            continue

        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue

            exercise_title = get_exercise_title(exercise)
            notes = exercise.get("notes") or ""
            print(f"   - {exercise_title} {notes}")
    print(f"\n")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "workouts":
        try:
            workouts = fetch_workouts(args.pageSize)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        print_workouts(workouts)
        return

    parser.print_help()


if __name__ == "__main__":
    main()