import copy
import datetime
import os

from cyy_naive_lib.data_structure.process_pool import ProcessPool
from cyy_naive_lib.data_structure.thread_pool import ThreadPool
from cyy_naive_lib.log import get_logger, set_file_handler
from cyy_naive_pytorch_lib.arg_parse import (affect_global_process_from_args,
                                             create_trainer_from_args,
                                             get_arg_parser, get_parsed_args)
from cyy_naive_pytorch_lib.dataset import DatasetUtil
from cyy_naive_pytorch_lib.device import get_cuda_devices
from cyy_naive_pytorch_lib.ml_type import MachineLearningPhase

from factory import get_server, get_worker

if __name__ == "__main__":
    parser = get_arg_parser()
    parser.add_argument("--algorithm", type=str, required=True)
    parser.add_argument("--worker_number", type=int, required=True)
    parser.add_argument("--round", type=int)
    args = get_parsed_args(parser=parser)
    affect_global_process_from_args(args)
    ProcessPool().exec(lambda: "1")

    set_file_handler(
        os.path.join(
            "log",
            args.algorithm,
            args.dataset_name,
            args.model_name,
            "{date:%Y-%m-%d_%H:%M:%S}.log".format(date=datetime.datetime.now()),
        )
    )

    server = get_server(args.algorithm, worker_number=args.worker_number)

    trainer = create_trainer_from_args(args)
    training_datasets = DatasetUtil(trainer.dataset).split_by_ratio(
        [1] * args.worker_number
    )

    devices = get_cuda_devices()
    worker_pool = ThreadPool()

    for worker_id in range(args.worker_number):
        get_logger().info("create worker %s", worker_id)
        worker_trainer = copy.deepcopy(trainer)

        worker_trainer.dataset_collection.transform_dataset(
            MachineLearningPhase.Training,
            lambda old_dataset: training_datasets[worker_id],
        )
        worker = get_worker(
            args.algorithm,
            trainer=worker_trainer,
            server=server,
            round=args.round,
        )
        worker_pool.exec(
            worker.train, device=devices[worker_id % len(devices)], worker_id=worker_id
        )
    get_logger().info("begin training")
    worker_pool.stop()
    get_logger().info("end training")
    server.stop()
