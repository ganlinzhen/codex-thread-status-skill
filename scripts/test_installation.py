"""通过临时目录验证真实安装和卸载，不接触本机全局配置。"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True

import _installation as installer


SCRIPTS = Path(__file__).resolve().parent


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="thread-status-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.codex = self.root / "配置 空间"
        self.skills = self.root / "技能 空间"
        self.codex.mkdir()
        self.agents = self.codex / "AGENTS.md"
        self.target = self.skills / "thread-status"

    def run_command(self, action, success=True, scripts=SCRIPTS):
        result = subprocess.run(
            [sys.executable, str(scripts / (action + ".py")),
             "--codex-home", str(self.codex), "--skills-dir", str(self.skills)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def test_round_trip_preserves_original_bytes_and_mode(self):
        original = "# 我的规则\r\n\r\n保留中文和末尾空格  ".encode("utf-8")
        self.agents.write_bytes(original)
        self.agents.chmod(0o640)
        self.run_command("install")
        installed = self.agents.read_bytes()
        self.assertTrue(installed.startswith(original))
        self.assertEqual(self.agents.stat().st_mode & 0o777, 0o640)
        self.run_command("install")
        self.assertEqual(self.agents.read_bytes(), installed)
        self.assertEqual(installed.count(b"<!-- thread-status:begin -->"), 1)
        self.assertTrue((self.target / "references/closeout.md").is_file())
        self.run_command("uninstall")
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.codex / "thread-status-install.json").exists())
        self.run_command("uninstall")
        self.assertEqual(self.agents.read_bytes(), original)

    def test_new_agents_file_can_be_removed(self):
        self.run_command("install")
        self.assertTrue(self.agents.is_file())
        self.run_command("uninstall")
        self.assertFalse(self.agents.exists())

    def test_existing_empty_agents_file_is_retained(self):
        self.agents.write_bytes(b"")
        self.run_command("install")
        self.run_command("uninstall")
        self.assertTrue(self.agents.is_file())
        self.assertEqual(self.agents.read_bytes(), b"")

    def test_uninstall_preserves_later_user_edits(self):
        original = "原有规则\n".encode("utf-8")
        addition = "\n## 后加规则\n不要覆盖\n".encode("utf-8")
        self.agents.write_bytes(original)
        self.run_command("install")
        self.agents.write_bytes(self.agents.read_bytes() + addition)
        self.run_command("uninstall")
        self.assertEqual(self.agents.read_bytes(), original + addition)

    def test_foreign_destination_is_not_overwritten(self):
        self.target.mkdir(parents=True)
        local = self.target / "SKILL.md"
        local.write_text("用户自己安装的内容", encoding="utf-8")
        self.agents.write_bytes(b"keep")
        self.run_command("install", success=False)
        self.assertEqual(self.agents.read_bytes(), b"keep")
        self.assertEqual(local.read_text(encoding="utf-8"), "用户自己安装的内容")

    def test_modified_installed_skill_is_preserved_on_uninstall(self):
        self.run_command("install")
        local = self.target / "personal-notes.md"
        local.write_text("我的补充", encoding="utf-8")
        self.run_command("install", success=False)
        self.run_command("uninstall")
        self.assertEqual(local.read_text(encoding="utf-8"), "我的补充")
        self.assertFalse(self.agents.exists())

    def test_reused_source_symlink_is_not_removed(self):
        self.skills.mkdir()
        self.target.symlink_to(SCRIPTS.parent, target_is_directory=True)
        self.run_command("install")
        self.run_command("uninstall")
        self.assertTrue(self.target.is_symlink())

    def test_agents_symlink_is_preserved(self):
        actual = self.root / "共享规则.md"
        actual.write_bytes(b"shared rules\n")
        self.agents.symlink_to(actual)
        self.run_command("install")
        self.assertTrue(self.agents.is_symlink())
        self.run_command("uninstall")
        self.assertTrue(self.agents.is_symlink())
        self.assertEqual(actual.read_bytes(), b"shared rules\n")

    def test_malformed_markers_abort_before_installing(self):
        original = b"user\n<!-- thread-status:begin -->\nmissing end"
        self.agents.write_bytes(original)
        self.run_command("install", success=False)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())

    def test_edited_managed_block_is_not_erased(self):
        self.run_command("install")
        content = self.agents.read_bytes().replace(b"<!-- thread-status:end -->", "我添加的内容\n<!-- thread-status:end -->".encode("utf-8"))
        self.agents.write_bytes(content)
        self.run_command("uninstall", success=False)
        self.assertEqual(self.agents.read_bytes(), content)
        self.assertTrue(self.target.is_dir())

    def test_installed_scripts_can_uninstall_themselves(self):
        self.run_command("install")
        self.run_command("uninstall", scripts=self.target / "scripts")
        self.assertFalse(self.target.exists())
        self.assertFalse(self.agents.exists())

    def test_original_newline_variations_round_trip(self):
        for original in (b"rule", b"rule\n", b"rule\n\n", b"rule\r\n", b"\xef\xbb\xbfrule\r\n"):
            with self.subTest(original=original):
                self.agents.write_bytes(original)
                self.run_command("install")
                self.run_command("uninstall")
                self.assertEqual(self.agents.read_bytes(), original)

    def test_added_empty_directory_is_preserved(self):
        self.run_command("install")
        personal = self.target / "personal"
        personal.mkdir()
        self.run_command("uninstall")
        self.assertTrue(personal.is_dir())

    def test_duplicate_managed_blocks_are_not_changed(self):
        self.run_command("install")
        duplicate = self.agents.read_bytes() * 2
        self.agents.write_bytes(duplicate)
        self.run_command("install", success=False)
        self.run_command("uninstall", success=False)
        self.assertEqual(self.agents.read_bytes(), duplicate)

    def test_state_write_failure_rolls_back_installation(self):
        original = b"original rules without newline"
        self.agents.write_bytes(original)
        real_write = installer.write_checked

        def fail_state(path, *args, **kwargs):
            if path.name == installer.STATE_NAME:
                raise OSError("模拟安装记录写入失败")
            return real_write(path, *args, **kwargs)

        with mock.patch.object(installer, "write_checked", side_effect=fail_state):
            with self.assertRaises(OSError):
                installer.install(SCRIPTS.parent, self.target, self.agents, self.codex / installer.STATE_NAME)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.codex / installer.STATE_NAME).exists())

    def test_concurrent_agents_edit_is_not_overwritten(self):
        original = b"original\n"
        changed = original + b"added by another editor\n"
        self.agents.write_bytes(original)
        real_write = installer.write_checked

        def concurrent_edit(path, *args, **kwargs):
            if path == self.agents:
                self.agents.write_bytes(changed)
            return real_write(path, *args, **kwargs)

        with mock.patch.object(installer, "write_checked", side_effect=concurrent_edit):
            with self.assertRaises(installer.InstallError):
                installer.install(SCRIPTS.parent, self.target, self.agents, self.codex / installer.STATE_NAME)
        self.assertEqual(self.agents.read_bytes(), changed)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
