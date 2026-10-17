"""Day 5 - fleet: many harnesses at once, each in its own directory.

A fleet is not a new abstraction - it is N Harnesses, each with its own
workdir and its own context, run concurrently and collected back into one
list. Nothing here is specific to Harness; make_harness is any callable that
takes a workdir and returns something with a .run(task) method.

Design rule embodied here:
  * One job's failure never loses another job's result. Each job's exception
    is caught at the job, not the fleet, so one bad task becomes one bad
    report and the rest of the fleet finishes regardless.
"""

from concurrent.futures import ThreadPoolExecutor


def run_fleet(jobs: list, make_harness, max_workers: int = 4) -> list:
    """Run each job's task on its own Harness, concurrently; return in order.

    Each job is {"name", "workdir", "task"}. Returns [{"name", "ok", "report"}]
    - "report" is the final text on success, or "<ExceptionType>: <message>"
    on failure.
    """
    def run_one(job):
        try:
            harness = make_harness(job["workdir"])
            return {"name": job["name"], "ok": True, "report": harness.run(job["task"])}
        except Exception as error:
            return {"name": job["name"], "ok": False,
                   "report": f"{type(error).__name__}: {error}"}

    # map() yields results in the order `jobs` was given, regardless of which
    # job's thread happens to finish first.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(run_one, jobs))
