import torch
from cyy_naive_lib.data_structure.task_queue import RepeatedResult

from .server import Server


class SignSGDServer(Server):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sign_gradients: list = []

    def __worker(self, sign_gradient: torch.Tensor):
        self.sign_gradients.append(sign_gradient)
        if len(self.sign_gradients) != self.worker_number:
            return None
        total_sign_gradient = [sum(i) for i in zip(*self.sign_gradients)]
        for idx, grad in enumerate(total_sign_gradient):
            total_sign_gradient[idx] = torch.sign(grad)

        self.sign_gradients = []
        return RepeatedResult(data=total_sign_gradient, num=self.worker_number)
