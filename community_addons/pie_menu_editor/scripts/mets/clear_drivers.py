
def clear_filtered_drivers(context, filtr: str) -> None:
    """Copy all drivers from one object to another."""

    for obj in context.selected_objects:
        if not hasattr(obj, "animation_data") or not obj.animation_data:
            continue

        for fc in obj.animation_data.drivers[:]:
            if filtr and filtr in fc.data_path:
                obj.animation_data.drivers.remove(fc)

kwargs = locals().get("kwargs", {})
filtr = kwargs.get("filter", '')
context = kwargs.get("context", '')

clear_filtered_drivers(context, filtr=filtr)