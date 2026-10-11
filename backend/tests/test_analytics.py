import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import analytics, main, storage


class FakePipeline:
    def __init__(self, parent):
        self.parent = parent
        self.commands = []

    def hincrby(self, key, field, amount):
        self.commands.append(("hincrby", key, field, amount))
        return self

    def hgetall(self, key):
        self.commands.append(("hgetall", key))
        return self

    def execute(self):
        results = []
        for command in self.commands:
            if command[0] == "hincrby":
                _, key, field, amount = command
                values = self.parent.hashes.setdefault(key, {})
                values[field] = values.get(field, 0) + amount
                results.append(values[field])
            else:
                results.append(dict(self.parent.hashes.get(command[1], {})))
        return results


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    def close(self):
        pass


class AnalyticsTest(unittest.TestCase):
    def test_private_statistics_require_the_owner_key(self):
        payload = {"timezone": "UTC", "total": {"visits": 2}, "days": []}
        with patch.dict(os.environ, {"ADMIN_TOKEN": "a" * 64}), patch.object(main, "snapshot", return_value=payload) as stats:
            with TestClient(main.app) as client:
                self.assertEqual(client.get("/api/admin/stats").status_code, 401)
                self.assertEqual(client.get("/api/admin/stats", headers={"Authorization": "Bearer wrong"}).status_code, 401)
                stats.assert_not_called()
                result = client.get("/api/admin/stats?days=7", headers={"Authorization": "Bearer " + "a" * 64})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), payload)
                self.assertEqual(result.headers["cache-control"], "private, no-store")
                stats.assert_called_once_with(7)

    def test_unconfigured_key_disables_private_statistics(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": ""}), patch.object(main, "snapshot") as stats:
            with TestClient(main.app) as client:
                result = client.get("/api/admin/stats", headers={"Authorization": "Bearer " + "a" * 64})
                self.assertEqual(result.status_code, 503)
                stats.assert_not_called()

    def test_visit_and_upload_count_without_collecting_file_names(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, "DATA_DIR", Path(directory)), \
             patch.object(main, "record_metric") as record:
            with TestClient(main.app) as client:
                self.assertEqual(client.post("/api/metrics/visit").status_code, 204)
                created = client.post("/api/uploads", json={"filename": "private.pptx", "size": 100})
                self.assertEqual(created.status_code, 200)
            self.assertEqual([call.args for call in record.call_args_list], [("visits",), ("uploads",)])

    def test_terminal_job_is_counted_once(self):
        connection = FakeRedis()
        analytics.record_job_outcome(connection, "job-1", "done")
        analytics.record_job_outcome(connection, "job-1", "done")
        analytics.record_job_outcome(connection, "job-2", "failed")
        self.assertEqual(connection.hashes[f"{analytics.PREFIX}:total"], {"completed": 1, "failed": 1})

    def test_daily_list_and_all_time_totals(self):
        connection = FakeRedis()
        with patch.object(analytics.redis.Redis, "from_url", return_value=connection):
            analytics.record_metric("visits")
            analytics.record_metric("uploads")
            report = analytics.snapshot(2)
        self.assertEqual(report["timezone"], "UTC")
        self.assertEqual(report["total"]["visits"], 1)
        self.assertEqual(report["total"]["uploads"], 1)
        self.assertEqual(report["days"][0]["date"], analytics._day())
        self.assertEqual(report["days"][0]["visits"], 1)
        self.assertEqual(report["days"][1]["visits"], 0)


if __name__ == "__main__":
    unittest.main()
