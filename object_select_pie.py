import bpy, re
from bpy.utils import flip_name
from bpy.types import Operator, Menu
from bpy.props import StringProperty, BoolProperty
from .util.hotkeys import addon_hotkey_register


def deselect_all_objects(context):
    for obj in context.selected_objects:
        obj.select_set(False)


def increment_name(name: str, increment=1, default_zfill=1) -> str:
    # Increment LAST number in the name.
    # Negative numbers will be clamped to 0.
    # Digit length will be preserved, so 10 will decrement to 09.
    # 99 will increment to 100, not 00.

    # If no number was found, one will be added at the end of the base name.
    # The length of this in digits is set with the `default_zfill` param.

    numbers_in_name = re.findall(r'\d+', name)
    if not numbers_in_name:
        return name + "_" + str(max(0, increment)).zfill(default_zfill)

    last = numbers_in_name[-1]
    incremented = str(max(0, int(last) + increment)).zfill(len(last))
    split = name.rsplit(last, 1)
    return incremented.join(split)


class ObjectSelectOperatorMixin:
    extend_selection: BoolProperty(
        name="Extend Selection",
        description="Bones that are already selected will remain selected",
    )

    def invoke(self, context, event):
        if event.shift:
            self.extend_selection = True
        else:
            self.extend_selection = False

        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if not self.extend_selection:
            deselect_all_objects(context)

        return {'FINISHED'}


class OBJECT_OT_select_object_by_name(Operator, ObjectSelectOperatorMixin):
    """Select this object. Hold Shift to extend selection"""

    bl_idname = "object.select_object_by_name"
    bl_label = "Select Object By Name"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    obj_name: StringProperty(
        name="Object Name", description="Name of the object to select"
    )

    def execute(self, context):
        obj = context.scene.objects.get(self.obj_name)

        if not obj:
            self.report({'ERROR'}, "Object name not found in scene: " + self.obj_name)
            return {'CANCELLED'}

        super().execute(context)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        return {'FINISHED'}


class OBJECT_OT_select_symmetry_object(Operator, ObjectSelectOperatorMixin):
    """Select opposite objects by name"""

    bl_idname = "object.select_opposite"
    bl_label = "Select Opposite Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = context.selected_objects[:]
        active_obj = context.active_object

        flipped_objs = [context.scene.objects.get(flip_name(ob.name)) for ob in objs]
        flipped_active = context.scene.objects.get(flip_name(active_obj.name))

        notflipped = len(
            [objs[i] for i in range(len(objs)) if objs[i] == flipped_objs[i]]
        )
        if notflipped > 0:
            self.report({'WARNING'}, f"{notflipped} objects had no opposite.")

        super().execute(context)

        for ob in flipped_objs:
            if not ob:
                continue
            ob.select_set(True)

        if flipped_active:
            context.view_layer.objects.active = flipped_active

        return {'FINISHED'}


class OBJECT_OT_select_parent_object(Operator, ObjectSelectOperatorMixin):
    """Select parent of the current bone"""

    bl_idname = "object.select_parent_object"
    bl_label = "Select Parent Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        obj = context.active_object
        return obj and obj.parent

    def execute(self, context):
        super().execute(context)

        active_obj = context.active_object

        active_obj.parent.select_set(True)
        context.view_layer.objects.active = active_obj.parent

        return {'FINISHED'}


class OBJECT_OT_select_object_by_name_search(Operator, ObjectSelectOperatorMixin):
    """Search for a bone name to select"""

    bl_idname = "object.select_by_name_search"
    bl_label = "Search Object"
    bl_options = {'REGISTER', 'UNDO'}

    obj_name: StringProperty(name="Object")

    def invoke(self, context, _event):
        obj = context.active_object
        if obj:
            self.obj_name = obj.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop_search(
            self, 'obj_name', context.scene, 'objects', icon='OBJECT_DATA'
        )
        layout.prop(self, 'extend_selection')

    def execute(self, context):
        obj = context.scene.objects.get(self.obj_name)
        if not self.extend_selection:
            deselect_all_objects(context)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        return {'FINISHED'}


class OBJECT_MT_PIE_child_objects(Menu):
    bl_label = "Child Objects"

    @classmethod
    def poll(cls, context):
        return context.active_object

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object

        for child_ob in active_obj.children:
            op = layout.operator(
                'object.select_object_by_name', text=child_ob.name, icon='OBJECT_DATA'
            )
            op.obj_name = child_ob.name


class OBJECT_MT_PIE_select_object(Menu):
    bl_idname = 'OBJECT_MT_PIE_select_object'
    bl_label = "Select Object"

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object

        pie = layout.menu_pie()

        # 1) < Parent Bone.
        if active_obj.parent:
            op = pie.operator(
                'object.select_parent_object',
                text="Parent: " + active_obj.parent.name,
                icon='OBJECT_DATA',
            )
        else:
            pie.separator()

        # 2) > Child Bone(s).
        if len(active_obj.children) == 1:
            child = active_obj.children[0]
            if child:
                # Sometimes child can be none...? I don't get how.
                op = pie.operator(
                    'object.select_object_by_name',
                    text="Child: " + child.name,
                    icon='OBJECT_DATA',
                )
                op.obj_name = child.name
        elif len(active_obj.children) > 1:
            pie.menu('OBJECT_MT_PIE_child_objects', icon='COLLAPSEMENU')
        else:
            pie.separator()

        # 3) v Lower number bone
        lower_obj = context.scene.objects.get(
            increment_name(active_obj.name, increment=-1)
        )
        if lower_obj:
            op = pie.operator(
                'object.select_object_by_name', text=lower_obj.name, icon='TRIA_DOWN'
            )
            op.obj_name = lower_obj.name
        else:
            pie.separator()

        # 4) ^ Higher number bone
        higher_obj = context.scene.objects.get(
            increment_name(active_obj.name, increment=1)
        )
        if higher_obj:
            op = pie.operator(
                'object.select_object_by_name', text=higher_obj.name, icon='TRIA_UP'
            )
            op.obj_name = higher_obj.name
        else:
            pie.separator()

        # 5) ^> Bone(s) with constraints that target this bone.
        # constrained_bones = get_constrained_bones(active_pb)
        # if len(constrained_bones) == 1:
        #     con, obj_name = constrained_bones[0]
        #     POSE_MT_PIE_constrained_bones.draw_select_bone(
        #         pie, con, obj_name, start_text="Constrained Bone: "
        #     )
        # elif len(constrained_bones) > 1:
        #     pie.menu('POSE_MT_PIE_constrained_bones', icon='COLLAPSEMENU')
        # else:
        # pie.separator()
        pie.separator()  # TODO: later.

        # 6) <^ Bone(s) targeted by this bone's constraints.
        # target_bones = get_target_bones(active_pb)
        # if len(target_bones) == 1:
        #     con, obj_name = target_bones[0]
        #     POSE_MT_PIE_bone_constraint_targets.draw_select_bone(
        #         pie, con, obj_name, start_text="Constraint Target: "
        #     )
        # elif len(target_bones) > 1:
        #     pie.menu('POSE_MT_PIE_bone_constraint_targets', icon='COLLAPSEMENU')
        # else:
        #     pie.separator()
        pie.separator()  # TODO: later.

        # 7) <v Symmetry Object
        pie.operator(
            OBJECT_OT_select_symmetry_object.bl_idname,
            text="Flip Selection",
            icon='MOD_MIRROR',
        )

        # 8) v> Search bone.
        pie.operator('object.select_by_name_search', icon='VIEWZOOM')


registry = [
    OBJECT_OT_select_object_by_name,
    OBJECT_OT_select_symmetry_object,
    OBJECT_OT_select_object_by_name_search,
    OBJECT_OT_select_parent_object,
    OBJECT_MT_PIE_child_objects,
    OBJECT_MT_PIE_select_object,
]

addon_hotkeys = []


def register():
    addon_hotkeys.append(
        addon_hotkey_register(
            op_idname='wm.call_menu_pie',
            keymap_name='3D View',
            key_id='F',
            ctrl=True,
            event_type='CLICK_DRAG',
            op_kwargs={'name': OBJECT_MT_PIE_select_object.bl_idname},
            add_on_conflict=False,
            warn_on_conflict=True,
            error_on_conflict=False,
        )
    )
    addon_hotkeys.append(
        addon_hotkey_register(
            op_idname=OBJECT_OT_select_symmetry_object.bl_idname,
            keymap_name='3D View',
            key_id='F',
            ctrl=True,
            event_type='RELEASE',
            op_kwargs={'extend_selection': False},
            add_on_conflict=False,
            warn_on_conflict=True,
            error_on_conflict=False,
        )
    )
    addon_hotkeys.append(
        addon_hotkey_register(
            op_idname=OBJECT_OT_select_symmetry_object.bl_idname,
            keymap_name='3D View',
            key_id='F',
            ctrl=True,
            shift=True,
            event_type='RELEASE',
            op_kwargs={'extend_selection': True},
            add_on_conflict=False,
            warn_on_conflict=True,
            error_on_conflict=False,
        )
    )


def unregister():
    for keymap, kmi in addon_hotkeys:
        keymap.keymap_items.remove(kmi)
