from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_BANK_ROOT = REPO_ROOT / "memorybank"
CORE_FILES = (
    "projectbrief.md",
    "productContext.md",
    "activeContext.md",
    "systemPatterns.md",
    "techContext.md",
    "progress.md",
)


def test_memory_bank_core_files_exist() -> None:
    assert MEMORY_BANK_ROOT.is_dir(), "Expected a root-level memorybank/ directory."
    missing = [name for name in CORE_FILES if not (MEMORY_BANK_ROOT / name).is_file()]
    assert not missing, f"Missing required memory bank files: {missing}"


def test_memory_bank_core_files_are_non_empty_markdown() -> None:
    for name in CORE_FILES:
        path = MEMORY_BANK_ROOT / name
        text = path.read_text(encoding="utf-8")
        assert text.strip(), f"{name} should not be empty."
        assert text.lstrip().startswith("#"), f"{name} should start with a markdown heading."
