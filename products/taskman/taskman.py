"""Task Manager CLI - A robust task tracking utility."""
import argparse
import json
import os
import sys
from typing import List, Dict, Any

DB_FILE = os.environ.get("TASKMAN_DB", "tasks.json")

def load_tasks() -> List[Dict[str, Any]]:
    """Loads tasks from the JSON storage."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading database: {e}", file=sys.stderr)
        return []

def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    """Saves tasks to the JSON storage."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
    except IOError as e:
        print(f"Error saving database: {e}", file=sys.stderr)

def add(args: argparse.Namespace) -> None:
    """Adds a new task."""
    task_text = args.task.strip()
    if not task_text:
        print("Error: Task description cannot be empty.")
        return
    tasks = load_tasks()
    tasks.append({"id": len(tasks) + 1, "task": task_text, "done": False})
    save_tasks(tasks)
    print(f"Added task: {task_text}")

def list_tasks(args: argparse.Namespace) -> None:
    """Lists all tasks."""
    tasks = load_tasks()
    if not tasks:
        print("No tasks found.")
        return
    print(f"{'ID':<4} {'Task':<30} {'Status'}")
    print("-" * 45)
    for t in tasks:
        status = "Done" if t["done"] else "Pending"
        print(f"{t['id']:<4} {t['task']:<30} {status}")

def done(args: argparse.Namespace) -> None:
    """Marks a task as done."""
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t["id"] == args.id:
            t["done"] = True
            found = True
            break
    if not found:
        print(f"Error: Task ID {args.id} not found.")
        return
    save_tasks(tasks)
    print(f"Marked task {args.id} as done.")

def rm(args: argparse.Namespace) -> None:
    """Removes a task."""
    tasks = load_tasks()
    if not any(t["id"] == args.id for t in tasks):
        print(f"Error: Task ID {args.id} not found.")
        return
    tasks = [t for t in tasks if t["id"] != args.id]
    for i, t in enumerate(tasks):
        t["id"] = i + 1
    save_tasks(tasks)
    print(f"Removed task {args.id}.")

def stats(args: argparse.Namespace) -> None:
    """Displays task statistics."""
    tasks = load_tasks()
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["done"])
    pending = total - done_count
    print(f"{'Metric':<15} {'Value'}")
    print("-" * 25)
    print(f"{'Total':<15} {total}")
    print(f"{'Done':<15} {done_count}")
    print(f"{'Pending':<15} {pending}")

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Task Manager CLI")
    parser.add_argument("--version", action="version", version="1.0.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add", help="Add a new task")
    parser_add.add_argument("task", help="Task description")
    parser_add.set_defaults(func=add)

    parser_list = subparsers.add_parser("list", help="List all tasks")
    parser_list.set_defaults(func=list_tasks)

    parser_done = subparsers.add_parser("done", help="Mark a task as done")
    parser_done.add_argument("id", type=int, help="Task ID")
    parser_done.set_defaults(func=done)

    parser_rm = subparsers.add_parser("rm", help="Remove a task")
    parser_rm.add_argument("id", type=int, help="Task ID")
    parser_rm.set_defaults(func=rm)

    parser_stats = subparsers.add_parser("stats", help="Show task statistics")
    parser_stats.set_defaults(func=stats)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
