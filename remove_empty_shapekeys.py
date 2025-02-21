import bpy

class OBJECT_OT_remove_empty_shape_keys(bpy.types.Operator):
    """Remove empty shape keys and their drivers."""

    bl_idname = "object.remove_empty_shape_keys"
    bl_label = "Remove Empty Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.data and hasattr(obj.data, 'shape_keys') and obj.data.shape_keys:
                remove_empty_shape_keys(obj)

        return {'FINISHED'}

def is_shape_key_empty(obj, shape_key, epsilon=1e-6):
    """Checks if a shape key is identical to the base shape within a small tolerance."""
    mesh = obj.data
    base_key = mesh.shape_keys.key_blocks[0]  # Basis shape key

    for i, vert in enumerate(mesh.vertices):
        if not (shape_key.data[i].co - base_key.data[i].co).length < epsilon:
            return False  # Significant difference found, not empty
    return True  # All coordinates are nearly identical

def remove_empty_shape_keys(obj):
    """Removes all empty shape keys from the given object."""
    if obj.data.shape_keys:
        shape_keys = obj.data.shape_keys.key_blocks
        animdata = obj.data.shape_keys.animation_data
        drivers = animdata.drivers
        keys_to_remove = [key.name for key in shape_keys[1:] if is_shape_key_empty(obj, key)]
        
        for key_name in keys_to_remove:
            if drivers:
                drv = drivers.find(f'key_blocks["{key_name}"].value')
                if drv:
                    drivers.remove(drv)
            obj.shape_key_remove(shape_keys[key_name])
        
        if keys_to_remove:
            print(f"Removed {len(keys_to_remove)} empty shape keys from {obj.name}.")
        else:
            print(f"No empty shape keys found in {obj.name}.")

def draw_shape_key_cleaner(self, context):
    layout = self.layout
    layout.operator(OBJECT_OT_remove_empty_shape_keys.bl_idname, icon='BRUSH_DATA')

registry = [OBJECT_OT_remove_empty_shape_keys]

def register():
    bpy.types.MESH_MT_shape_key_context_menu.append(draw_shape_key_cleaner)

def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(draw_shape_key_cleaner)
