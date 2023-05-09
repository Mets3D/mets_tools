from threading import Thread, Event, Lock, current_thread
from time import time, sleep
from sys import exc_info
from traceback import format_exception_only

lock = Lock()
lock2 = Lock()


class Timer(Thread):
    def __init__(self, interval, function):
        Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.stopped = Event()
        # self.daemon = True
        self.time = time()

    @property
    def elapsed_time(self):
        return time() - self.time

    def run(self):
        while not self.stopped.wait(self.interval):
            with lock:
                self.function()
            # with lock2:
            #     pass

    def cancel(self):
        self.stopped.set()


def multiton(cls):
    instances = {}

    def get_instance(id):
        if id not in instances:
            instances[id] = cls(id)
        return instances[id]

    return get_instance


def extract_str_flags(text, *flags):
    ret_flags = [False] * len(flags)
    if not text:
        return ("", *ret_flags)

    for i, f in enumerate(flags):
        if text.startswith(f):
            ret_flags[i] = True
            text = text[len(f):]

    return (text, *ret_flags)


def extract_str_flags_b(text, *flags):
    ret_flags = [False] * len(flags)
    if not text:
        return ("", *ret_flags)

    for i, f in reversed(list(enumerate(flags))):
        if text.endswith(f):
            ret_flags[i] = True
            text = text[:-len(f)]

    return (text, *ret_flags)


def format_exception(idx=None):
    ei = exc_info()
    if idx is None:
        return "".join(format_exception_only(ei[0], ei[1])).rstrip("\n")
    else:
        ret = format_exception_only(ei[0], ei[1])
        if not ret:
            return ""
        ret = ret[idx % len(ret)].rstrip("\n")
        return ret


def isclose(a, b):
    mod = max(abs(a) % 1, abs(b) % 1) or 1
    return abs(a - b) <= 1e-05 * mod
