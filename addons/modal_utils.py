from .addon import temp_prefs
from .utils import isclose


def encode_modal_data(pmi):
    cmd = pmi.mode == 'COMMAND'

    tpr = temp_prefs()
    # data = tpr.modal_item_prop_mode
    data = [tpr.modal_item_hk.to_string()]
    if cmd:
        data.append(tpr.modal_item_custom)

    elif tpr.modal_item_hk.key != 'NONE':
        data.append(
            "" if isclose(tpr.modal_item_prop_min, tpr.prop_data.min) else
            str(tpr.modal_item_prop_min))
        data.append(
            "" if isclose(tpr.modal_item_prop_max, tpr.prop_data.max) else
            str(tpr.modal_item_prop_max))
        data.append(
            "" if not tpr.modal_item_prop_step_is_set else
            str(tpr.modal_item_prop_step))
        data.append(tpr.modal_item_custom)

    pmi.icon = ";".join(data)


def decode_modal_data(pmi, prop_data=None, tpr=None):
    hk, min_value, max_value, step = None, None, None, None
    data = pmi.icon
    cmd = pmi.mode == 'COMMAND'
    custom = ""

    if data:
        if cmd:
            data = data.split(";", 4)
            hk = data[0]

            tpr and tpr.modal_item_hk.from_string(hk)
            n = len(data)
            if n > 1:
                custom = data[1]
                tpr and setattr(tpr, "modal_item_custom", custom)
                prop_data and setattr(prop_data, "custom", custom)

            return hk, 0, 0, 1, custom

        else:
            prop_data and setattr(prop_data, "icon", data)
            data = data.split(";", 4)
            hk = data[0]

            tpr and tpr.modal_item_hk.from_string(hk)
            n = len(data)
            if n > 1 and data[1]:
                min_value = float(data[1])
                tpr and setattr(tpr, "modal_item_prop_min", min_value)
                prop_data and setattr(prop_data, "min", min_value)
            if n > 2 and data[2]:
                max_value = float(data[2])
                tpr and setattr(tpr, "modal_item_prop_max", max_value)
                prop_data and setattr(prop_data, "max", max_value)
            if n > 3 and data[3]:
                step = float(data[3])
                tpr and setattr(tpr, "modal_item_prop_step", step)
                prop_data and setattr(prop_data, "_step", step)
            if n > 4:
                custom = data[4]
                if tpr:
                    tpr["modal_item_custom"] = custom
                prop_data and setattr(prop_data, "custom", custom)
    else:
        tpr and tpr.modal_item_hk.clear()

    if tpr and not cmd:
        if tpr.modal_item_hk.key in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            tpr["modal_item_prop_mode"] = 2
        elif tpr.modal_item_hk.key == 'MOUSEMOVE':
            tpr["modal_item_prop_mode"] = 1
        else:
            tpr["modal_item_prop_mode"] = 0

    return hk, min_value, max_value, step, custom
