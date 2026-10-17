#!/usr/bin/env python3
"""Read Git handoff facts without fetching, staging, committing, or fixing them.

Python 3.9+, standard library only. Exit 0 means inspection completed, not that
handoff is ready. Exit 2 means invalid input or an inspection failure.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class InspectionError(Exception):
    pass


class Git:
    def __init__(self, repo):
        self.repo = str(Path(repo).resolve())
        self.env = os.environ.copy()
        for name in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(name, None)
        self.env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")

    def run(self, *args, optional=False):
        try:
            result = subprocess.run(
                ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                 "-c", "core.quotepath=false", "-C", self.repo, *args],
                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding="utf-8", errors="replace", timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            if optional:
                return None
            raise InspectionError("Git unavailable or inspection timed out.") from None
        if result.returncode:
            if optional:
                return None
            # Remote/config errors can contain credential-bearing URLs. Do not echo stderr.
            raise InspectionError("Git inspection failed; inspect repository state manually.")
        return result.stdout

    def commit(self, ref):
        result = self.run("rev-parse", "--verify", ref + "^{commit}", optional=True)
        return result.strip() if result else None

    def relation(self, left, right):
        if not left or not right:
            return None
        result = self.run("rev-list", "--left-right", "--count", left + "..." + right, optional=True)
        if result is None:
            return None
        ahead, behind = map(int, result.split())
        state = "equal" if ahead == behind == 0 else (
            "diverged" if ahead and behind else "ahead" if ahead else "behind")
        return {"state": state, "ahead": ahead, "behind": behind}

    def contains(self, ancestor, descendant):
        if not ancestor or not descendant:
            return None
        # rev-list exposes failure separately from a valid negative relation.
        relation = self.relation(ancestor, descendant)
        return None if relation is None else relation["ahead"] == 0


def worktree_status(raw):
    """Parse porcelain v1 -z, including rename's extra original-name field."""
    entries = raw.split("\0")
    result, i = [], 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        xy, path = entry[:2], entry[3:]
        item = {"status": xy, "path": path}
        if "R" in xy or "C" in xy:
            if i >= len(entries) or not entries[i]:
                raise InspectionError("Incomplete Git status record.")
            item["original_path"] = entries[i]
            i += 1
        result.append(item)
    return result


def remote_mapping(git, branch, remote_override, remote_names):
    remote = remote_override
    merge = git.run("config", "--get", "branch." + branch + ".merge", optional=True)
    if remote is None:
        configured = git.run("config", "--get", "branch." + branch + ".remote", optional=True)
        remote = configured.strip() if configured else None
    if remote not in remote_names:
        return None
    configured_remote = git.run("config", "--get", "branch." + branch + ".remote", optional=True)
    same_remote = configured_remote and configured_remote.strip() == remote
    ref = merge.strip() if merge and same_remote else "refs/heads/" + branch
    if not ref.startswith("refs/heads/"):
        return None
    return {"remote": remote, "ref": ref}


def branch_info(git, name, remote_override, remote_names, check_remote):
    ref = "refs/heads/" + name
    oid = git.commit(ref)
    upstream = git.run("for-each-ref", "--format=%(upstream)", ref).strip() or None
    upstream_oid = git.commit(upstream) if upstream else None
    mapping = remote_mapping(git, name, remote_override, remote_names)
    remote = {"observation": "not_checked", "mapping": mapping, "commit": None, "relation": None}
    if check_remote:
        if mapping is None:
            remote["observation"] = "unconfigured"
        else:
            observed = git.run("ls-remote", "--heads", "--", mapping["remote"], mapping["ref"], optional=True)
            if observed is None:
                remote["observation"] = "unavailable"
            else:
                heads = [line.split() for line in observed.splitlines()]
                matches = [parts[0] for parts in heads if len(parts) == 2 and parts[1] == mapping["ref"]]
                if not matches:
                    remote["observation"] = "branch_missing"
                else:
                    remote_oid = matches[0]
                    remote.update(observation="observed", commit=remote_oid)
                    if oid == remote_oid:
                        remote["relation"] = {"state": "equal", "ahead": 0, "behind": 0}
                    elif git.commit(remote_oid):
                        remote["relation"] = git.relation(oid, remote_oid)
                    else:
                        remote["relation"] = {"state": "remote_history_not_local", "ahead": None, "behind": None}
    return {
        "name": name, "commit": oid, "cached_upstream": upstream,
        "cached_upstream_commit": upstream_oid,
        "cached_relation": git.relation(oid, upstream_oid), "remote": remote,
    }


def inspect(args):
    git = Git(args.repo)
    top = git.run("rev-parse", "--show-toplevel").strip()
    # Use repository root even when invoked from a subdirectory.
    git.repo = top
    for name in (args.dev, args.stable):
        if git.run("check-ref-format", "refs/heads/" + name, optional=True) is None:
            raise InspectionError("Invalid branch name.")
    if args.dev == args.stable:
        raise InspectionError("Development and stable branches must differ.")
    remotes = git.run("remote").splitlines()
    if args.remote is not None and args.remote not in remotes:
        raise InspectionError("Requested remote name is not configured.")
    current = git.run("symbolic-ref", "--quiet", "--short", "HEAD", optional=True)
    current = current.strip() if current else None
    head = git.commit("HEAD")
    changes = worktree_status(git.run("status", "--porcelain=v1", "-z", "--untracked-files=all"))
    operations = []
    for marker, label in (
        ("MERGE_HEAD", "merge"), ("rebase-merge", "rebase"), ("rebase-apply", "rebase_or_am"),
        ("CHERRY_PICK_HEAD", "cherry_pick"), ("REVERT_HEAD", "revert"),
        ("BISECT_LOG", "bisect"), ("sequencer", "sequencer"),
    ):
        marker_path = git.run("rev-parse", "--git-path", marker).strip()
        if (Path(top) / marker_path).exists():
            operations.append(label)
    branches = {
        "dev": branch_info(git, args.dev, args.remote, remotes, args.check_remote),
        "stable": branch_info(git, args.stable, args.remote, remotes, args.check_remote),
    }
    dev_oid, stable_oid = branches["dev"]["commit"], branches["stable"]["commit"]
    checkpoints = []
    if dev_oid:
        history = git.run("log", "--max-count=100", "--format=%H%x00%s", dev_oid)
        for line in history.splitlines():
            oid, _, subject = line.partition("\0")
            match = re.match(r"^checkpoint\(([^)]+)\):\s*(.*)$", subject)
            if match and (args.task is None or args.task == match[1]):
                checkpoints.append({"commit": oid, "task": match[1], "subject": subject})
                if len(checkpoints) == 5:
                    break
    expected = None
    if args.expect:
        if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", args.expect):
            raise InspectionError("--expect requires a full 40- or 64-character commit hash.")
        expected_oid = git.commit(args.expect)
        expected = {"requested": args.expect, "exists": bool(expected_oid),
                    "in_dev": git.contains(expected_oid, dev_oid)}
    reasons = []
    if not dev_oid:
        reasons.append("development_branch_missing_or_unborn")
    if changes:
        reasons.append("uncommitted_or_untracked_changes")
    if operations:
        reasons.append("git_operation_in_progress")
    if expected and not expected["in_dev"]:
        reasons.append("expected_commit_missing_or_not_in_dev")
    observation = branches["dev"]["remote"]
    observed_relation = observation["relation"] or {}
    if reasons:
        transfer = "blocked"
    elif observation["observation"] != "observed":
        transfer = "unverified"
        reasons.append("remote_not_verified")
    elif observed_relation.get("state") != "equal":
        transfer = "blocked"
        reasons.append("development_history_not_confirmed_equal")
    else:
        transfer = "git_history_verified"
    return {
        "schema_version": 1, "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo": top, "current_branch": current, "head": head,
        "shallow": git.run("rev-parse", "--is-shallow-repository").strip() == "true",
        "changes": changes, "operations": operations, "branches": branches,
        "stable_is_ancestor_of_dev": git.contains(stable_oid, dev_oid),
        "recent_checkpoints": checkpoints, "checkpoint_scan_limit": 100,
        "expected_commit": expected,
        "handoff": {"state": transfer, "reasons": reasons},
        "limits": ["ignored_assets_and_environment_not_audited",
                   "remote_alignment_cannot_prove_other_devices_have_no_unpushed_work",
                   "cached_upstream_may_be_stale", "checkpoint_scan_is_not_a_full_ledger"],
    }


def text_report(report):
    observations = {"not_checked": "未查询", "unconfigured": "未配置对应远程",
                    "unavailable": "查询失败或超时", "branch_missing": "远程分支不存在",
                    "observed": "已读取实际指向"}
    relations = {"equal": "一致", "ahead": "本地领先", "behind": "本地落后",
                 "diverged": "双方都有新提交，需要审查并集成",
                 "remote_history_not_local": "远程新历史尚未取得，无法计算差异"}
    reasons = {"development_branch_missing_or_unborn": "开发分支不存在或尚无首次提交",
               "uncommitted_or_untracked_changes": "存在未提交或未跟踪内容",
               "git_operation_in_progress": "有尚未结束的 Git 操作",
               "expected_commit_missing_or_not_in_dev": "预期提交缺失或不属于当前开发历史",
               "remote_not_verified": "实际远程尚未核实",
               "development_history_not_confirmed_equal": "本地与远程开发历史尚未确认一致"}
    print("仓库：" + report["repo"])
    print("当前分支：" + (report["current_branch"] or "detached HEAD"))
    print("工作区：%d 项未提交/未跟踪变化" % len(report["changes"]))
    change_names = {" ": "无", "M": "修改", "A": "新增", "D": "删除",
                    "R": "改名", "C": "复制", "U": "冲突", "T": "类型变化"}
    for change in report["changes"][:20]:
        xy = change["status"]
        label = "未跟踪" if xy == "??" else "暂存：%s；工作区：%s" % (
            change_names.get(xy[0], xy[0]), change_names.get(xy[1], xy[1]))
        path = json.dumps(change["path"], ensure_ascii=False)
        if "original_path" in change:
            path = json.dumps(change["original_path"], ensure_ascii=False) + " → " + path
        print("  " + path + "（" + label + "）")
    if len(report["changes"]) > 20:
        print("  只显示前 20 项；完整路径见 --json 输出。")
    if report["operations"]:
        print("进行中的 Git 操作：" + ", ".join(report["operations"]))
    for key, label in (("dev", "开发分支"), ("stable", "稳定分支")):
        branch = report["branches"][key]
        print("%s：%s [%s]" % (label, branch["name"], (branch["commit"] or "不存在/尚无提交")[:40]))
        cached = branch["cached_relation"]
        if cached:
            print("  缓存追踪记录（可能过期）：领先 %d，落后 %d" % (cached["ahead"], cached["behind"]))
        remote = branch["remote"]
        print("  实际远程：" + observations[remote["observation"]])
        if remote["relation"]:
            rel = remote["relation"]
            print("  比较结果：" + relations[rel["state"]])
            if rel["ahead"] is not None:
                print("  本地领先 %d 个提交，落后 %d 个提交" % (rel["ahead"], rel["behind"]))
    ancestor = report["stable_is_ancestor_of_dev"]
    print("稳定分支是否已包含在开发历史：" + ("未知" if ancestor is None else "是" if ancestor else "否"))
    print("最近快照（只扫描最近 100 个提交，最多显示 5 个）：")
    for cp in report["recent_checkpoints"]:
        print("  " + cp["commit"][:12] + " " + cp["subject"])
    if not report["recent_checkpoints"]:
        print("  本次扫描未找到；不代表全部历史中不存在。")
    if report["expected_commit"]:
        expected = report["expected_commit"]
        print("预期提交：" + expected["requested"])
        print("  本地可解析：" + ("是" if expected["exists"] else "否"))
        print("  属于开发历史：" + ("未核实" if expected["in_dev"] is None else "是" if expected["in_dev"] else "否"))
    states = {"blocked": "尚未就绪", "unverified": "尚未核实远程", "git_history_verified": "当前 Git 开发历史与观察到的远程一致"}
    print("跨设备交接检查：" + states[report["handoff"]["state"]])
    if report["handoff"]["reasons"]:
        print("  原因：" + "；".join(reasons[r] for r in report["handoff"]["reasons"]))
    print("限制：忽略资产与运行环境未检查；无法证明其他设备没有未推送工作。")
    print("同步未就绪不等于停止本机工作；本机接续需结合暂存、冲突和任务范围判断。")
    print("本工具未执行 fetch、暂存、提交、合并、推送或修复。")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--dev", default="dev", help="Actual development branch name")
    parser.add_argument("--stable", default="main", help="Actual stable branch name")
    parser.add_argument("--remote", help="Configured remote name; otherwise infer each branch upstream")
    parser.add_argument("--check-remote", action="store_true", help="Read ls-remote; never fetch")
    parser.add_argument("--expect", help="Expected full commit hash that must be in development history")
    parser.add_argument("--task", help="Filter recent checkpoints by exact task ID")
    parser.add_argument("--json", action="store_true", help="Emit structured facts")
    args = parser.parse_args()
    try:
        report = inspect(args)
    except InspectionError as error:
        if args.json:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
        else:
            print(str(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
