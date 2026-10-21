import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path
    temp_dir: Path
    db_path: Path
    replica_a_dir: Path
    replica_b_dir: Path
    replica_count: int
    allow_failure_simulation: bool


def get_settings():
    """Everything is configurable through environment variables; defaults work out of the box."""
    base = Path(os.getenv("CLOUDSHIELD_DATA_DIR", "data")).resolve()
    storage = base / "storage"
    return Settings(
        data_dir=base,
        temp_dir=base / "tmp",
        db_path=Path(os.getenv("CLOUDSHIELD_DB_PATH", str(base / "cloudshield.db"))).resolve(),
        replica_a_dir=Path(os.getenv("CLOUDSHIELD_REPLICA_A_DIR", str(storage / "replica_a"))).resolve(),
        replica_b_dir=Path(os.getenv("CLOUDSHIELD_REPLICA_B_DIR", str(storage / "replica_b"))).resolve(),
        replica_count=2,
        allow_failure_simulation=os.getenv("CLOUDSHIELD_ALLOW_FAILURE_SIMULATION", "true").lower() in {"1", "true", "yes"},
    )
