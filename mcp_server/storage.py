"""
Storage manager for notes and tasks.
FINAL VERSION — No circular imports, absolute paths only.

Notes:
- Reads from disk on every operation (safe for assignment scale)
- Atomic writes via temp file + shutil.move (no partial writes)
- No file locking (not concurrency-safe, acceptable for this scope)
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union


class StorageManager:
    """Manages persistent JSON storage for notes and tasks."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        else:
            data_dir = Path(data_dir)

        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True, parents=True)

        self.notes_file = self.data_dir / "notes.json"
        self.tasks_file = self.data_dir / "tasks.json"

        self._ensure_files()

    # ─────────────────────────────
    # INIT HELPERS
    # ─────────────────────────────

    def _ensure_files(self):
        """Ensure JSON files exist and are valid on startup."""
        for file in [self.notes_file, self.tasks_file]:
            if not file.exists():
                file.write_text(json.dumps({}), encoding="utf-8")
            else:
                try:
                    content = file.read_text(encoding="utf-8")
                    json.loads(content or "{}")
                except json.JSONDecodeError:
                    print(f"[Storage Warning] Corrupted file reset: {file}")
                    file.write_text(json.dumps({}), encoding="utf-8")

    def _load_json(self, filepath: Path) -> Dict[str, Dict]:
        """Load JSON from file. Raises on failure — no silent data loss."""
        try:
            content = filepath.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else {}
        except Exception as e:
            print(f"[Storage ERROR] Failed to read {filepath}: {e}")
            raise RuntimeError(f"Storage read failure: {filepath}") from e

    def _atomic_write(self, filepath: Path, data: Dict) -> bool:
        """
        Write data atomically via temp file + move.
        Prevents partial writes on crash.
        """
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=self.data_dir,
                encoding="utf-8",
                suffix=".tmp",
            ) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                temp_path = Path(tmp.name)

            shutil.move(str(temp_path), filepath)
            return True

        except Exception as e:
            print(f"[Storage ERROR] Failed to write {filepath}: {e}")
            if temp_path and temp_path.exists():
                os.remove(temp_path)
            return False

    # ─────────────────────────────
    # NOTES
    # ─────────────────────────────

    def get_all_notes(self) -> Dict[str, Dict]:
        """Load all notes sorted by created_at descending."""
        notes = self._load_json(self.notes_file)
        return dict(
            sorted(
                notes.items(),
                key=lambda x: x[1].get("created_at", ""),
                reverse=True,
            )
        )

    def save_note(self, note: Dict) -> bool:
        """Upsert note by ID. Overwrites existing note with same ID."""
        if "id" not in note:
            raise ValueError("Note must have an 'id'")

        notes = self.get_all_notes()
        notes[note["id"]] = note
        result = self._atomic_write(self.notes_file, notes)

        if not result:
            raise RuntimeError("Failed to persist note to disk")

        return True

    def get_note(self, note_id: str) -> Optional[Dict]:
        """Fetch a single note by ID."""
        return self.get_all_notes().get(note_id)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID. Returns False if not found."""
        notes = self.get_all_notes()
        if note_id not in notes:
            return False
        del notes[note_id]
        return self._atomic_write(self.notes_file, notes)

    def search_notes(self, query: str) -> List[Dict]:
        """Search notes by keyword across title, content, and tags."""
        notes = self.get_all_notes()
        query_lower = query.lower()

        return [
            note for note in notes.values()
            if (
                query_lower in note.get("title", "").lower()
                or query_lower in note.get("content", "").lower()
                or any(
                    query_lower in tag.lower()
                    for tag in note.get("tags", [])
                )
            )
        ]

    # ─────────────────────────────
    # TASKS
    # ─────────────────────────────

    def get_all_tasks(self) -> Dict[str, Dict]:
        """Load all tasks sorted by created_at descending."""
        tasks = self._load_json(self.tasks_file)
        return dict(
            sorted(
                tasks.items(),
                key=lambda x: x[1].get("created_at", ""),
                reverse=True,
            )
        )

    def save_task(self, task: Dict) -> bool:
        """
        Upsert task by ID.
        Overwrites existing task — safe for updates (e.g. complete_task).
        """
        if "id" not in task:
            raise ValueError("Task must have an 'id'")

        tasks = self.get_all_tasks()
        tasks[task["id"]] = task
        result = self._atomic_write(self.tasks_file, tasks)

        if not result:
            raise RuntimeError("Failed to persist task to disk")

        return True

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Fetch a single task by ID."""
        return self.get_all_tasks().get(task_id)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID. Returns False if not found."""
        tasks = self.get_all_tasks()
        if task_id not in tasks:
            return False
        del tasks[task_id]
        return self._atomic_write(self.tasks_file, tasks)

    # ─────────────────────────────
    # STATS
    # ─────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """
        Return workspace stats for dashboard and get_summary tool.
        Centralised here to avoid duplication in server.py.
        """
        notes = self.get_all_notes()
        tasks = self.get_all_tasks()

        completed = sum(1 for t in tasks.values() if t.get("completed"))
        pending = sum(1 for t in tasks.values() if not t.get("completed"))

        return {
            "total_notes": len(notes),
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "pending_tasks": pending,
        }