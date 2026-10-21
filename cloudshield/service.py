import time
from .utils import sha256_bytes, safe_filename
from .db import utcnow

class BackupService:
    def __init__(self, db, storage, settings):
        self.db = db
        self.storage = storage
        self.settings = settings

    @staticmethod
    def _key(filename, version, replica):
        # Keep original name in metadata, not in the storage path.
        return f"objects/{sha256_bytes(filename.encode())[:16]}/v{version}/{replica.lower()}.bin"

    def create_backup(self, filename, data: bytes, note=""):
        filename = safe_filename(filename)
        if not data:
            raise ValueError("Empty files are not accepted.")
        if len(data) > 200 * 1024 * 1024:
            raise ValueError("File exceeds the 200 MB application limit.")
        version = self.db.next_version(filename)
        sha = sha256_bytes(data)
        key_a = self._key(filename, version, "A")
        key_b = self._key(filename, version, "B")
        a_ok = b_ok = False
        errors = []
        try:
            self.storage.put("A", key_a, data)
            a_ok = True
        except Exception as exc:
            errors.append(f"Replica A: {exc}")
        try:
            self.storage.put("B", key_b, data)
            b_ok = True
        except Exception as exc:
            errors.append(f"Replica B: {exc}")
        status = "healthy" if a_ok and b_ok else ("degraded" if a_ok or b_ok else "unavailable")
        record = self.db.create_backup({
            "filename": filename, "version": version, "created_at": utcnow(),
            "size_bytes": len(data), "sha256": sha, "note": note,
            "replica_a_key": key_a, "replica_b_key": key_b,
            "replica_a_ok": a_ok, "replica_b_ok": b_ok, "status": status
        })
        self.db.add_audit("BACKUP_CREATED", filename,
                          f"version={version}; status={status}; bytes={len(data)}" +
                          (("; errors=" + " | ".join(errors)) if errors else ""))
        if not a_ok and not b_ok:
            raise RuntimeError("Both replica writes failed. " + " | ".join(errors))
        return {**record, "replica_a_ok": a_ok, "replica_b_ok": b_ok}

    def verify_replica(self, backup, replica):
        key = backup["replica_a_key"] if replica == "A" else backup["replica_b_key"]
        try:
            data = self.storage.get(replica, key)
            actual = sha256_bytes(data)
            expected = backup["sha256"]
            return {"backup_id": backup["id"], "filename": backup["filename"],
                    "version": backup["version"], "replica": replica,
                    "result": "OK" if actual == expected else "CORRUPTED",
                    "expected_hash": expected[:16], "actual_hash": actual[:16]}
        except FileNotFoundError:
            return {"backup_id": backup["id"], "filename": backup["filename"],
                    "version": backup["version"], "replica": replica,
                    "result": "MISSING", "expected_hash": backup["sha256"][:16], "actual_hash": "—"}
        except Exception as exc:
            return {"backup_id": backup["id"], "filename": backup["filename"],
                    "version": backup["version"], "replica": replica,
                    "result": "ERROR", "expected_hash": backup["sha256"][:16], "actual_hash": str(exc)[:80]}

    def scan_all(self):
        results = []
        for backup in reversed(self.db.list_backups(limit=10000)):
            checks = [self.verify_replica(backup, "A"), self.verify_replica(backup, "B")]
            results.extend(checks)
            ok_a = checks[0]["result"] == "OK"
            ok_b = checks[1]["result"] == "OK"
            self.db.update_replica(backup["id"], "A", ok_a)
            self.db.update_replica(backup["id"], "B", ok_b)
            if not (ok_a and ok_b):
                self.db.add_audit("INTEGRITY_ISSUE", backup["filename"],
                                  f"version={backup['version']}; A={checks[0]['result']}; B={checks[1]['result']}")
        self.db.add_audit("INTEGRITY_SCAN", "", f"Checked {len(results)} replica objects")
        return results

    def read_valid_replica(self, backup_id):
        backup = self.db.get_backup(backup_id)
        if not backup:
            raise ValueError("Backup version not found.")
        for replica, key in [("A", backup["replica_a_key"]), ("B", backup["replica_b_key"])]:
            try:
                data = self.storage.get(replica, key)
                if sha256_bytes(data) == backup["sha256"]:
                    self.db.add_audit("REPLICA_READ", backup["filename"], f"Recovered from replica {replica}, version={backup['version']}")
                    return data
            except Exception:
                continue
        raise RuntimeError("No valid replica is available for this backup version.")

    def repair_backup(self, backup_id):
        """Rewrite any missing/corrupted replica from a verified-good one and re-verify it."""
        backup = self.db.get_backup(backup_id)
        if not backup:
            raise ValueError("Backup version not found.")
        started = time.perf_counter()
        checks = {r: self.verify_replica(backup, r) for r in ("A", "B")}
        good = [r for r, c in checks.items() if c["result"] == "OK"]
        bad = [r for r in checks if r not in good]
        if not good:
            self.db.add_audit("REPAIR_FAILED", backup["filename"], f"version={backup['version']}; no valid replica")
            raise RuntimeError("No valid replica is available to repair from.")
        data = self.storage.get(good[0], backup[f"replica_{good[0].lower()}_key"])
        repaired = []
        for r in bad:
            self.storage.put(r, backup[f"replica_{r.lower()}_key"], data)
            if self.verify_replica(backup, r)["result"] == "OK":
                repaired.append(r)
        for r in ("A", "B"):
            self.db.update_replica(backup_id, r, r in good or r in repaired)
        ms = round((time.perf_counter() - started) * 1000, 1)
        if repaired:
            self.db.add_audit("REPLICA_REPAIRED", backup["filename"],
                              f"version={backup['version']}; source={good[0]}; repaired={','.join(repaired)}; time_ms={ms}")
        return {"backup_id": backup_id, "filename": backup["filename"], "version": backup["version"],
                "source": good[0], "repaired": repaired, "failed": [r for r in bad if r not in repaired], "ms": ms}

    def repair_all(self):
        """Repair every degraded version that still has one valid replica. Returns (repairs, unrecoverable)."""
        repairs, lost = [], []
        for backup in reversed(self.db.list_backups(limit=10000)):
            try:
                result = self.repair_backup(backup["id"])
                if result["repaired"]:
                    repairs.append(result)
            except RuntimeError:
                lost.append(backup)
        return repairs, lost

    def simulate_failure(self, backup_id, replica, action):
        if not self.settings.allow_failure_simulation:
            raise PermissionError("Failure simulation is disabled.")
        backup = self.db.get_backup(backup_id)
        if not backup:
            raise ValueError("Backup version not found.")
        key = backup["replica_a_key"] if replica == "A" else backup["replica_b_key"]
        if action == "Delete replica":
            self.storage.delete(replica, key)
        elif action == "Corrupt content":
            try:
                original = self.storage.get(replica, key)
            except Exception as exc:
                raise RuntimeError("Cannot corrupt a replica that cannot be read.") from exc
            changed = (b"CORRUPTED_BY_CLOUDSHIELD\n" + original[32:]) if len(original) > 32 else b"CORRUPTED_BY_CLOUDSHIELD"
            self.storage.put(replica, key, changed)
        else:
            raise ValueError("Unsupported failure simulation action.")
        self.db.add_audit("FAILURE_SIMULATED", backup["filename"],
                          f"version={backup['version']}; replica={replica}; action={action}")

    def health_summary(self):
        return self.storage.health()
