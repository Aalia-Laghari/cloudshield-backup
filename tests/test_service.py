from types import SimpleNamespace
from cloudshield.db import Database
from cloudshield.storage import LocalReplicaStorage
from cloudshield.service import BackupService
from cloudshield.utils import sha256_bytes


def make_service(tmp_path):
    settings = SimpleNamespace(data_dir=tmp_path, allow_failure_simulation=True)
    db = Database(tmp_path / "test.db")
    storage = LocalReplicaStorage(tmp_path / "a", tmp_path / "b")
    return BackupService(db, storage, settings), db, storage


def test_create_backup_and_recover(tmp_path):
    service, db, _ = make_service(tmp_path)
    payload = b"hello cloudshield"
    backup = service.create_backup("demo.txt", payload, "test")
    assert backup["status"] == "healthy"
    assert service.read_valid_replica(backup["id"]) == payload
    assert sha256_bytes(payload) == backup["sha256"]


def test_versions_increment(tmp_path):
    service, db, _ = make_service(tmp_path)
    assert service.create_backup("demo.txt", b"one")["version"] == 1
    assert service.create_backup("demo.txt", b"two")["version"] == 2


def test_corrupt_replica_recovers_from_other(tmp_path):
    service, db, _ = make_service(tmp_path)
    backup = service.create_backup("demo.txt", b"valid contents for test")
    service.simulate_failure(backup["id"], "A", "Corrupt content")
    assert service.read_valid_replica(backup["id"]) == b"valid contents for test"
    checks = service.scan_all()
    assert any(r["replica"] == "A" and r["result"] == "CORRUPTED" for r in checks)
    assert any(r["replica"] == "B" and r["result"] == "OK" for r in checks)


def test_repair_restores_deleted_and_corrupted_replicas(tmp_path):
    service, db, _ = make_service(tmp_path)
    payload = b"x" * 100
    one = service.create_backup("a.bin", payload)
    two = service.create_backup("b.bin", payload + b"y")
    service.simulate_failure(one["id"], "A", "Delete replica")
    service.simulate_failure(two["id"], "B", "Corrupt content")
    service.scan_all()
    assert db.get_backup(one["id"])["status"] == "degraded"
    repairs, lost = service.repair_all()
    assert len(repairs) == 2 and not lost
    assert all(r["result"] == "OK" for r in service.scan_all())
    assert db.get_backup(one["id"])["status"] == "healthy"


def test_repair_fails_when_both_replicas_lost(tmp_path):
    service, db, _ = make_service(tmp_path)
    b = service.create_backup("gone.txt", b"data data data")
    service.simulate_failure(b["id"], "A", "Delete replica")
    service.simulate_failure(b["id"], "B", "Delete replica")
    repairs, lost = service.repair_all()
    assert not repairs and len(lost) == 1


def test_preview_read_does_not_write_audit(tmp_path):
    service, db, _ = make_service(tmp_path)
    b = service.create_backup("quiet.txt", b"quiet data")
    before = len(db.list_audit())
    service.read_valid_replica(b["id"], audit=False)
    assert len(db.list_audit()) == before
