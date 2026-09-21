from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[2]


def _direct_requirements(path: Path) -> dict[str, tuple[str, str | None]]:
    result: dict[str, tuple[str, str | None]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        requirement = Requirement(line)
        result[canonicalize_name(requirement.name)] = (
            str(requirement.specifier),
            str(requirement.marker) if requirement.marker else None,
        )
    return result


def _optional_profile(name: str) -> dict[str, tuple[str, str | None]]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    result: dict[str, tuple[str, str | None]] = {}
    for raw in pyproject["project"]["optional-dependencies"][name]:
        requirement = Requirement(raw)
        result[canonicalize_name(requirement.name)] = (
            str(requirement.specifier),
            str(requirement.marker) if requirement.marker else None,
        )
    return result


def test_optional_dependency_profiles_match_requirement_inputs() -> None:
    assert _optional_profile("api") == _direct_requirements(
        ROOT / "backend/requirements/api.in"
    )
    assert _optional_profile("cv") == _direct_requirements(
        ROOT / "backend/requirements/cpu-cv.in"
    )
    assert _optional_profile("cuda") == _direct_requirements(
        ROOT / "backend/requirements/cuda.in"
    )


def test_overlapping_direct_requirement_pins_do_not_drift() -> None:
    profiles = {
        name: _direct_requirements(ROOT / f"backend/requirements/{name}.in")
        for name in ("api", "cpu-cv", "cuda", "dev")
    }
    seen: dict[str, tuple[str, str | None]] = {}
    for requirements in profiles.values():
        for package, pin in requirements.items():
            if package in seen:
                assert seen[package] == pin, package
            else:
                seen[package] = pin
