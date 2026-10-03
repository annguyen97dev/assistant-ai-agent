"""Check the one-shot job's Docker and scheduled-store contracts."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as job


class MainJobTests(unittest.TestCase):
    def test_api_key_only_can_create_store_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict("os.environ", {"API_KEY": "test-key"}, clear=True), \
             patch.object(job, "ROOT", Path(directory)), \
             patch.object(job, "resolve_store_name", return_value=None), \
             patch.object(job, "scrape", return_value={"total_public_articles_seen": 415}), \
             patch.object(job, "load_corpus", return_value=[{"id": "1"}]), \
             patch.object(job, "upload", return_value={"added": 1, "updated": 0, "skipped": 0}) as upload:
            self.assertEqual(job.main(), 0)
            upload.assert_called_once_with([{"id": "1"}], None)
            result = json.loads((Path(directory) / "logs" / "last-run.json").read_text())
            self.assertEqual(result["added"], 1)

    def test_scheduled_job_requires_existing_store(self):
        with patch.dict("os.environ", {"REQUIRE_EXISTING_STORE": "1"}, clear=True), \
             patch.object(job, "resolve_store_name", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "FILE_SEARCH_STORE_NAME"):
                job.main()


if __name__ == "__main__":
    unittest.main()
