import re
from . import addon
from .addon import prefs
from .debug_utils import *
from . import constants as CC


def fix(pms=None, version=None):
    DBG_INIT and logh("PME Fixes")
    pr = prefs()
    pr_version = version or tuple(pr.version)
    if pr_version == addon.VERSION:
        return

    fixes = []
    re_fix = re.compile(r"fix_(\d+)_(\d+)_(\d+)")
    for k, v in globals().items():
        mo = re_fix.search(k)
        if not mo:
            continue

        fix_version = (int(mo.group(1)), int(mo.group(2)), int(mo.group(3)))
        if fix_version <= pr_version or fix_version > addon.VERSION:
            continue
        fixes.append((fix_version, v))

    fixes.sort(key=lambda item: item[0])

    if pms is None:
        pms = pr.pie_menus

    for pm in pms:
        for fix_version, fix_func in fixes:
            fix_func(pr, pm)

    pr.version = addon.VERSION


def fix_json(pm, menu, version):
    DBG_INIT and logh("PME JSON Fixes")
    pr = prefs()
    fixes = []
    re_fix = re.compile(r"fix_json_(\d+)_(\d+)_(\d+)")
    for k, v in globals().items():
        mo = re_fix.search(k)
        if not mo:
            continue

        fix_version = (int(mo.group(1)), int(mo.group(2)), int(mo.group(3)))
        if fix_version <= version:
            continue
        fixes.append((fix_version, v))

    fixes.sort(key=lambda item: item[0])

    for fix_version, fix_func in fixes:
        fix_func(pr, pm, menu)


def fix_1_14_0(pr, pm):
    if pm.mode == 'PMENU':
        for pmi in pm.pmis:
            if pmi.mode == 'MENU':
                sub_pm = pmi.text in pr.pie_menus and \
                    pr.pie_menus[pmi.text]

                if sub_pm and sub_pm.mode == 'DIALOG' and \
                        sub_pm.get_data("pd_panel") == 0:
                    pmi.text = CC.F_EXPAND + pmi.text

                    if sub_pm.get_data("pd_box"):
                        pmi.text = CC.F_EXPAND + pmi.text

    elif pm.mode == 'DIALOG':
        if pm.get_data("pd_expand"):
            pm.set_data("pd_expand", False)
            for pmi in pm.pmis:
                if pmi.mode == 'MENU':
                    sub_pm = pmi.text in pr.pie_menus and \
                        pr.pie_menus[pmi.text]
                    if sub_pm and sub_pm.mode == 'DIALOG':
                        pmi.text = CC.F_EXPAND + pmi.text


def fix_1_14_9(pr, pm):
    if pm.mode == 'STICKY':
        pm.data = re.sub(r"([^_])block_ui", r"\1sk_block_ui", pm.data)


def fix_1_17_0(pr, pm):
    if pm.mode == 'PMENU':
        for i in range(len(pm.pmis), 10):
            pm.pmis.add()


def fix_1_17_1(pr, pm):
    if not pm.ed.has_hotkey:
        return

    pm.km_name = (CC.KEYMAP_SPLITTER + " ").join(pm.km_name.split(","))


def fix_json_1_17_1(pr, pm, menu):
    if not pm.ed.has_hotkey:
        return

    menu[1] = (CC.KEYMAP_SPLITTER + " ").join(menu[1].split(","))
