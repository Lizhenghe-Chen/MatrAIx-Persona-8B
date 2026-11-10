"""Record portable experiment files and local-only inputs; verify without network."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess

from data_sources import DATA_ROOT_ENV, DEFAULT_DATA_ROOT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = ROOT / "study/00_导航/文件清单.json"
LIMIT = 20 * 1024 * 1024


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_paths(*args: str) -> set[Path]:
    result = subprocess.check_output(
        ["git", "ls-files", "-z", *args, "--", str(ROOT.relative_to(REPO))], cwd=REPO
    )
    return {REPO / p.decode() for p in result.split(b"\0") if p}


def local_reason(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if "11_文献综述/全文资料/本机全文/" in relative:
        return "论文或附件；再分发用途受限或许可尚未确认，全文索引随 Git"
    if path.stat().st_size > LIMIT:
        return "大型原始下载包；保留本机和获取来源"
    if "pew.zip" in relative or "Pew_Wave13/" in relative:
        return "需账户取得的 Pew 数据；按原数据边界留在本机"
    if "origin-appendix.docx" in relative:
        return "出版方补充文件；未确认独立再分发条款"
    if "persona-1m-path.txt" in relative:
        return "旧版兼容路径；当前脚本从数据总库解析"
    if "02_模型对比/checkpoints.sqlite" in relative:
        return "可变检查点；同轮纯合成答卷已另存 ZIP 随 Git 保存"
    if "本机运行/" in relative or path.name in {
        "sample-index.json", "trials.zip", "checkpoints.sqlite"
    }:
        return "真人样本、预测关联或运行检查点；按原约定仅本机复算"
    raise ValueError(f"Unclassified local file: {relative}")


def record(path: Path, tracked: bool) -> dict:
    result = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "storage": "git" if tracked else "local_only",
    }
    if not tracked:
        result["reason"] = local_reason(path)
    return result


def write() -> None:
    tracked = git_paths("--cached") - {OUTPUT}
    pending = git_paths("--others", "--exclude-standard") - {OUTPUT}
    if pending:
        raise SystemExit("Stage the intended archive files first: " + ", ".join(
            str(p.relative_to(ROOT)) for p in sorted(pending)))
    local = {
        p for p in git_paths("--others", "--ignored", "--exclude-standard")
        if "__pycache__" not in p.parts and p.name != ".DS_Store" and not p.name.startswith("._")
    }
    rows = [record(p, p in tracked) for p in sorted(tracked | local)]
    oversized = [row["path"] for row in rows if row["storage"] == "git" and row["bytes"] > LIMIT]
    if oversized:
        raise SystemExit(f"Tracked files exceed the 20 MiB archive limit: {oversized}")
    counts = Counter(row["storage"] for row in rows)
    payload = {
        "schema_version": 1,
        "recorded_on": date.today().isoformat(),
        "root": "examples/sim-to-real",
        "scope": "实验代码、六轮结果、补充分析、报告、公开输入和本机复算材料；排除本清单自身与缓存",
        "size_unit": "bytes; 1 MiB = 1048576 bytes",
        "git_single_file_limit_bytes": LIMIT,
        "git_file_count": counts["git"],
        "git_bytes": sum(r["bytes"] for r in rows if r["storage"] == "git"),
        "local_only_file_count": counts["local_only"],
        "local_only_bytes": sum(r["bytes"] for r in rows if r["storage"] == "local_only"),
        "external_large_source": {
            "dataset": "MatrAIx Persona 1M",
            "version_manifest": "study/数据/persona-1m-official-manifest.json",
            "default_data_root": str(DEFAULT_DATA_ROOT),
            "root_override_env": DATA_ROOT_ENV,
            "release_path": "09_MatrAIx画像/Persona-1M发行版",
            "note": "多 GB 分片留在共享盘，不计入本目录体积；实际实验冻结画像已随 Git 保存",
        },
        "files": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: payload[k] for k in (
        "git_file_count", "git_bytes", "local_only_file_count", "local_only_bytes")}, ensure_ascii=False))


def check() -> None:
    payload = json.loads(OUTPUT.read_text())
    checked = Counter()
    absent_local = 0
    failures = []
    for row in payload["files"]:
        path = ROOT / row["path"]
        if not path.is_file():
            if row["storage"] == "local_only":
                absent_local += 1
            else:
                failures.append("missing: " + row["path"])
            continue
        if path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
            failures.append("changed: " + row["path"])
        else:
            checked[row["storage"]] += 1
    print(json.dumps({"verified": dict(checked), "local_files_not_in_this_copy": absent_local,
                      "failures": failures}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    write() if args.action == "write" else check()
