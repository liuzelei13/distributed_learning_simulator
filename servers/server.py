class Server:
    def __init__(self, tester, worker_number):
        self.__tester = tester
        self.__worker_num = worker_number

    @property
    def tester(self):
        return self.__tester

    @property
    def worker_number(self):
        return self.__worker_num
