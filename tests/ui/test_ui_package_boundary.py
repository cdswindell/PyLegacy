import ast
from pathlib import Path


def test_pytrain_init_does_not_eagerly_import_gui_modules() -> None:
    init_file = Path("src/pytrain/__init__.py")
    tree = ast.parse(init_file.read_text(encoding="utf-8"))

    eager_gui_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and ".gui" in node.module:
            eager_gui_imports.append(node.module)
        elif isinstance(node, ast.Import):
            eager_gui_imports.extend(alias.name for alias in node.names if ".gui" in alias.name)

    assert eager_gui_imports == []
