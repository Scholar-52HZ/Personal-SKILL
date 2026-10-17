"""Local-only regression fixtures. Retain artifacts; never delete existing paths.

Run with Python -B. HANDOFF_TEST_ROOT optionally selects the fixture parent.
All pushes target fixture-local bare repositories, never external networks.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "inspect_handoff.py"


def tree_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = os.environ.get("HANDOFF_TEST_ROOT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="ht-", dir=parent)).resolve()
        print("\nRetained fixtures: " + str(cls.root), flush=True)

    def setUp(self):
        # Git for Windows may add long quarantine object paths during push.
        self.case = self.root / hashlib.sha256(self._testMethodName.encode()).hexdigest()[:8]
        self.case.mkdir()
        (self.case / "test-name.txt").write_text(self._testMethodName, encoding="utf-8")
        self.repo = self.case / "device-a"
        self.repo.mkdir()
        self.env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            self.env.pop(key, None)
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file", PYTHONUTF8="1")
        self.git("init", "--initial-branch=main")
        self.configure(self.repo)
        self.inspection_count = 0

    def git(self, *args, repo=None, ok=True):
        cwd = (repo or self.repo).resolve()
        if self.root not in cwd.parents:
            raise AssertionError("Git cwd outside fixture")
        result = subprocess.run(["git", "-C", str(cwd), *args], env=self.env,
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        with (self.case / "operations.log").open("a", encoding="utf-8") as out:
            out.write(json.dumps({"cwd": str(cwd), "args": args, "exit": result.returncode,
                                  "stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False) + "\n")
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip() if ok else result

    def configure(self, repo):
        for key, value in (("user.name", "Isolated Handoff Test"),
                           ("user.email", "handoff-test@example.invalid"),
                           ("core.autocrlf", "false"), ("core.longpaths", "true"), ("commit.gpgsign", "false"),
                           ("core.hooksPath", str(self.case / "no-hooks"))):
            self.git("config", key, value, repo=repo)

    def put(self, name, content, repo=None):
        path = (repo or self.repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def baseline(self, remote=False):
        self.put("app.txt", "baseline\n")
        self.put("user.txt", "user baseline\n")
        self.put(".gitignore", ".ai/\n")
        self.git("add", "--", "app.txt", "user.txt", ".gitignore")
        self.git("commit", "-m", "chore: baseline")
        self.git("switch", "-c", "dev")
        if remote:
            self.bare = self.case / "origin.git"
            self.git("init", "--bare", "--initial-branch=main", str(self.bare))
            self.git("config", "core.longpaths", "true", repo=self.bare)
            self.git("remote", "add", "origin", str(self.bare))
            self.git("push", "-u", "origin", "dev", "main")

    def commit(self, name, content, subject, repo=None):
        self.put(name, content, repo)
        self.git("add", "--", name, repo=repo)
        self.git("commit", "-m", subject, repo=repo)
        return self.git("rev-parse", "HEAD", repo=repo)

    def second_device(self):
        other = self.case / "device-b"
        self.git("clone", "--no-hardlinks", str(self.bare), str(other))
        self.configure(other)
        self.git("switch", "--track", "origin/dev", repo=other)
        return other

    def inspect(self, *args, expect_exit=0):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo),
                                 "--json", *args], env=self.env, capture_output=True,
                                text=True, encoding="utf-8", timeout=90)
        self.assertEqual(result.returncode, expect_exit, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.inspection_count += 1
        (self.case / ("inspection-%d.json" % self.inspection_count)).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def test_unborn_repository(self):
        self.put("draft.txt", "uncommitted")
        before = tree_hashes(self.repo)
        report = self.inspect()
        self.assertIsNone(report["head"])
        self.assertEqual(report["current_branch"], "main")
        self.assertIsNone(report["branches"]["dev"]["commit"])
        self.assertEqual(report["handoff"]["state"], "blocked")
        self.assertEqual(before, tree_hashes(self.repo))

    def test_live_observation_and_cached_only(self):
        self.baseline(remote=True)
        cached = self.inspect()
        self.assertEqual(cached["branches"]["dev"]["cached_relation"]["state"], "equal")
        self.assertEqual(cached["handoff"]["state"], "unverified")
        before, bare_before = tree_hashes(self.repo), tree_hashes(self.bare)
        actual = self.inspect("--check-remote")
        self.assertEqual(actual["handoff"]["state"], "git_history_verified")
        self.assertTrue(actual["stable_is_ancestor_of_dev"])
        self.assertEqual(before, tree_hashes(self.repo))
        self.assertEqual(bare_before, tree_hashes(self.bare))

    def test_staged_user_rename_binary_and_ignored_preserved(self):
        self.baseline(remote=True)
        self.put("user.txt", "user staged content\n")
        self.git("add", "--", "user.txt")
        self.put("user.txt", "user unstaged layer\n")
        self.git("mv", "app.txt", "有 空格的文件.txt")
        (self.repo / "draft.bin").write_bytes(bytes([0, 1, 128, 255]))
        self.put(".ai/unique-design.txt", "unique ignored artifact")
        before = tree_hashes(self.repo)
        report = self.inspect("--check-remote")
        statuses = {item["path"]: item for item in report["changes"]}
        self.assertEqual(statuses["user.txt"]["status"], "MM")
        self.assertEqual(statuses["有 空格的文件.txt"]["original_path"], "app.txt")
        self.assertEqual(statuses["draft.bin"]["status"], "??")
        self.assertNotIn(".ai/unique-design.txt", statuses)
        self.assertIn("ignored_assets_and_environment_not_audited", report["limits"])
        self.assertEqual(report["handoff"]["state"], "blocked")
        self.assertEqual(before, tree_hashes(self.repo))

    def test_remote_changed_without_fetch(self):
        self.baseline(remote=True)
        other = self.second_device()
        remote_cp = self.commit("remote-only.txt", "new work", "checkpoint(TASK-002): CP-01 remote work", other)
        self.git("push", "origin", "dev", repo=other)
        before = tree_hashes(self.repo)
        report = self.inspect("--check-remote", "--expect", remote_cp)
        dev = report["branches"]["dev"]
        self.assertEqual(dev["cached_relation"]["state"], "equal")
        self.assertEqual(dev["remote"]["relation"]["state"], "remote_history_not_local")
        self.assertFalse(report["expected_commit"]["exists"])
        self.assertEqual(report["handoff"]["state"], "blocked")
        self.assertEqual(before, tree_hashes(self.repo))
        self.assertNotEqual(self.git("cat-file", "-e", remote_cp + "^{commit}", ok=False).returncode, 0)

    def test_diverged_devices(self):
        self.baseline(remote=True)
        other = self.second_device()
        self.commit("remote-only.txt", "remote", "checkpoint(TASK-002): CP-01 remote", other)
        self.git("push", "origin", "dev", repo=other)
        self.commit("local-only.txt", "local", "checkpoint(TASK-001): CP-01 local")
        self.git("fetch", "origin")  # Fixture preparation; inspector must never fetch.
        before = tree_hashes(self.repo)
        report = self.inspect("--check-remote")
        relation = report["branches"]["dev"]["remote"]["relation"]
        self.assertEqual(relation, {"state": "diverged", "ahead": 1, "behind": 1})
        self.assertEqual(report["handoff"]["state"], "blocked")
        self.assertEqual(before, tree_hashes(self.repo))

    def test_interrupted_delivery_resume_without_duplicate(self):
        self.baseline(remote=True)
        source = self.commit("app.txt", "complete feature\n", "checkpoint(TASK-001): CP-01 complete feature")
        self.git("switch", "main")
        self.git("merge", "--squash", source)
        staged = self.inspect()
        self.assertEqual(staged["handoff"]["state"], "blocked")
        self.assertEqual((self.repo / "app.txt").read_text(), "complete feature\n")
        self.git("commit", "-m", "feat: deliver feature", "-m", "Development-source: " + source)
        delivered = self.git("rev-parse", "main")
        # Restart from actual evidence: existing main commit means do not squash again.
        self.assertIn("Development-source: " + source, self.git("show", "-s", "--format=%B", "main"))
        self.git("switch", "dev")
        if self.git("merge-base", "--is-ancestor", "main", "dev", ok=False).returncode:
            self.git("merge", "--no-ff", "main", "-m", "merge: resume delivery backflow")
        count = self.git("rev-list", "--count", "dev")
        # Second restart: relation proves backflow is already done.
        self.assertEqual(self.git("merge-base", "--is-ancestor", "main", "dev", ok=False).returncode, 0)
        self.assertEqual(self.git("rev-list", "--count", "dev"), count)
        self.assertEqual(self.git("rev-parse", "main"), delivered)
        self.assertEqual(self.git("rev-parse", "dev^{tree}"), self.git("rev-parse", "main^{tree}"))
        self.assertTrue(self.inspect()["stable_is_ancestor_of_dev"])

    def test_main_backflow_conflict_preserved(self):
        self.baseline()
        source = self.commit("app.txt", "accepted value\n", "checkpoint(TASK-001): CP-01 accepted")
        self.git("switch", "main")
        self.git("merge", "--squash", source)
        self.git("commit", "-m", "feat: accepted delivery", "-m", "Development-source: " + source)
        self.git("switch", "dev")
        self.commit("app.txt", "next development value\n", "wip(TASK-002): continued work")
        merge = self.git("merge", "main", "-m", "merge: backflow", ok=False)
        self.assertNotEqual(merge.returncode, 0)
        self.assertTrue((self.repo / ".git/MERGE_HEAD").exists())
        before = tree_hashes(self.repo)
        report = self.inspect()
        self.assertIn("merge", report["operations"])
        self.assertTrue(any(c["status"] == "UU" for c in report["changes"]))
        self.assertEqual(report["handoff"]["state"], "blocked")
        self.assertEqual(before, tree_hashes(self.repo))

    def test_partial_push_separate_branches(self):
        self.baseline(remote=True)
        source = self.commit("app.txt", "complete feature\n", "checkpoint(TASK-001): CP-01 accepted")
        self.git("switch", "main")
        self.git("merge", "--squash", source)
        self.git("commit", "-m", "feat: delivery", "-m", "Development-source: " + source)
        self.git("switch", "dev")
        self.git("merge", "--no-ff", "main", "-m", "merge: backflow")
        # Local-only fixture remote rejects main, modeling one branch failing to push.
        hook = self.bare / "hooks/pre-receive"
        hook.write_text('#!/bin/sh\nwhile read old new ref; do\n  if [ "$ref" = "refs/heads/main" ]; then exit 1; fi\ndone\nexit 0\n')
        hook.chmod(0o755)
        self.git("push", "origin", "dev")
        self.assertNotEqual(self.git("push", "origin", "main", ok=False).returncode, 0)
        before = tree_hashes(self.repo)
        report = self.inspect("--check-remote")
        self.assertEqual(report["branches"]["dev"]["remote"]["relation"]["state"], "equal")
        self.assertEqual(report["branches"]["stable"]["remote"]["relation"]["state"], "ahead")
        self.assertEqual(before, tree_hashes(self.repo))
        # Restore fixture remote acceptance, then finish only the missing push.
        hook.write_text("#!/bin/sh\nexit 0\n")
        before_main = self.git("rev-parse", "main")
        self.git("push", "origin", "main")
        completed = self.inspect("--check-remote")
        self.assertEqual(completed["branches"]["stable"]["remote"]["relation"]["state"], "equal")
        self.assertEqual(self.git("rev-parse", "main"), before_main)

    def test_offline_remote_not_reported_equal(self):
        self.baseline(remote=True)
        self.git("remote", "set-url", "origin", str(self.case / "missing-remote.git"))
        before = tree_hashes(self.repo)
        report = self.inspect("--check-remote")
        self.assertEqual(report["branches"]["dev"]["cached_relation"]["state"], "equal")
        self.assertEqual(report["branches"]["dev"]["remote"]["observation"], "unavailable")
        self.assertEqual(report["handoff"]["state"], "unverified")
        self.assertEqual(before, tree_hashes(self.repo))

    def test_checkpoint_filter_and_expected_history(self):
        self.baseline(remote=True)
        cp = self.commit("app.txt", "phase 1", "checkpoint(TASK-001): CP-01 first")
        self.commit("app.txt", "phase 2", "checkpoint(TASK-0010): CP-01 different task")
        self.commit("app.txt", "draft", "wip(TASK-001): unfinished")
        report = self.inspect("--task", "TASK-001", "--expect", cp)
        self.assertEqual([c["commit"] for c in report["recent_checkpoints"]], [cp])
        self.assertTrue(report["expected_commit"]["in_dev"])
        self.assertEqual(self.inspect("--expect", "bad", expect_exit=2).keys(), {"error"})

    def test_custom_remote_branch_mapping(self):
        self.baseline(remote=True)
        self.git("push", "origin", "dev:refs/heads/development")
        self.git("config", "branch.dev.merge", "refs/heads/development")
        report = self.inspect("--check-remote")
        self.assertEqual(report["branches"]["dev"]["remote"]["mapping"]["ref"], "refs/heads/development")
        self.assertEqual(report["branches"]["dev"]["remote"]["relation"]["state"], "equal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
