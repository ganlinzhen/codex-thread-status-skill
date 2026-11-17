"""安装器共用逻辑；仅使用 Python 标准库。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile


BEGIN = b"<!-- thread-status:begin -->"
END = b"<!-- thread-status:end -->"
STATE_NAME = "thread-status-install.json"
PACKAGE_ENTRIES = ("SKILL.md", "agents", "references", "scripts", "prompts", "README.md", "LICENSE")


class InstallError(Exception):
    """需要保留现场并告知用户的安装错误。"""


def snapshot(path):
    return path.read_bytes() if path.exists() else None


def write_checked(path, content, expected, mode=0o644):
    """以原子替换写入，提交前检查文件未被其他程序改动。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix=".thread-status-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        if snapshot(path) != expected:
            raise InstallError("检测到并发修改，未覆盖文件：" + str(path))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def managed_span(content):
    """只识别完整且唯一的一对行标记，不吞掉标记外的用户原文。"""
    starts, ends, offset = [], [], 0
    for line in content.splitlines(keepends=True):
        stripped = line.rstrip(b"\r\n")
        if stripped == BEGIN:
            starts.append(offset)
        if stripped == END:
            ends.append(offset + len(line))
        offset += len(line)
    if not starts and not ends:
        if BEGIN in content or END in content:
            raise InstallError("触发规则标记格式异常，请先检查，未修改文件。")
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise InstallError("触发规则标记重复或不完整，请先检查，未修改文件。")
    return starts[0], ends[0]


def file_hashes(root):
    """记录实际安装文件；新增、修改或符号链接都会阻止整目录删除。"""
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise InstallError("技能目录含符号链接，保留该目录：" + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            result[path.relative_to(root).as_posix() + "/"] = "directory"
    return result


def copy_package(source, destination):
    for name in PACKAGE_ENTRIES:
        path = source / name
        if not path.exists():
            continue
        if path.is_symlink() or (path.is_dir() and any(p.is_symlink() for p in path.rglob("*"))):
            raise InstallError("技能源中含符号链接，未复制：" + str(path))
        if path.is_dir():
            shutil.copytree(path, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test_*.py"))
        else:
            shutil.copy2(path, destination / name)


def load_state(path, target, agents_path):
    raw = snapshot(path)
    if raw is None:
        return None, raw
    try:
        state = json.loads(raw)
        valid = (state["version"] == 1 and state["skill_dir"] == str(target)
                 and state["agents_path"] == str(agents_path)
                 and isinstance(state["created_skill"], bool)
                 and isinstance(state["agents_existed"], bool)
                 and isinstance(state["separator"], str)
                 and isinstance(state["block"], str)
                 and isinstance(state["files"], dict))
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise InstallError("安装记录损坏或路径不匹配，未修改任何文件：" + str(path))
    return state, raw


def install(source, target, agents_path, state_path):
    if not (source / "SKILL.md").is_file():
        raise InstallError("未找到技能源 SKILL.md。")
    template = (source / "prompts/global-trigger.md").read_text(encoding="utf-8")
    block = template.replace("{{SKILL_PATH}}", json.dumps(str(target / "SKILL.md"), ensure_ascii=False)).encode("utf-8")
    if managed_span(block) != (0, len(block)):
        raise InstallError("全局触发规则模板格式异常。")
    before = snapshot(agents_path)
    current = before or b""
    span = managed_span(current)
    state, old_state = load_state(state_path, target, agents_path)
    if state:
        if not target.exists() or (span and current[slice(*span)] != state["block"].encode("utf-8")):
            raise InstallError("技能或托管规则已被改动，请先检查；未覆盖用户内容。")
        if state["created_skill"] and (target.is_symlink() or file_hashes(target) != state["files"]):
            raise InstallError("已安装技能存在本地改动，未覆盖；请先保留这些改动。")
    elif span:
        raise InstallError("已存在托管规则但没有匹配安装记录，未自动接管。")
    elif os.path.lexists(target) and target.resolve() != source:
        raise InstallError("技能安装位置已被占用，未覆盖：" + str(target))

    created = False
    if not os.path.lexists(target):
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".thread-status-", dir=target.parent))
        try:
            copy_package(source, staging)
            if os.path.lexists(target):
                raise InstallError("技能安装位置被其他程序占用，未覆盖。")
            staging.rename(target)
            created = True
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    if span:
        updated = current[:span[0]] + block + current[span[1]:]
        separator = state["separator"]
    else:
        separator = "" if not current or current.endswith(b"\n\n") else "\n" if current.endswith(b"\n") else "\n\n"
        updated = current + separator.encode() + block
    record = {
        "version": 1, "skill_dir": str(target), "agents_path": str(agents_path),
        "created_skill": state["created_skill"] if state else created,
        "agents_existed": state["agents_existed"] if state else before is not None,
        "separator": separator, "block": block.decode("utf-8"),
        "files": state["files"] if state else file_hashes(target) if created else {},
    }
    encoded_state = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        if updated != current:
            write_checked(agents_path, updated, before)
        if encoded_state != old_state:
            write_checked(state_path, encoded_state, old_state, mode=0o600)
    except (OSError, InstallError):
        if updated != current and snapshot(agents_path) == updated:
            if before is None:
                agents_path.unlink()
            else:
                write_checked(agents_path, before, updated)
        if created:
            shutil.rmtree(target)
        raise
    print("已安装技能：" + str(target))
    print("全局触发规则已配置；重复安装不会重复添加：" + str(agents_path))
    print("请在新会话验证；若技能尚未显示，可重新启动 Codex。改名仍需宿主提供对应工具。")


def uninstall(target, agents_path, state_path):
    state, raw_state = load_state(state_path, target, agents_path)
    if state is None:
        print("没有本安装器的安装记录，未修改技能或全局规则。")
        return
    before = snapshot(agents_path)
    current = before or b""
    span = managed_span(current)
    if span:
        start, end = span
        if current[start:end] != state["block"].encode("utf-8"):
            raise InstallError("托管规则内存在手工改动，已保留；未卸载。")
        separator = state["separator"].encode()
        if separator and current[:start].endswith(separator):
            start -= len(separator)
        updated = current[:start] + current[end:]
        if not updated and not state["agents_existed"]:
            if snapshot(agents_path) != before:
                raise InstallError("检测到全局规则并发修改，未卸载。")
            agents_path.unlink()
        else:
            write_checked(agents_path, updated, before)
    preserved = False
    if os.path.lexists(target):
        try:
            removable = state["created_skill"] and not target.is_symlink() and file_hashes(target) == state["files"]
        except InstallError:
            removable = False
        if removable:
            shutil.rmtree(target)
        else:
            preserved = True
            print("已保留预先存在或包含本地改动的技能目录：" + str(target))
    if snapshot(state_path) != raw_state:
        raise InstallError("安装记录被其他程序修改，已保留该记录。")
    state_path.unlink()
    print("已移除本安装器管理的全局触发规则；用户其他内容保持不变。")
    if preserved:
        print("保留的技能仍可被显式或隐式调用；如需移除，请先核对其中的个人改动。")


def main(action):
    parser = argparse.ArgumentParser(description="安装 thread-status 和全局触发规则。" if action == "install" else "仅卸载本安装器管理的内容。")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"), help="Codex 配置目录；默认尊重 CODEX_HOME，未设置时为 ~/.codex。")
    parser.add_argument("--skills-dir", type=Path, default=Path.home() / ".agents/skills", help="技能父目录，默认为 ~/.agents/skills；卸载须与安装时一致。")
    args = parser.parse_args()
    codex_home = args.codex_home.expanduser().resolve()
    target = args.skills_dir.expanduser().absolute() / "thread-status"
    agents_path = (codex_home / "AGENTS.md").resolve()
    state_path = codex_home / STATE_NAME
    try:
        if action == "install":
            install(Path(__file__).resolve().parents[1], target, agents_path, state_path)
        else:
            uninstall(target, agents_path, state_path)
    except (OSError, ValueError, InstallError) as error:
        print("操作未完成：" + str(error), file=sys.stderr)
        return 1
    return 0
