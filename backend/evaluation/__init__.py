"""GA-13/15 evaluation boundary. Locked labels never become training data."""

from backend.app.workbench.benchmarks import experiment_receipt
from backend.app.workbench.evaluation import current_repository_evaluation_gate, evaluate_protocol_prerequisites

__all__ = [
    "current_repository_evaluation_gate",
    "evaluate_protocol_prerequisites",
    "experiment_receipt",
]
