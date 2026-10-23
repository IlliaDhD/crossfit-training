from crosfit_training_backend.models.complex import Complex
from crosfit_training_backend.models.exercise import Exercise
from crosfit_training_backend.models.training import Training

DOCUMENT_MODELS = [Exercise, Complex, Training]

__all__ = ["DOCUMENT_MODELS", "Complex", "Exercise", "Training"]
