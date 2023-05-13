DBG = False
DBG_INIT = False
DBG_LAYOUT = False
DBG_TREE = False
DBG_CMD_EDITOR = False
DBG_MACRO = False
DBG_STICKY = False
DBG_STACK = False
DBG_PANEL = False
DBG_PM = False
DBG_PROP = False
DBG_PROP_PATH = False


def _log(color, *args):
    msg = ""
    for arg in args:
        if msg:
            msg += ", "
        msg += str(arg)
    print(color + msg + '\033[0m')


def logi(*args):
    _log('\033[34m', *args)


def loge(*args):
    _log('\033[31m', *args)


def logh(msg):
    _log('\033[1;32m', "")
    _log('\033[1;32m', msg)


def logw(*args):
    _log('\033[33m', *args)
