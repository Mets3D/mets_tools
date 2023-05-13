import bpy


def _get_area():
    return bpy.context.area and bpy.context.area.type


def _get_mode(atype):
    if not atype:
        return None

    if atype == 'PROPERTIES':
        return bpy.context.space_data.context

    if atype in {'VIEW_3D', 'IMAGE_EDITOR'}:
        return bpy.context.mode

    return None


def _get_submode(atype):
    if not atype:
        return None

    C = bpy.context
    ao = C.active_object
    if not ao:
        return None

    if atype == 'VIEW_3D':
        if ao.mode == 'EDIT':
            if ao.type == 'MESH':
                sm = C.tool_settings.mesh_select_mode
                return "%d,%d,%d" % (sm[0], sm[1], sm[2])

    elif atype == 'IMAGE_EDITOR':
        if C.space_data.mode != 'PAINT':
            return C.tool_settings.uv_select_mode

    return None


def _get_ao():
    if bpy.context.active_operator:
        return bpy.context.active_operator.bl_idname
    return None


class BlenderState:
    def __init__(self):
        self.area = None
        self.mode = None
        self.submode = None

    def update(self):
        self.area = _get_area()
        self.mode = _get_mode(self.area)
        self.submode = _get_submode(self.area)

    def __str__(self):
        return "[%s] %s" % (self.mode, self.submode)


_state = BlenderState()


def check():
    area = _get_area()
    if _state.area != area:
        return False

    mode = _get_mode(area)
    if _state.mode != mode:
        return False

    submode = _get_submode(area)
    if _state.submode != submode:
        return False

    return True


def update():
    _state.update()
