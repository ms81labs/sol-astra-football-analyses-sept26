"""Execution-boundary tests for sidecar output path isolation."""

import os
import tempfile
from pathlib import Path

import pytest


def _relocate_addon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    import research_addon.path_guards as guards

    checkout = tmp_path / "moved-checkout"
    addon = checkout / "research-addon"
    package = addon / "research_addon"
    package.mkdir(parents=True)
    monkeypatch.setattr(guards, "__file__", str(package / "path_guards.py"))
    monkeypatch.setattr(guards.tempfile, "gettempdir", lambda: str(tmp_path))
    return checkout, addon


def test_installed_package_does_not_claim_shared_site_packages(tmp_path, monkeypatch):
    import research_addon.path_guards as guards

    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    site_packages = tmp_path / "install" / "site-packages"
    package = site_packages / "research_addon"
    package.mkdir(parents=True)
    monkeypatch.setattr(guards, "__file__", str(package / "path_guards.py"))
    monkeypatch.setattr(guards.tempfile, "gettempdir", lambda: str(system_temp))

    assert guards.get_addon_root() == package
    with pytest.raises(guards.PathResolutionError):
        guards.resolve_run_root(site_packages)


def test_exact_addon_root_and_descendant_are_allowed():
    from research_addon.path_guards import get_addon_root, resolve_run_root

    addon = get_addon_root()
    assert resolve_run_root(addon) == addon
    assert resolve_run_root(addon / "runs" / "one") == addon / "runs" / "one"


def test_addon_sibling_prefix_is_rejected(tmp_path, monkeypatch):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    checkout, addon = _relocate_addon(monkeypatch, tmp_path)
    lookalike = checkout / f"{addon.name}-copy"
    lookalike.mkdir()

    with pytest.raises(PathResolutionError, match="Rejected"):
        resolve_run_root(lookalike)


def test_traversal_and_physical_symlink_escape_are_rejected(tmp_path, monkeypatch):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    checkout, addon = _relocate_addon(monkeypatch, tmp_path)
    backend = checkout / "backend"
    backend.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (addon / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathResolutionError):
        resolve_run_root(addon / "runs" / ".." / ".." / "backend")
    with pytest.raises(PathResolutionError):
        resolve_run_root(addon / "escape" / "run")


def test_protected_subtree_symlink_cannot_reenter_owned_temp(tmp_path, monkeypatch):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    checkout, _ = _relocate_addon(monkeypatch, tmp_path)
    outside_run = tmp_path / "outside" / "run"
    outside_run.mkdir(parents=True)
    (checkout / "backend").symlink_to(outside_run.parent, target_is_directory=True)

    with pytest.raises(PathResolutionError):
        resolve_run_root(checkout / "backend" / "run")


@pytest.mark.parametrize("product", ["backend", "frontend", "detector", "analytics", "truth-gate"])
def test_moved_checkout_under_temp_still_rejects_product_subtrees(
    tmp_path, monkeypatch, product
):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    checkout, _ = _relocate_addon(monkeypatch, tmp_path)
    protected = checkout / product
    protected.mkdir()

    with pytest.raises(PathResolutionError):
        resolve_run_root(protected)


def test_factory_is_not_an_allowed_output_root(tmp_path, monkeypatch):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    checkout, _ = _relocate_addon(monkeypatch, tmp_path)
    factory = checkout / ".factory"
    factory.mkdir()

    with pytest.raises(PathResolutionError):
        resolve_run_root(factory)


def test_default_root_rejects_symlink_non_directory_and_wrong_owner(tmp_path, monkeypatch):
    import research_addon.path_guards as guards

    _relocate_addon(monkeypatch, tmp_path)
    default_root = tmp_path / "fotball-analyst-research-addon"
    outside = tmp_path / "outside"
    outside.mkdir()

    default_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(guards.PathResolutionError):
        guards.resolve_run_root()
    default_root.unlink()

    default_root.write_text("not a directory")
    with pytest.raises(guards.PathResolutionError):
        guards.resolve_run_root()
    default_root.unlink()

    default_root.mkdir()
    monkeypatch.setattr(guards.os, "geteuid", lambda: os.stat(default_root).st_uid + 1)
    with pytest.raises(guards.PathResolutionError):
        guards.resolve_run_root()


def test_absent_dedicated_default_root_is_allowed(tmp_path, monkeypatch):
    import research_addon.path_guards as guards

    _relocate_addon(monkeypatch, tmp_path)
    assert guards.resolve_run_root() == tmp_path / "fotball-analyst-research-addon"


def test_generic_nonexistent_temp_path_and_temp_root_are_rejected(tmp_path, monkeypatch):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    _relocate_addon(monkeypatch, tmp_path)

    with pytest.raises(PathResolutionError):
        resolve_run_root(tmp_path / "missing")
    with pytest.raises(PathResolutionError):
        resolve_run_root(tmp_path)


def test_raw_parent_component_is_rejected_even_when_destination_is_allowed(tmp_path):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    requested = source / ".." / destination.name
    assert requested.resolve() == destination

    with pytest.raises(PathResolutionError):
        resolve_run_root(requested)


@pytest.mark.parametrize(
    "pyproject",
    [
        "[project]\nname = 'something-else'\n",
        "[project]\nname = 'research-addon'\nbroken = [\n",
        (
            "[tool.host]\ndescription = '''\n"
            "[project]\nname = 'research-addon'\n'''\n"
        ),
    ],
    ids=["valid-unrelated", "malformed-after-name", "multiline-misleading"],
)
def test_unrelated_parent_project_content_cannot_claim_installed_package(
    tmp_path, monkeypatch, pyproject
):
    import research_addon.path_guards as guards

    project = tmp_path / "unrelated-project"
    package = project / "research_addon"
    package.mkdir(parents=True)
    backend = project / "backend"
    backend.mkdir()
    (project / "pyproject.toml").write_text(pyproject)
    monkeypatch.setattr(guards, "__file__", str(package / "path_guards.py"))

    assert guards.get_addon_root() == package
    with pytest.raises(guards.PathResolutionError):
        guards.resolve_run_root(backend)


def test_existing_effective_user_owned_temporary_directory_is_allowed():
    from research_addon.path_guards import resolve_run_root

    with tempfile.TemporaryDirectory() as tmpdir:
        assert resolve_run_root(tmpdir) == Path(tmpdir).resolve()


def test_existing_temporary_symlink_is_rejected(tmp_path):
    from research_addon.path_guards import PathResolutionError, resolve_run_root

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(PathResolutionError):
        resolve_run_root(link)
