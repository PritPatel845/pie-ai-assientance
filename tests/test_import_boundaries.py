"""Import and shell-safety boundaries follow Phase 0S §§3.1–3.7 (PDF pp. 16–22)."""

import ast
import pathlib


PURE_MODULES = (
    "inputs/gesture/features.py",
    "inputs/gesture/frame.py",
    "inputs/gesture/learning.py",
    "inputs/voice/commands.py",
    "inputs/voice/executor.py",
)


def test_pure_modules_do_not_import_platform_or_camera_libraries() -> None:
    root = pathlib.Path(__file__).parents[1] / "src" / "pie"
    for relative in PURE_MODULES:
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name.split(".", maxsplit=1)[0] for alias in node.names}
                assert not imported.intersection({"cv2", "Quartz"}), relative
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".", maxsplit=1)[0]
                assert module not in {"cv2", "Quartz"}, relative


def test_source_tree_never_enables_subprocess_shell_true() -> None:
    root = Path(__file__).parents[1] / "src" / "pie"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        assert not (
                            isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is True
                        ), f"shell=True in {path}:{node.lineno}"
