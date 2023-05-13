import bpy
import re
from . import operator_utils
from .debug_utils import *
from .addon import prefs, print_exc
from .bl_utils import uname


_operators = {}
_macros = {}
_macro_execs = []
_exec_base = None
_sticky_op = None
_modal_op = None


def init_macros(exec1, base, sticky, modal):
    _macro_execs.append(exec1)
    global _exec_base, _sticky_op, _modal_op
    _exec_base = base
    _sticky_op = sticky
    _modal_op = modal


def add_macro_exec():
    id = "macro_exec%d" % (len(_macro_execs) + 1)
    tp_name = "PME_OT_" + id
    defs = {
        "bl_idname": "pme." + id,
    }

    tp = type(tp_name, (_exec_base, bpy.types.Operator), defs)

    bpy.utils.register_class(tp)
    _macro_execs.append(tp)


def _gen_tp_id(name):
    def repl(mo):
        c = mo.group(0)
        try:
            cc = ord(c)
        except:
            return "_"

        return chr(97 + cc % 26)

    name = name.replace(" ", "_")
    name = name.lower()
    pre_tp, pre_id = "PME_OT_", "pme."
    id = "macro_" + re.sub(r"[^_a-z0-9]", repl, name, flags=re.I)
    id = uname(bpy.types, pre_tp + id, sep="_")[len(pre_tp):]
    return pre_tp + id, pre_id + id


def _gen_op(tp, idx, **kwargs):
    tpname = tp.__name__[:-5] + str(idx + 1)
    bl_idname = tp.bl_idname + str(idx + 1)

    if tpname not in _operators:
        defs = dict(bl_idname=bl_idname)
        defs.update(kwargs)
        new_tp = type(tpname, (tp, bpy.types.Operator), defs)
        bpy.utils.register_class(new_tp)
        _operators[tpname] = new_tp

    return tpname


def _gen_modal_op(pm, idx):
    lock = pm.get_data("lock")

    tpname = _modal_op.__name__[:-5]
    bl_idname = _modal_op.bl_idname
    if lock:
        tpname += "_grab"
        bl_idname += "_grab"

    tpname += str(idx + 1)
    bl_idname += str(idx + 1)

    if tpname not in _operators:
        defs = dict(bl_idname=bl_idname)
        if not lock:
            defs["bl_options"] = {'REGISTER'}
        new_tp = type(tpname, (_modal_op, bpy.types.Operator), defs)
        bpy.utils.register_class(new_tp)
        _operators[tpname] = new_tp

    return tpname


def add_macro(pm):
    if pm.name in _macros:
        return

    pr = prefs()
    tp_name, tp_bl_idname = _gen_tp_id(pm.name)

    DBG_MACRO and logh("Add Macro: %s (%s)" % (pm.name, tp_name))

    defs = {
        "bl_label": pm.name,
        "bl_idname": tp_bl_idname,
        # "bl_options": {'REGISTER', 'UNDO', 'MACRO'},
        "bl_options": {'REGISTER', 'UNDO'},
    }

    tp = type(tp_name, (bpy.types.Macro,), defs)

    try:
        bpy.utils.register_class(tp)
        _macros[pm.name] = tp

        idx, sticky_idx, modal_idx = 1, 0, 0
        for pmi in pm.pmis:
            if not pmi.enabled:
                continue

            pmi.icon = ''
            if pmi.mode == 'COMMAND':
                sub_op_idname, _, pos_args = operator_utils.find_operator(
                    pmi.text)

                _, sub_op_exec_ctx, _ = operator_utils.parse_pos_args(pos_args)

                if sub_op_idname and sub_op_exec_ctx.startswith('INVOKE'):
                    sub_tp = eval("bpy.ops." + sub_op_idname).idname()
                    pmi.icon = 'BLENDER'
                    DBG_MACRO and logi("Type", sub_tp)
                    tp.define(sub_tp)
                else:
                    while len(_macro_execs) < idx:
                        add_macro_exec()
                    pmi.icon = 'TEXT'
                    DBG_MACRO and logi("Command", pmi.text)
                    tp.define("PME_OT_macro_exec%d" % idx)
                    idx += 1

            elif pmi.mode == 'MENU':
                if pmi.text not in pr.pie_menus:
                    continue
                sub_pm = pr.pie_menus[pmi.text]
                if sub_pm.mode == 'MACRO':
                    sub_tp = _macros.get(sub_pm.name, None)
                    if sub_tp:
                        DBG_MACRO and logi("Macro", sub_pm.name)
                        tp.define(sub_tp.__name__)

                elif sub_pm.mode == 'MODAL':
                    DBG_MACRO and logi("Modal", sub_pm.name)
                    idname = _gen_modal_op(sub_pm, modal_idx)
                    tp.define(idname)
                    modal_idx += 1

                elif sub_pm.mode == 'STICKY':
                    DBG_MACRO and logi("Sticky", sub_pm.name)
                    idname = _gen_op(_sticky_op, sticky_idx)
                    tp.define(idname)
                    sticky_idx += 1

    except:
        print_exc()


def remove_macro(pm):
    if pm.name not in _macros:
        return

    bpy.utils.unregister_class(_macros[pm.name])
    del _macros[pm.name]


def remove_all_macros():
    for v in _macros.values():
        bpy.utils.unregister_class(v)
    _macros.clear()

    while len(_macro_execs) > 1:
        bpy.utils.unregister_class(_macro_execs.pop())
    _macro_execs.clear()


def update_macro(pm):
    if pm.name not in _macros:
        return

    remove_macro(pm)
    add_macro(pm)


def _fill_props(props, pm, idx=1):
    pr = prefs()

    sticky_idx, modal_idx = 0, 0
    for pmi in pm.pmis:
        if not pmi.enabled:
            continue

        if pmi.mode == 'COMMAND':
            sub_op_idname, args, pos_args = operator_utils.find_operator(
                pmi.text)

            _, sub_op_exec_ctx, _ = operator_utils.parse_pos_args(pos_args)

            if sub_op_idname and sub_op_exec_ctx.startswith('INVOKE'):
                args = ",".join(args)
                sub_tp = eval("bpy.ops." + sub_op_idname).idname()

                props[sub_tp] = eval("dict(%s)" % args)
            else:
                # while len(_macro_execs) < idx:
                #     add_macro_exec()
                props["PME_OT_macro_exec%d" % idx] = dict(cmd=pmi.text)
                idx += 1

        elif pmi.mode == 'MENU':
            sub_pm = pr.pie_menus[pmi.text]
            if sub_pm.mode == 'STICKY':
                props[_gen_op(_sticky_op, sticky_idx)] = \
                    dict(pm_name=sub_pm.name)
                sticky_idx += 1

            elif sub_pm.mode == 'MODAL':
                idname = _gen_modal_op(sub_pm, modal_idx)
                props[idname] = dict(pm_name=sub_pm.name)
                modal_idx += 1

            elif sub_pm.mode == 'MACRO':
                sub_props = {}
                _fill_props(sub_props, sub_pm)
                props[_macros[sub_pm.name].__name__] = sub_props


def execute_macro(pm):
    if pm.name not in _macros:
        return

    tp = _macros[pm.name]
    op = eval("bpy.ops." + tp.bl_idname)
    props = {}
    _fill_props(props, pm)
    op('INVOKE_DEFAULT', True, **props)


def rename_macro(old_name, name):
    if old_name not in _macros:
        return

    _macros[name] = _macros[old_name]
    _macros[name].bl_label = name
    del _macros[old_name]

    bpy.utils.unregister_class(_macros[name])

    tp_name, tp_bl_idname = _gen_tp_id(name)
    _macros[name].__name__ = tp_name
    _macros[name].bl_idname = tp_bl_idname
    bpy.utils.register_class(_macros[name])


def register():
    pass


def unregister():
    remove_all_macros()

    for v in _operators.values():
        bpy.utils.unregister_class(v)
    _operators.clear()
