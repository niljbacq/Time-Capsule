import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from session_snapshot.models.manifest import SESSION_ID_RE, Manifest


class ManifestError(Exception):
    """Raised for any problem reading, writing, or validating a manifest."""


def default_session_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "linux-session-snapshot" / "sessions"


class ManifestStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_session_dir()

    def _path(self, session_id: str) -> Path:
        if not SESSION_ID_RE.match(session_id):
            raise ManifestError(f"invalid session id: {session_id!r}")
        return self.root / f"{session_id}.json"

    def save(self, manifest: Manifest) -> Path:
        path = self._path(manifest.session.id)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        data = manifest.model_dump_json(indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        return path

    def load(self, session_id: str) -> Manifest:
        path = self._path(session_id)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ManifestError(f"session not found: {session_id}") from None
        except OSError as exc:
            raise ManifestError(f"cannot read session {session_id}: {exc}") from exc
        try:
            return Manifest.model_validate(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"session {session_id} is not valid JSON: {exc}") from exc
        except ValidationError as exc:
            raise ManifestError(f"session {session_id} failed validation: {exc}") from exc

    def list_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            p.stem for p in self.root.glob("*.json") if SESSION_ID_RE.match(p.stem)
        )

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            raise ManifestError(f"session not found: {session_id}") from None
