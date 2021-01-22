import copy
import os
import sys

import torch
from cyy_naive_lib.log import get_logger
from cyy_naive_pytorch_lib.device import get_cpu_device
from cyy_naive_pytorch_lib.inference import Inferencer
from cyy_naive_pytorch_lib.ml_types import MachineLearningPhase
from cyy_naive_pytorch_lib.model_util import ModelUtil
from cyy_naive_pytorch_lib.trainer import Trainer
from torch.optim.sgd import SGD

from fed_quant_server import FedQuantServer
from worker import Worker


class FedQuantWorker(Worker):
    def __init__(self, trainer: Trainer, server: FedQuantServer, **kwargs):
        super().__init__(trainer, server)
        assert isinstance(trainer.get_optimizer(), SGD)

        self.local_epoch = kwargs.get("local_epoch")
        assert self.local_epoch
        self.original_model = trainer.model

    def train(self, device):
        self.__prepare_quantization()
        self.trainer.train(
            device=device, after_epoch_callbacks=[self.__send_parameters]
        )

    def __prepare_quantization(self):
        quant_model = torch.quantization.QuantWrapper(
            copy.deepcopy(self.original_model)
        )
        quant_model.cpu()
        quant_model.qconfig = torch.quantization.get_default_qat_qconfig("fbgemm")
        torch.quantization.fuse_modules(
            quant_model,
            [
                ["module.convnet.c1", "module.convnet.relu1"],
                ["module.convnet.c3", "module.convnet.relu3"],
                ["module.convnet.c5", "module.convnet.relu5"],
                ["module.fc.f6", "module.fc.relu6"],
            ],
            inplace=True,
        )
        torch.quantization.prepare_qat(quant_model, inplace=True)
        self.trainer.set_model(quant_model)

    def __get_parameter_list(self):
        return ModelUtil(self.trainer.model).get_parameter_list()

    def __send_parameters(self, trainer: Trainer, epoch, **kwargs):
        if epoch % self.local_epoch != 0:
            return

        trainer.model.eval()
        trainer.model.cpu()
        get_logger().info(trainer.model)

        quantized_model: torch.nn.Module = torch.quantization.convert(trainer.model)

        trainer.set_model(quantized_model)
        trainer.train(device=get_cpu_device())
        sys.exit(0)
        state_dict = quantized_model.state_dict()

        model_util = ModelUtil(trainer.model)
        for k in state_dict.keys():
            # if k.startswith("quant."):
            #     continue
            v = state_dict[k]
            if not isinstance(v, torch.Tensor):
                continue
            if v.is_quantized:
                get_logger().info("for quantization k=%s", k)
                v = v.int_repr().float()
                print(v.shape)
            else:
                get_logger().info("for not quantization k=%s", k)

            # if model_util.has_attr(k):
            #     model_util.set_attr(k, v)
            # # prefix = "module."
            # # if k.startswith(prefix):
            # #     k = k[len(prefix):]
            # # get_logger().info(k)
            # # if not model_util.has_attr(k):
            #     continue
            # model_util.set_attr(k, v)

        # quantized_model.load_state_dict(state_dict)
        # trainer.set_model(quantized_model)
        # device = kwargs.get("device")
        sys.exit(0)
        res = trainer.get_inferencer(
            MachineLearningPhase.Test, copy_model=False
        ).inference(device=get_cpu_device())
        get_logger().info(res)

        sys.exit(0)
        return

        # self.__prepare_quantization()
        # self.trainer.set_model(self.original_model)
        optimizer: torch.optim.Optimizer = kwargs.get("optimizer")
        optimizer.param_groups.clear()
        optimizer.add_param_group({"params": trainer.model.parameters()})

        # get_logger().info("aggregate parameters at epoch %s", epoch)
        # self.server.add_parameter(model_util.get_parameter_list())
        # parameter_list = copy.deepcopy(self.server.get_parameter_list())
        # ModelUtil(trainer.model).load_parameter_list(parameter_list)
        # get_logger().info("finish aggregating parameters at epoch %s", epoch)
