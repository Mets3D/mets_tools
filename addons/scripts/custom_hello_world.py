# Draw label

# Usage (Custom tab):
# execute_script("scripts/custom_hello_world.py", msg="My Message")

msg = kwargs.get("msg", pme.context.text or "Hello World!")

box = L.box()
box.label(
    text=msg,
    icon=pme.context.icon,
    icon_value=pme.context.icon_value)
