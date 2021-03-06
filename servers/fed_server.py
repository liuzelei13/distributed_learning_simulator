import copy

from cyy_naive_lib.data_structure.task_queue import RepeatedResult
from cyy_naive_lib.log import get_logger
from cyy_naive_pytorch_lib.device import get_device
from cyy_naive_pytorch_lib.model_util import ModelUtil

from .server import Server


class FedServer(Server):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.round = 0
        self.parameters: dict = dict()
        self._prev_model = copy.deepcopy(
            ModelUtil(self.tester.model).get_parameter_dict()
        )

    def _process_client_parameter(self, client_parameter: dict):
        return client_parameter

    def _process_aggregated_parameter(self, aggregated_parameter: dict):
        return aggregated_parameter

    def get_subset_model(self, client_subset, init_model=None):
        # empty set
        if not client_subset:
            assert init_model is not None
            return init_model
        avg_parameter: dict = None

        device = get_device()
        for idx in client_subset:
            parameter = self.parameters[idx]
            if avg_parameter is None:
                avg_parameter = parameter
            else:
                for k in avg_parameter:
                    avg_parameter[k] = avg_parameter[k].to(device) + parameter[k].to(
                        device
                    )
        for k, v in avg_parameter.items():
            avg_parameter[k] = v / len(client_subset)
        return avg_parameter

    def _process_worker_data(self, data, __):
        worker_id, parameter_dict = data
        self.parameters[worker_id] = self._process_client_parameter(parameter_dict)

        if len(self.parameters) != self.worker_number:
            get_logger().debug("%s %s,skip", len(self.parameters), self.worker_number)
            return None
        self.round += 1
        get_logger().info("begin aggregating")

        avg_parameter = self.get_subset_model(self.parameters.keys())

        data = self._process_aggregated_parameter(avg_parameter)
        self._prev_model = copy.deepcopy(data)
        get_logger().info("end aggregating")
        self.parameters.clear()
        return RepeatedResult(
            data=data,
            num=self.worker_number,
        )
