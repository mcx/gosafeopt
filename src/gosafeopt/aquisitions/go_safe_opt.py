from enum import Enum
from gosafeopt.aquisitions.safe_opt import SafeOpt
from gosafeopt.tools.misc import singleton
import torch
import gosafeopt
from torch import Tensor
from gosafeopt.tools.data import Data
from typing import Optional

from botorch.models.pairwise_gp import GPyTorchPosterior


class OptimizationStep(Enum):
    LOCAL = 1
    GLOBAL = 2


@singleton
class GoSafeOptState(object):
    def __init__(self, config: dict):
        self.config = config
        self.n_max_local: int = config["n_max_local"]
        self.n_max_global: int = config["n_max_global"]
        self.n = 0

    def go_to_local(self):
        self.n = -1

    def advance(self):
        self.n += 1
        self.n %= self.n_max_local + self.n_max_global

    def get_step(self):
        if self.n < self.n_max_local:
            return OptimizationStep.LOCAL
        elif self.n < self.n_max_global + self.n_max_local:
            return OptimizationStep.GLOBAL


class GoSafeOpt(SafeOpt):
    def __init__(self, model, config: dict, context: Optional[Tensor] = None, data: Optional[Data] = None):
        super().__init__(model, config, context, data)

        self.go_state = GoSafeOptState(config)

    @property
    def n_steps(self) -> int:
        if self.go_state.get_step() == OptimizationStep.LOCAL:
            return 3
        else:
            return 1

    def override_set_initialization(self) -> bool | str:
        if self.go_state.get_step() == OptimizationStep.GLOBAL:
            "random"
        else:
            return super().override_set_initialization()

    def is_internal_step(self, step: int = 0):
        if self.go_state.get_step() == OptimizationStep.LOCAL:
            return super().is_internal_step(step)
        else:
            return False

    def evaluate(self, X: Tensor, step: int = 0) -> Tensor:
        if self.go_state.get_step() == OptimizationStep.LOCAL:
            return super().evaluate(X, step)
        else:
            return self.s3(X)

    def after_optimization(self):
        self.go_state.advance()

    # TODO: No need to compute posterior
    def s3(self, X: Tensor):
        data = self.data.train_x
        if self.data.failed_k is not None:
            data = torch.vstack([data, self.data.failed_k])

        # TODO: rethink this
        distance = self.model.models[0].covar_module.covar_dist(data.to(gosafeopt.device), X).min(axis=0)[0]
        return distance
