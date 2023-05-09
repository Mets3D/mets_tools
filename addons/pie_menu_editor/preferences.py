import bpy
import os
import json
import datetime
import re
from types import MethodType
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .addon import (
    ADDON_ID, ADDON_PATH, SCRIPT_PATH, SAFE_MODE,
    prefs, uprefs, temp_prefs,
    print_exc, ic, ic_fb, ic_cb, ic_eye, is_28)
from . import constants as CC
from . import operators as OPS
from . import extra_operators as EOPS
from .bl_utils import (
    bp, uname, bl_context, gen_prop_path, ConfirmBoxHandler, message_box)
from .collection_utils import BaseCollectionItem, sort_collection
from .layout_helper import lh, operator, split
from .debug_utils import *
from .panel_utils import (
    hide_panel, unhide_panel, add_panel,
    hidden_panel, rename_panel_group, remove_panel_group,
    panel_context_items, bl_panel_types, bl_menu_types, bl_header_types)
from .macro_utils import add_macro, remove_macro, update_macro
from .modal_utils import encode_modal_data
from . import compatibility_fixes
from . import addon
from . import keymap_helper
from . import pme
from . import operator_utils
from .keymap_helper import (
    KeymapHelper, MOUSE_BUTTONS,
    add_mouse_button, remove_mouse_button, to_key_name, to_ui_hotkey)
from .previews_helper import ph
from .overlay import OverlayPrefs
from .ui import (
    tag_redraw, draw_addons_maximized, is_userpref_maximized
)
from .ui_utils import (
    get_pme_menu_class, execute_script
)
from . import utils as U
from .property_utils import PropertyData, to_py_value
from .types import Tag, PMItem, PMIItem, PMLink, EdProperties, UserProperties
from .ed_base import (
    WM_OT_pmi_icon_select, WM_OT_pmi_data_edit, PME_OT_pm_edit,
    PME_OT_pmi_cmd_generate, PME_OT_tags_filter, PME_OT_tags,
    PME_OT_pm_add, WM_OT_pmi_icon_tag_toggle
)
from .ed_panel_group import (
    PME_OT_interactive_panels_toggle, draw_pme_panel, poll_pme_panel)
from .ed_sticky_key import PME_OT_sticky_key_edit
from .ed_modal import PME_OT_prop_data_reset

pp = pme.props
import_filepath = os.path.join(ADDON_PATH, "examples", "examples.json")
export_filepath = os.path.join(ADDON_PATH, "examples", "my_pie_menus.json")


def update_pmi_data(self, context, reset_prop_data=True):
    pr = prefs()
    pm = pr.selected_pm
    pmi_data = pr.pmi_data
    pmi_data.check_pmi_errors(context)

    data_mode = pmi_data.mode
    if data_mode in CC.MODAL_CMD_MODES:
        data_mode = 'COMMAND'

    if data_mode == 'COMMAND' and pr.use_cmd_editor:
        op_idname, args, pos_args = operator_utils.find_operator(pmi_data.cmd)

        pmi_data.kmi.idname = ""
        pmi_data.cmd_ctx = 'INVOKE_DEFAULT'
        pmi_data.cmd_undo = True

        if not op_idname:
            return
        else:
            mod, _, op = op_idname.partition(".")
            mod = getattr(bpy.ops, mod, None)
            if not mod or not hasattr(mod, op):
                return

        pmi_data.kmi.idname = op_idname

        has_exec_ctx = False
        has_undo = False
        for i, arg in enumerate(pos_args):
            if i > 2:
                break
            try:
                value = eval(arg)
            except:
                continue
            try:
                if isinstance(value, str):
                    pmi_data.cmd_ctx = value
                    has_exec_ctx = True
                    continue
            except:
                pmi_data.cmd_ctx = 'INVOKE_DEFAULT'
                continue

            if isinstance(value, bool):
                has_undo = True
                pmi_data.cmd_undo = value

        if has_undo and not has_exec_ctx:
            pmi_data.cmd_ctx = 'EXEC_DEFAULT'

        keys = list(pmi_data.kmi.properties.keys())
        for k in keys:
            del pmi_data.kmi.properties[k]

        operator_utils.apply_properties(
            pmi_data.kmi.properties, args, pm, pmi_data)

    if pm.mode == 'MODAL':
        if data_mode == 'PROP':
            tpr = temp_prefs()
            tpr.prop_data.init(pmi_data.prop, pme.context.globals)
            if reset_prop_data:
                tpr.modal_item_prop_min = tpr.prop_data.min
                tpr.modal_item_prop_max = tpr.prop_data.max
                tpr.modal_item_prop_step = tpr.prop_data.step
                tpr.modal_item_prop_step_is_set = False


def update_data(self, context):
    update_pmi_data(self, context, reset_prop_data=True)


class WM_OT_pm_import(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.pm_import"
    bl_label = "Import Menus"
    bl_description = "Import menus"
    bl_options = {'INTERNAL'}

    filename_ext = ".json"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="*.json")
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    filter_glob: bpy.props.StringProperty(
        default="*.json;*.zip", options={'HIDDEN'})
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    mode: bpy.props.StringProperty()
    tags: bpy.props.StringProperty(
        name="Tags", description="Assign tags (separate by comma)",
        options={'SKIP_SAVE'})
    password: bpy.props.StringProperty(
        name="Password",
        description="Password for zip files",
        subtype='PASSWORD', options={'HIDDEN', 'SKIP_SAVE'})
    password_visible: bpy.props.StringProperty(
        name="Password",
        description="Password for zip files",
        get=lambda s: s.password,
        set=lambda s, v: setattr(s, "password", v),
        options={'HIDDEN', 'SKIP_SAVE'})
    show_password: bpy.props.BoolProperty(options={'HIDDEN'})

    def _draw(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        lh.operator(
            WM_OT_pm_import.bl_idname, "Rename if exists",
            filepath=import_filepath,
            mode='RENAME')

        lh.operator(
            WM_OT_pm_import.bl_idname, "Skip if exists",
            filepath=import_filepath,
            mode='SKIP')

        lh.operator(
            WM_OT_pm_import.bl_idname, "Replace if exists",
            filepath=import_filepath,
            mode='REPLACE')

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Assign Tags:")
        col.prop(self, "tags", text="", icon=ic_fb(False))

        col = self.layout.column(align=True)
        col.active = self.password != ""
        col.label(text="Password:")
        row = col.row(align=True)
        row.prop(
            self,
            "password_visible" if self.show_password else "password",
            text="")
        row.prop(
            self, "show_password", text="", toggle=True,
            icon=ic_eye(self.show_password))

    def import_json(self, json_data):
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")
        try:
            data = json.loads(json_data)
        except:
            self.report({'WARNING'}, CC.W_JSON)
            return

        pr = prefs()

        menus = None
        if isinstance(data, list):
            version = "1.13.6"
            menus = data
        elif isinstance(data, dict):
            try:
                version = data["version"]
                menus = data["menus"]
            except:
                self.report({'WARNING'}, CC.W_JSON)
                return
        else:
            self.report({'WARNING'}, CC.W_JSON)
            return

        if not menus:
            return

        version = tuple(int(i) for i in version.split("."))

        new_names = {}
        if self.mode == 'RENAME':
            pm_names = [menu[0] for menu in menus]

            for name in pm_names:
                if name in pr.pie_menus:
                    new_names[name] = pr.unique_pm_name(name)

        for menu in menus:
            if self.mode == 'REPLACE':
                if menu[0] in pr.pie_menus:
                    pr.remove_pm(pr.pie_menus[menu[0]])
            elif self.mode == 'RENAME':
                if menu[0] in new_names:
                    menu[0] = new_names[menu[0]]
            elif self.mode == 'SKIP':
                if menu[0] in pr.pie_menus:
                    continue

            mode = menu[4] if len(menu) > 4 else 'PMENU'
            # pm = pr.add_pm(mode, menu[0], True)
            pm = pr.pie_menus.add()
            pm.mode = mode
            compatibility_fixes.fix_json(pm, menu, version)
            pm.name = pr.unique_pm_name(menu[0] or pm.ed.default_name)
            pm.km_name = menu[1]

            n = len(menu)
            if n > 5:
                pm.data = menu[5]
            if n > 6:
                pm.open_mode = menu[6]
            if n > 7:
                pm.poll_cmd = menu[7] or CC.DEFAULT_POLL
            if n > 8:
                pm.tag = menu[8]

            if self.tags:
                tags = self.tags.split(",")
                for t in tags:
                    pm.add_tag(t)

            if menu[2]:
                try:
                    pm.key, pm.ctrl, pm.shift, pm.alt, pm.oskey, \
                        pm.any, pm.key_mod, pm.chord = \
                        keymap_helper.parse_hotkey(menu[2])
                except:
                    self.report({'WARNING'}, CC.W_KEY % menu[2])

            items = menu[3]
            for i in range(0, len(items)):
                item = items[i]
                # pmi = pm.pmis[i] if mode == 'PMENU' else pm.pmis.add()
                pmi = pm.pmis.add()
                n = len(item)
                if n >= 4:
                    if self.mode == 'RENAME' and \
                            item[1] == 'MENU' and item[3] in new_names:
                        item[3] = new_names[item[3]]

                    try:
                        pmi.mode = item[1]
                    except:
                        pmi.mode = 'EMPTY'

                    pmi.name = item[0]
                    pmi.icon = item[2]
                    pmi.text = item[3]

                    if n >= 5:
                        pmi.flags(item[4])

                elif n == 3:
                    pmi.mode = 'EMPTY'
                    pmi.name = item[0]
                    pmi.icon = item[1]
                    pmi.text = item[2]

                elif n == 1:
                    pmi.mode = 'EMPTY'
                    pmi.text = item[0]

            if pm.mode == 'SCRIPT' and not pm.data.startswith("s?"):
                pmi = pm.pmis.add()
                pmi.text = pm.data
                pmi.mode = 'COMMAND'
                pmi.name = "Command 1"
                pm.data = pm.ed.default_pmi_data

        pms = [pr.pie_menus[menu[0]] for menu in menus]

        compatibility_fixes.fix(pms, version)

        for pm in pms:
            pm.ed.init_pm(pm)

    def import_file(self, filepath):
        from zipfile import ZipFile, is_zipfile
        if is_zipfile(filepath):
            with ZipFile(filepath, "r") as f:
                if self.password:
                    f.setpassword(self.password.encode("utf-8"))

                try:
                    f.testzip()
                except RuntimeError as e:
                    message_box(str(e))
                    return

                for info in f.infolist():
                    if info.is_dir():
                        if info.filename == "icons/":
                            self.refresh_icons_flag = True

                        try:
                            os.mkdir(os.path.join(ADDON_PATH, info.filename))
                        except:
                            pass

                    elif info.filename.endswith(".json"):
                        self.import_json(f.read(info.filename))

                    else:
                        if os.path.isfile(
                                os.path.join(ADDON_PATH, info.filename)):
                            if self.mode == 'SKIP':
                                continue
                            elif self.mode == 'RENAME':
                                mo = re.search(
                                    r"(.+)\.(\d{3,})(\.\w+)", info.filename)
                                if mo:
                                    name, idx, ext = mo.groups()
                                    idx = int(idx)

                                else:
                                    name, ext = os.path.splitext(info.filename)
                                    idx = 0

                                while True:
                                    idx += 1
                                    info.filename = "%s.%s%s" % (
                                        name, str(idx).zfill(3), ext)
                                    if not os.path.isfile(
                                            os.path.join(
                                            ADDON_PATH, info.filename)):
                                        break

                        f.extract(info, path=ADDON_PATH)
        else:
            try:
                with open(filepath, "r") as f:
                    s = f.read()
            except:
                self.report({'WARNING'}, CC.W_FILE)
                return

            self.import_json(s)

    def execute(self, context):
        global import_filepath
        pr = prefs()
        pr.tree.lock()

        select_pm_flag = len(pr.pie_menus) == 0

        self.refresh_icons_flag = False
        try:
            for f in self.files:
                filepath = os.path.join(self.directory, f.name)
                if os.path.isfile(filepath):
                    self.import_file(filepath)
        except:
            raise
        finally:
            pr.tree.unlock()

        import_filepath = self.filepath

        temp_prefs().init_tags()
        PME_UL_pm_tree.update_tree()

        if select_pm_flag:
            idx = pr.active_pie_menu_idx
            pr["active_pie_menu_idx"] = -1
            pr.active_pie_menu_idx = idx

        if self.refresh_icons_flag:
            bpy.ops.pme.icons_refresh()

        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.mode:
            context.window_manager.popup_menu(
                self._draw, title=self.bl_description)
            return {'FINISHED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class WM_OT_pm_export(bpy.types.Operator, ExportHelper):
    bl_idname = "wm.pm_export"
    bl_label = "Export Menus"
    bl_description = "Export menus"
    bl_options = {'INTERNAL', 'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="*.json")
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    mode: bpy.props.StringProperty(options={'SKIP_SAVE'})
    tag: bpy.props.StringProperty(options={'SKIP_SAVE'})
    export_tags: bpy.props.BoolProperty(
        name="Export Tags", description="Export tags",
        default=True, options={'SKIP_SAVE'})

    def _draw(self, menu, context):
        lh.lt(menu.layout, operator_context='INVOKE_DEFAULT')

        lh.operator(
            WM_OT_pm_export.bl_idname, "All Menus", 'ALIGN_JUSTIFY',
            filepath=export_filepath,
            mode='ALL')

        lh.operator(
            WM_OT_pm_export.bl_idname, "All Enabled Menus", 'SYNTAX_ON',
            filepath=export_filepath,
            mode='ENABLED')

        lh.operator(
            WM_OT_pm_export.bl_idname, "Selected Menu", 'REMOVE',
            filepath=export_filepath,
            mode='ACTIVE')

        if temp_prefs().tags:
            lh.operator(
                WM_OT_pm_export.bl_idname, "By Tag",
                filepath=export_filepath,
                mode='TAG')

        lh.sep()

        lh.layout.prop(prefs(), "auto_backup")

        lh.operator(
            PME_OT_backup.bl_idname, "Backup Now", 'FILE_HIDDEN')

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_tags")

    def execute(self, context):
        global export_filepath

        if not self.filepath:
            return {'CANCELLED'}

        if not self.filepath.endswith(".json"):
            self.filepath += ".json"

        data = prefs().get_export_data(
            export_tags=self.export_tags, mode=self.mode, tag=self.tag)
        data = json.dumps(data, indent=2, separators=(", ", ": "))
        try:
            with open(self.filepath, 'w') as f:
                f.write(data)
        except:
            print_exc()
            return {'CANCELLED'}

        export_filepath = self.filepath
        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.mode:
            context.window_manager.popup_menu(
                self._draw, title=self.bl_description)
            return {'FINISHED'}

        elif self.mode == 'TAG' and not self.tag:
            Tag.popup_menu(
                self.bl_idname, "Export by Tag", invoke=True,
                mode=self.mode)
            return {'FINISHED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PME_OT_backup(bpy.types.Operator):
    bl_idname = "pme.backup"
    bl_label = "Backup Menus"
    bl_description = "Backup PME menus"

    def invoke(self, context, event):
        prefs().backup_menus(operator=self)
        return {'FINISHED'}


class WM_OT_pm_duplicate(bpy.types.Operator):
    bl_idname = "wm.pm_duplicate"
    bl_label = ""
    bl_description = "Duplicate the active item"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        pr = prefs()
        if len(pr.pie_menus) == 0:
            return {'FINISHED'}

        apm = pr.selected_pm
        apm_name = apm.name

        pm = pr.add_pm(apm.mode, apm_name, True)

        pm.ed.on_pm_duplicate(apm, pm)

        PME_UL_pm_tree.update_tree()

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return len(prefs().pie_menus) > 0


class PME_OT_pm_remove(ConfirmBoxHandler, bpy.types.Operator):
    bl_idname = "pme.pm_remove"
    bl_label = "Remove Item(s)"
    bl_description = "Remove item(s)"
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(
        items=(
            ('ACTIVE', "Remove Active Item", "Remove active item"),
            ('ALL', "Remove All Items", "Remove all items"),
            ('ENABLED', "Remove Enabled Items", "Remove enabled items"),
            ('DISABLED', "Remove Disabled Items", "Remove disabled items"),
        ),
        options={'SKIP_SAVE'})

    def on_confirm(self, value):
        if not value:
            return

        pr = prefs()
        if self.mode == 'ACTIVE':
            pr.remove_pm()
        elif self.mode == 'ALL':
            for i in range(len(pr.pie_menus)):
                pr.remove_pm()
        elif self.mode in {'ENABLED', 'DISABLED'}:
            i = 0
            while i < len(pr.pie_menus):
                pm = pr.pie_menus[i]
                if pm.enabled and self.mode == 'ENABLED' or \
                        not pm.enabled and self.mode == 'DISABLED':
                    pr.remove_pm(pm=pm)
                else:
                    i += 1

        PME_UL_pm_tree.update_tree()
        tag_redraw()

    @classmethod
    def poll(cls, context):
        return len(prefs().pie_menus) > 0

    def invoke(self, context, event):
        self.box = True
        self.title = bpy.types.UILayout.enum_item_name(self, "mode", self.mode)
        return ConfirmBoxHandler.invoke(self, context, event)


class PME_OT_pm_enable_all(bpy.types.Operator):
    bl_idname = "wm.pm_enable_all"
    bl_label = ""
    bl_description = "Enable or disable all items"
    bl_options = {'INTERNAL'}

    enable: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        for pm in prefs().pie_menus:
            pm.enabled = self.enable
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return prefs().pie_menus


class PME_OT_pm_enable_by_tag(bpy.types.Operator):
    bl_idname = "pme.pm_enable_by_tag"
    bl_label = ""
    bl_description = "Enable or disable items by tag"
    bl_options = {'INTERNAL'}

    enable: bpy.props.BoolProperty(options={'SKIP_SAVE'})
    tag: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        if not self.tag:
            Tag.popup_menu(
                self.bl_idname,
                "Enable by Tag" if self.enable else "Disable by Tag",
                enable=self.enable)
        else:
            for pm in prefs().pie_menus:
                if pm.has_tag(self.tag):
                    pm.enabled = self.enable
            tag_redraw()

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return prefs().pie_menus


class PME_OT_pm_remove_by_tag(bpy.types.Operator):
    bl_idname = "pme.pm_remove_by_tag"
    bl_label = ""
    bl_description = "Remove items by tag"
    bl_options = {'INTERNAL'}

    tag: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        if not self.tag:
            Tag.popup_menu(self.bl_idname, "Remove by Tag")
        else:
            pr = prefs()
            pm_names = []
            for pm in prefs().pie_menus:
                if pm.has_tag(self.tag):
                    pm_names.append(pm.name)

            for pm_name in pm_names:
                pr.remove_pm(pr.pie_menus[pm_name])

            PME_UL_pm_tree.update_tree()
            tag_redraw()

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return prefs().pie_menus


class WM_OT_pm_move(bpy.types.Operator):
    bl_idname = "wm.pm_move"
    bl_label = ""
    bl_description = "Move the active item"
    bl_options = {'INTERNAL'}

    direction: bpy.props.IntProperty()

    def execute(self, context):
        pr = prefs()
        tpr = temp_prefs()
        if pr.tree_mode:
            link = tpr.links[tpr.links_idx]
            if link.label:
                return {'CANCELLED'}

            new_idx = tpr.links_idx + self.direction
            num_links = len(tpr.links)
            if 0 <= new_idx <= num_links - 1:
                new_link = tpr.links[new_idx]
                if link.is_folder or not link.path:
                    while 0 <= new_idx < num_links:
                        new_link = tpr.links[new_idx]
                        if new_link.label:
                            return {'CANCELLED'}
                        elif not new_link.path:
                            break

                        new_idx += self.direction

                    if new_idx < 0 or new_idx >= num_links:
                        return {'CANCELLED'}

                else:
                    if new_link.label or new_link.is_folder or \
                            not new_link.path:
                        return {'CANCELLED'}

                pm_idx = pr.pie_menus.find(new_link.pm_name)
                pr.pie_menus.move(pr.active_pie_menu_idx, pm_idx)
                pr.active_pie_menu_idx = pm_idx
                PME_UL_pm_tree.update_tree()
                # PME.links_idx = new_idx

            else:
                return {'CANCELLED'}

        else:
            new_idx = pr.active_pie_menu_idx + self.direction
            if 0 <= new_idx <= len(pr.pie_menus) - 1:
                pr.pie_menus.move(pr.active_pie_menu_idx, new_idx)
                pr.active_pie_menu_idx = new_idx

            PME_UL_pm_tree.update_tree()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return len(prefs().pie_menus) > 1


class WM_OT_pm_sort(bpy.types.Operator):
    bl_idname = "wm.pm_sort"
    bl_label = ""
    bl_description = "Sort items by"
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(
        items=(
            ('NONE', "None", ""),
            ('NAME', "Name", ""),
            ('HOTKEY', "Hotkey", ""),
            ('KEYMAP', "Keymap", ""),
            ('TYPE', "Type", ""),
            ('TAG', "Tag", ""),
        ),
        options={'SKIP_SAVE'})

    def _draw(self, menu, context):
        lh.lt(menu.layout)
        lh.operator(
            WM_OT_pm_sort.bl_idname, "Name", 'SORTALPHA',
            mode='NAME')

        lh.operator(
            WM_OT_pm_sort.bl_idname, "Hotkey", 'FILE_FONT',
            mode='HOTKEY')

        lh.operator(
            WM_OT_pm_sort.bl_idname, "Keymap Name", 'SPLITSCREEN',
            mode='KEYMAP')

        lh.operator(
            WM_OT_pm_sort.bl_idname, "Type", 'PROP_CON',
            mode='TYPE')

        lh.operator(
            WM_OT_pm_sort.bl_idname, "Tag", 'SOLO_OFF',
            mode='TAG')

    def execute(self, context):
        if self.mode == 'NONE':
            context.window_manager.popup_menu(
                self._draw, title=WM_OT_pm_sort.bl_description)
            return {'FINISHED'}

        pr = prefs()
        if len(pr.pie_menus) == 0:
            return {'FINISHED'}

        items = [pm for pm in pr.pie_menus]

        if self.mode == 'NAME':
            items.sort(key=lambda pm: pm.name)
        elif self.mode == 'KEYMAP':
            items.sort(key=lambda pm: (pm.km_name, pm.name))
        elif self.mode == 'HOTKEY':
            items.sort(key=lambda pm: (
                to_key_name(pm.key) if pm.key != 'NONE' else '_',
                pm.ctrl, pm.shift, pm.alt, pm.oskey,
                pm.key_mod if pm.key_mod != 'NONE' else '_'))
        elif self.mode == 'TYPE':
            items.sort(key=lambda pm: (pm.mode, pm.ed.default_name))
        elif self.mode == 'TAG':
            items.sort(key=lambda pm: (pm.tag, pm.name))

        items = [pm.name for pm in items]
        apm = pr.selected_pm
        apm_name = apm.name

        idx = len(items) - 1
        aidx = 0
        while idx > 0:
            k = items[idx]
            if pr.pie_menus[idx] != pr.pie_menus[k]:
                k_idx = pr.pie_menus.find(k)
                pr.pie_menus.move(k_idx, idx)
            if apm_name == k:
                aidx = idx
            idx -= 1
        pr.active_pie_menu_idx = aidx

        PME_UL_pm_tree.update_tree()

        tag_redraw()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return len(prefs().pie_menus) > 1


class PME_OT_pmi_name_apply(bpy.types.Operator):
    bl_idname = "pme.pmi_name_apply"
    bl_label = ""
    bl_description = "Apply the suggested name"
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty()

    def execute(self, context):
        data = prefs().pmi_data
        data.name = data.sname
        return {'FINISHED'}


# class WM_OT_icon_filter_clear(bpy.types.Operator):
#     bl_idname = "wm.icon_filter_clear"
#     bl_label = ""
#     bl_description = "Clear Filter"
#     bl_options = {'INTERNAL'}

#     def execute(self, context):
#         prefs().icon_filter = ""
#         return {'FINISHED'}


class PME_OT_icons_refresh(bpy.types.Operator):
    bl_idname = "pme.icons_refresh"
    bl_label = ""
    bl_description = "Refresh icons"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        ph.refresh()
        return {'FINISHED'}


class PMEData(bpy.types.PropertyGroup):
    update_lock = False
    prop_data = PropertyData()

    ed_props: bpy.props.PointerProperty(type=EdProperties)

    def get_links_idx(self):
        return self["links_idx"] if "links_idx" in self else 0

    def set_links_idx(self, value):
        pr = prefs()
        tpr = temp_prefs()

        if value < 0 or value >= len(tpr.links):
            return
        link = tpr.links[value]

        self["links_idx"] = value
        if link.pm_name:
            pr.active_pie_menu_idx = pr.pie_menus.find(link.pm_name)

    def update_modal_item_hk(self, context):
        pmi_data = prefs().pmi_data
        encode_modal_data(pmi_data)
        pmi_data.check_pmi_errors(context)

        if PMEData.update_lock:
            return
        PMEData.update_lock = True

        tpr = temp_prefs()
        if pmi_data.mode == 'PROP':
            if tpr.modal_item_hk.key == 'WHEELUPMOUSE':
                tpr.modal_item_prop_mode = 'WHEEL'
            elif tpr.modal_item_hk.key == 'WHEELDOWNMOUSE':
                tpr.modal_item_prop_mode = 'WHEEL'
                tpr.modal_item_hk.key = 'WHEELUPMOUSE'

        PMEData.update_lock = False

    def update_modal_item_prop_mode(self, context):
        if PMEData.update_lock:
            return
        PMEData.update_lock = True

        if self.modal_item_prop_mode == 'KEY':
            self.modal_item_hk.key = 'NONE'
        elif self.modal_item_prop_mode == 'MOVE':
            self.modal_item_hk.key = 'MOUSEMOVE'
        elif self.modal_item_prop_mode == 'WHEEL':
            self.modal_item_hk.key = 'WHEELUPMOUSE'

        PMEData.update_lock = False

    tags: bpy.props.CollectionProperty(type=Tag)
    links: bpy.props.CollectionProperty(type=PMLink)
    links_idx: bpy.props.IntProperty(get=get_links_idx, set=set_links_idx)
    hidden_panels_idx: bpy.props.IntProperty()
    pie_menus: bpy.props.CollectionProperty(type=BaseCollectionItem)
    # modal_item_hk: bpy.props.EnumProperty(
    #     items=keymap_helper.key_items,
    #     description="Key pressed", update=update_modal_item_hk)
    modal_item_hk: bpy.props.PointerProperty(type=keymap_helper.Hotkey)
    modal_item_prop_mode: bpy.props.EnumProperty(
        items=(
            ('KEY', "Hotkey", (
                "Command tab: Press the hotkey\n"
                "Property tab: Press and hold the hotkey and move the mouse "
                "to change the value"
                )),
            ('MOVE', "Move Mouse", "Move mouse to change the value"),
            ('WHEEL', "Mouse Wheel", "Scroll mouse wheel to change the value"),
        ),
        update=update_modal_item_prop_mode)
    modal_item_prop_min: bpy.props.FloatProperty(
        name="Min Value", step=100)
    modal_item_prop_max: bpy.props.FloatProperty(
        name="Max Value", step=100)

    def set_modal_item_prop_step(self, value):
        self["modal_item_prop_step"] = value
        self.modal_item_prop_step_is_set = True

    modal_item_prop_step: bpy.props.FloatProperty(
        name="Step", min=0, step=100,
        get=lambda s: s.get("modal_item_prop_step", 1),
        set=set_modal_item_prop_step)
    modal_item_prop_step_is_set: bpy.props.BoolProperty()
    # modal_item_custom_use: bpy.props.BoolProperty(
    #     name="Display Custom Value",
    #     description="Display custom value")

    def modal_item_custom_update(self, context):
        update_pmi_data(self, context, reset_prop_data=False)

    modal_item_custom: bpy.props.StringProperty(
        description="Custom value to display",
        update=modal_item_custom_update)

    def modal_item_show_get(self):
        return self.modal_item_custom != 'HIDDEN'

    def modal_item_show_set(self, value):
        self.modal_item_custom = "" if value else 'HIDDEN'

    modal_item_show: bpy.props.BoolProperty(
        description="Show the hotkey",
        get=modal_item_show_get, set=modal_item_show_set)

    settings_tab: bpy.props.EnumProperty(
        items=CC.SETTINGS_TAB_ITEMS,
        name="Settings", description="Settings",
        # options={'ENUM_FLAG'},
        default=CC.SETTINGS_TAB_DEFAULT
    )
    icons_tab: bpy.props.EnumProperty(
        name="Icons", description="Icons",
        items=(
            ('BLENDER', "Blender", ""),
            ('CUSTOM', "Custom", ""),
        )
    )

    def init_tags(self):
        pr = prefs()
        tpr = temp_prefs()
        self.tags.clear()
        for pm in pr.pie_menus:
            tags = pm.get_tags()
            if not tags:
                continue
            for t in tags:
                if t in self.tags:
                    continue
                tag = self.tags.add()
                tag.name = t
        sort_collection(tpr.tags, lambda t: t.name)
        Tag.filter()

    def update_pie_menus(self):
        pr = prefs()
        spm = pr.selected_pm
        supported_sub_menus = spm.ed.supported_sub_menus
        pms = set()

        for pm in pr.pie_menus:
            if pm.name == spm.name:
                continue
            if pm.mode in supported_sub_menus:
                pms.add(pm.name)

        self.pie_menus.clear()
        for pm in sorted(pms):
            item = self.pie_menus.add()
            item.name = pm


class WM_UL_panel_list(bpy.types.UIList):

    def draw_item(
            self, context, layout, data, item,
            icon, active_data, active_propname, index):
        tp = hidden_panel(item.text)
        pr = prefs()
        v = pr.panel_info_visibility
        ic_items = pr.rna_type.properties["panel_info_visibility"].enum_items

        if 'NAME' in v:
            layout.label(
                text=item.name or item.text, icon=ic(ic_items['NAME'].icon))
        if 'CLASS' in v:
            layout.label(text=item.text, icon=ic(ic_items['CLASS'].icon))
        if 'CTX' in v:
            layout.label(
                text=tp.bl_context if tp and hasattr(tp, "bl_context") else
                "-", icon=ic(ic_items['CTX'].icon))
        if 'CAT' in v:
            layout.label(
                text=tp.bl_category if tp and hasattr(tp, "bl_category") else
                "-", icon=ic(ic_items['CAT'].icon))


class WM_UL_pm_list(bpy.types.UIList):

    def _draw_filter(self, context, layout):
        pr = prefs()

        col = layout.column(align=True)
        col.prop(self, "filter_name", text="", icon=ic('VIEWZOOM'))
        col.prop(pr, "list_size")
        col.prop(pr, "num_list_rows")

    def draw_filter27(self, context, layout):
        self._draw_filter(context, layout)

    def draw_filter28(self, context, layout, reverse=False):
        self._draw_filter(context, layout)

    draw_filter = draw_filter27
    # draw_filter = draw_filter28 if is_28() else draw_filter27

    def draw_item(
            self, context, layout, data, item,
            icon, active_data, active_propname, index):
        pr = prefs()
        pm = item

        layout = layout.row(align=True)
        lh.lt(layout)

        num_cols = (
            pr.show_names +
            pr.show_hotkeys +
            pr.show_keymap_names +
            pr.show_tags)

        use_split = num_cols > 2
        if use_split:
            layout = lh.split(factor=0.5 if pr.show_names else 0.4)
            lh.row()

        lh.prop(
            item, "enabled", "", emboss=False,
            icon=ic_cb(item.enabled))

        lh.label("", item.ed.icon)
        # mark_row = layout.row(align=True)
        # mark_row.scale_y = 0.95
        # mark_row.operator(EOPS.PME_OT_none.bl_idname, text="", icon=item.ed.icon)

        col = 0

        hk = to_ui_hotkey(pm)
        show_hotkeys = pr.show_hotkeys
        if pr.show_names:
            lh.prop(pm, "label", "", emboss=False)
            col += 1
        elif show_hotkeys:
            if hk:
                lh.label(hk)
            else:
                lh.prop(pm, "label", "", emboss=False)
            show_hotkeys = False
            col += 1

        if use_split:
            lh.lt(layout)

        if pr.show_tags:
            if col == num_cols - 1:
                lh.row(layout, alignment='RIGHT')
            elif use_split:
                lh.row(layout)
            tag = pm.tag
            if tag:
                tag, _, rest = pm.tag.partition(",")
                if rest:
                    tag += ",.."
            lh.label(tag)
            col += 1

        if pr.show_keymap_names:
            if col == num_cols - 1:
                lh.row(layout, alignment='RIGHT')
            elif use_split:
                lh.row(layout)
            km_name, _, rest = pm.km_name.partition(",")
            if rest:
                km_name += ",.."
            lh.label(km_name)
            col += 1

        if show_hotkeys:
            if num_cols > 1:
                lh.row(layout, alignment='RIGHT')

            lh.label(hk)

    def filter_items(self, context, data, propname):
        pr = prefs()
        pie_menus = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        filtered = []
        ordered = []

        if self.filter_name and self.use_filter_show:
            filtered = helper_funcs.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item,
                pie_menus, "name")

        if not filtered:
            filtered = [self.bitflag_filter_item] * len(pie_menus)

        if pr.use_filter:
            for idx, pm in enumerate(pie_menus):
                if not pm.filter_list(pr):
                    filtered[idx] = 0

        if self.use_filter_sort_alpha:
            ordered = helper_funcs.sort_items_by_name(pie_menus, "name")

        return filtered, ordered


class PME_UL_pm_tree(bpy.types.UIList):
    locked = False
    groups = []
    collapsed_groups = set()
    expanded_folders = set()
    # keymap_names = None
    has_folders = False

    @staticmethod
    def save_state():
        pr = prefs()
        if not pr.tree_mode or not pr.save_tree:
            return

        data = dict(
            group_by=pr.group_by,
            groups=[v for v in PME_UL_pm_tree.collapsed_groups],
            folders=[v for v in PME_UL_pm_tree.expanded_folders],
        )
        path = os.path.join(ADDON_PATH, "data", "tree.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb+") as f:
            f.write(
                json.dumps(
                    data, indent=2, separators=(", ", ": "),
                    ensure_ascii=False).encode("utf8"))

    @staticmethod
    def load_state():
        pr = prefs()
        if not pr.tree_mode or not pr.save_tree:
            return

        path = os.path.join(ADDON_PATH, "data", "tree.json")
        if not os.path.isfile(path):
            return

        with open(path, "rb") as f:
            data = f.read()
            try:
                data = json.loads(data)
            except:
                return

            # groups, _, folders = s.partition("\n\n")
            if "group_by" in data:
                item = pr.bl_rna.properties[
                    "group_by"].enum_items.get(data["group_by"], None)
                if item:
                    pr["group_by"] = item.value
                    pr.tree.update()

            existing_groups = set(PME_UL_pm_tree.groups)
            groups = data.get("groups", None)
            if groups and isinstance(groups, list):
                PME_UL_pm_tree.collapsed_groups.clear()
                for v in groups:
                    v = v.strip()
                    if v and v in existing_groups:
                        PME_UL_pm_tree.collapsed_groups.add(v)

            folders = data.get("folders", None)
            if folders and isinstance(folders, list):
                PME_UL_pm_tree.expanded_folders.clear()
                for v in folders:
                    v = v.strip()
                    if v:
                        elems = v.split(CC.TREE_SPLITTER)
                        for i, e in enumerate(elems):
                            if i == 0:
                                if e not in existing_groups:
                                    break
                            elif e not in pr.pie_menus:
                                break
                        else:
                            PME_UL_pm_tree.expanded_folders.add(v)

    @staticmethod
    def link_is_collapsed(link):
        path = link.path
        p = link.group
        for i in range(0, len(path)):
            if p:
                p += CC.TREE_SPLITTER
            p += path[i]
            if p not in PME_UL_pm_tree.expanded_folders:
                return True
        return False

    @staticmethod
    def update_tree():
        if PME_UL_pm_tree.locked:
            return

        pr = prefs()

        if not pr.tree_mode:
            return

        tpr = temp_prefs()

        DBG_TREE and logh("Update Tree")
        num_links = len(tpr.links)
        sel_link, sel_folder = None, None
        sel_link = 0 <= tpr.links_idx < num_links and tpr.links[tpr.links_idx]
        if not sel_link or not sel_link.pm_name or \
                sel_link.pm_name not in pr.pie_menus:
            sel_link = None
        sel_folder = sel_link and sel_link.path and sel_link.path[-1]

        tpr.links.clear()
        PMLink.clear()

        folders = {}
        groups = {}
        files = set()

        pms = [
            pm for pm in pr.pie_menus
            if not pr.use_filter or pm.filter_list(pr)
        ]
        if pr.group_by == 'TAG':
            groups[CC.UNTAGGED] = []
            for t in tpr.tags:
                groups[t.name] = []
            pms.sort(key=lambda pm: pm.tag)
        elif pr.group_by == 'KEYMAP':
            pms.sort(key=lambda pm: pm.km_name)
        elif pr.group_by == 'TYPE':
            pms.sort(key=lambda pm: pm.ed.default_name)
        elif pr.group_by == 'KEY':
            pms.sort(key=lambda pm: to_key_name(pm.key))
        else:
            groups[CC.TREE_ROOT] = True
            pms.sort(key=lambda pm: pm.name)

        for pm in pms:
            if pr.group_by == 'TAG':
                if pm.tag:
                    tags = pm.tag.split(", ")
                    for t in tags:
                        groups[t].append(pm)
                else:
                    groups[CC.UNTAGGED].append(pm)
            elif pr.group_by == 'KEYMAP':
                kms = pm.km_name.split(", ")
                for km in kms:
                    if km not in groups:
                        groups[km] = []
                    groups[km].append(pm)
            elif pr.group_by == 'TYPE':
                if pm.ed.default_name not in groups:
                    groups[pm.ed.default_name] = []
                groups[pm.ed.default_name].append(pm)
            elif pr.group_by == 'KEY':
                key_name = to_key_name(pm.key)
                if key_name not in groups:
                    groups[key_name] = []
                groups[key_name].append(pm)

            for pmi in pm.pmis:
                if pmi.mode == 'MENU':
                    name, *_ = U.extract_str_flags(
                        pmi.text, CC.F_EXPAND, CC.F_EXPAND)
                    if name not in pr.pie_menus or \
                            pr.use_filter and \
                            not pr.pie_menus[name].filter_list(pr):
                        continue

                    if pm.name not in folders:
                        folders[pm.name] = []

                    if name not in folders[pm.name]:
                        folders[pm.name].append(name)
                        files.add(name)

        PME_UL_pm_tree.has_folders = len(folders) > 0

        if pr.use_groups:
            for kpms in groups.values():
                kpms.sort(key=lambda pm: pm.name)

        def add_children(files, group, path, idx, aidx):
            DBG_TREE and logi(" " * len(path) + "/".join(path))
            for file in files:
                if file in path:
                    continue
                link = PMLink.add()
                link.group = group
                link.pm_name = file
                link.folder = pm.name
                link.path.extend(path)
                if file == apm_name and (
                        not sel_link or sel_folder == pm.name):
                    aidx = idx
                idx += 1

                if file in folders:
                    link.is_folder = True
                    path.append(file)
                    new_idx, aidx = add_children(
                        folders[file], group, path, idx, aidx)
                    if new_idx == idx:
                        link.is_folder = False
                    idx = new_idx
                    path.pop()

            return idx, aidx

        idx = 0
        aidx = -1
        apm_name = len(pr.pie_menus) and pr.selected_pm.name

        groups_to_remove = []
        for k, v in groups.items():
            if not v or pr.group_by == 'TAG' and \
                    pr.tag_filter and k != pr.tag_filter:
                groups_to_remove.append(k)

        for g in groups_to_remove:
            groups.pop(g)

        # PME_UL_pm_tree.keymap_names = \
        group_names = sorted(groups.keys())

        if pr.group_by == 'TAG' and group_names and \
                group_names[-1] != CC.UNTAGGED and CC.UNTAGGED in group_names:
            group_names.remove(CC.UNTAGGED)
            group_names.append(CC.UNTAGGED)
        elif pr.group_by == 'KEY' and group_names and \
                group_names[-1] != "None" and "None" in group_names:
            group_names.remove("None")
            group_names.append("None")

        PME_UL_pm_tree.groups.clear()
        PME_UL_pm_tree.groups.extend(group_names)

        for g in group_names:
            if pr.use_groups:
                link = PMLink.add()
                link.label = g
                idx += 1

                pms = groups[g]

            path = []
            for pm in pms:
                # if pr.show_keymap_names and km_name != pm.km_name:
                #     km_name = pm.km_name
                #     link = PMLink.add()
                #     link.label = km_name
                #     idx += 1

                if pm.name in folders:
                    link = PMLink.add()
                    link.group = g
                    link.is_folder = True
                    link.pm_name = pm.name
                    if pm.name == apm_name and (
                            not sel_link or not sel_folder):
                        aidx = idx
                    idx += 1
                    path.append(pm.name)
                    idx, aidx = add_children(
                        folders[pm.name], g, path, idx, aidx)
                    path.pop()

                # elif pm.name not in files:
                else:
                    link = PMLink.add()
                    link.group = g
                    link.pm_name = pm.name
                    if pm.name == apm_name and (
                            not sel_link or not sel_folder):
                        aidx = idx
                    idx += 1

            pm_links = {}
            for link in tpr.links:
                if link.label:
                    continue
                if link.pm_name not in pm_links:
                    pm_links[link.pm_name] = []
                pm_links[link.pm_name].append(link)

            if pr.group_by == 'NONE':
                links_to_remove = set()
                fixed_links = set()
                for pm_name, links in pm_links.items():
                    if len(links) == 1:
                        continue
                    links.sort(key=lambda link: len(link.path), reverse=True)
                    can_be_removed = False
                    for link in links:
                        if len(link.path) == 0:
                            if can_be_removed and \
                                    link.pm_name not in fixed_links:
                                links_to_remove.add(link.name)
                                DBG_TREE and logi("REMOVE", link.pm_name)
                        else:
                            if not can_be_removed and \
                                    link.name not in links_to_remove and \
                                    link.path[0] != pm_name:
                                fixed_links.add(link.path[0])
                                DBG_TREE and logi("FIXED", link.path[0])
                                can_be_removed = True

                prev_link_will_be_removed = False
                for link in tpr.links:
                    if link.label:
                        prev_link_will_be_removed = False
                        continue
                    if link.path:
                        if prev_link_will_be_removed:
                            links_to_remove.add(link.name)
                    else:
                        prev_link_will_be_removed = \
                            link.name in links_to_remove

                for link in links_to_remove:
                    PME_UL_pm_tree.expanded_folders.discard(
                        tpr.links[link].fullpath())
                    tpr.links.remove(tpr.links.find(link))

                # if pr.use_groups:
                #     links_to_remove.clear()
                #     prev_link = None
                #     for link in tpr.links:
                #         if link.label and prev_link and prev_link.label:
                #             links_to_remove.add(prev_link.name)
                #         prev_link = link

                #     if prev_link and prev_link.label:
                #         links_to_remove.add(prev_link.name)

                #     for link in links_to_remove:
                #         tpr.links.remove(tpr.links.find(link))

            aidx = -1
            for i, link in enumerate(tpr.links):
                if link.pm_name == apm_name:
                    aidx = i
                    break

            tpr["links_idx"] = aidx
            if len(tpr.links):
                sel_link = tpr.links[tpr.links_idx]
                if sel_link.pm_name:
                    pm = pr.selected_pm
                    if pr.group_by == 'KEYMAP' and \
                            pm.km_name in PME_UL_pm_tree.collapsed_groups:
                        PME_UL_pm_tree.collapsed_groups.remove(pm.km_name)

            tag_redraw()

    def draw_item(
            self, context, layout, data, item,
            icon, active_data, active_propname, index):
        pr = prefs()
        layout = layout.row(align=True)
        lh.lt(layout)

        if item.pm_name:
            pm = pr.pie_menus[item.pm_name]

            num_cols = (
                pr.show_names +
                pr.show_hotkeys +
                pr.show_keymap_names +
                pr.show_tags)

            use_split = num_cols > 2
            if use_split:
                layout = lh.split(factor=0.5 if pr.show_names else 0.4)
                lh.row()

            lh.prop(
                pm, "enabled", "", CC.ICON_ON if pm.enabled else CC.ICON_OFF,
                emboss=False)

            for i in range(0, len(item.path)):
                lh.label("", icon=ic('BLANK1'))

            lh.label("", pm.ed.icon)
            # mark_row = layout.row(align=True)
            # mark_row.scale_y = 0.95
            # mark_row.operator(EOPS.PME_OT_none.bl_idname, text="", icon=pm.ed.icon)

            if item.is_folder:
                icon = 'TRIA_DOWN' \
                    if item.fullpath() in PME_UL_pm_tree.expanded_folders \
                    else 'TRIA_RIGHT'
                lh.operator(
                    PME_OT_tree_folder_toggle.bl_idname, "",
                    icon, emboss=False,
                    folder=item.fullpath(),
                    idx=index)

            col = 0

            hk = to_ui_hotkey(pm)
            show_hotkeys = pr.show_hotkeys
            if pr.show_names:
                lh.prop(pm, "label", "", emboss=False)
                col += 1
            elif show_hotkeys:
                if hk:
                    lh.label(hk)
                else:
                    lh.prop(pm, "label", "", emboss=False)
                show_hotkeys = False
                col += 1

            if use_split:
                lh.lt(layout)

            if pr.show_tags:
                if col == num_cols - 1:
                    lh.row(layout, alignment='RIGHT')
                elif use_split:
                    lh.row(layout)
                tag = pm.tag
                if tag:
                    tag, _, rest = pm.tag.partition(",")
                    if rest:
                        tag += ",.."
                lh.label(tag)
                col += 1

            if pr.show_keymap_names:
                if col == num_cols - 1:
                    lh.row(layout, alignment='RIGHT')
                elif use_split:
                    lh.row(layout)
                km_name, _, rest = pm.km_name.partition(",")
                if rest:
                    km_name += ",.."
                lh.label(km_name)
                col += 1

            if show_hotkeys:
                if num_cols > 1:
                    lh.row(layout, alignment='RIGHT')

                lh.label(hk)

        else:
            lh.row()
            # lh.layout.active = False
            lh.layout.scale_y = 0.95
            icon = 'TRIA_RIGHT_BAR' \
                if item.label in PME_UL_pm_tree.collapsed_groups else \
                'TRIA_DOWN_BAR'
            lh.operator(
                PME_OT_tree_group_toggle.bl_idname, item.label,
                icon, group=item.label, idx=index, all=False)
            # lh.label()
            icon = 'TRIA_LEFT_BAR' \
                if item.label in PME_UL_pm_tree.collapsed_groups else \
                'TRIA_DOWN_BAR'
            lh.operator(
                PME_OT_tree_group_toggle.bl_idname, "",
                icon, group=item.label, idx=index,
                all=True)

    def _draw_filter(self, context, layout):
        pr = prefs()

        col = layout.column(align=True)
        # col.prop(self, "filter_name", text="", icon='VIEWZOOM')
        col.prop(pr, "list_size")
        col.prop(pr, "num_list_rows")

    def draw_filter27(self, context, layout):
        self._draw_filter(context, layout)

    def draw_filter28(self, context, layout, reverse=False):
        self._draw_filter(context, layout)

    draw_filter = draw_filter27
    # draw_filter = draw_filter28 if is_28() else draw_filter27

    def filter_items(self, context, data, propname):
        pr = prefs()

        links = getattr(data, propname)
        filtered = [self.bitflag_filter_item] * len(links)

        cur_group = None
        for idx, link in enumerate(links):
            pm = None
            if link.path:
                pm = pr.pie_menus[link.path[0]]
            elif link.pm_name:
                pm = pr.pie_menus[link.pm_name]

            if link.label and pr.use_groups:
                cur_group = link.label

            if not pm:
                continue

            if cur_group in PME_UL_pm_tree.collapsed_groups:
                if pr.group_by == 'TAG':
                    if pm.has_tag(cur_group):
                        filtered[idx] = 0
                elif pr.group_by == 'KEYMAP' and cur_group in pm.km_name:
                    filtered[idx] = 0
                elif pr.group_by == 'TYPE' and cur_group == pm.ed.default_name:
                    filtered[idx] = 0
                elif pr.group_by == 'KEY' and cur_group == to_key_name(pm.key):
                    filtered[idx] = 0
            elif pr.tree_mode:
                if link.path and PME_UL_pm_tree.link_is_collapsed(link):
                    filtered[idx] = 0

        return filtered, []


class PME_OT_tree_folder_toggle(bpy.types.Operator):
    bl_idname = "pme.tree_folder_toggle"
    bl_label = ""
    bl_description = "Expand or collapse"
    bl_options = {'INTERNAL'}

    folder: bpy.props.StringProperty()
    idx: bpy.props.IntProperty()

    def execute(self, context):
        temp_prefs().links_idx = self.idx
        if self.folder:
            if self.folder in PME_UL_pm_tree.expanded_folders:
                PME_UL_pm_tree.expanded_folders.remove(self.folder)
            else:
                PME_UL_pm_tree.expanded_folders.add(self.folder)

        PME_UL_pm_tree.save_state()
        return {'FINISHED'}


class PME_OT_tree_folder_toggle_all(bpy.types.Operator):
    bl_idname = "pme.tree_folder_toggle_all"
    bl_label = ""
    bl_description = "Expand or collapse all items"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if PME_UL_pm_tree.expanded_folders:
            PME_UL_pm_tree.expanded_folders.clear()
        else:
            for link in temp_prefs().links:
                if link.is_folder:
                    PME_UL_pm_tree.expanded_folders.add(link.fullpath())

        PME_UL_pm_tree.save_state()
        return {'FINISHED'}


class PME_OT_tree_group_toggle(bpy.types.Operator):
    bl_idname = "pme.tree_group_toggle"
    bl_label = ""
    bl_description = "Expand or collapse groups"
    bl_options = {'INTERNAL'}

    group: bpy.props.StringProperty(options={'SKIP_SAVE'})
    idx: bpy.props.IntProperty(options={'SKIP_SAVE'})
    all: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        tpr = temp_prefs()

        if self.idx != -1:
            tpr.links_idx = self.idx

        if self.all:
            add = len(PME_UL_pm_tree.collapsed_groups) != \
                len(PME_UL_pm_tree.groups)
            if self.group:
                add = True

            for group in PME_UL_pm_tree.groups:
                if add:
                    PME_UL_pm_tree.collapsed_groups.add(group)
                else:
                    PME_UL_pm_tree.collapsed_groups.discard(group)

            if self.group and \
                    self.group in PME_UL_pm_tree.collapsed_groups:
                PME_UL_pm_tree.collapsed_groups.remove(self.group)

        else:
            if self.group in PME_UL_pm_tree.collapsed_groups:
                PME_UL_pm_tree.collapsed_groups.remove(self.group)
            else:
                PME_UL_pm_tree.collapsed_groups.add(self.group)

        PME_UL_pm_tree.save_state()
        return {'FINISHED'}


class PMIClipboard:
    def __init__(self):
        self.clear()

    def copy(self, pm, pmi):
        self.pm_mode = pm.mode
        self.mode = pmi.mode
        self.icon = pmi.icon
        self.text = pmi.text
        self.name = pmi.name

    def paste(self, pm, pmi):
        pmi.name = self.name
        pmi.icon = self.icon
        pmi.mode = self.mode
        pmi.text = self.text

    def clear(self):
        self.pm_mode = None
        self.mode = None
        self.icon = None
        self.text = None
        self.name = None

    def has_data(self):
        return self.mode is not None


class PME_OT_list_specials(bpy.types.Operator):
    bl_idname = "pme.list_specials"
    bl_label = ""
    bl_description = "Extra tools"
    bl_options = {'INTERNAL'}

    def draw_menu(self, menu, context):
        layout = menu.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        operator(
            layout, PME_OT_pm_enable_by_tag.bl_idname,
            "Enable by Tag", CC.ICON_ON,
            enable=True)
        operator(
            layout, PME_OT_pm_enable_by_tag.bl_idname,
            "Disable by Tag", CC.ICON_OFF,
            enable=False)

        layout.separator()

        operator(
            layout, PME_OT_tags.bl_idname, "Tag Enabled Items", 'SOLO_ON',
            group=True, action='TAG')
        operator(
            layout, PME_OT_tags.bl_idname, "Untag Enabled Items", 'SOLO_OFF',
            group=True, action='UNTAG')

        layout.separator()

        operator(
            layout, PME_OT_pm_remove_by_tag.bl_idname,
            "Remove Items by Tag", 'X')
        operator(
            layout, PME_OT_pm_remove.bl_idname, "Remove Enabled Items", 'X',
            mode='ENABLED')
        operator(
            layout, PME_OT_pm_remove.bl_idname, "Remove Disabled Items", 'X',
            mode='DISABLED')
        operator(
            layout, PME_OT_pm_remove.bl_idname, "Remove All Items", 'X',
            mode='ALL')

    def execute(self, context):
        context.window_manager.popup_menu(self.draw_menu)
        return {'FINISHED'}


class PMIData(bpy.types.PropertyGroup):
    _kmi = None
    errors = []
    infos = []

    @property
    def kmi(self):
        pr = prefs()
        if not PMIData._kmi:
            pr.kh.keymap()
            PMIData._kmi = pr.kh.operator(EOPS.PME_OT_none)
            PMIData._kmi.active = False

        return PMIData._kmi

    def check_pmi_errors(self, context):
        pr = prefs()
        pm = pr.selected_pm
        pm.ed.on_pmi_check(pm, self)

    def mode_update(self, context):
        tpr = temp_prefs()
        if prefs().selected_pm.mode == 'MODAL':
            if self.mode == 'COMMAND' and \
                    tpr.modal_item_prop_mode != 'KEY':
                tpr["modal_item_prop_mode"] = 0
                tpr.modal_item_hk.key = 'NONE'

        self.check_pmi_errors(context)

    mode: bpy.props.EnumProperty(
        items=CC.EMODE_ITEMS, description="Type of the item",
        update=mode_update)
    cmd: bpy.props.StringProperty(
        description="Python code", maxlen=CC.MAX_STR_LEN, update=update_data)
    cmd_ctx: bpy.props.EnumProperty(
        items=CC.OP_CTX_ITEMS,
        name="Execution Context",
        description="Execution context")
    cmd_undo: bpy.props.BoolProperty(
        name="Undo Flag",
        description="'Undo' positional argument")
    custom: bpy.props.StringProperty(
        description="Python code", maxlen=CC.MAX_STR_LEN, update=update_data)
    prop: bpy.props.StringProperty(
        description="Property", update=update_data)
    menu: bpy.props.StringProperty(
        description="Menu's name", update=update_data)
    expand_menu: bpy.props.BoolProperty(
        description="Expand Menu")
    use_cb: bpy.props.BoolProperty(
        name="Use Checkboxes instead of Toggle Buttons",
        description="Use checkboxes instead of toggle buttons")
    use_frame: bpy.props.BoolProperty(
        name="Use Frame", description="Use frame")
    icon: bpy.props.StringProperty(description="Icon")
    name: bpy.props.StringProperty(description="Name")

    def sname_update(self, context):
        if not self.name:
            self.name = self.sname

    sname: bpy.props.StringProperty(
        description="Suggested name", update=sname_update)
    key: bpy.props.EnumProperty(
        items=keymap_helper.key_items, description="Key pressed",
        update=update_data)
    any: bpy.props.BoolProperty(
        description="Any key pressed",
        update=update_data)
    ctrl: bpy.props.BoolProperty(
        description="Ctrl key pressed",
        update=update_data)
    shift: bpy.props.BoolProperty(
        description="Shift key pressed",
        update=update_data)
    alt: bpy.props.BoolProperty(
        description="Alt key pressed",
        update=update_data)
    oskey: bpy.props.BoolProperty(
        description="Operating system key pressed",
        update=update_data)
    key_mod: bpy.props.EnumProperty(
        items=keymap_helper.key_items,
        description="Regular key pressed as a modifier",
        update=update_data)

    def info(self, text=None, is_error=True):
        if text:
            if text not in self.errors:
                lst = self.errors if is_error else self.infos
                lst.append(text)
        else:
            self.errors.clear()
            self.infos.clear()

    def has_info(self):
        return self.errors or self.infos

    def has_errors(self, text=None):
        if not self.errors:
            return False
        if text:
            return text in self.errors
        return bool(self.errors)

    def extract_flags(self):
        return PMIItem.extract_flags(self)

    def parse_icon(self, default_icon='NONE'):
        return PMIItem.parse_icon(self, default_icon)


class PieMenuPrefs:
    def __init__(self):
        self.num_saves = 0
        self.lock = False
        self.confirm = 0
        self.threshold = 12
        self.animation_timeout = 0

    def save(self):
        self.num_saves += 1
        DBG_PM and logi("SAVE PM Prefs", self.num_saves, self.lock)
        if not self.lock:
            v = uprefs().view
            self.confirm = v.pie_menu_confirm
            self.threshold = v.pie_menu_threshold
            self.lock = True

    def restore(self):
        self.num_saves -= 1
        DBG_PM and logi("RESTORE", self.num_saves)
        if self.lock and self.num_saves == 0:
            v = uprefs().view
            v.pie_menu_confirm = self.confirm
            v.pie_menu_threshold = self.threshold
            self.lock = False


class PieMenuRadius:
    def __init__(self):
        self.radius = -1
        self.num_saves = 0

    @property
    def is_saved(self):
        return self.radius != -1

    def save(self):
        self.num_saves += 1
        if self.radius != -1:
            return

        v = uprefs().view
        self.animation_timeout = v.pie_animation_timeout
        self.radius = v.pie_menu_radius

    def restore(self):
        self.num_saves -= 1
        if self.num_saves == 0:
            v = uprefs().view
            v.pie_menu_radius = self.radius
            v.pie_animation_timeout = self.animation_timeout
            self.radius = -1


class TreeView:

    def expand_km(self, name):
        if name in PME_UL_pm_tree.collapsed_groups:
            PME_UL_pm_tree.collapsed_groups.remove(name)

    def lock(self):
        PME_UL_pm_tree.locked = True

    def unlock(self):
        PME_UL_pm_tree.locked = False

    def update(self):
        PME_UL_pm_tree.update_tree()


class InvalidPMEPreferences:
    bl_idname = ADDON_ID

    def draw(self, context):
        col = self.layout.column(align=True)
        row = col.row()
        row.alignment = 'CENTER'
        row.label(
            text="Please update Blender to the latest version",
            icon=ic('ERROR'))


class PMEPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    _mode = 'ADDON'
    editors = {}
    mode_history = []
    unregistered_pms = []
    old_pms = set()
    missing_kms = {}
    pie_menu_prefs = PieMenuPrefs()
    pie_menu_radius = PieMenuRadius()
    tree = TreeView()
    pmi_clipboard = PMIClipboard()
    pdr_clipboard = []
    rmc_clipboard = []
    window_kmis = []

    version: bpy.props.IntVectorProperty(size=3)
    pie_menus: bpy.props.CollectionProperty(type=PMItem)
    props: bpy.props.PointerProperty(type=UserProperties)

    def pie_menu_idx_get(self):
        return self.get("active_pie_menu_idx", 0)

    def pie_menu_idx_set(self, value):
        if self.active_pie_menu_idx == value:
            return

        self["active_pie_menu_idx"] = value
        self.pmi_data.info()
        temp_prefs().hidden_panels_idx = 0
        if self.active_pie_menu_idx >= 0:
            self.selected_pm.ed.on_pm_select(self.selected_pm)

    active_pie_menu_idx: bpy.props.IntProperty(
        get=pie_menu_idx_get, set=pie_menu_idx_set)

    overlay: bpy.props.PointerProperty(type=OverlayPrefs)
    list_size: bpy.props.IntProperty(
        name="List Width", description="Width of the list",
        default=40, min=20, max=80, subtype='PERCENTAGE'
    )
    num_list_rows: bpy.props.IntProperty(
        name="List Rows Number", description="Number of list rows",
        default=10, min=5, max=50
    )

    def update_interactive_panels(self, context=None):
        if PME_OT_interactive_panels_toggle.active == self.interactive_panels:
            return

        PME_OT_interactive_panels_toggle.active = self.interactive_panels

        for tp in bl_header_types():
            if self.interactive_panels:
                if isinstance(tp.append, MethodType) and hasattr(tp, "draw"):
                    tp.append(PME_OT_interactive_panels_toggle._draw_header)
            else:
                if isinstance(tp.remove, MethodType) and hasattr(tp, "draw"):
                    tp.remove(PME_OT_interactive_panels_toggle._draw_header)

        for tp in bl_menu_types():
            if self.interactive_panels:
                if isinstance(tp.append, MethodType) and hasattr(tp, "draw"):
                    tp.append(PME_OT_interactive_panels_toggle._draw_menu)
            else:
                if isinstance(tp.remove, MethodType) and hasattr(tp, "draw"):
                    tp.remove(PME_OT_interactive_panels_toggle._draw_menu)

        for tp in bl_panel_types():
            if getattr(tp, "bl_space_type", None) == CC.UPREFS:
                continue

            if tp.__name__ == "PROPERTIES_PT_navigation_bar":
                continue

            if self.interactive_panels:
                if isinstance(tp.append, MethodType):
                    tp.append(PME_OT_interactive_panels_toggle._draw)
            else:
                if isinstance(tp.remove, MethodType):
                    tp.remove(PME_OT_interactive_panels_toggle._draw)

        tag_redraw(True)

    interactive_panels: bpy.props.BoolProperty(
        name="Interactive Panels",
        description="Interactive panels",
        update=update_interactive_panels)

    auto_backup: bpy.props.BoolProperty(
        name="Auto Backup",
        description="Auto backup menus",
        default=True)
    expand_item_menu: bpy.props.BoolProperty(
        name="Expand Slot Tools", description="Expand slot tools")
    icon_filter: bpy.props.StringProperty(
        description="Filter", options={'TEXTEDIT_UPDATE'})
    hotkey: bpy.props.PointerProperty(type=keymap_helper.Hotkey)
    hold_time: bpy.props.IntProperty(
        name="Hold Mode Timeout", description="Hold timeout (ms)",
        default=200, min=50, max=1000, step=10)
    chord_time: bpy.props.IntProperty(
        name="Chord Mode Timeout", description="Chord timeout (ms)",
        default=300, min=50, max=1000, step=10)
    use_chord_hint: bpy.props.BoolProperty(
        name="Show Next Key Chord",
        description="Show next key chord in the sequence",
        default=True)
    tab: bpy.props.EnumProperty(
        items=(
            ('EDITOR', "Editor", ""),
            ('SETTINGS', "Settings", ""),
        ),
        options={'HIDDEN'})

    def update_show_names(self, context):
        if not self.show_names and not self.show_hotkeys:
            self["show_hotkeys"] = True

    show_names: bpy.props.BoolProperty(
        default=True, description="Show names",
        update=update_show_names)

    def update_show_hotkeys(self, context):
        if not self.show_hotkeys and not self.show_names:
            self["show_names"] = True

    show_hotkeys: bpy.props.BoolProperty(
        default=True, description="Show hotkeys",
        update=update_show_hotkeys)

    def update_tree(self, context=None):
        self.tree.update()

    # def update_show_keymap_names(self, context=None):
    #     if self.tree_mode:
    #         if self.show_tags:
    #             self["show_tags"] = False
    #             PME_UL_pm_tree.collapsed_groups.clear()
    #         self.tree.update()

    show_keymap_names: bpy.props.BoolProperty(
        name="Keymap Names",
        default=False, description="Show keymap names")

    # def update_show_tags(self, context=None):
    #     if self.tree_mode:
    #         if self.show_keymap_names:
    #             self["show_keymap_names"] = False
    #             PME_UL_pm_tree.collapsed_groups.clear()
    #         self.tree.update()

    show_tags: bpy.props.BoolProperty(
        name="Tags",
        default=False, description="Show tags")

    def update_group_by(self, context=None):
        if self.tree_mode:
            PME_UL_pm_tree.expanded_folders.clear()
            PME_UL_pm_tree.collapsed_groups.clear()
            self.tree.update()
            if self.group_by != 'NONE':
                bpy.ops.pme.tree_group_toggle(all=True)

            PME_UL_pm_tree.save_state()

    group_by: bpy.props.EnumProperty(
        name="Group by", description="Group items by",
        items=(
            ('NONE', "None", "", ic('CHECKBOX_DEHLT'), 0),
            ('KEYMAP', "Keymap", "", ic('SPLITSCREEN'), 1),
            ('TYPE', "Type", "", ic('PROP_CON'), 2),
            ('TAG', "Tag", "", ic('SOLO_OFF'), 3),
            ('KEY', "Key", "", ic('FILE_FONT'), 4),
        ),
        update=update_group_by)

    num_icons_per_row: bpy.props.IntProperty(
        name="Icons per Row", description="Icons per row",
        default=30, min=1, max=100)
    pie_extra_slot_gap_size: bpy.props.IntProperty(
        name="Extra Pie Slot Gap Size",
        description="Extra pie slot gap size",
        default=5, min=3, max=100)
    show_custom_icons: bpy.props.BoolProperty(
        default=False, description="Show custom icons")
    show_advanced_settings: bpy.props.BoolProperty(
        default=False, description="Advanced settings")
    show_list: bpy.props.BoolProperty(
        default=True, description="Show the list")
    show_sidepanel_prefs: bpy.props.BoolProperty(
        name="Show PME Preferences in 3DView's N-panel",
        description="Show PME preferences in 3D View N-panel")

    use_filter: bpy.props.BoolProperty(
        description="Use filters", update=update_tree)
    mode_filter: bpy.props.EnumProperty(
        items=CC.PM_ITEMS_M, default=CC.PM_ITEMS_M_DEFAULT,
        description="Show items",
        options={'ENUM_FLAG'},
        update=update_tree
    )
    tag_filter: bpy.props.StringProperty(update=update_tree)
    show_only_new_pms: bpy.props.BoolProperty(
        description="Show only new menus", update=update_tree
    )
    cache_scripts: bpy.props.BoolProperty(
        name="Cache External Scripts", description="Cache external scripts",
        default=True)
    panel_info_visibility: bpy.props.EnumProperty(
        name="Panel Info",
        description="Show panel info",
        items=(
            ('NAME', "Name", "", 'SYNTAX_OFF', 1),
            ('CLASS', "Class", "", 'COPY_ID', 2),
            ('CTX', "Context", "", 'WINDOW', 4),
            ('CAT', "Category", "", 'MENU_PANEL', 8),
        ),
        default={'NAME', 'CLASS'},
        options={'ENUM_FLAG'}
    )
    show_pm_title: bpy.props.BoolProperty(
        name="Show Title", description="Show pie menu title",
        default=True)
    restore_mouse_pos: bpy.props.BoolProperty(
        name="Restore Mouse Position",
        description=(
            "Restore mouse position "
            "after releasing the pie menu's hotkey"))
    use_spacer: bpy.props.BoolProperty(
        name="Use 'Spacer' Separator by Default",
        description="Use 'Spacer' separator by default",
        default=False)
    default_popup_mode: bpy.props.EnumProperty(
        description="Default popup mode",
        items=CC.PD_MODE_ITEMS,
        default='PANEL',
        update=lambda s, c: s.ed('DIALOG').update_default_pmi_data()
    )
    use_cmd_editor: bpy.props.BoolProperty(
        name="Use Operator Properties Editor",
        description="Use operator properties editor in Command tab",
        default=True)

    toolbar_width: bpy.props.IntProperty(
        name="Max Width",
        description="Maximum width of vertical toolbars",
        subtype='PIXEL',
        default=60)
    toolbar_height: bpy.props.IntProperty(
        name="Max Height",
        description="Maximum height of horizontal toolbars",
        subtype='PIXEL',
        default=60)

    def get_debug_mode(self):
        return bpy.app.debug_wm

    def set_debug_mode(self, value):
        bpy.app.debug_wm = value

    debug_mode: bpy.props.BoolProperty(
        name="Debug Mode", description="Debug Mode\nShow error messages",
        get=get_debug_mode, set=set_debug_mode)

    # show_errors: bpy.props.BoolProperty(
    #     description="Show error messages")

    def update_tree_mode(self, context):
        if self.tree_mode:
            # if self.show_keymap_names and self.show_tags:
            #     self["show_keymap_names"] = False
            PME_UL_pm_tree.collapsed_groups.clear()
            PME_UL_pm_tree.update_tree()

    tree_mode: bpy.props.BoolProperty(
        description="Tree Mode", update=update_tree_mode)

    def save_tree_update(self, context):
        if self.save_tree and self.tree_mode:
            PME_UL_pm_tree.save_state()

    save_tree: bpy.props.BoolProperty(
        name="Save and Restore Tree View State",
        description=(
            "Save and restore tree view state\n"
            "from %s/data/tree.json file") % ADDON_ID,
        default=False,
        update=save_tree_update)

    def get_maximize_prefs(self):
        return bpy.types.USERPREF_PT_addons.draw == draw_addons_maximized

    def set_maximize_prefs(self, value):
        if value and not is_userpref_maximized():
            bpy.ops.pme.userpref_show(addon="pie_menu_editor")

        elif not value and is_userpref_maximized():
            bpy.ops.pme.userpref_restore()

    maximize_prefs: bpy.props.BoolProperty(
        description="Maximize preferences area",
        get=get_maximize_prefs, set=set_maximize_prefs)

    # use_square_buttons: bpy.props.BoolProperty(
    #     name="Use Square Icon-Only Buttons",
    #     description="Use square icon-only buttons")
    pmi_data: bpy.props.PointerProperty(type=PMIData)
    scripts_filepath: bpy.props.StringProperty(subtype='FILE_PATH', default=SCRIPT_PATH)

    def _update_mouse_threshold(self, context):
        OPS.PME_OT_modal_base.prop_data.clear()

    mouse_threshold_float: bpy.props.IntProperty(
        name="Slider (Float)", description="Slider (Float)",
        subtype='PIXEL', default=10,
        update=_update_mouse_threshold)
    mouse_threshold_int: bpy.props.IntProperty(
        name="Slider (Int)", description="Slider (Integer)",
        subtype='PIXEL', default=20,
        update=_update_mouse_threshold)
    mouse_threshold_bool: bpy.props.IntProperty(
        name="Checkbox (Bool)", description="Checkbox (Boolean)",
        subtype='PIXEL', default=40,
        update=_update_mouse_threshold)
    mouse_threshold_enum: bpy.props.IntProperty(
        name="Drop-Down List (Enum)", description="Drop-down list (Enum)",
        subtype='PIXEL', default=40,
        update=_update_mouse_threshold)
    use_mouse_threshold_bool: bpy.props.BoolProperty(
        description="Use mouse movement to change the value",
        default=True)
    use_mouse_threshold_enum: bpy.props.BoolProperty(
        description="Use mouse movement to change the value",
        default=True)
    mouse_dir_mode: bpy.props.EnumProperty(
        name="Mode", description="Mode",
        items=(
            ('H', "Horizontal", ""),
            ('V', "Vertical", ""),
        ))

    @property
    def tree_ul(self):
        return PME_UL_pm_tree

    @property
    def selected_pm(self):
        if 0 <= self.active_pie_menu_idx < len(self.pie_menus):
            return self.pie_menus[self.active_pie_menu_idx]
        return None

    @property
    def mode(self):
        return PMEPreferences._mode

    @mode.setter
    def mode(self, value):
        PMEPreferences._mode = value

    def enter_mode(self, mode):
        self.mode_history.append(PMEPreferences._mode)
        PMEPreferences._mode = mode

    def leave_mode(self):
        PMEPreferences._mode = self.mode_history.pop()

    def is_edit_mode(self):
        return 'PMI' in PMEPreferences.mode_history

    @property
    def use_groups(self):
        return self.tree_mode and self.group_by != 'NONE'

    def get_threshold(self, prop_type=None):
        if prop_type == 'FLOAT':
            return self.mouse_threshold_float
        elif prop_type == 'INT':
            return self.mouse_threshold_int
        elif prop_type == 'ENUM':
            return self.mouse_threshold_enum
        elif prop_type == 'BOOL':
            return self.mouse_threshold_bool

        return 20

    def enable_window_kmis(self, value=True):
        for kmi in self.window_kmis:
            kmi.active = value

    def add_pm(self, mode='PMENU', name=None, duplicate=False):
        link = None
        pr = prefs()
        tpr = temp_prefs()

        if "active_pie_menu_idx" not in self:
            self["active_pie_menu_idx"] = 0

        if self.tree_mode and len(tpr.links):
            link = tpr.links[tpr.links_idx]
            if link.path:
                self["active_pie_menu_idx"] = self.pie_menus.find(link.path[0])

        tpr.links_idx = -1

        self.pie_menus.add()
        if self["active_pie_menu_idx"] < len(self.pie_menus) - 1:
            self["active_pie_menu_idx"] += 1
        self.pie_menus.move(
            len(self.pie_menus) - 1, self["active_pie_menu_idx"])
        pm = self.selected_pm

        pm.mode = mode
        pm.name = self.unique_pm_name(name or pm.ed.default_name)

        if self.tree_mode and self.show_keymap_names \
                and not duplicate and link:
            if link.label:
                pm.km_name = link.label
            elif link.path and link.path[0] in self.pie_menus:
                pm.km_name = self.pie_menus[link.path[0]].km_name
            elif link.pm_name and link.pm_name in self.pie_menus:
                pm.km_name = self.pie_menus[link.pm_name].km_name

            if pm.km_name in PME_UL_pm_tree.collapsed_groups:
                PME_UL_pm_tree.collapsed_groups.remove(pm.km_name)

        pm.data = pm.ed.default_pmi_data

        if duplicate:
            apm = pr.pie_menus[name]

            pm.mode = apm.mode
            pm.km_name = apm.km_name
            if pm.km_name in PME_UL_pm_tree.collapsed_groups:
                PME_UL_pm_tree.collapsed_groups.remove(pm.km_name)

            pm.data = apm.data
            pm.open_mode = apm.open_mode
            pm.poll_cmd = apm.poll_cmd
            pm.tag = apm.tag

        else:
            pm.ed.on_pm_add(pm)

        pm.register_hotkey()

        pm.ed.on_pm_select(pm)

        return pm

    def remove_pm(self, pm=None):
        tpr = temp_prefs()
        idx = 0

        if pm:
            idx = self.pie_menus.find(pm.name)
        else:
            idx = self.active_pie_menu_idx

        if idx < 0 or idx >= len(self.pie_menus):
            return

        apm = self.pie_menus[idx]
        new_idx = -1
        num_links = len(tpr.links)
        if self.tree_mode and num_links:
            d = 1
            i = tpr.links_idx + d
            while True:
                if i >= num_links:
                    d = -1
                    i = tpr.links_idx + d
                    continue
                if i < 0:
                    break
                link = tpr.links[i]
                if not link.label and not link.path and \
                        link.pm_name != apm.name:
                    tpr["links_idx"] = i
                    new_idx = self.pie_menus.find(link.pm_name)
                    break
                i += d

        apm.key_mod = 'NONE'

        apm.ed.on_pm_remove(apm)

        apm.unregister_hotkey()

        if apm.name in self.old_pms:
            self.old_pms.remove(apm.name)

        self.pie_menus.remove(idx)

        if new_idx >= idx:
            new_idx -= 1

        if new_idx >= 0:
            self.active_pie_menu_idx = new_idx
        elif self.active_pie_menu_idx >= len(self.pie_menus) and \
                self.active_pie_menu_idx > 0:
            self.active_pie_menu_idx -= 1

    def unique_pm_name(self, name):
        return uname(self.pie_menus, name)

    def from_dict(self, value):
        pass

    def to_dict(self):
        d = {}
        return d

    def _draw_pm_item(self, context, layout):
        pr = prefs()
        tpr = temp_prefs()
        pm = pr.selected_pm

        lh.lt(layout)
        split = lh.split(None, 0.75, False)
        lh.row()

        data = pr.pmi_data
        icon = data.parse_icon('FILE_HIDDEN')

        if pm.ed.use_slot_icon:
            lh.operator(
                WM_OT_pmi_icon_select.bl_idname, "", icon,
                idx=pme.context.edit_item_idx,
                icon="")

        lh.prop(data, "name", "")

        if data.name != data.sname and data.sname:
            lh.operator(
                PME_OT_pmi_name_apply.bl_idname, "", 'BACK',
                idx=pme.context.edit_item_idx)

            lh.prop(data, "sname", "", enabled=False)

        lh.lt(split)
        lh.operator(
            WM_OT_pmi_data_edit.bl_idname, "OK",
            idx=pme.context.edit_item_idx, ok=True,
            enabled=not data.has_errors())
        lh.operator(WM_OT_pmi_data_edit.bl_idname, "Cancel", idx=-1)

        lh.lt(layout)

        mode_col = lh.column(layout)
        lh.row(mode_col)
        pm.ed.draw_slot_modes(lh.layout, pm, data, pme.context.edit_item_idx)
        lh.operator(
            OPS.PME_OT_pmidata_specials_call.bl_idname, "", 'COLLAPSEMENU')

        lh.box(mode_col)
        subcol = lh.column()

        data_mode = data.mode
        if data_mode in CC.MODAL_CMD_MODES:
            data_mode = 'COMMAND'

        if data_mode == 'COMMAND':
            lh.row(subcol)
            if pm.mode == 'MODAL' and data.mode == 'COMMAND':
                lh.prop(
                    tpr, "modal_item_show", "",
                    ic_eye(tpr.modal_item_show))

            icon = 'ERROR' if data.has_errors(CC.W_PMI_SYNTAX) else 'NONE'
            lh.prop(data, "cmd", "", icon)

            if pm.mode == 'STICKY' and PME_OT_sticky_key_edit.pmi_prop and \
                    pme.context.edit_item_idx == 0 and not data.has_errors():
                lh.lt(subcol)
                lh.operator(PME_OT_sticky_key_edit.bl_idname)

        elif data_mode == 'PROP':
            lh.row(subcol)
            if pm.mode == 'MODAL':
                lh.prop(
                    tpr, "modal_item_show", "",
                    ic_eye(tpr.modal_item_show))

            icon = 'ERROR' if data.has_errors(CC.W_PMI_SYNTAX) else 'NONE'
            lh.prop(data, "prop", "", icon)

            lh.lt(subcol)
            lh.sep()
            lh.row(alignment='LEFT')
            # lh.prop(data, "use_cb", label)
            lh.operator(
                WM_OT_pmi_icon_tag_toggle.bl_idname,
                "Use Checkboxes instead of Toggle Buttons",
                ic_cb(CC.F_CB in data.icon),
                idx=-1,
                tag=CC.F_CB,
                emboss=False)

        elif data_mode == 'MENU':
            icon = 'ERROR' if data.has_errors(CC.W_PMI_MENU) else 'NONE'
            if data.menu in pr.pie_menus:
                icon = pr.pie_menus[data.menu].ed.icon
            row = lh.row(subcol)
            row.prop_search(
                data, "menu", tpr, "pie_menus", text="", icon=ic(icon))

            sub_pm = data.menu and data.menu in pr.pie_menus and \
                pr.pie_menus[data.menu]
            if sub_pm:
                label = None
                if sub_pm.mode == 'RMENU':
                    label = "Open on Mouse Over"
                elif sub_pm.mode == 'DIALOG' and pm.mode != 'RMENU':
                    label = "Expand Popup Dialog"
                if label:
                    lh.lt(subcol)
                    lh.sep()
                    lh.prop(data, "expand_menu", label)

                if sub_pm.mode == 'DIALOG' and pm.mode == 'PMENU' and \
                        data.expand_menu:
                    lh.prop(data, "use_frame")
                    lh.operator(
                        "pme.exec",
                        "Make Popup Wider",
                        cmd=(
                            "d = prefs().pmi_data; "
                            "d.mode = 'CUSTOM'; "
                            "d.custom = '"
                            "col = L.%s(); "
                            "col.scale_x = 1.01; "
                            "draw_menu(\"%s\", layout=col)'"
                        ) % ("box" if data.use_frame else "column", data.menu))

        elif data_mode == 'HOTKEY':
            row = lh.row(subcol)
            icon = 'ERROR' if data.has_errors(CC.W_PMI_HOTKEY) else 'NONE'
            row.alert = icon == 'ERROR'
            lh.prop(data, "key", "", icon, event=True)

            lh.row(subcol)
            lh.prop(data, "ctrl", "Ctrl", toggle=True)
            lh.prop(data, "shift", "Shift", toggle=True)
            lh.prop(data, "alt", "Alt", toggle=True)
            lh.prop(data, "oskey", "OSkey", toggle=True)
            lh.prop(data, "key_mod", "", event=True)

        elif data_mode == 'CUSTOM':
            lh.row(subcol)
            icon = 'ERROR' if data.has_errors(CC.W_PMI_SYNTAX) else 'NONE'
            lh.prop(data, "custom", "", icon)

        if pr.use_cmd_editor and data_mode == 'COMMAND' and \
                data.kmi.idname and not data.has_errors(CC.W_PMI_SYNTAX):
            lh.lt(mode_col.box().column(align=True))

            lh.save()
            lh.label(
                operator_utils.operator_label(data.kmi.idname) + " Operator:")
            lh.sep()
            lh.row(align=False)
            lh.prop(data, "cmd_ctx", "")
            lh.prop(data, "cmd_undo", toggle=True)
            lh.restore()

            lh.template_keymap_item_properties(data.kmi)

            lh.sep()

            lh.row(align=False)
            lh.operator(
                PME_OT_pmi_cmd_generate.bl_idname,
                "Clear", clear=True)
            lh.operator(
                PME_OT_pmi_cmd_generate.bl_idname, "Apply", 'FILE_TICK')

        if pm.mode == 'MODAL':
            if data.mode == 'COMMAND':
                lh.row(subcol)

                if tpr.modal_item_custom != 'HIDDEN':
                    if tpr.modal_item_custom:
                        lh.layout.alert = data.has_errors(CC.W_PMI_EXPR)
                        lh.prop(tpr, "modal_item_custom", "")
                        lh.operator(
                            OPS.PME_OT_exec.bl_idname, "", 'X',
                            cmd="temp_prefs().modal_item_custom = ''")
                    else:
                        lh.operator(
                            OPS.PME_OT_exec.bl_idname, "Display Custom Value",
                            cmd="temp_prefs().modal_item_custom = "
                            "'\"Path or string\"'")

                lh.lt(layout.column(align=True))
                lh.layout.prop_enum(tpr, "modal_item_prop_mode", 'KEY')

                lh.box()
                # lh.prop(tpr, "modal_item_hk", "", event=True)
                tpr.modal_item_hk.draw(lh.layout, key_mod=False, alert=True)

            elif data.mode == 'PROP':
                # lh.lt(mode_col.box().column(align=True))
                if tpr.prop_data.path:
                    lh.row(subcol)
                    pd = tpr.prop_data
                    min_active = not U.isclose(pd.min, tpr.modal_item_prop_min)
                    max_active = not U.isclose(pd.max, tpr.modal_item_prop_max)
                    step_active = tpr.modal_item_prop_step_is_set
                    lh.prop(tpr, "modal_item_prop_min", active=min_active)
                    lh.prop(tpr, "modal_item_prop_max", active=max_active)
                    lh.prop(tpr, "modal_item_prop_step", active=step_active)
                    if min_active or max_active or step_active:
                        lh.operator(PME_OT_prop_data_reset.bl_idname, "", 'X')

                    lh.row(subcol)
                    if tpr.modal_item_custom != 'HIDDEN':
                        if tpr.modal_item_custom:
                            lh.layout.alert = data.has_errors(CC.W_PMI_EXPR)
                            lh.prop(tpr, "modal_item_custom", "")
                            lh.operator(
                                OPS.PME_OT_exec.bl_idname, "", 'X',
                                cmd="temp_prefs().modal_item_custom = ''")
                        else:
                            lh.operator(
                                OPS.PME_OT_exec.bl_idname, "Display Custom Value",
                                cmd="temp_prefs().modal_item_custom = "
                                "'\"Path or string\"'")

                lh.lt(layout)
                lh.column()
                lh.save()
                lh.row()
                lh.prop(tpr, "modal_item_prop_mode", expand=True)
                lh.restore()

                if tpr.modal_item_prop_mode == 'KEY':
                    lh.box()
                    tpr.modal_item_hk.draw(
                        lh.layout, key_mod=False, alert=True)
                elif tpr.modal_item_prop_mode == 'WHEEL':
                    lh.box()
                    tpr.modal_item_hk.draw(
                        lh.layout, key=False, key_mod=False)

        if data.has_info():
            lh.box(layout)
            lh.column()
            for error in data.errors:
                lh.label(error, icon='INFO')
            for info in data.infos:
                lh.label(info, icon='QUESTION')

    def _draw_icons(self, context, layout):
        pr = prefs()
        tpr = temp_prefs()
        pm = pr.selected_pm
        pmi = pm.pmis[pme.context.edit_item_idx]

        lh.lt(layout)
        split = lh.split(None, 0.75, False)
        lh.row()

        data = pmi
        if pr.is_edit_mode():
            data = pr.pmi_data

        icon = data.parse_icon('FILE_HIDDEN')

        lh.prop(data, "name", "", icon)
        lh.sep()
        lh.prop(pr, "icon_filter", "", icon='VIEWZOOM')
        # if pr.icon_filter:
        #     lh.operator(WM_OT_icon_filter_clear.bl_idname, "", 'X')

        lh.lt(split)
        lh.operator(
            WM_OT_pmi_icon_select.bl_idname, "None",
            idx=pme.context.edit_item_idx,
            icon='NONE')

        lh.operator(
            WM_OT_pmi_icon_select.bl_idname, "Cancel", idx=-1)

        icon_filter = pr.icon_filter.upper()

        layout = layout.column(align=True)
        row = layout.row(align=True)
        row.prop(tpr, "icons_tab", expand=True)

        if tpr.icons_tab == 'CUSTOM':
            # row.prop(
            #     pr, "show_custom_icons", text="Custom Icons", toggle=True)

            row.operator(
                PME_OT_icons_refresh.bl_idname, text="",
                icon=ic('FILE_REFRESH'))

            p = row.operator("wm.path_open", text="", icon=ic('FILE_FOLDER'))
            p.filepath = ph.path

        if tpr.icons_tab == 'BLENDER':
            box = layout.box()
            column = box.column(align=True)
            row = column.row(align=True)
            row.alignment = 'CENTER'
            idx = 0

            for k, i in bpy.types.UILayout.bl_rna.functions[
                    "prop"].parameters["icon"].enum_items.items():
                icon = i.identifier
                if k == 'NONE':
                    continue
                if icon_filter != "" and icon_filter not in icon:
                    continue

                p = row.operator(
                    WM_OT_pmi_icon_select.bl_idname, text="",
                    icon=ic(icon), emboss=False)
                p.idx = pme.context.edit_item_idx
                p.icon = icon
                idx += 1
                if idx > pr.num_icons_per_row - 1:
                    idx = 0
                    row = column.row(align=True)
                    row.alignment = 'CENTER'

            if idx != 0:
                while idx < pr.num_icons_per_row:
                    row.label(text="", icon=ic('BLANK1'))
                    idx += 1

        elif tpr.icons_tab == 'CUSTOM':
            icon_filter = pr.icon_filter

            box = layout.box()
            column = box.column(align=True)
            row = column.row(align=True)
            row.alignment = 'CENTER'
            idx = 0

            for icon in sorted(ph.get_names()):
                if icon_filter != "" and icon_filter not in icon:
                    continue

                p = row.operator(
                    WM_OT_pmi_icon_select.bl_idname, text="",
                    icon_value=ph.get_icon(icon), emboss=False)
                p.idx = pme.context.edit_item_idx
                p.icon = CC.F_CUSTOM_ICON + icon
                idx += 1
                if idx > pr.num_icons_per_row - 1:
                    idx = 0
                    row = column.row(align=True)
                    row.alignment = 'CENTER'

            if idx != 0:
                while idx < pr.num_icons_per_row:
                    row.label(text="", icon=ic('BLANK1'))
                    idx += 1

        layout.prop(pr, "num_icons_per_row", slider=True)

    def _draw_tab_editor(self, context, layout):
        pr = prefs()
        tpr = temp_prefs()
        pm = None
        link = None
        if pr.tree_mode and tpr.links_idx >= 0:
            if len(tpr.links) > 0:
                link = tpr.links[tpr.links_idx]
                if link.pm_name:
                    pm = pr.pie_menus[link.pm_name]
        else:
            if len(pr.pie_menus):
                pm = pr.selected_pm

        if pr.show_list:
            spl = split(layout, pr.list_size / 100)
            row = spl.row()
            column1 = row.column(align=True)
            row = spl.row()
            column2 = row.column(align=True)
        else:
            row = layout

        column3 = row.column()

        if pr.show_list:
            subrow = column1

            if pr.use_filter:
                subrow = column1.row()
                subcol = subrow.column(align=True)

                subcol.prop(
                    pr, "show_only_new_pms", text="", icon=ic('FILE_NEW'),
                    toggle=True)
                subcol.separator()

                subcol.prop(
                    pr, "mode_filter", text="",
                    expand=True, icon_only=True)

                subcol.separator()
                icon = 'SOLO_ON' if pr.tag_filter else 'SOLO_OFF'
                subcol.operator(
                    PME_OT_tags_filter.bl_idname, text="", icon=ic(icon))

                column1 = subrow.column(align=True)

            if pr.tree_mode:
                column1.template_list(
                    "PME_UL_pm_tree", "",
                    tpr, "links",
                    tpr, "links_idx", rows=pr.num_list_rows)
            else:
                column1.template_list(
                    "WM_UL_pm_list", "",
                    self, "pie_menus", self, "active_pie_menu_idx",
                    rows=pr.num_list_rows)

            row = column1.row(align=True)
            p = row.operator(WM_OT_pm_import.bl_idname, text="Import")
            p.mode = ""

            if pm or link:
                p = row.operator(WM_OT_pm_export.bl_idname, text="Export")
                p.mode = ""

            lh.lt(column2)

            if len(pr.pie_menus):
                lh.operator(
                    OPS.PME_OT_pm_search_and_select.bl_idname, "", 'VIEWZOOM')

                lh.sep()

            lh.operator(
                PME_OT_pm_add.bl_idname, "", 'ZOOMIN',
                mode="")

            if pm:
                lh.operator(WM_OT_pm_duplicate.bl_idname, "", 'GHOST')
                lh.operator(PME_OT_pm_remove.bl_idname, "", 'ZOOMOUT')

            lh.sep()

            if pm and not pr.tree_mode:
                if not link or not link.path:
                    lh.operator(
                        WM_OT_pm_move.bl_idname, "", 'TRIA_UP',
                        direction=-1)
                    lh.operator(
                        WM_OT_pm_move.bl_idname, "", 'TRIA_DOWN',
                        direction=1)
                lh.operator(WM_OT_pm_sort.bl_idname, "", 'SORTALPHA')

                lh.sep()

            lh.operator(
                PME_OT_pm_enable_all.bl_idname, "", CC.ICON_ON).enable = True
            lh.operator(
                PME_OT_pm_enable_all.bl_idname, "", CC.ICON_OFF).enable = False

            if pr.tree_mode and PME_UL_pm_tree.has_folders:
                lh.sep(group='EXP_COL_ALL')
                icon = 'TRIA_RIGHT' \
                    if PME_UL_pm_tree.expanded_folders else \
                    'TRIA_DOWN'
                lh.operator(PME_OT_tree_folder_toggle_all.bl_idname, "", icon)

            if pr.use_groups and len(pr.pie_menus):
                lh.sep(group='EXP_COL_ALL')
                icon = 'TRIA_LEFT_BAR' \
                    if len(PME_UL_pm_tree.collapsed_groups) != \
                    len(PME_UL_pm_tree.groups) else \
                    'TRIA_DOWN_BAR'
                lh.operator(
                    PME_OT_tree_group_toggle.bl_idname, "", icon,
                    group="",
                    idx=-1,
                    all=True)

            lh.sep(group='SPEC')
            lh.operator(PME_OT_list_specials.bl_idname, "", 'COLLAPSEMENU')

        if not pm:
            if link and link.label:
                subcol = column3.box().column(align=True)
                subrow = subcol.row()
                subrow.enabled = False
                subrow.scale_y = pr.num_list_rows + CC.LIST_PADDING
                subrow.alignment = 'CENTER'
                subrow.label(text=link.label)
                subcol.row(align=True)
            else:
                subcol = column3.box().column(align=True)
                subrow = subcol.row()
                subrow.enabled = False
                subrow.scale_y = pr.num_list_rows + CC.LIST_PADDING
                subrow.alignment = 'CENTER'
                subrow.label(text=" ")
                subcol.row(align=True)
            return

        pm.ed.draw_pm_name(column3, pm)

        column = column3.column(align=True)
        pm.ed.draw_keymap(column, pm)
        pm.ed.draw_hotkey(column, pm)
        pm.ed.draw_items(column3, pm)

    def _draw_hprop(self, layout, data, prop, url=None):
        row = layout.row(align=True)
        row.prop(data, prop)
        if url:
            operator(
                row, OPS.PME_OT_docs.bl_idname, "", 'QUESTION',
                emboss=False,
                url=url)

    def _draw_hlabel(self, layout, text, url=None):
        row = layout.row(align=True)
        row.label(text=text)
        if url:
            operator(
                row, OPS.PME_OT_docs.bl_idname, "", 'QUESTION',
                emboss=False,
                url=url)

    def _draw_tab_settings(self, context, layout):
        pr = prefs()
        tpr = temp_prefs()

        col = layout.column(align=True)

        col.row(align=True).prop(tpr, "settings_tab", expand=True)
        box = col.box()
        if tpr.settings_tab == 'GENERAL':
            # box = self._offset_column(box)
            row = box.row()
            row.scale_x = 1.2
            row.alignment = 'CENTER'

            col = row.column()
            subcol = col.column(align=True)
            self._draw_hprop(subcol, pr, "show_sidepanel_prefs")
            self._draw_hprop(
                subcol, pr, "expand_item_menu",
                "https://en.blender.org/uploads/b/b7/"
                "Pme1.14.0_expand_item_menu.gif")
            self._draw_hprop(
                subcol, pr, "use_cmd_editor",
                "https://en.blender.org/uploads/f/f4/Pme_item_edit.png")
            self._draw_hprop(subcol, pr, "cache_scripts")
            self._draw_hprop(subcol, pr, "save_tree")
            self._draw_hprop(subcol, pr, "auto_backup")
            subcol.separator()
            self._draw_hprop(subcol, pr, "list_size")
            self._draw_hprop(subcol, pr, "num_list_rows")

        elif tpr.settings_tab == 'HOTKEYS':
            # box = self._offset_column(col.box())

            row = box.row()
            row.scale_x = 0.3
            row.alignment = 'CENTER'
            col = row.column()

            self._draw_hlabel(col, "PME Hotkey:")
            subcol = col.column(align=True)
            pr.hotkey.draw(subcol)

            col.separator()

            self._draw_hlabel(col, "Hotkey Modes:")
            subcol = col.column(align=True)
            subcol.prop(
                uprefs().inputs,
                "drag_threshold" if is_28() else "tweak_threshold",
                text="Tweak Mode Threshold")
            subcol.prop(pr, "hold_time")
            subcol.prop(pr, "chord_time")

            subcol = col.column(align=True)
            subcol.prop(pr, "use_chord_hint")

        elif tpr.settings_tab == 'OVERLAY':
            row = box.row()
            row.scale_x = 0.6
            row.alignment = 'CENTER'

            col = row.column()

            pr.overlay.draw(col)

        elif tpr.settings_tab == 'PIE':
            row = box.row()
            row.scale_x = 1.5
            row.alignment = 'CENTER'

            col = row.column()

            subcol = col.column(align=True)
            subcol.prop(pr, "show_pm_title")
            subcol.prop(pr, "restore_mouse_pos")

            subcol = col.column(align=True)
            subcol.prop(pr, "pie_extra_slot_gap_size")

            view = uprefs().view
            subcol = col.column(align=True)
            subcol.prop(view, "pie_animation_timeout")
            subcol.prop(view, "pie_initial_timeout")
            subcol.prop(view, "pie_menu_radius")
            subcol.prop(view, "pie_menu_threshold")
            subcol.prop(view, "pie_menu_confirm")

        elif tpr.settings_tab == 'MENU':
            row = box.row()
            row.scale_x = 1.5
            row.alignment = 'CENTER'

            col = row.column()

            view = uprefs().view
            col.prop(view, "use_mouse_over_open")

            subcol = col.column(align=True)
            subcol.active = view.use_mouse_over_open
            subcol.prop(view, "open_toplevel_delay", text="Top Level")
            subcol.prop(view, "open_sublevel_delay", text="Sub Level")

        elif tpr.settings_tab == 'POPUP':
            row = box.row()
            row.scale_x = 0.5
            row.alignment = 'CENTER'

            col = row.column()

            sub = col.column(align=True)
            # self._draw_hprop(sub, pr, "use_square_buttons")
            self._draw_hprop(sub, pr, "use_spacer")

            col.separator()

            self._draw_hlabel(
                col, "Default Mode:",
                "https://en.blender.org/index.php/User:Raa/Addons/"
                "Pie_Menu_Editor/Editors/Popup_Dialog#Mode")
            sub = col.row(align=True)
            sub.prop(pr, "default_popup_mode", expand=True)

            col.separator()

            self._draw_hlabel(col, "Toolbars:")
            sub = col.column(align=True)
            sub.prop(pr, "toolbar_width")
            sub.prop(pr, "toolbar_height")

        elif tpr.settings_tab == 'MODAL':
            row = box.row()
            row.scale_x = 1.5
            row.alignment = 'CENTER'

            col = row.column()

            col.label(
                text="Mouse Movement Direction and Threshold:")
            subcol = col.column(align=True)
            subcol.prop(self, "mouse_dir_mode", text="")
            subcol.prop(self, "mouse_threshold_int")
            subcol.prop(self, "mouse_threshold_float")
            subrow = subcol.row(align=True)
            subrow.prop(
                self, "use_mouse_threshold_bool", text="", toggle=True,
                icon=ic_cb(self.use_mouse_threshold_bool))
            subrow.prop(self, "mouse_threshold_bool")
            subrow = subcol.row(align=True)
            subrow.prop(
                self, "use_mouse_threshold_enum", text="", toggle=True,
                icon=ic_cb(self.use_mouse_threshold_enum))
            subrow.prop(self, "mouse_threshold_enum")

    def _draw_preferences(self, context, layout):
        pr = prefs()
        row = layout.row()

        sub = row.row(align=True)
        sub.prop(pr, "show_list", text="", icon=ic('COLLAPSEMENU'))

        if pr.show_list:
            sub.prop(pr, "use_filter", text="", icon=ic('FILTER'))
            sub.prop(pr, "tree_mode", text="", icon=ic('OUTLINER'))
            sub.separator()
            sub.prop(pr, "show_names", text="", icon=ic('SYNTAX_OFF'))
            sub.prop(pr, "show_hotkeys", text="", icon=ic('FILE_FONT'))
            sub.prop(
                pr, "show_keymap_names", text="", icon=ic('SPLITSCREEN'))
            sub.prop(pr, "show_tags", text="", icon=ic_fb(False))
            if pr.tree_mode:
                sub.prop(pr, "group_by", text="", icon_only=True)

        row.prop(pr, "tab", expand=True)

        sub = row.row(align=True)
        sub.prop(pr, "interactive_panels", text="", icon=ic('WINDOW'))
        # sub.prop(pr, "show_errors", text="", icon=ic('CONSOLE'))
        sub.prop(pr, "debug_mode", text="", icon=ic('SCRIPT'))

        # row.separator()

        row.prop(pr, "maximize_prefs", text="", icon=ic('FULLSCREEN_ENTER'))

        if pr.tab == 'EDITOR':
            self._draw_tab_editor(context, layout)

        elif pr.tab == 'SETTINGS':
            self._draw_tab_settings(context, layout)

    def draw_prefs(self, context, layout):
        if self.mode == 'ADDON':
            self._draw_preferences(context, layout)
        elif self.mode == 'ICONS':
            self._draw_icons(context, layout)
        elif self.mode == 'PMI':
            self._draw_pm_item(context, layout)

    def draw(self, context):
        self.draw_prefs(context, self.layout)

    def init_menus(self):
        pr = prefs()
        DBG and logh("Init Menus")

        if len(self.pie_menus) == 0:
            self.add_pm()
            return

        for pm in self.pie_menus:
            self.old_pms.add(pm.name)

            pm.ed.init_pm(pm)

            if 'MENU' in pm.ed.supported_slot_modes:
                for pmi in pm.pmis:
                    if pmi.mode == 'MENU':
                        menu_name, mouse_over, _ = U.extract_str_flags(
                            pmi.text, CC.F_EXPAND, CC.F_EXPAND)
                        if mouse_over and menu_name in pr.pie_menus and \
                                pr.pie_menus[menu_name].mode == 'RMENU':
                            get_pme_menu_class(menu_name)

            km_names = pm.parse_keymap(False)
            if km_names:
                for km_name in km_names:
                    if km_name not in self.missing_kms:
                        self.missing_kms[km_name] = []
                    self.missing_kms[km_name].append(pm.name)
            else:
                pm.register_hotkey()

    def backup_menus(self, operator=None):
        DBG_INIT and logh("Backup")
        # gen new filename
        backup_folder_path = os.path.abspath(os.path.join(
            ADDON_PATH, os.pardir, ADDON_ID + "_data", "backups"))
        new_backup_filepath = os.path.join(
            backup_folder_path,
            "backup_%s.json" % datetime.datetime.now().strftime(
                "%Y.%m.%d_%H.%M.%S"))
        if os.path.isfile(new_backup_filepath):
            DBG_INIT and logi("Backup exists")
            if operator:
                bpy.ops.pme.message_box(
                    title="Backup Menus",
                    message="Backup exists: " + new_backup_filepath)
            return

        # find backups
        re_backup_filename = re.compile(
            r"backup_\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}\.json")
        if not os.path.exists(backup_folder_path):
            os.makedirs(backup_folder_path)

        MAX_NUM_BACKUPS = 20
        backups = []
        for filepath in sorted(os.listdir(backup_folder_path)):
            if re_backup_filename.match(filepath):
                backups.append(filepath)

        # open last backup
        last_data = None
        if len(backups):
            with open(os.path.join(backup_folder_path, backups[-1])) as f:
                last_data = f.read()

        data = self.get_export_data()
        data = json.dumps(data, indent=2, separators=(", ", ": "))
        if not data or last_data and last_data == data:
            DBG_INIT and logi("No changes")
            if operator:
                bpy.ops.pme.message_box(
                    title="Backup Menus",
                    message="No changes")
            return

        # remove old backups
        if len(backups) >= MAX_NUM_BACKUPS:
            for i in range(len(backups) + 1 - MAX_NUM_BACKUPS):
                DBG_INIT and logw("Remove backup", backups[i])
                os.remove(os.path.join(backup_folder_path, backups[i]))

        # save new backup
        with open(new_backup_filepath, "w") as f:
            f.write(data)
            DBG_INIT and logi("New backup", new_backup_filepath)
            if operator:
                bpy.ops.pme.message_box(
                    title="Backup Menus",
                    message="New backup: " + new_backup_filepath)

    def get_export_data(self, export_tags=True, mode='ALL', tag=""):
        pr = self
        tpr = temp_prefs()
        menus = []
        apm = pr.selected_pm
        apm_name = apm and apm.name

        pms_to_export = []
        parsed_pms = set()

        def parse_children(pmis):
            for pmi in pmis:
                if pmi.mode == 'MENU':
                    menu_name, _, _ = U.extract_str_flags(
                        pmi.text, CC.F_EXPAND, CC.F_EXPAND)
                    if menu_name in pr.pie_menus:
                        if menu_name not in pms_to_export:
                            pms_to_export.append(menu_name)

                        if menu_name not in parsed_pms:
                            parsed_pms.add(menu_name)
                            parse_children(pr.pie_menus[menu_name].pmis)

        def gen_pms():
            if pr.tree_mode:
                pm_names = set()
                for link in tpr.links:
                    if link.pm_name and link.pm_name not in pm_names:
                        pm_names.add(link.pm_name)
                        yield pr.pie_menus[link.pm_name]
            else:
                for pm in pr.pie_menus:
                    yield pm

        for pm in gen_pms():
            if mode == 'ENABLED' and not pm.enabled:
                continue
            elif mode == 'ACTIVE' and pm.name != apm_name:
                continue
            elif mode == 'TAG' and not pm.has_tag(tag):
                continue

            pms_to_export.append(pm.name)
            parsed_pms.add(pm.name)

            if mode != 'ALL':
                parse_children(pm.pmis)

        for pm_name in pms_to_export:
            pm = pr.pie_menus[pm_name]
            items = []

            for pmi in pm.pmis:
                if pmi.mode == 'EMPTY':
                    if pmi.name:
                        item = (pmi.name, pmi.icon, pmi.text)
                    else:
                        item = (pmi.text,)
                else:
                    item = (
                        pmi.name,
                        pmi.mode,
                        pmi.icon,
                        pmi.text,
                        pmi.flags()
                    )
                items.append(item)

            menu = (
                pm.name,
                pm.km_name,
                pm.to_hotkey(),
                items,
                pm.mode,
                pm.data,
                pm.open_mode,
                "" if pm.poll_cmd == CC.DEFAULT_POLL else pm.poll_cmd,
                pm.tag if export_tags else ""
            )
            menus.append(menu)

        return dict(
            version=".".join(str(i) for i in addon.VERSION),
            menus=menus)

    def ed(self, id):
        return self.editors[id]


class PME_PT_preferences(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_label = "Pie Menu Editor"
    bl_category = "PME"

    @classmethod
    def poll(cls, context):
        return prefs().show_sidepanel_prefs

    def draw(self, context):
        prefs().draw_prefs(context, self.layout)


class PME_MT_button_context:
    bl_label = "Button Context Menu"

    def draw(self, context):
        self.layout.separator()


class PME_OT_context_menu(bpy.types.Operator):
    bl_idname = "pme.context_menu"
    bl_label = ""
    bl_description = ""
    bl_options = {'INTERNAL'}

    prop: bpy.props.StringProperty(options={'SKIP_SAVE'})
    operator: bpy.props.StringProperty(options={'SKIP_SAVE'})
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def draw_menu(self, menu, context):
        layout = menu.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        pr = prefs()
        pm = pr.selected_pm
        if pm:
            if self.prop or self.operator:
                operator(
                    layout, PME_OT_context_menu.bl_idname,
                    "Add to " + pm.name, icon=ic('ZOOMIN'),
                    prop=self.prop, operator=self.operator, name=self.name)
            else:
                row = layout.row()
                row.enabled = False
                row.label(text="Can't Add This Widget", icon=ic('ZOOMIN'))
            layout.separator()

        operator(
            layout, OPS.WM_OT_pm_select.bl_idname, None, 'COLLAPSEMENU',
            pm_name="", use_mode_icons=False)
        operator(
            layout, OPS.PME_OT_pm_search_and_select.bl_idname, None,
            'VIEWZOOM')

        layout.separator()

        layout.prop(pr, "debug_mode")
        layout.prop(pr, "interactive_panels")

    def execute(self, context):
        if self.prop:
            bpy.ops.pme.pm_edit(
                'INVOKE_DEFAULT',
                text=self.prop, name=self.name, auto=False)
            return {'FINISHED'}

        if self.operator:
            bpy.ops.pme.pm_edit(
                'INVOKE_DEFAULT', text=self.operator, name=self.name,
                auto=False)
            return {'FINISHED'}

        button_pointer = getattr(context, "button_pointer", None)
        button_prop = getattr(context, "button_prop", None)
        if button_prop and button_pointer:
            path = gen_prop_path(button_pointer, button_prop)
            if path:
                value = pme.context.eval(path)
                if value is not None:
                    path = "%s = %s" % (path, repr(value))

                self.prop = path
                # self.name = button_prop.name or utitle(
                #     button_prop.identifier)

        button_operator = getattr(context, "button_operator", None)
        if button_operator:
            tpname = button_operator.__class__.__name__
            idname = operator_utils.to_bl_idname(tpname)
            args = ""
            keys = button_operator.keys()
            if keys:
                args = []
                for k in keys:
                    v = getattr(button_operator, k)
                    value = to_py_value(button_operator.rna_type, k, v)
                    if value is None or isinstance(value, dict) and not value:
                        continue
                    args.append("%s=%s" % (k, repr(value)))

                args = ", ".join(args)
            cmd = "bpy.ops.%s(%s)" % (idname, args)

            self.operator = cmd

        context.window_manager.popup_menu(
            self.draw_menu, title="Pie Menu Editor")
        return {'FINISHED'}


def button_context_menu(self, context):
    layout = self.layout

    button_pointer = getattr(context, "button_pointer", None)
    button_prop = getattr(context, "button_prop", None)
    button_operator = getattr(context, "button_operator", None)

    layout.operator(
        PME_OT_context_menu.bl_idname, text="Pie Menu Editor",
        icon=ic('COLOR'))


def add_rmb_menu():
    if not hasattr(bpy.types, "WM_MT_button_context"):
        tp = type(
            "WM_MT_button_context",
            (PME_MT_button_context, bpy.types.Menu), {})
        bpy.utils.register_class(tp)

    bpy.types.WM_MT_button_context.append(button_context_menu)


def register():
    if not hasattr(bpy.types.WindowManager, "pme"):
        bpy.types.WindowManager.pme = bpy.props.PointerProperty(
            type=PMEData)
        bpy.context.window_manager.pme.modal_item_hk.setvar(
            "update", PMEData.update_modal_item_hk)

    PMEPreferences.kh = KeymapHelper()

    add_rmb_menu()

    pr = prefs()
    pr.tree.lock()
    pr.init_menus()
    if pr.auto_backup:
        pr.backup_menus()

    pr.ed('DIALOG').update_default_pmi_data()

    tpr = temp_prefs()
    tpr.init_tags()

    pme.context.add_global("_prefs", prefs)
    pme.context.add_global("prefs", prefs)
    pme.context.add_global("temp_prefs", temp_prefs)
    pme.context.add_global("pme", pme)
    pme.context.add_global("os", os)
    pme.context.add_global("PMEData", PMEData)

    pr.interactive_panels = False
    pr.icon_filter = ""
    pr.show_custom_icons = False
    pr.tab = 'EDITOR'
    pr.use_filter = False
    pr.show_only_new_pms = False
    pr.maximize_prefs = False
    pr.show_advanced_settings = False
    pr.mode_filter = CC.PM_ITEMS_M_DEFAULT
    pr["tag_filter"] = ""
    Tag.filter()

    h = pr.hotkey
    if h.key == 'NONE':
        h.key = 'ACCENT_GRAVE'
        h.ctrl = True
        h.shift = True

    if pr.kh.available():
        pr.kh.keymap("Screen Editing")

        h.add_kmi(
            pr.kh.operator(
                PME_OT_pm_edit, h,
                auto=True))

        pr.kh.operator(
            WM_OT_pmi_icon_select, key='ESC', idx=-1).properties.hotkey = True
        pr.kh.operator(
            WM_OT_pmi_data_edit, key='RET', ok=True).properties.hotkey = True
        pr.kh.operator(
            WM_OT_pmi_data_edit, key='ESC', idx=-1).properties.hotkey = True

        pr.window_kmis.append(
            pr.kh.operator(EOPS.PME_OT_window_auto_close, 'Any+LEFTMOUSE'))
        pr.window_kmis.append(
            pr.kh.operator(EOPS.PME_OT_window_auto_close, 'Any+RIGHTMOUSE'))
        pr.window_kmis.append(
            pr.kh.operator(EOPS.PME_OT_window_auto_close, 'Any+MIDDLEMOUSE'))
        pr.enable_window_kmis(False)

    pr.selected_pm.ed.register_props(pr.selected_pm)

    pr.tree.unlock()
    pr.tree.update()
    PME_UL_pm_tree.load_state()

    for root, dirs, files in os.walk(
            os.path.join(SCRIPT_PATH, "autorun"), followlinks=True):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith('.py'):
                execute_script(os.path.join(root, file))

    for root, dirs, files in os.walk(
            os.path.join(SCRIPT_PATH, "register"), followlinks=True):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith('.py'):
                execute_script(os.path.join(root, file))


def unregister():
    pr = prefs()
    pr.kh.unregister()
    pr.window_kmis.clear()

    PMIData._kmi = None

    if hasattr(bpy.types, "WM_MT_button_context"):
        bpy.types.WM_MT_button_context.remove(button_context_menu)

    for root, dirs, files in os.walk(
            os.path.join(SCRIPT_PATH, "unregister"), followlinks=True):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith('.py'):
                execute_script(os.path.join(root, file))
