import bpy
import addon_utils
from bpy.app.handlers import persistent
from .addon import ADDON_ID, prefs, uprefs, is_28
from .bl_utils import PopupOperator, popup_area, ctx_dict, area_header_text_set
from .panel_utils import panel, panel_label, bl_panel_enum_items
from .constants import (
    PME_TEMP_SCREEN, PME_SCREEN, MAX_STR_LEN,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
)
from . import constants as CC
from . import c_utils as CTU
from . import screen_utils as SU
from .layout_helper import lh, split
from . import pme
from . import operator_utils


class PME_OT_dummy(bpy.types.Operator):
    bl_idname = "pme.dummy"
    bl_label = ""
    bl_options = {'INTERNAL', 'REGISTER', 'UNDO'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return {'FINISHED'}


class PME_OT_modal_dummy(bpy.types.Operator):
    bl_idname = "pme.modal_dummy"
    bl_label = "Dummy Modal"

    message: bpy.props.StringProperty(
        name="Message", options={'SKIP_SAVE'},
        default="OK: Enter/LClick, Cancel: Esc/RClick)")

    def modal(self, context, event):
        if event.value == 'PRESS':
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                area_header_text_set()
                return {'CANCELLED'}
            elif event.type in {'RET', 'LEFTMOUSE'}:
                area_header_text_set()
                return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        area_header_text_set(self.message)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class PME_OT_none(bpy.types.Operator):
    bl_idname = "pme.none"
    bl_label = ""
    bl_options = {'INTERNAL'}

    pass_through: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        return {'PASS_THROUGH' if self.pass_through else 'CANCELLED'}

    def invoke(self, context, event):
        return {'PASS_THROUGH' if self.pass_through else 'CANCELLED'}


class WM_OT_pme_sidebar_toggle(bpy.types.Operator):
    bl_idname = "wm.pme_sidebar_toggle"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    tools: bpy.props.BoolProperty()

    def execute(self, context):
        SU.toggle_sidebar(tools=self.tools)
        return {'FINISHED'}


class PME_OT_sidebar_toggle(bpy.types.Operator):
    bl_idname = "pme.sidebar_toggle"
    bl_label = "Toggle Sidebar"
    bl_description = "Toggle sidebar"

    sidebar: bpy.props.EnumProperty(
        name="Sidebar", description="Sidebar",
        items=(
            ('TOOLS', "Tools", "", 'PREFERENCES', 0),
            ('PROPERTIES', "Properties", "", 'BUTS', 1),
        ),
        options={'SKIP_SAVE'})

    action: bpy.props.EnumProperty(
        name="Action", description="Action",
        items=(
            ('TOGGLE', "Toggle", ""),
            ('SHOW', "Show", ""),
            ('HIDE', "Hide", ""),
        ),
        options={'SKIP_SAVE'}
    )

    def execute(self, context):
        value = None
        if self.action == 'SHOW':
            value = True
        elif self.action == 'HIDE':
            value = False

        SU.toggle_sidebar(
            tools=self.sidebar == 'TOOLS',
            value=value)

        return {'FINISHED'}


class PME_OT_screen_set(bpy.types.Operator):
    bl_idname = "pme.screen_set"
    bl_label = "Set Screen/Workspace By Name"

    name: bpy.props.StringProperty(
        name="Screen Layout/Workspace Name",
        description="Screen layout/workspace name")

    def execute(self, context):
        if self.name not in bpy.data.workspaces:
            return {'CANCELLED'}

        if context.screen.show_fullscreen:
            bpy.ops.screen.back_to_previous()

        if context.screen.show_fullscreen:
            bpy.ops.screen.back_to_previous()

        context.window.workspace = bpy.data.workspaces[self.name]

        return {'FINISHED'}


class PME_OT_popup_property(PopupOperator, bpy.types.Operator):
    bl_idname = "pme.popup_property"
    bl_label = "Property"
    bl_description = "Edit property"
    bl_options = {'INTERNAL'}

    path: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw(self, context):
        super().draw(context)
        lh.lt(self.layout)
        obj, sep, prop = self.path.rpartition(".")
        if sep:
            obj = pme.context.eval(obj)
            if obj:
                lh.prop_compact(obj, prop)


class PME_OT_popup_user_preferences(PopupOperator, bpy.types.Operator):
    bl_idname = "pme.popup_user_preferences"
    bl_label = "User Preferences"
    bl_description = "Open the user preferences in a popup"
    bl_options = {'INTERNAL'}

    tab: bpy.props.EnumProperty(
        name="Tab", description="Tab", options={'SKIP_SAVE'},
        items=(
            ('CURRENT', "Current", ""),
            ('INTERFACE', "Interface", ""),
            ('EDITING', "Editing", ""),
            ('INPUT', "Input", ""),
            ('ADDONS', "Add-ons", ""),
            ('THEMES', "Themes", ""),
            ('FILES', "File", ""),
            ('SYSTEM', "System", ""),
        ))
    width: bpy.props.IntProperty(
        name="Width", description="Width of the popup",
        default=800, options={'SKIP_SAVE'})
    center: bpy.props.BoolProperty(
        name="Center", description="Center",
        default=True, options={'SKIP_SAVE'})

    def draw(self, context):
        PopupOperator.draw(self, context)

        upr = uprefs()
        col = self.layout.column(align=True)
        col.row(align=True).prop(
            upr, "active_section", expand=True)

        if upr.active_section == 'INTERFACE':
            tp = bpy.types.USERPREF_PT_interface
        elif upr.active_section == 'EDITING':
            tp = bpy.types.USERPREF_PT_edit
        elif upr.active_section == 'INPUT':
            tp = bpy.types.USERPREF_PT_input
        elif upr.active_section == 'ADDONS':
            tp = bpy.types.USERPREF_PT_addons
        elif upr.active_section == 'THEMES':
            tp = bpy.types.USERPREF_PT_theme
        elif upr.active_section == 'FILES':
            tp = bpy.types.USERPREF_PT_file
        elif upr.active_section == 'SYSTEM':
            tp = getattr(bpy.types, "USERPREF_PT_system", None) or \
                getattr(bpy.types, "USERPREF_PT_system_general", None)

        pme.context.layout = col
        panel(tp, frame=True, header=False, poll=False)

    def invoke(self, context, event):
        if self.tab != 'CURRENT':
            try:
                uprefs().active_section = self.tab
            except:
                pass

        return PopupOperator.invoke(self, context, event)


class PME_OT_popup_addon_preferences(PopupOperator, bpy.types.Operator):
    bl_idname = "pme.popup_addon_preferences"
    bl_label = "Addon Preferences"
    bl_description = "Open the addon preferences in a popup"
    bl_options = {'INTERNAL'}

    addon: bpy.props.StringProperty(
        name="Add-on", description="Add-on", options={'SKIP_SAVE'})
    width: bpy.props.IntProperty(
        name="Width", description="Width of the popup",
        default=800, options={'SKIP_SAVE'})
    center: bpy.props.BoolProperty(
        default=True, name="Center", description="Center",
        options={'SKIP_SAVE'})
    auto_close: bpy.props.BoolProperty(
        default=False, name="Auto Close",
        description="Auto close the popup", options={'SKIP_SAVE'})

    def draw(self, context):
        title = None
        if self.auto_close:
            mod = addon_utils.addons_fake_modules.get(self.addon)
            if not mod:
                return
            info = addon_utils.module_bl_info(mod)
            title = info["name"]

        PopupOperator.draw(self, context, title)

        addon_prefs = None
        for addon in uprefs().addons:
            if addon.module == self.addon:
                addon_prefs = addon.preferences
                break

        if addon_prefs and hasattr(addon_prefs, "draw"):
            col = self.layout.column(align=True)
            addon_prefs.layout = col.box()
            addon_prefs.draw(context)
            addon_prefs.layout = None

            row = col.row(align=True)
            row.operator_context = 'INVOKE_DEFAULT'
            row.operator("wm.save_userpref")

    def invoke(self, context, event):
        if not self.addon:
            self.addon = ADDON_ID
        return PopupOperator.invoke(self, context, event)


class PME_OT_popup_panel(PopupOperator, bpy.types.Operator):
    bl_idname = "pme.popup_panel"
    bl_label = "Pie Menu Editor"
    bl_description = "Open the panel in a popup"
    bl_options = {'INTERNAL'}

    panel: bpy.props.StringProperty(
        name="Panel(s)",
        description=(
            "Comma/semicolon separated panel ID(s).\n"
            "  Use a semicolon to add columns.\n"
        ),
        options={'SKIP_SAVE'})
    frame: bpy.props.BoolProperty(
        name="Frame", description="Frame",
        default=True, options={'SKIP_SAVE'})
    header: bpy.props.BoolProperty(
        name="Header", description="Header",
        default=True, options={'SKIP_SAVE'})
    area: bpy.props.EnumProperty(
        name="Area Type", description="Area type",
        items=CC.area_type_enum_items(), options={'SKIP_SAVE'})
    width: bpy.props.IntProperty(
        name="Width", description="Width of the popup",
        default=-1, options={'SKIP_SAVE'})

    def draw(self, context):
        title = None
        panel_groups = self.panel.split(";")
        if len(panel_groups) == 1:
            panels = panel_groups[0].split(",")
            if len(panels) == 1:
                p = panels[0]
                if p[0] == "!":
                    p = p[1:]
                title = panel_label(p)
        PopupOperator.draw(self, context, title)

        layout = self.layout

        if len(panel_groups) > 1:
            layout = split(layout)

        for group in panel_groups:
            panels = group.split(",")
            col = layout.column()
            pme.context.layout = col
            for p in panels:
                expand = None
                if p[0] == "!":
                    expand = False
                    p = p[1:]
                panel(
                    p.strip(), frame=self.frame, header=self.header,
                    area=self.area, expand=expand)

    def cancel(self, context):
        PopupOperator.cancel(self, context)
        # bpy.types.Context.__getattribute__ = self.oga

    def execute(self, context):
        PopupOperator.execute(self, context)
        # bpy.types.Context.__getattribute__ = self.oga
        return {'FINISHED'}

    def invoke(self, context, event):
        pme.context.reset()

        if self.width == -1:
            panel_groups = self.panel.split(";")
            self.width = 300 * len(panel_groups)

        return PopupOperator.invoke(self, context, event)


class PME_OT_select_popup_panel(bpy.types.Operator):
    bl_idname = "pme.select_popup_panel"
    bl_label = "Select and Open Panel"
    bl_description = "Select and open the panel in a popup"
    bl_options = {'INTERNAL'}
    bl_property = "item"

    enum_items = None

    def get_items(self, context):
        if not PME_OT_select_popup_panel.enum_items:
            PME_OT_select_popup_panel.enum_items = bl_panel_enum_items()

        return PME_OT_select_popup_panel.enum_items

    item: bpy.props.EnumProperty(
        items=get_items, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        PME_OT_select_popup_panel.enum_items = None
        bpy.ops.pme.popup_panel('INVOKE_DEFAULT', panel=self.item)
        return {'FINISHED'}

    def invoke(self, context, event):
        PME_OT_select_popup_panel.enum_items = None
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


class PME_OT_window_auto_close(bpy.types.Operator):
    bl_idname = "pme.window_auto_close"
    bl_label = "Close Temp Windows (PME)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # if context.window.screen.name.startswith(PME_SCREEN) or \
        #         context.window.screen.name.startswith(PME_TEMP_SCREEN):
        #     bpy.ops.wm.window_close(dict(window=context.window))

        # return {'PASS_THROUGH'}

        if not context.window.screen.name.startswith(PME_TEMP_SCREEN):
            # delete_flag = False
            # window = context.window

            wm = context.window_manager
            # used_pme_screens = set()
            for w in wm.windows:
                if w.screen.name.startswith(PME_TEMP_SCREEN):
                    bpy.ops.screen.new(dict(window=w))
                    bpy.ops.pme.timeout(
                        cmd="p = %d; "
                        "w = [w for w in C.window_manager.windows "
                        "if w.as_pointer() == p][0]; "
                        "bpy.ops.wm.window_close(dict(window=w)); "
                        % w.as_pointer())

                # elif w.screen.name.startswith(PME_SCREEN):
                #     used_pme_screens.add(w.screen.name)

            # screens = [w.screen for w in wm.windows]

            # for s in bpy.data.screens:
            #     if s.name.startswith(PME_TEMP_SCREEN):
            #         delete_flag = True
            #         bpy.ops.screen.delete(dict(window=window, screen=s))

            #     elif s.name.startswith(PME_SCREEN) and \
            #             s.name not in used_pme_screens:
            #         delete_flag = True
            #         bpy.ops.screen.delete(dict(window=window, screen=s))

            # if delete_flag:
            #     for s, w in zip(screens, wm.windows):
            #         bpy.ops.pme.screen_set(
            #             dict(window=w, screen=s),
            #             'INVOKE_DEFAULT', name=s.name)

            prefs().enable_window_kmis(False)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        return self.execute(context)


class PME_OT_area_move(bpy.types.Operator):
    bl_idname = "pme.area_move"
    bl_label = "Move Area"
    bl_description = "Move area"
    bl_options = {'INTERNAL'}

    area: bpy.props.EnumProperty(
        name="Area Type", description="Area type",
        items=CC.area_type_enum_items(),
        options={'SKIP_SAVE'})
    edge: bpy.props.EnumProperty(
        name="Area Edge", description="Edge of the area to move",
        items=(
            ('TOP', "Top", "", 'TRIA_TOP_BAR', 0),
            ('BOTTOM', "Bottom", "", 'TRIA_BOTTOM_BAR', 1),
            ('LEFT', "Left", "", 'TRIA_LEFT_BAR', 2),
            ('RIGHT', "Right", "", 'TRIA_RIGHT_BAR', 3),
        ),
        options={'SKIP_SAVE'})
    delta: bpy.props.IntProperty(
        name="Delta", description="Delta", default=300,
        options={'SKIP_SAVE'})
    move_cursor: bpy.props.BoolProperty(
        name="Move Cursor", description="Move cursor",
        options={'SKIP_SAVE'})

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        for a in reversed(context.screen.areas):
            if a.type == self.area:
                break
        else:
            self.report({'WARNING'}, "Main area not found")
            return {'CANCELLED'}

        bpy.ops.view2d.scroll_up(SU.override_context(a))
        return {'FINISHED'}

        mx, my = event.mouse_x, event.mouse_y
        x, y = mx, my
        if self.edge == 'TOP':
            y = a.y + a.height
            my += self.delta * self.move_cursor
        elif self.edge == 'BOTTOM':
            y = a.y
            my += self.delta * self.move_cursor
        elif self.edge == 'RIGHT':
            x = a.x + a.width
            mx += self.delta * self.move_cursor
        elif self.edge == 'LEFT':
            x = a.x
            mx += self.delta * self.move_cursor

        bpy.context.window.cursor_warp(x, y)

        bpy.ops.pme.timeout(
            delay=0.0001,
            cmd=(
                "bpy.context.window.cursor_warp(%d, %d);"
                "bpy.ops.screen.area_move(x=%d, y=%d, delta=%d);"
            ) % (x, y, self.delta, mx, my)
        )
        return {'FINISHED'}


class PME_OT_sidearea_toggle(bpy.types.Operator):
    bl_idname = "pme.sidearea_toggle"
    bl_label = "Toggle Side Area"
    bl_description = "Toggle side area"
    bl_options = {'INTERNAL'}

    sidebars_state = None

    action: bpy.props.EnumProperty(
        name="Action", description="Action",
        items=(
            ('TOGGLE', "Toggle", ""),
            ('SHOW', "Show", ""),
            ('HIDE', "Hide", ""),
        ),
        options={'SKIP_SAVE'}
    )
    main_area: bpy.props.EnumProperty(
        name="Main Area Type", description="Main area type",
        items=CC.area_type_enum_items(current=False),
        default='VIEW_3D',
        options={'SKIP_SAVE'})
    area: bpy.props.EnumProperty(
        name="Side Area Type", description="Side area type",
        items=CC.area_type_enum_items(current=False),
        default='OUTLINER',
        options={'SKIP_SAVE'})
    ignore_area: bpy.props.EnumProperty(
        name="Ignore Area Type", description="Area type to ignore",
        items=CC.area_type_enum_items(current=False, none=True),
        default='NONE',
        options={'SKIP_SAVE'})
    side: bpy.props.EnumProperty(
        name="Side", description="Side",
        items=(
            ('LEFT', "Left", "", 'TRIA_LEFT_BAR', 0),
            ('RIGHT', "Right", "", 'TRIA_RIGHT_BAR', 1),
        ),
        options={'SKIP_SAVE'})
    width: bpy.props.IntProperty(
        name="Width", default=300,
        subtype='PIXEL', options={'SKIP_SAVE'})
    header: bpy.props.EnumProperty(
        name="Header", description="Header options",
        items=CC.header_action_enum_items(),
        options={'SKIP_SAVE'})
    ignore_areas: bpy.props.StringProperty(
        name="Ignore Area Types",
        description="Comma separated area types to ignore",
        options={'SKIP_SAVE'})

    def get_side_areas(self, area):
        l, r, b, t = None, None, None, None
        for a in bpy.context.screen.areas:
            if a.height == area.height and a.y == area.y and \
                    a.ui_type not in self.ia:
                if not l and a.x + a.width + 1 == area.x:
                    l = a
                elif not r and area.x + area.width + 1 == a.x:
                    r = a

            if a.width == area.width and a.x == area.x:
                if not b and a.y + a.height + 1 == area.y:
                    b = a
                elif not t and area.y + area.height + 1 == a.y:
                    t = a

        if b or t:
            l, r = None, None

        return l, r

    def add_space(self, area, space_type):
        a_type = area.ui_type
        area.ui_type = space_type
        area.ui_type = a_type

    def move_header(self, area):
        if self.header != 'DEFAULT':
            SU.move_header(
                area,
                top='TOP' in self.header,
                visible='HIDE' not in self.header)

    def fix_area(self, area):
        if area.ui_type in ('INFO', 'PROPERTIES'):
            bpy.ops.pme.timeout(
                'INVOKE_DEFAULT',
                cmd=("redraw_screen()"))

    def save_sidebars(self, area):
        if self.sidebars_state is None:
            self.__class__.sidebars_state = dict()

        r_tools, r_ui = None, None
        for r in area.regions:
            if r.type == 'TOOLS':
                r_tools = r
            elif r.type == 'UI':
                r_ui = r

        self.sidebars_state[area.ui_type] = (
            r_tools and r_tools.width or 0,
            r_ui and r_ui.width or 0)

    def restore_sidebars(self, area):
        if self.sidebars_state is None or \
                area.ui_type not in self.sidebars_state:
            return

        state = self.sidebars_state[area.ui_type]
        if state[0] > 1:
            SU.toggle_sidebar(area, True, True)
        if state[1] > 1:
            SU.toggle_sidebar(area, False, True)

    def close_area(self, main, area):
        CTU.swap_spaces(area, main, self.area)
        try:
            bpy.ops.screen.area_close(dict(area=area))
            return
        except:
            pass

        if area.x < main.x:
            try:
                bpy.ops.screen.area_join(
                    min_x=area.x + 2, min_y=area.y + 2,
                    max_x=area.x - 2, max_y=area.y + 2)
            except:
                bpy.ops.screen.area_join(
                    cursor=(area.x, area.y + 2))

        else:
            try:
                bpy.ops.screen.area_join(
                    min_x=area.x + area.width - 2,
                    min_y=area.y + area.height - 2,
                    max_x=area.x + area.width + 2,
                    max_y=area.y + area.height - 2)
            except:
                bpy.ops.screen.area_swap(
                    cursor=(area.x + area.width - 2, area.y + 2))
                bpy.ops.screen.area_join(
                    cursor=(area.x + area.width - 2, area.y + 2))

    def execute(self, context):
        self.ia = set(a.strip() for a in self.ignore_areas.split(","))
        self.ia.add(self.ignore_area)
        if self.area in self.ia:
            self.ia.remove(self.area)

        for a in context.screen.areas:
            if a.ui_type == self.main_area:
                break
        else:
            self.report({'WARNING'}, "Main area not found")
            return {'CANCELLED'}

        l, r = self.get_side_areas(a)

        if l and self.side == 'LEFT' and \
                self.action in ('TOGGLE', 'SHOW') and \
                l.ui_type != self.area:
            self.save_sidebars(l)
            CTU.swap_spaces(l, a, l.ui_type)
            self.add_space(a, self.area)
            l.ui_type = self.area
            CTU.swap_spaces(l, a, self.area)

            if l.width != self.width:
                CTU.resize_area(l, self.width, direction='RIGHT')
                SU.redraw_screen()

            self.restore_sidebars(l)
            self.move_header(l)
            self.fix_area(l)

        elif r and self.side == 'RIGHT' and \
                self.action in ('TOGGLE', 'SHOW') and \
                r.ui_type != self.area:
            self.save_sidebars(r)
            CTU.swap_spaces(r, a, r.ui_type)
            self.add_space(a, self.area)
            r.ui_type = self.area
            CTU.swap_spaces(r, a, self.area)

            if r.width != self.width:
                CTU.resize_area(r, self.width, direction='LEFT')
                SU.redraw_screen()

            self.restore_sidebars(r)
            self.move_header(r)
            self.fix_area(r)

        elif l and self.side == 'LEFT' and self.action in ('TOGGLE', 'HIDE'):
            self.save_sidebars(l)
            self.close_area(a, l)
            SU.redraw_screen()

        elif r and self.side == 'RIGHT' and self.action in ('TOGGLE', 'HIDE'):
            self.save_sidebars(r)
            self.close_area(a, r)
            SU.redraw_screen()

        elif (not l and self.side == 'LEFT' or
                not r and self.side == 'RIGHT') and \
                self.action in ('TOGGLE', 'SHOW'):
            if self.width > a.width >> 1:
                self.width = a.width >> 1

            factor = (self.width - 1) / a.width
            if self.side == 'RIGHT':
                factor = 1 - factor

            self.add_space(a, self.area)
            mouse = {}
            area_split_props = operator_utils.get_rna_type(
                bpy.ops.screen.area_split).properties

            if "cursor" in area_split_props:
                mouse["cursor"] = [a.x + 1, a.y + 1]
            else:
                mouse["mouse_x"] = a.x + 1
                mouse["mouse_y"] = a.y + 1

            bpy.ops.screen.area_split(
                SU.override_context(a),
                direction='VERTICAL',
                factor=factor,
                **mouse)

            new_area = context.screen.areas[-1]
            new_area.ui_type = self.area
            CTU.swap_spaces(new_area, a, self.area)

            self.restore_sidebars(new_area)
            self.move_header(new_area)
            self.fix_area(new_area)

        return {'FINISHED'}


class PME_OT_popup_area(bpy.types.Operator):
    bl_idname = "pme.popup_area"
    bl_label = "Popup Area"
    bl_description = "Open the area in a new window"
    bl_options = {'INTERNAL'}

    width: bpy.props.IntProperty(
        name="Width", description="Width of the window (-1 - auto)",
        subtype='PIXEL',
        default=-1, min=WINDOW_MIN_WIDTH, soft_min=-1, options={'SKIP_SAVE'})
    height: bpy.props.IntProperty(
        name="Height", description="Height of the window (-1 - auto)",
        subtype='PIXEL',
        default=-1, min=WINDOW_MIN_HEIGHT, soft_min=-1, options={'SKIP_SAVE'})
    center: bpy.props.BoolProperty(
        name="Center", description="Center", options={'SKIP_SAVE'})
    area: bpy.props.EnumProperty(
        name="Area", description="Area",
        items=CC.area_type_enum_items(), options={'SKIP_SAVE'})
    auto_close: bpy.props.BoolProperty(
        default=True, name="Auto Close",
        description="Click outside to close the window", options={'SKIP_SAVE'})
    header: bpy.props.EnumProperty(
        name="Header", description="Header options",
        items=CC.header_action_enum_items(),
        options={'SKIP_SAVE'})
    cmd: bpy.props.StringProperty(
        name="Exec on Open",
        description="Execute python code on window open",
        maxlen=MAX_STR_LEN, options={'SKIP_SAVE'})

    def update_header(self, on_top, visible, d):
        if self.header == 'DEFAULT':
            return

        if 'TOP' in self.header:
            # not on_top and bpy.ops.screen.header_flip(d)
            not on_top and bpy.ops.screen.region_flip(d)
        else:
            # on_top and bpy.ops.screen.header_flip(d)
            on_top and bpy.ops.screen.region_flip(d)

        if 'HIDE' in self.header:
            visible and bpy.ops.screen.header(d)
        else:
            not visible and bpy.ops.screen.header(d)

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.area == 'CURRENT':
            if not context.area:
                return {'CANCELLED'}

            self.area = context.area.ui_type if is_28() else context.area.type

        area_name = ""
        for item in CC.area_type_enum_items():
            if item[0] == self.area:
                area_name = item[1]
                break

        screen_name = PME_TEMP_SCREEN if self.auto_close else PME_SCREEN
        screen_name += area_name

        area_type = None
        new_screen_flag = False
        # if screen_name in bpy.data.screens:
        if False:
            area = bpy.data.screens[screen_name].areas[0]
        else:
            new_screen_flag = True
            area = context.screen.areas[0]
            if is_28():
                area_type = area.ui_type
                area.ui_type = self.area
            else:
                area_type = area.type
                area.type = self.area

        rh, rw = None, None
        for r in area.regions:
            if r.type == 'HEADER':
                rh = r
            elif r.type == 'WINDOW':
                rw = r

        header_dict = ctx_dict(area=area, region=rh)
        header_visible = rh.height > 1
        if header_visible:
            header_on_top = rw.y == area.y
        else:
            header_on_top = rh.y > area.y

        self.update_header(header_on_top, header_visible, header_dict)

        window = context.window
        windows = [w for w in context.window_manager.windows]

        if self.width == -1:
            if self.area == 'PROPERTIES':
                self.width = round(
                    350 * uprefs().view.ui_scale)
            elif self.area == 'OUTLINER':
                self.width = round(
                    400 * uprefs().view.ui_scale)
            else:
                self.width = round(window.width * 0.8)

        if self.width < WINDOW_MIN_WIDTH:
            self.width = WINDOW_MIN_WIDTH
        elif self.width > window.width:
            self.width = window.width

        if self.height == -1:
            self.height = round(window.height * 0.8)
        elif self.height < WINDOW_MIN_HEIGHT:
            self.height = WINDOW_MIN_HEIGHT

        x, y = event.mouse_x, event.mouse_y
        if self.center:
            x = window.width >> 1
            y = window.height - (
                window.height - self.height >> 1)
            context.window.cursor_warp(x, y)

        popup_area(area, self.width, self.height, x, y)

        new_window = None
        if context.window_manager.windows[-1] not in windows:
            new_window = context.window_manager.windows[-1]

        if new_window:
            if self.cmd:
                getattr(bpy.ops.pme, "timeout")(
                    ctx_dict(window=new_window),
                    'INVOKE_DEFAULT',
                    cmd=self.cmd)

            new_screen_name = new_window.screen.name
            # if screen_name in bpy.data.screens:
            if False:
                bpy.ops.screen.delete(
                    dict(
                        window=new_window,
                        screen=bpy.data.screens[new_screen_name]))
                bpy.ops.pme.screen_set(
                    dict(window=new_window), name=screen_name)
            else:
                new_window.screen.name = screen_name
                new_window.screen.user_clear()

        if new_screen_flag:
            self.update_header(header_on_top, header_visible, header_dict)

        if area_type:
            if is_28():
                area.ui_type = area_type
            else:
                area.type = area_type

        prefs().enable_window_kmis()

        return {'FINISHED'}


class PME_OT_clipboard_copy(bpy.types.Operator):
    bl_idname = "pme.clipboard_copy"
    bl_label = "Copy"
    bl_options = {'INTERNAL'}

    text: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        context.window_manager.clipboard = self.text
        return {'FINISHED'}


@persistent
def save_pre_handler(_):
    for s in bpy.data.screens:
        if s.name.startswith(PME_TEMP_SCREEN) and s.users > 0:
            s.user_clear()


def register():
    bpy.app.handlers.save_pre.append(save_pre_handler)


def unregister():
    if save_pre_handler in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(save_pre_handler)
