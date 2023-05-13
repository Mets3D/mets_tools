import bpy
from . import constants as CC
from .addon import uprefs, print_exc, is_28
from .property_utils import DynamicPG, to_py_value
from .debug_utils import *
from . import c_utils as CTU
from . import operator_utils as OU
from . import (
    pme,
    selection_state,
)

MOUSE_BUTTONS = {
    'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE',
    'BUTTON4MOUSE', 'BUTTON5MOUSE', 'BUTTON6MOUSE', 'BUTTON7MOUSE'}
TWEAKS = {
    'EVT_TWEAK_L', 'EVT_TWEAK_M', 'EVT_TWEAK_R', 'EVT_TWEAK_A', 'EVT_TWEAK_S'}
MAP_TYPES = ['KEYBOARD', 'MOUSE', 'TWEAK', 'NDOF', 'TEXTINPUT', 'TIMER']

CTRL = 1 << 0
SHIFT = 1 << 1
ALT = 1 << 2
OSKEY = 1 << 3

key_items = []
key_names = {}
for i in bpy.types.Event.bl_rna.properties["type"].enum_items.values():
    key_items.append((i.identifier, i.name, "", i.value))
    key_names[i.identifier] = i.description or i.name

_keymap_names = {
    "Window": ('EMPTY', 'WINDOW'),
    "3D View": ('VIEW_3D', 'WINDOW'),
    "Timeline": ('TIMELINE', 'WINDOW'),
    "Graph Editor": ('GRAPH_EDITOR', 'WINDOW'),
    "Dopesheet": ('DOPESHEET_EDITOR', 'WINDOW'),
    "NLA Editor": ('NLA_EDITOR', 'WINDOW'),
    "Image": ('IMAGE_EDITOR', 'WINDOW'),
    "UV Editor": ('IMAGE_EDITOR', 'WINDOW'),
    "Sequencer": ('SEQUENCE_EDITOR', 'WINDOW'),
    "Clip Editor": ('CLIP_EDITOR', 'WINDOW'),
    "Text": ('TEXT_EDITOR', 'WINDOW'),
    "Node Editor": ('NODE_EDITOR', 'WINDOW'),
    "Logic Editor": ('LOGIC_EDITOR', 'WINDOW'),
    "Property Editor": ('PROPERTIES', 'WINDOW'),
    "Outliner": ('OUTLINER', 'WINDOW'),
    "User Preferences": (CC.UPREFS, 'WINDOW'),
    "Info": ('INFO', 'WINDOW'),
    "File Browser": ('FILE_BROWSER', 'WINDOW'),
    "Console": ('CONSOLE', 'WINDOW'),
}

_keymaps_obj_mode = {
    "OBJECT": "Object Mode",
    "EDIT": "Mesh",
    "MESH": "Mesh",
    "POSE": "Pose",
    "SCULPT": "Sculpt",
    "VERTEX_PAINT": "Vertex Paint",
    "WEIGHT_PAINT": "Weight Paint",
    "TEXTURE_PAINT": "Image Paint",
    "CURVE": "Curve",
    "SURFACE": "Curve",
    "ARMATURE": "Armature",
    "META": "Metaball",
    "FONT": "Font",
    "LATTICE": "Lattice",
    "PARTICLE_EDIT": "Particle",
}


class _KMList:
    default_header = [
        "Screen Editing",
        "View2D",
        "Frames",
        "Header",
        "Window",
        "Screen"
    ]
    default_empty = [
        "Screen Editing",
        "Window",
        "Screen"
    ]

    def __init__(
            self, window=None, header=None, tools=None, ui=None,
            channels=None, preview=None):

        def init_rlist(lst):
            if lst is not None:
                lst.insert(0, "Screen Editing")
                lst.append("Window")
                lst.append("Screen")
            return lst

        self.rlists = {
            'WINDOW': init_rlist(window),
            'HEADER': init_rlist(header) if header else _KMList.default_header,
            'CHANNELS': init_rlist(channels),
            'TOOLS': init_rlist(tools),
            'TOOL_PROPS': tools,
            'UI': init_rlist(ui) if ui else tools,
            'PREVIEW': init_rlist(preview)
        }

    def get_keymaps(self, context):
        region = context.region.type
        if region in self.rlists and self.rlists[region]:
            return self.rlists[region]

        return _KMList.default_empty


class _View3DKMList(_KMList):
    def get_keymaps(self, context):
        region = context.region.type
        if region == 'WINDOW':
            lst = [
                "Screen Editing",
                "Grease Pencil"
            ]

            mode = "OBJECT"
            if context.active_object:
                mode = context.active_object.mode

            if mode == "EDIT":
                tp = context.active_object.type
                if tp in _keymaps_obj_mode:
                    lst.append(_keymaps_obj_mode[tp])
            else:
                if mode in _keymaps_obj_mode:
                    lst.append(_keymaps_obj_mode[mode])

            lst.append("Object Non-modal")
            lst.append("Frames")
            lst.append("3D View Generic")
            lst.append("3D View")
            lst.append("Window")
            lst.append("Screen")

            return lst

        return super(_View3DKMList, self).get_keymaps(context)


class _ImageKMList(_KMList):
    def get_keymaps(self, context):
        region = context.region.type
        if region == 'WINDOW':
            lst = [
                "Screen Editing",
                "Frames",
                "Grease Pencil"
            ]

            mode = bpy.context.space_data.mode
            if mode == 'PAINT':
                lst.append("Image Paint")
            elif mode == 'MASK':
                lst.append("Mask Editing")
            elif mode == 'VIEW' and not is_28() or \
                    mode == 'UV' and is_28():
                ao = context.active_object
                if ao and ao.data and \
                        ao.type == 'MESH' and ao.mode == 'EDIT' and \
                        ao.data.uv_layers.active:
                    lst.append("UV Editor")

            lst.append("Image Generic")
            lst.append("Image")
            lst.append("Window")
            lst.append("Screen")

            return lst

        return super(_ImageKMList, self).get_keymaps(context)


_km_lists = {
    "VIEW_3D": _View3DKMList(
        header=[
            "View2D",
            "Frames",
            "Header",
            "3D View Generic"
        ],
        tools=[
            "Frames",
            "View2D Buttons List",
            "3D View Generic"
        ]),

    "TIMELINE": _KMList(
        window=[
            "View2D",
            "Markers",
            "Animation",
            "Frames",
            "Timeline"
        ]),

    "GRAPH_EDITOR": _KMList(
        window=[
            "View2D",
            "Animation",
            "Frames",
            "Graph Editor",
            "Graph Editor Generic"
        ],
        channels=[
            "View2D",
            "Frames",
            "Animation Channels",
            "Graph Editor Generic"
        ],
        tools=[
            "View2D Buttons List",
            "Graph Editor Generic"
        ]),

    "DOPESHEET_EDITOR": _KMList(
        window=[
            "View2D",
            "Animation",
            "Frames",
            "Dopesheet"
        ],
        channels=[
            "View2D",
            "Frames",
            "Animation Channels"
        ]),

    "NLA_EDITOR": _KMList(
        window=[
            "View2D",
            "Animation",
            "Frames",
            "NLA Editor",
            "NLA Generic"
        ],
        channels=[
            "View2D",
            "Frames",
            "NLA Channels",
            "Animation Channels",
            "NLA Generic"
        ],
        tools=[
            "View2D Buttons List",
            "NLA Generic"
        ]),

    "IMAGE_EDITOR": _ImageKMList(
        tools=[
            "Frames",
            "View2D Buttons List",
            "Image Generic"
        ]),

    "SEQUENCE_EDITOR": _KMList(
        window=[
            "View2D",
            "Animation",
            "Frames",
            "SequencerCommon",
            "Sequencer"
        ],
        preview=[
            "View2D",
            "Frames",
            "Grease Pencil",
            "SequencerCommon",
            "SequencerPreview"
        ],
        tools=[
            "Frames",
            "SequencerCommon",
            "View2D Buttons List"
        ]),

    "CLIP_EDITOR": _KMList(
        window=[
            "Frames",
            "Grease Pencil",
            "Clip",
            "Clip Editor"
        ],
        channels=[
            "Frames",
            "Clip Dopesheet Editor"
        ],
        preview=[
            "View2D",
            "Frames",
            "Clip",
            "Clip Graph Editor",
            "Clip Dopesheet Editor"
        ],
        tools=[
            "Frames",
            "View2D Buttons List",
            "Clip"
        ]),

    "TEXT_EDITOR": _KMList(
        window=[
            "Text Generic",
            "Text"
        ],
        header=[
            "View2D",
            "Header"
        ],
        tools=[
            "View2D Buttons List",
            "Text Generic"
        ]),

    "NODE_EDITOR": _KMList(
        window=[
            "View2D",
            "Frames",
            "Grease Pencil",
            "Node Generic",
            "Node Editor"
        ],
        header=[
            "View2D",
            "Header",
            "Frames"
        ],
        tools=[
            "Frames",
            "View2D Buttons List",
            "Node Generic"
        ]),

    "LOGIC_EDITOR": _KMList(
        window=[
            "View2D",
            "Frames",
            "Logic Editor"
        ],
        tools=[
            "Frames",
            "View2D Buttons List",
            "Logic Editor"
        ]),

    "PROPERTIES": _KMList(
        window=[
            "Frames",
            "View2D Buttons List",
            "Property Editor"
        ]),

    "OUTLINER": _KMList(
        window=[
            "View2D",
            "Frames",
            "Outliner"
        ]),

    CC.UPREFS: _KMList(
        window=[
            "View2D Buttons List"
        ],
        header=[
            "View2D",
            "Header"
        ]),

    "INFO": _KMList(
        window=[
            "View2D",
            "Frames",
            "Info"
        ]),

    "FILE_BROWSER": _KMList(
        window=[
            "View2D",
            "File Browser",
            "File Browser Main"
        ],
        header=[
            "View2D",
            "Header",
            "File Browser"
        ],
        tools=[
            "View2D Buttons List",
            "File Browser"
        ],
        ui=[
            "File Browser",
            "File Browser Buttons"
        ]),

    "CONSOLE": _KMList(
        window=[
            "View2D",
            "Console"
        ],
        header=[
            "View2D",
            "Header"
        ])
}


def is_default_select_key():
    context = bpy.context
    upr = uprefs()
    if hasattr(upr.inputs, "select_mouse"):
        ret = upr.inputs.select_mouse == 'RIGHT'
    else:
        kc = context.window_manager.keyconfigs.active
        if not kc.preferences:
            return True

        ret = kc.preferences.select_mouse == 'RIGHT'

    return ret


def to_blender_mouse_key(key, context):
    default = is_default_select_key()

    if key == 'LEFTMOUSE':
        key = 'ACTIONMOUSE' if default else 'SELECTMOUSE'
    elif key == 'RIGHTMOUSE':
        key = 'SELECTMOUSE' if default else 'ACTIONMOUSE'

    return key


def to_system_mouse_key(key, context):
    default = is_default_select_key()

    if key == 'ACTIONMOUSE':
        key = 'LEFTMOUSE' if default else 'RIGHTMOUSE'
    elif key == 'SELECTMOUSE':
        key = 'RIGHTMOUSE' if default else 'LEFTMOUSE'

    return key


def compare_km_names(name1, name2):
    if name1 == name2:
        return 2

    name1 = set(s.strip() for s in name1.split(CC.KEYMAP_SPLITTER))
    name2 = set(s.strip() for s in name2.split(CC.KEYMAP_SPLITTER))
    name = name1.intersection(name2)

    if name == name1:
        return 2

    elif not name:
        return 0

    return 1


def encode_mods(ctrl, shift, alt, oskey):
    ret = 0
    if ctrl:
        ret |= CTRL
    if shift:
        ret |= SHIFT
    if alt:
        ret |= ALT
    if oskey:
        ret |= OSKEY
    return ret


def test_mods(event, mods):
    return encode_mods(event.ctrl, event.shift, event.alt, event.oskey) == mods


def parse_hotkey(hotkey):
    hotkey, _, chord = hotkey.partition(",")
    chord = chord.strip() if chord else 'NONE'
    parts = hotkey.upper().split("+")

    ctrl = 'CTRL' in parts
    if ctrl:
        parts.remove('CTRL')

    alt = 'ALT' in parts
    if alt:
        parts.remove('ALT')

    shift = 'SHIFT' in parts
    if shift:
        parts.remove('SHIFT')

    oskey = 'OSKEY' in parts
    if oskey:
        parts.remove('OSKEY')

    any = 'ANY' in parts
    if any:
        parts.remove('ANY')

    key_mod = 'NONE' if len(parts) == 1 else parts[0]
    key = parts[-1]

    enum_items = bpy.types.Event.bl_rna.properties["type"].enum_items
    if key_mod not in enum_items:
        key_mod = 'NONE'
    if key not in enum_items:
        key = 'NONE'

    return key, ctrl, shift, alt, oskey, any, key_mod, chord


def run_operator(context, key, ctrl, shift, alt, oskey, key_mod):
    area = context.area.type
    if area not in _km_lists:
        return

    key1 = key
    key2 = key
    default = is_default_select_key()

    if key == 'LEFTMOUSE':
        key2 = 'ACTIONMOUSE' if default else 'SELECTMOUSE'
    if key == 'RIGHTMOUSE':
        key2 = 'SELECTMOUSE' if default else 'ACTIONMOUSE'
    if key == 'ACTIONMOUSE':
        key2 = 'LEFTMOUSE' if default else 'RIGHTMOUSE'
    if key == 'SELECTMOUSE':
        key2 = 'RIGHTMOUSE' if default else 'LEFTMOUSE'

    km_names = _km_lists[area].get_keymaps(context)
    km_item = None
    keymaps = context.window_manager.keyconfigs.user.keymaps
    for km_name in km_names:
        if km_name not in keymaps:
            continue
        km = keymaps[km_name]
        for kmi in km.keymap_items:
            if (kmi.type == key1 or kmi.type == key2) and \
                    kmi.value == 'PRESS' and \
                    kmi.active and \
                    kmi.ctrl == ctrl and \
                    kmi.shift == shift and \
                    kmi.alt == alt and \
                    kmi.oskey == oskey and \
                    kmi.key_modifier == key_mod and \
                    kmi.idname != "pme.mouse_state" and \
                    kmi.idname != "wm.pme_user_pie_menu_call":
                module, _, operator = kmi.idname.rpartition(".")
                if not module or "." in module:
                    continue

                if not hasattr(bpy.ops, module):
                    continue

                module = getattr(bpy.ops, module)
                if not hasattr(module, operator):
                    continue

                operator = getattr(module, operator)
                if operator.poll():

                    # operator = OU.operator(kmi.idname)
                    # if not operator:
                    #     return

                    args = {}
                    for k in kmi.properties.keys():
                        v = getattr(kmi.properties, k)
                        v = to_py_value(kmi, k, v)
                        if v is None or isinstance(v, dict) and not v:
                            continue

                        args[k] = v

                    try:
                        ret = operator('INVOKE_DEFAULT', True, **args)
                        if 'PASS_THROUGH' not in ret:
                            return

                    except:
                        print_exc()
                        return

                    # km_item = kmi

        # if km_item:
        #     break


def run_operator_by_hotkey(context, hotkey):
    key, ctrl, shift, alt, oskey, any, key_mod, _ = parse_hotkey(hotkey)
    run_operator(context, key, ctrl, shift, alt, oskey, key_mod)


def call_operator(hotkey):
    key, ctrl, shift, alt, oskey, any, key_mod, _ = parse_hotkey(hotkey)
    run_operator(bpy.context, key, ctrl, shift, alt, oskey, key_mod)


def to_key_name(key):
    if key == 'NONE':
        return "None"
    return key_names.get(key, key)


def to_hotkey(
        key, ctrl=False, shift=False, alt=False, oskey=False,
        key_mod=None, any=False, use_key_names=False, chord=None):
    if not key or key == 'NONE':
        return ""

    hotkey = ""
    if any:
        hotkey += "any+"
    else:
        if ctrl:
            hotkey += "ctrl+"
        if shift:
            hotkey += "shift+"
        if alt:
            hotkey += "alt+"
        if oskey:
            hotkey += "oskey+"
    if key_mod and key_mod != 'NONE':
        hotkey += key_names[key_mod] if use_key_names else key_mod
        hotkey += "+"
    hotkey += key_names[key] if use_key_names else key
    if chord:
        hotkey += ", " + chord

    return hotkey


def to_ui_hotkey(data):
    if not data.key or data.key == 'NONE':
        return ""

    hotkey = ""
    if data.any:
        hotkey += "?"
    else:
        if data.ctrl:
            hotkey += "c"
        if data.shift:
            hotkey += "s"
        if data.alt:
            hotkey += "a"
        if data.oskey:
            hotkey += "o"
    if hotkey:
        hotkey += "+"
    if data.key_mod and data.key_mod != 'NONE':
        hotkey += "[%s]+" % key_names[data.key_mod]

    if hasattr(data, "open_mode"):
        if data.open_mode == 'PRESS':
            hotkey += key_names[data.key]
        elif data.open_mode == 'HOLD':
            hotkey += "[%s]" % key_names[data.key]
        elif data.open_mode == 'TWEAK':
            hotkey += "{%s}" % key_names[data.key]
        elif data.open_mode == 'DOUBLE_CLICK':
            hotkey += "%sx2" % key_names[data.key]
        elif data.open_mode == 'CHORDS':
            hotkey += "%s, %s" % (key_names[data.key], key_names[data.chord])
    else:
        hotkey += key_names[data.key]

    return hotkey


def set_kmi_type(kmi, type):
    for map_type in MAP_TYPES:
        try:
            kmi.type = type
            break
        except TypeError:
            kmi.map_type = map_type


class KeymapHelper:

    def __init__(self):
        self.keymap_items = {}
        self.km = None

    def _add_item(self, km, item):
        if km.name not in self.keymap_items:
            self.keymap_items[km.name] = []
        self.keymap_items[km.name].append(item)

    def available(self):
        DBG_INIT and not bpy.context.window_manager.keyconfigs.addon and \
            loge("KH is not available")
        return True if bpy.context.window_manager.keyconfigs.addon else False

    def keymap(self, name="Window", space_type='EMPTY', region_type='WINDOW'):
        keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
        bl_keymaps = bpy.context.window_manager.keyconfigs.default.keymaps

        if name not in keymaps:
            if name in bl_keymaps:
                space_type = bl_keymaps[name].space_type
                region_type = bl_keymaps[name].region_type
            elif name in _keymap_names:
                space_type = _keymap_names[name][0]
                region_type = _keymap_names[name][1]
            keymaps.new(
                name=name, space_type=space_type, region_type=region_type)

        self.km = keymaps[name]

    def menu(
            self, bl_class, hotkey=None,
            key='NONE', ctrl=False, shift=False, alt=False, oskey=False,
            key_mod='NONE'):
        if not self.km:
            return

        if hotkey:
            key, ctrl, shift, alt, oskey, any, key_mod, _ = \
                parse_hotkey(hotkey)

        item = self.km.keymap_items.new(
            'wm.call_menu', key, 'PRESS',
            ctrl=ctrl, shift=shift, alt=alt, oskey=oskey, any=any,
            key_modifier=key_mod)
        item.properties.name = bl_class.bl_idname

        self._add_item(self.km, item)

        return item

    def operator(
            self, bl_class, hotkey=None,
            key='NONE', ctrl=False, shift=False, alt=False, oskey=False,
            key_mod='NONE', any=False, **kwargs):
        if not self.km:
            return

        if hotkey:
            if isinstance(hotkey, str):
                key, ctrl, shift, alt, oskey, any, key_mod, _ = \
                    parse_hotkey(hotkey)
            else:
                key, ctrl, shift, alt, oskey, key_mod = \
                    hotkey.key, hotkey.ctrl, hotkey.shift, hotkey.alt, \
                    hotkey.oskey, hotkey.key_mod

        item = self.km.keymap_items.new(
            bl_class.bl_idname, key, 'PRESS',
            ctrl=ctrl, shift=shift, alt=alt, oskey=oskey, key_modifier=key_mod,
            any=any)

        if bl_class != PME_OT_key_state_init:
            n = len(self.km.keymap_items)
            i = n - 1
            ms_items = []
            keys = []
            while i >= 1 and self.km.keymap_items[i - 1].idname == \
                    PME_OT_key_state_init.bl_idname:
                ms_item = self.km.keymap_items[i - 1]
                ms_items.append(ms_item)
                keys.append(ms_item.type)
                i -= 1

            if ms_items:
                for ms_item in ms_items:
                    self.km.keymap_items.remove(ms_item)

                for key in keys:
                    self.km.keymap_items.new(
                        PME_OT_key_state_init.bl_idname,
                        key, 'PRESS', 1, 1, 1, 1, 1).properties.key = key

        self._add_item(self.km, item)

        for k, v in kwargs.items():
            setattr(item.properties, k, v)

        return item

    def pie(self, bl_class, hotkey=None,
            key='NONE', ctrl=False, shift=False, alt=False, oskey=False,
            key_mod='NONE'):
        if not self.km:
            return

        if hotkey:
            key, ctrl, shift, alt, oskey, any, key_mod, _ = \
                parse_hotkey(hotkey)

        item = self.km.keymap_items.new(
            'wm.call_menu_pie', key, 'PRESS',
            ctrl=ctrl, shift=shift, alt=alt, oskey=oskey, key_modifier=key_mod)
        item.properties.name = bl_class.bl_idname

        self._add_item(self.km, item)

        return item

    def remove(self, item):
        if not self.km:
            return

        keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps

        if self.km.name not in keymaps or \
                self.km.name not in self.keymap_items or \
                item not in self.keymap_items[self.km.name]:
            return

        try:
            keymaps[self.km.name].keymap_items.remove(item)
        except:
            pass

        self.keymap_items[self.km.name].remove(item)

    def unregister(self):
        keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps

        for k, i in self.keymap_items.items():
            if k not in keymaps:
                continue

            for item in i:
                keymaps[k].keymap_items.remove(item)

        self.km = None
        self.keymap_items = None


class Hotkey(DynamicPG):
    lock = False

    def _hotkey_update(self, context):
        if Hotkey.lock:
            return

        if self.hasvar("update"):
            self.getvar("update")(self, context)

        if self.hasvar("kmis"):
            kmis = self.getvar("kmis")
            for kmi in kmis:
                self.to_kmi(kmi)

    key: bpy.props.EnumProperty(
        items=key_items, description="Key pressed", update=_hotkey_update)
    ctrl: bpy.props.BoolProperty(
        description="Ctrl key pressed", update=_hotkey_update)
    shift: bpy.props.BoolProperty(
        description="Shift key pressed", update=_hotkey_update)
    alt: bpy.props.BoolProperty(
        description="Alt key pressed", update=_hotkey_update)
    oskey: bpy.props.BoolProperty(
        description="Operating system key pressed", update=_hotkey_update)
    key_mod: bpy.props.EnumProperty(
        items=key_items,
        description="Regular key pressed as a modifier",
        update=_hotkey_update)

    def add_kmi(self, kmi):
        if not self.hasvar("kmis"):
            self.setvar("kmis", [])
        self.getvar("kmis").append(kmi)
        return kmi

    def draw(self, layout, key=True, key_mod=True, alert=True):
        col = row = layout.column(align=True)
        if key:
            if alert and self.key == 'NONE':
                row = col.row(align=True)
                row.alert = True
            row.prop(self, "key", text="", event=True)
        row = col.row(align=True)
        row.prop(self, "ctrl", text="Ctrl", toggle=True)
        row.prop(self, "shift", text="Shift", toggle=True)
        row.prop(self, "alt", text="Alt", toggle=True)
        row.prop(self, "oskey", text="OSKey", toggle=True)
        if key_mod:
            row.prop(self, "key_mod", text="", event=True)

    def clear(self):
        Hotkey.lock = True
        self.key = 'NONE'
        self.ctrl = False
        self.shift = False
        self.alt = False
        self.oskey = False
        self.key_mod = 'NONE'
        Hotkey.lock = False

    def from_string(self, text):
        Hotkey.lock = True
        self.key, self.ctrl, self.shift, self.alt, self.oskey, self.any, \
            self.key_modifier, _ = parse_hotkey(text)
        Hotkey.lock = False

    def from_kmi(self, kmi):
        Hotkey.lock = True
        self.key = kmi.type
        self.ctrl = kmi.ctrl
        self.shift = kmi.shift
        self.alt = kmi.alt
        self.oskey = kmi.oskey
        self.key_mod = kmi.key_modifier
        Hotkey.lock = False

    def to_string(self):
        return to_hotkey(
            self.key, self.ctrl, self.shift, self.alt, self.oskey,
            self.key_mod)

    def to_kmi(self, kmi):
        set_kmi_type(kmi, self.key)
        kmi.ctrl = self.ctrl
        kmi.shift = self.shift
        kmi.alt = self.alt
        kmi.oskey = self.oskey
        kmi.key_modifier = self.key_mod


class PME_OT_mouse_state(bpy.types.Operator):
    bl_idname = "pme.mouse_state"
    bl_label = ""
    bl_options = {'INTERNAL'}

    inst = None

    cancelled: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def stop(self):
        self.cancelled = True
        self.bl_timer = \
            bpy.context.window_manager.event_timer_add(
                0.1, window=bpy.context.window)

    def modal_stop(self, context):
        if self.bl_timer:
            context.window_manager.event_timer_remove(self.bl_timer)
            self.bl_timer = None

        if self.__class__.inst == self:
            self.__class__.inst = None

        return {'CANCELLED'}

    def modal(self, context, event):
        if event.type in TWEAKS:
            update_mouse_state(self.key)
            return {'PASS_THROUGH'}

        if event.type == 'WINDOW_DEACTIVATE':
            self.stop()
            return {'PASS_THROUGH'}

        if event.value == 'PRESS':
            if event.type == 'ESC':
                return {'CANCELLED'}
            elif event.type != 'MOUSEMOVE' and \
                    event.type != 'INBETWEEN_MOUSEMOVE':
                update_mouse_state(self.key)
                return {'PASS_THROUGH'}

        elif event.value == 'RELEASE':
            if event.type == self.key or event.type == 'WINDOW_DEACTIVATE':
                self.stop()

                if to_system_mouse_key(self.key, context) == 'RIGHTMOUSE':
                    self.key = 'NONE'
                    return {'RUNNING_MODAL'}

                self.key = 'NONE'

        elif event.type == 'TIMER':
            if self.cancelled:
                return self.modal_stop(context)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.__class__.inst = self
        context.window_manager.modal_handler_add(self)

        return {'RUNNING_MODAL'}


class PME_OT_mouse_state_wait(bpy.types.Operator):
    bl_idname = "pme.mouse_state_wait"
    bl_label = ""
    bl_options = {'INTERNAL'}

    inst = None

    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def stop(self):
        self.cancelled = True

    def modal(self, context, event):
        if event.type == 'ESC':
            self.__class__.inst = None
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self.cancelled:
                self.__class__.inst = None
                context.window_manager.event_timer_remove(self.bl_timer)
                self.bl_timer = None
                return {'CANCELLED'}

            bpy.ops.pme.mouse_state('INVOKE_DEFAULT', key=self.key)
            context.window_manager.event_timer_remove(self.bl_timer)
            self.bl_timer = None
            self.__class__.inst = None
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.cancelled = False
        context.window_manager.modal_handler_add(self)
        self.bl_timer = \
            context.window_manager.event_timer_add(
                0.0001, window=context.window)

        self.__class__.inst = self
        return {'RUNNING_MODAL'}


class PME_OT_mouse_state_init(bpy.types.Operator):
    bl_idname = "pme.mouse_state_init"
    bl_label = "Mouse State (PME)"
    bl_options = {'INTERNAL'}

    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if PME_OT_mouse_state.inst:
            if self.key != PME_OT_mouse_state.inst.key:
                return {'PASS_THROUGH'}
            PME_OT_mouse_state.inst.stop()
        if PME_OT_mouse_state_wait.inst:
            if self.key != PME_OT_mouse_state_wait.inst.key:
                return {'PASS_THROUGH'}
            PME_OT_mouse_state_wait.inst.stop()

        bpy.ops.pme.mouse_state_wait('INVOKE_DEFAULT', key=self.key)
        return {'PASS_THROUGH'}


class PME_OT_key_state(bpy.types.Operator):
    bl_idname = "pme.key_state"
    bl_label = ""
    bl_options = {'INTERNAL'}

    inst = None

    cancelled: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def stop(self):
        self.cancelled = True

    def modal_stop(self, context):
        if self.bl_timer:
            context.window_manager.event_timer_remove(self.bl_timer)
            self.bl_timer = None

        if self.__class__.inst == self:
            self.__class__.inst = None

        return {'CANCELLED'}

    def modal(self, context, event):
        # if event.type in TWEAKS:
        #     update_mouse_state(self.key)
        #     return {'PASS_THROUGH'}

        if event.type == 'WINDOW_DEACTIVATE':
            self.stop()
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE' or \
                event.type == 'INBETWEEN_MOUSEMOVE':
            self.active = True
            return {'PASS_THROUGH'}

        # if event.value == 'PRESS':
        #     if event.type == 'ESC':
        #         return {'CANCELLED'}
        #     # elif event.type == 'MOUSEMOVE' or \
        #     #         event.type == 'INBETWEEN_MOUSEMOVE':
        #     #     self.active = True
        #     else:
        #         update_mouse_state(self.key)
        #         return {'PASS_THROUGH'}

        if event.value == 'RELEASE':
            if event.type == self.key:
                self.stop()

                # if to_system_mouse_key(self.key, context) == 'RIGHTMOUSE':
                #     self.key = 'NONE'
                #     return {'RUNNING_MODAL'}

                self.key = 'NONE'

        elif event.type == 'TIMER':
            if self.cancelled:
                return self.modal_stop(context)

            if not self.active:
                bpy.ops.pme.key_state('INVOKE_DEFAULT', key=self.key)
                return self.modal_stop(context)

            context.window.cursor_warp(event.mouse_x, event.mouse_y)
            self.active = False

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.active = True
        self.__class__.inst = self
        self.bl_timer = context.window_manager.event_timer_add(
            0.01, window=bpy.context.window)
        context.window_manager.modal_handler_add(self)

        return {'RUNNING_MODAL'}


class PME_OT_key_state_init(bpy.types.Operator):
    bl_idname = "pme.key_state_init"
    bl_label = "Key State Init (PME)"
    bl_options = {'INTERNAL'}

    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if PME_OT_key_state.inst:
            return {'PASS_THROUGH'}
        bpy.ops.pme.key_state('INVOKE_DEFAULT', key=self.key)
        return {'PASS_THROUGH'}


class PME_OT_mouse_btn_state(bpy.types.Operator, CTU.HeadModalHandler):
    bl_idname = "pme.mouse_btn_state"
    bl_label = "Internal (PME)"
    bl_options = {'REGISTER'}

    inst = None

    def finish(self):
        self.__class__.inst = None

    def invoke(self, context, event):
        cls = self.__class__
        if cls.inst:
            return {'PASS_THROUGH'}

        cls.inst = self

        return self.execute(context)


def is_key_pressed(key):
    ret = PME_OT_mouse_btn_state.inst and \
        PME_OT_mouse_btn_state.inst.key == key
    # ret = PME_OT_key_state.inst and PME_OT_key_state.inst.key == key
    return ret
    # return PME_OT_mouse_state.inst and PME_OT_mouse_state.inst.key == key or \
    #     PME_OT_mouse_state_wait.inst and \
    #     PME_OT_mouse_state_wait.inst.key == key


# def get_pressed_mouse_button():
#     if PME_OT_mouse_state.inst:
#         return PME_OT_mouse_state.inst.key
#     if PME_OT_mouse_state_wait.inst:
#         return PME_OT_mouse_state_wait.inst.key

#     return None


def update_mouse_state(key):
    pass
    # bpy.ops.pme.mouse_state_init('INVOKE_DEFAULT', key=key)


added_mouse_buttons = dict()


def add_mouse_button(key, kh, km="Screen Editing"):
    btn_key = key + km
    if btn_key not in added_mouse_buttons:
        added_mouse_buttons[btn_key] = 0

    added_mouse_buttons[btn_key] += 1

    if added_mouse_buttons[btn_key] == 1:
        kh.keymap(km)
        kh.operator(
            PME_OT_mouse_btn_state,
            # PME_OT_key_state_init,
            # PME_OT_mouse_state_init,
            None, key, 1, 1, 1, 1, any=True).properties.key = key


def remove_mouse_button(key, kh, km="Screen Editing"):
    btn_key = key + km
    if btn_key not in added_mouse_buttons:
        return

    added_mouse_buttons[btn_key] -= 1

    if added_mouse_buttons[btn_key] == 0:
        keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps

        items = kh.keymap_items[km]
        for i, item in enumerate(items):
            if item.type == key and \
                    item.idname == PME_OT_mouse_btn_state.bl_idname:
                keymaps[km].keymap_items.remove(item)
                items.pop(i)
                break


class PME_OT_key_is_pressed(bpy.types.Operator):
    bl_idname = "pme.key_is_pressed"
    bl_label = ""
    bl_options = {'INTERNAL'}

    inst = None
    instance = None
    idx = 1

    key: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def add_timer(self, step=0):
        if self.timer:
            bpy.context.window_manager.event_timer_remove(self.timer)
        self.timer = bpy.context.window_manager.event_timer_add(
            step, window=bpy.context.window)

    def remove_timer(self):
        if self.timer:
            bpy.context.window_manager.event_timer_remove(self.timer)
            self.timer = None

    def stop(self):
        self.finished = True
        self.add_timer()

    def restart(self):
        self.restart_flag = True
        self.add_timer()

    def modal(self, context, event):
        if event.type == 'TIMER' and self.timer:
            if not self.is_pressed and self.timer.time_duration > 0.2:
                if self.instance:
                    self.instance.stop()
                self.stop()
                return {'PASS_THROUGH'}

            if self.finished:
                self.remove_timer()
                self.instance = None

                if PME_OT_key_is_pressed.inst == self:
                    PME_OT_key_is_pressed.inst = None
                return {'FINISHED'}

            elif self.restart_flag:
                self.remove_timer()
                ret = {'FINISHED'}
                if not self.instance:
                    ret = {'PASS_THROUGH'}
                    self.instance = self
                PME_OT_key_is_pressed.instance = self.instance
                bpy.ops.pme.key_is_pressed('INVOKE_DEFAULT', key=self.key)
                PME_OT_key_is_pressed.instance = None
                return ret

            return {'PASS_THROUGH'}

        if self.restart_flag:
            return {'PASS_THROUGH'}

        if event.type == 'WINDOW_DEACTIVATE':
            if self.instance:
                self.instance.stop()
            self.stop()

        elif event.type == 'MOUSEMOVE' or \
                event.type == 'INBETWEEN_MOUSEMOVE':
            return {'PASS_THROUGH'}

        if event.type == self.key:
            if event.value == 'RELEASE':
                if self.instance:
                    self.instance.stop()
                self.stop()

            elif event.value == 'PRESS':
                self.is_pressed = True
                if self.instance and self.timer:
                    self.remove_timer()

            return {'PASS_THROUGH'}

        if event.value != 'ANY' and event.value != 'NOTHING':
            self.restart()
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.idx = self.__class__.idx
        self.__class__.idx += 1
        self.restart_flag = False
        self.instance = PME_OT_key_is_pressed.instance
        self.finished = False
        self.timer = None
        self.is_pressed = True
        if self.instance:
            self.is_pressed = False
            self.add_timer(0.02)
        if not PME_OT_key_is_pressed.inst:
            PME_OT_key_is_pressed.inst = self
        if not self.key:
            if event.value == 'RELEASE':
                return {'FINISHED'}
            self.key = event.type
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def is_pressed(key):
    return PME_OT_key_is_pressed.inst and PME_OT_key_is_pressed.inst.key == key


def mark_pressed(event):
    if PME_OT_key_is_pressed.inst:
        return False

    bpy.ops.pme.key_is_pressed('INVOKE_DEFAULT', key=event.type)


class StackKey:
    name = None
    idx = -1
    cur_idx = -1
    count = -1
    is_first = True
    cur_pm = None
    lo = None
    exec_globals = {}
    operator_mode = False
    sk_states = {}

    @staticmethod
    def _next_pmi(slot=-1):
        pm = StackKey.cur_pm
        num_pmis = len(pm.pmis)

        if slot != -1:
            StackKey.idx = slot
            StackKey.count = 0
            StackKey.lo = None
            StackKey.exec_globals.clear()
            StackKey.exec_globals = pme.context.gen_globals()

        elif StackKey.is_first:
            prop = pme.props.parse(pm.data)
            StackKey.idx = 0
            StackKey.count = 0
            StackKey.lo = None
            StackKey.exec_globals.clear()
            StackKey.exec_globals = pme.context.gen_globals()

            i = 0
            eglobals = StackKey.exec_globals
            while i < num_pmis:
                if pm.pmis[i].mode != 'COMMAND':
                    break

                prop, value = OU.find_statement(pm.pmis[i].text)
                if not prop:
                    break

                try:
                    if eval(prop, eglobals) != eval(value, eglobals):
                        break
                except:
                    print_exc()

                i += 1
                StackKey.idx = i % num_pmis
                StackKey.count += 1
        else:
            StackKey.count += 1
            StackKey.idx += 1
            StackKey.idx %= num_pmis

        if not pm.pmis[StackKey.idx].enabled:
            step = 0
            while not pm.pmis[StackKey.idx].enabled and step < num_pmis:
                StackKey.idx = (StackKey.idx + 1) % num_pmis
                step += 1

        return pm.pmis[StackKey.idx]

    @staticmethod
    def _reset():
        StackKey.name = None
        StackKey.is_first = True
        StackKey.idx = 0
        StackKey.count = 0
        StackKey.lo = None
        StackKey.exec_globals.clear()
        StackKey.exec_globals = pme.context.gen_globals()
        StackKey.operator_mode = False

        return StackKey.cur_pm.pmis[0]

    @staticmethod
    def next(pm=None, slot=-1):
        cpm = pm or StackKey.cur_pm
        StackKey.cur_pm = cpm
        DBG_STACK and logh("Stack Key" + cpm.name)

        lo = 0

        num_pmis = len(cpm.pmis)
        if num_pmis == 0:
            return

        if slot >= num_pmis:
            return

        elif num_pmis == 1:
            pmi = StackKey._reset()

        else:
            StackKey.is_first = pm is not None and cpm.name != StackKey.name

            lo = len(bpy.context.window_manager.operators) and \
                bpy.context.window_manager.operators[-1].as_pointer()

            if not StackKey.is_first and (
                    lo == 0 and StackKey.lo or
                    lo and StackKey.lo and lo != StackKey.lo):
                StackKey.is_first = True

            StackKey.name = cpm.name
            prop = pme.props.parse(cpm.data)
            if StackKey.is_first:
                StackKey.operator_mode = prop.s_undo

            if not StackKey.is_first and StackKey.operator_mode and \
                    StackKey.cur_idx == -1:
                if not lo or not StackKey.lo or lo != StackKey.lo:
                    StackKey.is_first = True
                elif not selection_state.check():
                    StackKey.is_first = True

            if prop.s_state:
                if cpm.name in StackKey.sk_states:
                    StackKey.is_first = False
                    StackKey.idx = StackKey.sk_states[cpm.name]

            pmi = StackKey._next_pmi(slot)
            if prop.s_state:
                StackKey.sk_states[cpm.name] = StackKey.idx

            DBG_STACK and logh(
                "STACK: %s (OpM: %d, 1st: %d, i: %d, c: %d, ci: %d) %s" % (
                    cpm.name, StackKey.operator_mode, StackKey.is_first,
                    StackKey.idx, StackKey.count, StackKey.cur_idx, pmi.name
                ))
            DBG_STACK and logi("AO: %s, LO: %s" % (str(lo), str(StackKey.lo)))

        try:
            if slot == -1 and num_pmis > 1 and \
                    prop.s_undo and not StackKey.is_first and pm:
                bpy.ops.ed.undo()

            cur_idx = StackKey.idx
            if StackKey.cur_idx == -1:
                StackKey.cur_idx = cur_idx
            elif StackKey.cur_idx == cur_idx:
                raise StopIteration()

            if pmi.mode == 'HOTKEY':
                run_operator_by_hotkey(bpy.context, pmi.text)
            elif pmi.mode == 'COMMAND':
                StackKey.exec_globals.update(menu=cpm.name, slot=pmi.name)
                pme.context.exe(
                    OU.add_default_args(pmi.text),
                    StackKey.exec_globals)

            if StackKey.idx == cur_idx and len(cpm.pmis) > 1:
                selection_state.update()
                if slot == -1:
                    bpy.ops.pme.overlay('INVOKE_DEFAULT', text=pmi.name)

        except:
            print_exc()

        StackKey.cur_idx = -1

        StackKey.lo = len(bpy.context.window_manager.operators) and \
            bpy.context.window_manager.operators[-1].as_pointer()
        if lo != 0 and not StackKey.operator_mode:
            if StackKey.lo and lo != StackKey.lo:
                StackKey.operator_mode = True

        return True


def register():
    pme.context.add_global("SK", StackKey)
    pme.context.add_global("call_operator", call_operator)
