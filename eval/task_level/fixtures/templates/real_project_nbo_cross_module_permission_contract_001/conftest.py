from __future__ import annotations

import pytest


class DartPythonTestFile(pytest.File):
    def collect(self):
        namespace: dict[str, object] = {"__file__": str(self.path)}
        exec(compile(self.path.read_text(encoding="utf-8"), str(self.path), "exec"), namespace)
        for name, value in sorted(namespace.items()):
            if name.startswith("test_") and callable(value):
                yield pytest.Function.from_parent(self, name=name, callobj=value)


def pytest_collect_file(file_path, parent):
    if file_path.suffix == ".dart" and file_path.name.endswith("_test.dart"):
        return DartPythonTestFile.from_parent(parent, path=file_path)
    return None
