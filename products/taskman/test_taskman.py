import unittest
import subprocess
import json
import os

class TestTaskMan(unittest.TestCase):
    def setUp(self):
        self.db = "test_tasks.json"
        if os.path.exists(self.db):
            os.remove(self.db)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def run_cli(self, args):
        env = os.environ.copy()
        env["TASKMAN_DB"] = self.db
        return subprocess.run(["python", "taskman.py"] + args, capture_output=True, text=True, env=env)

    def test_01_add(self):
        self.run_cli(["add", "buy milk"])
        with open(self.db, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["task"], "buy milk")

    def test_02_list(self):
        self.run_cli(["add", "task1"])
        res = self.run_cli(["list"])
        self.assertIn("task1", res.stdout)

    def test_03_done(self):
        self.run_cli(["add", "task1"])
        self.run_cli(["done", "1"])
        with open(self.db, "r") as f:
            data = json.load(f)
        self.assertTrue(data[0]["done"])

    def test_04_rm(self):
        self.run_cli(["add", "task1"])
        self.run_cli(["rm", "1"])
        with open(self.db, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 0)

    def test_05_stats(self):
        self.run_cli(["add", "t1"])
        self.run_cli(["add", "t2"])
        self.run_cli(["done", "1"])
        res = self.run_cli(["stats"])
        self.assertIn("Total", res.stdout)
        self.assertIn("2", res.stdout)
        self.assertIn("Done", res.stdout)
        self.assertIn("1", res.stdout)

    def test_06_add_multiple(self):
        self.run_cli(["add", "t1"])
        self.run_cli(["add", "t2"])
        with open(self.db, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 2)

    def test_07_rm_reindex(self):
        self.run_cli(["add", "t1"])
        self.run_cli(["add", "t2"])
        self.run_cli(["rm", "1"])
        with open(self.db, "r") as f:
            data = json.load(f)
        self.assertEqual(data[0]["task"], "t2")
        self.assertEqual(data[0]["id"], 1)

    def test_08_done_nonexistent(self):
        self.run_cli(["done", "99"])
        
    def test_09_rm_nonexistent(self):
        self.run_cli(["rm", "99"])

    def test_10_list_empty(self):
        res = self.run_cli(["list"])
        self.assertEqual(res.returncode, 0)

if __name__ == "__main__":
    unittest.main()
