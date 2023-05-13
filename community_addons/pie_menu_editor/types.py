import bpy
from . import bl_utils as BU
from . import constants as CC
from . import ui_utils as UU
from . import panel_utils as PAU
from . import macro_utils as MAU
from . import utils as U
from .addon import prefs, temp_prefs, ic_fb
from . import keymap_helper as KH
from . import pme
from .ui import tag_redraw
from .pme import props as pp
from .operators import WM_OT_pme_user_pie_menu_call


class UserProperties(bpy.types.PropertyGroup):
    pass


class EdProperties(bpy.types.PropertyGroup):
    pass


class Tag(bpy.types.PropertyGroup):
    filtered_pms = None

    @staticmethod
    def popup_menu(
            idname, title="", icon='NONE',
            untagged=True, invoke=False, **kwargs):
        def draw_menu(menu, context):
            tpr = temp_prefs()
            layout = menu.layout
            if invoke:
                layout.operator_context = 'INVOKE_DEFAULT'
            for t in tpr.tags:
                p = layout.operator(idname, text=t.name, icon=ic_fb(True))
                p.tag = t.name
                for k, v in kwargs.items():
                    setattr(p, k, v)

            if untagged:
                if tpr.tags:
                    layout.separator()
                p = layout.operator(
                    idname, text=CC.UNTAGGED, icon=ic_fb(False))
                p.tag = CC.UNTAGGED
                for k, v in kwargs.items():
                    setattr(p, k, v)

        bpy.context.window_manager.popup_menu(
            draw_menu, title=title, icon=icon)

    @staticmethod
    def filter():
        pr = prefs()
        tpr = temp_prefs()
        if not tpr.tags or not pr.tag_filter:
            Tag.filtered_pms = None
            return
        elif Tag.filtered_pms is None:
            Tag.filtered_pms = set()
        else:
            Tag.filtered_pms.clear()

        for pm in pr.pie_menus:
            if pm.has_tag(pr.tag_filter):
                Tag.filtered_pms.add(pm.name)

    @staticmethod
    def check_pm(pm):
        return Tag.filtered_pms is None or pm.name in Tag.filtered_pms


class PMLink(bpy.types.PropertyGroup):
    pm_name: bpy.props.StringProperty()
    is_folder: bpy.props.BoolProperty()
    label: bpy.props.StringProperty()
    folder: bpy.props.StringProperty()
    group: bpy.props.StringProperty()

    idx = 0
    paths = {}

    @staticmethod
    def add():
        link = temp_prefs().links.add()
        link.name = str(PMLink.idx)
        PMLink.idx += 1
        return link

    @staticmethod
    def clear():
        PMLink.idx = 0
        PMLink.paths.clear()

    def __getattr__(self, attr):
        if attr == "path":
            if self.name not in PMLink.paths:
                PMLink.paths[self.name] = []
            return PMLink.paths[self.name]

    def __str__(self):
        return "%s [%s] (%r) (%s)" % (
            self.pm_name, "/".join(self.path), self.is_folder, self.label)

    def curpath(self):
        ret = self.group + CC.TREE_SPLITTER
        ret += CC.TREE_SPLITTER.join(self.path)
        return ret

    def fullpath(self):
        ret = self.group + CC.TREE_SPLITTER
        ret += CC.TREE_SPLITTER.join(self.path)
        if self.is_folder:
            if self.path:
                ret += CC.TREE_SPLITTER
            ret += self.pm_name
        return ret


class PMIItem(bpy.types.PropertyGroup):
    expandable_props = {}

    mode: bpy.props.EnumProperty(
        items=CC.MODE_ITEMS, description="Type of the item")
    text: bpy.props.StringProperty(maxlen=CC.MAX_STR_LEN)
    icon: bpy.props.StringProperty(description="Icon")
    enabled: bpy.props.BoolProperty(
        name="Enable/Disable",
        description="Enable/Disable", default=True)

    def get_pmi_label(self):
        return self.name

    def set_pmi_label(self, value):
        if self.name == value:
            return

        pm = prefs().selected_pm
        pm.ed.on_pmi_rename(pm, self, self.name, value)

    label: bpy.props.StringProperty(
        description="Label", get=get_pmi_label, set=set_pmi_label)

    @property
    def rm_class(self):
        value = self.text.replace(CC.F_EXPAND, "")
        return UU.get_pme_menu_class(value)

    def from_dict(self, value):
        pass

    def to_dict(self):
        return {k: self[k] for k in self.keys()}

    def flags(self, data=None):
        if data is None:
            return int(not self.enabled and CC.PMIF_DISABLED)

        self.enabled = not bool(data & CC.PMIF_DISABLED)

    def parse(self, default_icon='NONE'):
        icon, icon_only, hidden, use_cb = self.extract_flags()
        oicon = icon
        text = self.name

        if icon_only:
            text = ""
        if hidden:
            icon = 'NONE' if not icon or not icon_only else 'BLANK1'
            if text:
                text = " " * len(text)
        elif not icon:
            icon = default_icon

        if not hidden:
            if self.mode == 'PROP':
                bl_prop = BU.bp.get(
                    self.prop if hasattr(self, "prop") else self.text)
                if bl_prop:
                    if bl_prop.type in {'STRING', 'ENUM', 'POINTER'}:
                        text = ""
                    if bl_prop.type in {'FLOAT', 'INT', 'BOOLEAN'} and len(
                            bl_prop.default_array) > 1:
                        text = ""

            if icon[0] != CC.F_EXPAND and icon not in CC.BL_ICONS:
                icon = 'CANCEL'

        return text, icon, oicon, icon_only, hidden, use_cb

    def parse_edit(self):
        text, icon, oicon, icon_only, hidden, use_cb = self.parse()

        if not text and not hidden:
            if self.mode == 'PROP' and (
                    self.is_expandable_prop() or icon == 'NONE'):
                if icon_only:
                    text = "[%s]" % self.name if self.name else " "
                else:
                    text = self.name if self.name else " "

        return text, icon, oicon, icon_only, hidden, use_cb

    def extract_flags(self):
        icon, icon_only, hidden, use_cb = U.extract_str_flags(
            self.icon, CC.F_ICON_ONLY, CC.F_HIDDEN, CC.F_CB)
        return icon, icon_only, hidden, use_cb

    def parse_icon(self, default_icon='NONE'):
        icon = self.extract_flags()[0]
        if not icon:
            return default_icon

        if icon[0] != CC.F_EXPAND and icon not in CC.BL_ICONS:
            return 'CANCEL'

        if icon == 'NONE':
            icon = default_icon

        return icon

    def is_expandable_prop(self):
        if self.mode != 'PROP':
            return False

        prop = self.text
        if prop in self.expandable_props:
            return self.expandable_props[prop]

        value = None
        try:
            value = eval(prop, pme.context.globals)
        except:
            return False

        self.expandable_props[prop] = not isinstance(value, bool)

        return self.expandable_props[prop]


class PMItem(bpy.types.PropertyGroup):
    poll_methods = {}
    kmis_map = {}

    @property
    def selected_pmi(self):
        return self.pmis[pme.context.edit_item_idx]

    @staticmethod
    def _parse_keymap(km_name, exists=True, splitter=None):
        names = []
        keymaps = bpy.context.window_manager.keyconfigs.user.keymaps
        if splitter is None:
            splitter = CC.KEYMAP_SPLITTER

        for name in km_name.split(splitter):
            name = name.strip()
            if not name:
                continue

            name_in_keymaps = name in keymaps
            if exists and not name_in_keymaps or \
                    not exists and name_in_keymaps:
                continue

            names.append(name)

        if exists and not names:
            names.append("Window")

        return names

    def parse_keymap(self, exists=True, splitter=None):
        return PMItem._parse_keymap(self.km_name, exists, splitter)

    def get_pm_km_name(self):
        if "km_name" not in self:
            self["km_name"] = "Window"
        return self["km_name"]

    def set_pm_km_name(self, value):
        if not self.ed.has_hotkey:
            self["km_name"] = value
            return

        if not value:
            value = "Window"
        else:
            value = (CC.KEYMAP_SPLITTER + " ").join(
                PMItem._parse_keymap(value))

        if "km_name" not in self or self["km_name"] != value:
            if "km_name" in self:
                self.unregister_hotkey()

            self["km_name"] = value
            self.register_hotkey()

        prefs().update_tree()

    km_name: bpy.props.StringProperty(
        default="Window", description="Keymap names",
        get=get_pm_km_name, set=set_pm_km_name)

    def get_pm_name(self):
        return self.name

    def set_pm_name(self, value):
        pr = prefs()

        value = value.replace(CC.F_EXPAND, "")

        if value == self.name or not value:
            return

        if value in pr.pie_menus:
            value = pr.unique_pm_name(value)

        self.ed.on_pm_rename(self, value)

    label: bpy.props.StringProperty(
        get=get_pm_name, set=set_pm_name, description="Menu name")

    pmis: bpy.props.CollectionProperty(type=PMIItem)
    mode: bpy.props.EnumProperty(items=CC.PM_ITEMS)
    tag: bpy.props.StringProperty()

    def update_keymap_item(self, context):
        if not self.ed.has_hotkey:
            return

        pr = prefs()
        kmis = self.kmis_map[self.name]

        if kmis:
            for k, kmi in kmis.items():
                KH.set_kmi_type(kmi, self.key)

                if self.any:
                    kmi.any = self.any
                else:
                    kmi.ctrl = self.ctrl
                    kmi.shift = self.shift
                    kmi.alt = self.alt
                    kmi.oskey = self.oskey

                kmi.key_modifier = self.key_mod
                kmi.value = \
                    'DOUBLE_CLICK' if self.open_mode == 'DOUBLE_CLICK' \
                    else 'PRESS'

                if self.key == 'NONE' or not self.enabled:
                    if pr.kh.available():
                        pr.kh.keymap(k)
                        pr.kh.remove(kmi)

            if self.key == 'NONE' or not self.enabled:
                self.kmis_map[self.name] = None
        else:
            self.register_hotkey()

    def get_key(self):
        return self.get("key", 0)

    def set_key(self, value):
        if self.get("key", 0) == value:
            return

        self["key"] = value
        self.update_keymap_item(bpy.context)

        pr = prefs()
        if pr.group_by == 'KEY':
            pr.tree.update()

    def update_open_mode(self, context):
        if self.open_mode == 'CHORDS' and self.chord == 'NONE':
            self.chord = 'A'
        if self.open_mode != 'CHORDS' and self. chord != 'NONE':
            self.chord = 'NONE'

        self.update_keymap_item(context)

    open_mode: bpy.props.EnumProperty(
        name="Hotkey Mode",
        items=CC.OPEN_MODE_ITEMS,
        update=update_open_mode)
    key: bpy.props.EnumProperty(
        items=KH.key_items,
        description="Key pressed",
        get=get_key, set=set_key)

    chord: bpy.props.EnumProperty(
        items=KH.key_items,
        description="Chord pressed")
    any: bpy.props.BoolProperty(
        description="Any key pressed", update=update_keymap_item)
    ctrl: bpy.props.BoolProperty(
        description="Ctrl key pressed", update=update_keymap_item)
    shift: bpy.props.BoolProperty(
        description="Shift key pressed", update=update_keymap_item)
    alt: bpy.props.BoolProperty(
        description="Alt key pressed", update=update_keymap_item)
    oskey: bpy.props.BoolProperty(
        description="Operating system key pressed", update=update_keymap_item)

    def get_pm_key_mod(self):
        return self["key_mod"] if "key_mod" in self else 0

    def set_pm_key_mod(self, value):
        pr = prefs()
        prev_value = self.key_mod
        self["key_mod"] = value
        value = self.key_mod

        if prev_value == value or not self.enabled:
            return

        kms = self.parse_keymap()
        if prev_value != 'NONE' and prev_value in KH.MOUSE_BUTTONS:
            for km in kms:
                KH.remove_mouse_button(prev_value, pr.kh, km)

        if value != 'NONE' and value in KH.MOUSE_BUTTONS:
            for km in kms:
                KH.add_mouse_button(value, pr.kh, km)

    key_mod: bpy.props.EnumProperty(
        items=KH.key_items,
        description="Regular key pressed as a modifier",
        get=get_pm_key_mod, set=set_pm_key_mod)

    def get_pm_enabled(self):
        if "enabled" not in self:
            self["enabled"] = True
        return self["enabled"]

    def set_pm_enabled(self, value):
        if "enabled" in self and self["enabled"] == value:
            return

        self["enabled"] = value

        self.ed.on_pm_enabled(self, value)

    enabled: bpy.props.BoolProperty(
        description="Enable or disable the menu",
        default=True,
        get=get_pm_enabled, set=set_pm_enabled)

    def update_poll_cmd(self, context):
        if self.poll_cmd == CC.DEFAULT_POLL:
            self.poll_methods.pop(self.name, None)
        else:
            try:
                co = compile(
                    "def poll(cls, context):" + self.poll_cmd,
                    "<string>", "exec")
                self.poll_methods[self.name] = co
            except:
                self.poll_methods[self.name] = None

    poll_cmd: bpy.props.StringProperty(
        description=(
            "Poll method\nTest if the item can be called/displayed or not"),
        default=CC.DEFAULT_POLL, maxlen=CC.MAX_STR_LEN, update=update_poll_cmd)
    data: bpy.props.StringProperty(maxlen=CC.MAX_STR_LEN)

    def update_panel_group(self):
        self.ed.update_panel_group(self)

    def get_panel_context(self):
        prop = pp.parse(self.data)
        for item in PAU.panel_context_items(self, bpy.context):
            if item[0] == prop.pg_context:
                return item[4]
        return 0

    def set_panel_context(self, value):
        value = PAU.panel_context_items(self, bpy.context)[value][0]
        prop = pp.parse(self.data)
        if prop.pg_context == value:
            return
        self.data = pp.encode(self.data, "pg_context", value)
        self.update_panel_group()

    panel_context: bpy.props.EnumProperty(
        items=PAU.panel_context_items,
        name="Context",
        description="Panel context",
        get=get_panel_context, set=set_panel_context)

    def get_panel_category(self):
        prop = pp.parse(self.data)
        return prop.pg_category

    def set_panel_category(self, value):
        prop = pp.parse(self.data)
        if prop.pg_category == value:
            return
        self.data = pp.encode(self.data, "pg_category", value)
        self.update_panel_group()

    panel_category: bpy.props.StringProperty(
        default="", description="Panel category (tab)",
        get=get_panel_category, set=set_panel_category)

    def get_panel_region(self):
        prop = pp.parse(self.data)
        for item in CC.REGION_ITEMS:
            if item[0] == prop.pg_region:
                return item[4]
        return 0

    def set_panel_region(self, value):
        value = CC.REGION_ITEMS[value][0]
        prop = pp.parse(self.data)
        if prop.pg_region == value:
            return
        self.data = pp.encode(self.data, "pg_region", value)
        self.update_panel_group()

    panel_region: bpy.props.EnumProperty(
        items=CC.REGION_ITEMS,
        name="Region",
        description="Panel region",
        get=get_panel_region, set=set_panel_region)

    def get_panel_space(self):
        prop = pp.parse(self.data)
        for item in CC.SPACE_ITEMS:
            if item[0] == prop.pg_space:
                return item[4]
        return 0

    def set_panel_space(self, value):
        value = CC.SPACE_ITEMS[value][0]
        prop = pp.parse(self.data)
        if prop.pg_space == value:
            return
        self.data = pp.encode(self.data, "pg_space", value)
        self.update_panel_group()

    panel_space: bpy.props.EnumProperty(
        items=CC.SPACE_ITEMS,
        name="Space",
        description="Panel space",
        get=get_panel_space, set=set_panel_space)

    panel_wicons: bpy.props.BoolProperty(
        name="Use Wide Icon Buttons",
        description="Use wide icon buttons",
        get=lambda s: s.get_data("pg_wicons"),
        set=lambda s, v: s.set_data("pg_wicons", v))

    pm_radius: bpy.props.IntProperty(
        subtype='PIXEL',
        description="Radius of the pie menu (-1 - use default value)",
        get=lambda s: s.get_data("pm_radius"),
        set=lambda s, v: s.set_data("pm_radius", v),
        default=-1, step=10, min=-1, max=1000)
    pm_threshold: bpy.props.IntProperty(
        subtype='PIXEL',
        description=(
            "Distance from center needed "
            "before a selection can be made(-1 - use default value)"),
        get=lambda s: s.get_data("pm_threshold"),
        set=lambda s, v: s.set_data("pm_threshold", v),
        default=-1, step=10, min=-1, max=1000)
    pm_confirm: bpy.props.IntProperty(
        subtype='PIXEL',
        description=(
            "Distance threshold after which selection is made "
            "(-1 - use default value)"),
        get=lambda s: s.get_data("pm_confirm"),
        set=lambda s, v: s.set_data("pm_confirm", v),
        default=-1, step=10, min=-1, max=1000)
    pm_flick: bpy.props.BoolProperty(
        name="Confirm on Release",
        description="Confirm selection when releasing the hotkey",
        get=lambda s: s.get_data("pm_flick"),
        set=lambda s, v: s.set_data("pm_flick", v))
    pd_title: bpy.props.BoolProperty(
        name="Show Title", description="Show title",
        get=lambda s: s.get_data("pd_title"),
        set=lambda s, v: s.set_data("pd_title", v))
    pd_box: bpy.props.BoolProperty(
        name="Use Frame", description="Use a frame",
        get=lambda s: s.get_data("pd_box"),
        set=lambda s, v: s.set_data("pd_box", v))
    pd_auto_close: bpy.props.BoolProperty(
        name="Auto Close on Mouse Out", description="Auto close on mouse out",
        get=lambda s: s.get_data("pd_auto_close"),
        set=lambda s, v: s.set_data("pd_auto_close", v))
    pd_expand: bpy.props.BoolProperty(
        name="Expand Sub Popup Dialogs",
        description=(
            "Expand all sub popup dialogs "
            "instead of using them as a button"),
        get=lambda s: s.get_data("pd_expand"),
        set=lambda s, v: s.set_data("pd_expand", v))
    pd_panel: bpy.props.EnumProperty(
        name="Mode", description="Popup dialog mode",
        items=CC.PD_MODE_ITEMS,
        get=lambda s: s.get_data("pd_panel"),
        set=lambda s, v: s.set_data("pd_panel", v))
    pd_width: bpy.props.IntProperty(
        name="Width", description="Width of the popup",
        subtype='PIXEL',
        get=lambda s: s.get_data("pd_width"),
        set=lambda s, v: s.set_data("pd_width", v),
        min=100, max=2000)
    rm_title: bpy.props.BoolProperty(
        name="Show Title", description="Show title",
        get=lambda s: s.get_data("rm_title"),
        set=lambda s, v: s.set_data("rm_title", v))
    # s_scroll: bpy.props.BoolProperty(
    #     description="Use both WheelUp and WheelDown hotkeys",
    #     get=lambda s: s.get_data("s_scroll"),
    #     set=lambda s, v: s.set_data("s_scroll", v),
    #     update=update_keymap_item)
    sk_block_ui: bpy.props.BoolProperty(
        name="Block UI",
        description=(
            "Block other tools, while the Sticky Key is active.\n"
            "Useful when the Sticky Key is a part of Macro Operator."
        ),
        get=lambda s: s.get_data("sk_block_ui"),
        set=lambda s, v: s.set_data("sk_block_ui", v))
    mo_confirm_on_release: bpy.props.BoolProperty(
        name="Confirm On Release",
        description="Confirm on release",
        get=lambda s: s.get_data("confirm"),
        set=lambda s, v: s.set_data("confirm", v))
    mo_block_ui: bpy.props.BoolProperty(
        name="Block UI",
        description="Block other hotkeys",
        get=lambda s: s.get_data("block_ui"),
        set=lambda s, v: s.set_data("block_ui", v))

    def mo_lock_update(self, context):
        for pm in prefs().pie_menus:
            if pm.mode == 'MACRO':
                for pmi in pm.pmis:
                    menu_name, *_ = U.extract_str_flags(
                        pmi.text, CC.F_EXPAND, CC.F_EXPAND)
                    if menu_name == self.name:
                        MAU.update_macro(pm)

    mo_lock: bpy.props.BoolProperty(
        name="Lock Mouse",
        description="Lock the mouse in the current area",
        get=lambda s: s.get_data("lock"),
        set=lambda s, v: s.set_data("lock", v),
        update=mo_lock_update)

    def poll(self, cls=None, context=None):
        if self.poll_cmd == CC.DEFAULT_POLL:
            return True

        if self.name not in self.poll_methods:
            self.update_poll_cmd(bpy.context)

        poll_method_co = self.poll_methods[self.name]
        if poll_method_co is None:
            return True

        exec_globals = pme.context.gen_globals()
        exec_globals.update(menu=self.name)
        if not pme.context.exe(poll_method_co, exec_globals):
            return True

        BU.bl_context.reset(bpy.context)
        return exec_globals["poll"](cls, BU.bl_context)

    @property
    def is_new(self):
        return self.name not in prefs().old_pms

    def register_hotkey(self, km_names=None):
        pr = prefs()
        if self.name not in self.kmis_map:
            self.kmis_map[self.name] = None

        if self.key == 'NONE' or not self.enabled:
            return

        if pr.kh.available():
            if km_names is None:
                km_names = self.parse_keymap()

            if self.ed.use_scroll(self):
                keys = ('WHEELUPMOUSE', 'WHEELDOWNMOUSE')
            else:
                keys = (self.key,)

            for key in keys:
                for km_name in km_names:
                    pr.kh.keymap(km_name)
                    kmi = pr.kh.operator(
                        WM_OT_pme_user_pie_menu_call,
                        None,  # hotkey
                        key, self.ctrl, self.shift, self.alt, self.oskey,
                        'NONE' if self.key_mod in KH.MOUSE_BUTTONS else \
                        self.key_mod,
                        self.any
                    )

                    kmi.properties.pie_menu_name = self.name
                    kmi.properties.invoke_mode = 'HOTKEY'
                    kmi.properties.keymap = km_name

                    kmi.value = \
                        'DOUBLE_CLICK' if self.open_mode == 'DOUBLE_CLICK' \
                        else 'PRESS'

                    if self.kmis_map[self.name]:
                        self.kmis_map[self.name][km_name] = kmi
                    else:
                        self.kmis_map[self.name] = {km_name: kmi}

                    if self.key_mod in KH.MOUSE_BUTTONS:
                        KH.add_mouse_button(self.key_mod, pr.kh, km_name)

    def unregister_hotkey(self):
        pr = prefs()
        if pr.kh.available() and self.name in self.kmis_map and \
                self.kmis_map[self.name]:
            for k, v in self.kmis_map[self.name].items():
                pr.kh.keymap(k)
                if isinstance(v, list):
                    for kmi in v:
                        pr.kh.remove(kmi)
                else:
                    pr.kh.remove(v)

                if self.key_mod in KH.MOUSE_BUTTONS:
                    KH.remove_mouse_button(self.key_mod, pr.kh, k)

        if self.name in self.kmis_map:
            del self.kmis_map[self.name]

    def filter_by_mode(self, pr):
        return self.mode in pr.mode_filter

    def filter_list(self, pr):
        return self.filter_by_mode(pr) and (
            not pr.show_only_new_pms or self.is_new) and Tag.check_pm(self)

    def has_tag(self, tag):
        if not self.tag:
            return tag == CC.UNTAGGED
        tags = {t.strip() for t in self.tag.split(",")}
        return tag in tags

    def get_tags(self):
        if not self.tag:
            return None
        return [t.strip() for t in self.tag.split(",")]

    def add_tag(self, tag):
        tag = tag.strip()
        if not tag or tag == CC.UNTAGGED:
            return

        if self.tag:
            tags = {t.strip() for t in self.tag.split(",")}
        else:
            tags = set()
        tags.add(tag)
        self.tag = ", ".join(sorted(tags))

    def remove_tag(self, tag):
        if not self.tag:
            return False
        tags = {t.strip() for t in self.tag.split(",")}
        tags.discard(tag)
        self.tag = ", ".join(sorted(tags))

    def from_dict(self, value):
        pass

    def to_dict(self):
        d = {}
        return d

    def to_hotkey(self, use_key_names=False):
        return KH.to_hotkey(
            self.key, self.ctrl, self.shift, self.alt, self.oskey,
            self.key_mod, self.any, use_key_names=use_key_names,
            chord=self.chord)

    def get_data(self, key):
        value = getattr(pp.parse(self.data), key)
        return value

    def set_data(self, key, value):
        self.data = pp.encode(self.data, key, value)

    def clear_data(self, *args):
        self.data = pp.clear(self.data, *args)

    @property
    def ed(self):
        return prefs().ed(self.mode)

    def __str__(self):
        return "[%s][%s][%s] %s" % (
            "V" if self.enabled else " ",
            self.mode, self.to_hotkey(), self.label
        )

