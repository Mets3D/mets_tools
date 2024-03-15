"""
This is currently intended to be used with the Pie Menu Editor add-on.
In future, we could create our own pie menu and hotkey UI.
"""

import bpy
from typing import List

from .util.hotkeys import addon_hotkey_register

class OBJECT_OT_unlink_from_scene(bpy.types.Operator):
    bl_idname = "object.unlink_from_scene"
    bl_label = "Unlink Selected From Scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.area.type == 'OUTLINER':
            return bool(get_objects_to_unlink(context) or get_collections_to_unlink(context))
        elif context.area.type == 'VIEW_3D':
            return bool(get_objects_to_unlink(context))

    def execute(self, context):
        unlink_collections_from_scene(get_collections_to_unlink(context), context.scene)
        unlink_objects_from_scene(get_objects_to_unlink(context), context.scene)

        return {'FINISHED'}


class OUTLINER_OT_better_delete(bpy.types.Operator):
    bl_idname = "outliner.better_delete"
    bl_label = "Delete Datablocks From File"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'OUTLINER' and context.selected_ids

    def execute(self, context):
        if context.scene in context.selected_ids:
            self.report({'ERROR'}, "Cannot delete active Scene.")
            return {'CANCELLED'}
        if context.workspace in context.selected_ids:
            self.report({'ERROR'}, "Cannot delete active Workspace.")
            return {'CANCELLED'}
        for id in context.selected_ids:
            if id.id_type in {'SCREEN', 'WINDOWMANAGER'}:
                self.report({'ERROR'}, f"Cannot delete type: {id.id_type}")
                return {'CANCELLED'}

        count = len(context.selected_ids)
        plural = "s" if count>1 else ""
        bpy.data.batch_remove(context.selected_ids)

        self.report({'INFO'}, f"Deleted {count} datablock{plural}.")
        return {'FINISHED'}

def get_objects_to_unlink(context) -> List[bpy.types.Object]:
    if context.area.type == 'OUTLINER':
        selected_objs = [id for id in context.selected_ids if type(id) == bpy.types.Object]
    elif context.area.type == 'VIEW_3D':
        selected_objs = context.selected_objects

    scene_objs = set(context.scene.objects)
    return [ob for ob in selected_objs if ob in scene_objs]

def unlink_objects_from_scene(objects, scene):
    for obj in objects:
        for coll in [scene.collection] + scene.collection.children_recursive:
            if obj.name in coll.objects:
                coll.objects.unlink(obj)

def get_collections_to_unlink(context) -> List[bpy.types.Collection]:
    if context.area.type == 'OUTLINER':
        return [id for id in context.selected_ids if type(id) == bpy.types.Collection]
    elif context.area.type == 'VIEW_3D':
        return []

def unlink_collections_from_scene(collections_to_unlink, scene):
    for coll_to_unlink in collections_to_unlink:
        for coll in scene.collection.children_recursive:
            if coll_to_unlink.name in coll.children:
                coll.children.unlink(coll_to_unlink)


class OBJECT_MT_delete_pie(bpy.types.Menu):
    # bl_label is displayed at the center of the pie menu
    bl_label = 'Unlink / Delete'
    bl_idname = 'OBJECT_MT_delete_pie'

    @classmethod
    def poll(cls, context):
        return context.area.type in {'VIEW_3D', 'OUTLINER'}

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        # <
        pie.operator(OBJECT_OT_unlink_from_scene.bl_idname, icon='TRASH', text="Unlink From Scene")

        if context.area.type == 'VIEW_3D':
            # > 3D View
            op = pie.operator('object.delete', icon='X', text="Delete From File")
            op.use_global = True
            op.confirm = False
            return

        # >
        pie.operator('outliner.better_delete', icon='X', text="Delete From File")

        # V
        pie.operator('outliner.id_operation', text="Unlink From Collection", icon="OUTLINER_COLLECTION").type='UNLINK'

        # ^
        pie.operator('outliner.delete', text="Delete Hierarchy", icon="OUTLINER").hierarchy=True

registry = [
    OBJECT_OT_unlink_from_scene,
    OUTLINER_OT_better_delete,
    OBJECT_MT_delete_pie
]

addon_hotkeys = []

def register():
    addon_hotkeys.append(
        addon_hotkey_register(
            op_idname='wm.call_menu_pie',
            keymap_name='Outliner',
            key_id='X',
            op_kwargs={'name': OBJECT_MT_delete_pie.bl_idname},

            add_on_conflict=True,
            warn_on_conflict=False,
            error_on_conflict=False,
        )
    )
    addon_hotkeys.append(
        addon_hotkey_register(
            op_idname='wm.call_menu_pie',
            keymap_name='Object Mode',
            key_id='X',
            op_kwargs={'name': OBJECT_MT_delete_pie.bl_idname},

            add_on_conflict=True,
            warn_on_conflict=False,
            error_on_conflict=False,
        )
    )

def unregister():
    for keymap, kmi in addon_hotkeys:
        keymap.keymap_items.remove(kmi)
