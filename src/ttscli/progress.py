from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console(stderr=True)


@contextmanager
def make_progress():
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=Console(stderr=True),
        transient=False,
    )
    with progress:
        yield progress


class StepProgress:
    def __init__(self, progress: Progress, description: str, total: int = 100):
        self.progress = progress
        self.task_id = progress.add_task(description, total=total)

    def update(self, completed: int, description: str | None = None):
        kwargs: dict = {"completed": completed}
        if description is not None:
            kwargs["description"] = description
        self.progress.update(self.task_id, **kwargs)

    def advance_to(self, pct: int, description: str | None = None):
        self.update(pct, description)

    def finish(self, description: str | None = None):
        self.advance_to(100, description)
        self.progress.update(self.task_id, visible=False)
