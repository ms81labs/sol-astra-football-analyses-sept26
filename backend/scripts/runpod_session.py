"""Fail-closed compatibility shim for historical research scripts.

RunPod execution was retired. Existing importers may still export or inspect old
research recipes, but any attempt to resolve an execution symbol stops here.
"""


class RetiredRemoteProviderError(RuntimeError):
    pass


def require_retired_runpod_disabled() -> None:
    """Stop an old provider-bound recipe before it performs any work."""

    raise RetiredRemoteProviderError(
        "historical RunPod recipe is retired; use the Daytona job path"
    )


DEFAULT_POD_VENV_PATH = "/workspace/fotball-venv"
DEFAULT_POD_YOLO_CONFIG_DIR = "/workspace/.config/Ultralytics"
_load_saved_runpod_gpu_id = None


def _retired(*_args: object, **_kwargs: object) -> object:
    require_retired_runpod_disabled()


cleanup_runpod_session = _retired
copy_directory_to_pod = _retired
copy_file_to_pod = _retired
create_runpod_session = _retired
pull_pod_file = _retired
run_json_command_over_ssh = _retired
stage_model_on_pod = _retired


def resolve_remote_model_path(model_path: str) -> str:
    """Keep historical recipe rendering usable without enabling execution."""

    return f"/workspace/weights/{model_path.rsplit('/', 1)[-1]}"


def __getattr__(_name: str) -> object:
    require_retired_runpod_disabled()
