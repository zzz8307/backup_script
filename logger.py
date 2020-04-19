import os
import sys
import logging
from datetime import datetime


class Logger(object):
    """
    log_path 默认为脚本路径下的 log 文件夹
    log_name 默认为脚本名
    log_time 默认为当前时间
    生成的日志文件名默认格式为 脚本名-当前时间.log
    """

    def __init__(self,
                 log_path=os.path.join(sys.path[0], "log"),
                 log_name=os.path.splitext(os.path.split(sys.argv[0])[-1])[0],
                 log_time=datetime.strftime(datetime.now(), "%Y-%m-%d_%H-%M-%S")):

        name = "{0}-{1}.log".format(log_name, log_time)
        log_filename = os.path.join(log_path, name)

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)

        if not os.path.exists(log_path):
            os.makedirs(log_path)

        ch = logging.StreamHandler()
        fh = logging.FileHandler(filename=log_filename, encoding="utf-8")

        ch.setLevel(logging.INFO)
        fh.setLevel(logging.DEBUG)

        ch_formatter = logging.Formatter("%(asctime)s|%(levelname)s: %(message)s")
        fh_formatter = logging.Formatter("%(asctime)s|%(filename)s|%(funcName)s|%(lineno)d|%(levelname)s: %(message)s")
        ch.setFormatter(ch_formatter)
        fh.setFormatter(fh_formatter)

        self.logger.addHandler(ch)
        self.logger.addHandler(fh)

    def getlogger(self):
        return self.logger
