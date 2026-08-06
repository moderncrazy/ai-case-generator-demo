from pathlib import Path


def test_v2_packages_exist_without_v1_imports() -> None:
    roots = ["bootstrap", "modules", "integrations", "transport", "persistence", "shared"]
    for root in roots:
        assert Path(f"src/{root}/__init__.py").is_file()

    forbidden = ("src.frontend", "src.models.business", "src.repositories")
    for root in roots:
        for path in Path("src", root).rglob("*.py"):
            text = path.read_text()
            assert not any(name in text for name in forbidden)
