from typing import Any, Optional
from bpy.types import FCurve, Object

from pie_menu_editor import pme

def copy_attributes(a: Any, b: Any) -> None:
    keys = dir(a)
    for key in keys:
        if (
            not key.startswith("_")
            and not key.startswith("error_")
            and key not in ['group', 'is_valid', 'rna_type', 'bl_rna']
        ):
            try:
                setattr(b, key, getattr(a, key))
            except AttributeError:
                pass


def copy_driver(
    source_fcurve: FCurve,
    target_obj: Object,
    data_path: Optional[str] = None,
    index: Optional[int] = None,
) -> FCurve:
    if not data_path:
        data_path = source_fcurve.data_path

    new_fc = None
    try:
        if index:
            new_fc = target_obj.driver_add(data_path, index)
        else:
            new_fc = target_obj.driver_add(data_path)
    except:
        print(f"Couldn't copy driver {source_fcurve.data_path} to {target_obj.name}")
        return

    copy_attributes(source_fcurve, new_fc)
    copy_attributes(source_fcurve.driver, new_fc.driver)

    # Remove default curve modifiers and driver variables.
    for m in new_fc.modifiers:
        new_fc.modifiers.remove(m)
    for v in new_fc.driver.variables:
        new_fc.driver.variables.remove(v)

    # Copy curve modifiers.
    for m1 in source_fcurve.modifiers:
        m2 = new_fc.modifiers.new(type=m1.type)
        copy_attributes(m1, m2)

    # Copy driver variables.
    for v1 in source_fcurve.driver.variables:
        v2 = new_fc.driver.variables.new()
        copy_attributes(v1, v2)
        for i in range(len(v1.targets)):
            copy_attributes(v1.targets[i], v2.targets[i])

    return new_fc


def copy_filtered_drivers_to_selected_obs(context, filtr: str) -> None:
    """Copy all drivers from one object to another."""

    source_ob = context.object
    for target_ob in context.selected_objects:
        if target_ob == source_ob:
            continue
        if not hasattr(source_ob, "animation_data") or not source_ob.animation_data:
            return

        for fc in source_ob.animation_data.drivers:
            if filtr and filtr in fc.data_path:
                copy_driver(fc, target_ob)

kwargs = locals().get("kwargs", {})
filtr = kwargs.get("filter", '')
context = kwargs.get("context", '')

copy_filtered_drivers_to_selected_obs(context, filtr=filtr)
