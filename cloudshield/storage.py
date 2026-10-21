from pathlib import Path


class LocalReplicaStorage:
    """Two independent replica directories. Replica B can live on a different disk (e.g. Google Drive)."""

    def __init__(self, a_dir: Path, b_dir: Path):
        self.a = Path(a_dir)
        self.b = Path(b_dir)
        self.a.mkdir(parents=True, exist_ok=True)
        self.b.mkdir(parents=True, exist_ok=True)

    def _path(self, replica, key):
        base = self.a if replica == "A" else self.b
        path = (base / key).resolve()
        if base.resolve() not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def put(self, replica, key, data):
        path = self._path(replica, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, replica, key):
        path = self._path(replica, key)
        if not path.is_file():
            raise FileNotFoundError(f"Replica {replica} object is missing")
        return path.read_bytes()

    def delete(self, replica, key):
        path = self._path(replica, key)
        if path.exists():
            path.unlink()

    def exists(self, replica, key):
        return self._path(replica, key).is_file()

    def health(self):
        def state(p):
            return "Available" if p.is_dir() else "Unavailable"
        return {"replica_a": state(self.a), "replica_b": state(self.b)}


def build_storage(settings):
    return LocalReplicaStorage(settings.replica_a_dir, settings.replica_b_dir)
