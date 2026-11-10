"""Resolve external experiment inputs without moving frozen run outputs."""

import hashlib
import os
from pathlib import Path
import subprocess

DEFAULT_DATA_ROOT = Path("/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据")
DATA_ROOT_ENV = "MATRAIX_DATA_ROOT"

# This revision preserves the code hashes recorded before the data-only migration.
PRE_MIGRATION_REVISION = "fb57d8fa07a515411191d840385bfd2c674a40a8"
MIGRATED_CODE_SHA256 = {
    "optimize_profiles.py": "440f5a3211e5d9d8d35e2485540f4452c4a7206f3988f4fb8cb83bd0e3f57fa5",
    "experiment.py": "b7058e8564ce1655f8a95c4d657a413ff5b90768ab895f54fdbad60448ccf271",
    "optimize.py": "275f804cb223582d5ef090b203d50b6fa486d524f963eb933247a200d72589f4",
    "shopping.py": "a30b73e0ec74891f3fda6bbda9a965094b64e154b9c7238d3ff547307de95319",
    "retail_pew.py": "efd882b1ea23e238f5690aff9ae50f636db9a56d16983ac00d4f906fae537ab4",
    "revalidation.py": "f160a24a0703657a341911a61fe6d4eedd13d82b497f739e020f52ec435163bc",
}
CODE_ROOT = Path(__file__).resolve().parent


def data_root():
    override = os.environ.get(DATA_ROOT_ENV)
    return Path(override).expanduser() if override else DEFAULT_DATA_ROOT


def survey_source(survey):
    names = {"shed": "shed.zip", "pew": "Pew-W168.zip", "anes": "anes.zip"}
    return data_root() / "00_历史通用问卷" / names[survey]


def shopping_sources():
    directory = data_root() / "06_历史北美电商"
    names = ("origin-appendix.docx", "origin-original.tab", "origin.csv", "packaging.csv", "pew.zip")
    return {name: directory / ("Pew-W111.zip" if name == "pew.zip" else name) for name in names}


def frozen_code_matches(name, expected, current):
    if expected == current:
        return True
    if MIGRATED_CODE_SHA256.get(name) != current:
        return False
    try:
        original = subprocess.check_output(
            ["git", "show", f"{PRE_MIGRATION_REVISION}:examples/sim-to-real/{name}"],
            cwd=CODE_ROOT, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return hashlib.sha256(original).hexdigest() == expected
