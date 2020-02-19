# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

bl_info = {
    "name": "Corrective Shape Keys",
    "author": "Ivo Grigull (loolarge), Tal Trachtman", "Tokikake"
    "version": (1, 1, 1),
    "blender": (2, 80, 0),
    "location": "Object Data > Shape Keys Specials or Search",
    "description": "Creates a corrective shape key for the current pose",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
                "Scripts/Animation/Corrective_Shape_Key",
    "category": "Animation",
}

"""
This script transfers the shape from an object (base mesh without
modifiers) to another object with modifiers (i.e. posed Armature).
Only two objects must be selected.
The first selected object will be added to the second selected
object as a new shape key.

- Original 2.4x script by Brecht
- Unpose-function reused from a script by Tal Trachtman in 2007
  http://www.apexbow.com/randd.html
- Converted to Blender 2.5 by Ivo Grigull
- Converted to Blender 2.8 by Tokikake 
("fast" option was removed, add new "delta" option 
which count currently used shape key values of armature mesh when transfer)

Limitations and new delta option for 2.8
- Target mesh may not have any transformation at object level,
  it will be set to zero.
  
- new "delta" option usage, when you hope to make new shape-key with keep currently visible other shape keys value.
 it can generate new shape key, with value as 1.00. then deform target shape as source shape with keep other shape key values relative.

- If overwrite shape key,<select active shape key of target as non "base shape">
 current shape key value is ignored and turn as 1.00.

 then if active shape key was driven (bone rotation etc), you may get un-expected result. When transfer, I recommend, keep set active-shape key as base. so transferred shape key do not "overwrite". but generate new shape key.
 if active-shape key have no driver, you can overwrite it (but as 1.00 value )
"""


import bpy
from mathutils import Vector, Matrix

iterations = 20
threshold = 1e-16

def update_mesh(ob):
    depth = bpy.context.evaluated_depsgraph_get()
    depth.update()
    ob.update_tag() 
    bpy.context.view_layer.update()    
    ob.data.update()

def reset_transform(ob):
    ob.matrix_local.identity()


# this version is for shape_key data
def extract_vert_coords(verts):
    return [v.co.copy() for v in verts]

def extract_mapped_coords(ob, shape_verts):
    depth = bpy.context.evaluated_depsgraph_get()
    eobj = ob.evaluated_get(depth)
    mesh = bpy.data.meshes.new_from_object(eobj)

    # cheating, the original mapped verts happen
    # to be at the end of the vertex array
    verts = mesh.vertices
    #arr = [verts[i].co.copy() for i in range(len(verts) - totvert, len(verts))]
    arr = [verts[i].co.copy() for i in range(0, len(verts))]
    mesh.user_clear()
    bpy.data.meshes.remove(mesh)
    update_mesh(ob)
    return arr


def apply_vert_coords(ob, mesh, x):
    for i, v in enumerate(mesh):
        v.co = x[i]
    update_mesh(ob)

def func_add_corrective_pose_shape(source, target, flag):

    ob_1 = target
    mesh_1 = target.data
    ob_2 = source
    mesh_2 = source.data

    reset_transform(target)

    # If target object doesn't have Base shape key, create it.
    if not mesh_1.shape_keys:
        basis = ob_1.shape_key_add()
        basis.name = "Basis"
        update_mesh(ob_1)
        ob_1.active_shape_key_index = 0
    ob_1.show_only_shape_key = False
    key_index = ob_1.active_shape_key_index
    print(ob_1)
    print(ob_1.active_shape_key)
    active_key_name = ob_1.active_shape_key.name
    
    if (flag == True):
    # Make mix shape key from currently used shape keys  
        if not key_index == 0:
            ob_1.active_shape_key.value = 0
        mix_shape = ob_1.shape_key_add(from_mix = True)
        mix_shape.name = "Mix_shape"
        update_mesh(ob_1)
        keys = ob_1.data.shape_keys.key_blocks.keys()       
        ob_1.active_shape_key_index = keys.index(active_key_name)
    
    print("active_key_name: ", active_key_name)  
    
    if key_index == 0:
        new_shapekey = ob_1.shape_key_add()
        new_shapekey.name = "Shape_" + ob_2.name
        update_mesh(ob_1)
        keys = ob_1.data.shape_keys.key_blocks.keys()        
        ob_1.active_shape_key_index = keys.index(new_shapekey.name) 

    # else, the active shape will be used (updated)

    ob_1.show_only_shape_key = True

    vgroup = ob_1.active_shape_key.vertex_group
    ob_1.active_shape_key.vertex_group = ""

    #mesh_1_key_verts = mesh_1.shape_keys.key_blocks[key_index].data
    mesh_1_key_verts = ob_1.active_shape_key.data

    x = extract_vert_coords(mesh_1_key_verts)

    targetx = extract_vert_coords(mesh_2.vertices)

    for iteration in range(0, iterations):
        dx = [[], [], [], [], [], []]

        mapx = extract_mapped_coords(ob_1, mesh_1_key_verts)

        # finite differencing in X/Y/Z to get approximate gradient
        for i in range(0, len(mesh_1.vertices)):
            epsilon = (targetx[i] - mapx[i]).length

            if epsilon < threshold:
                epsilon = 0.0

            dx[0] += [x[i] + 0.5 * epsilon * Vector((1, 0, 0))]
            dx[1] += [x[i] + 0.5 * epsilon * Vector((-1, 0, 0))]
            dx[2] += [x[i] + 0.5 * epsilon * Vector((0, 1, 0))]
            dx[3] += [x[i] + 0.5 * epsilon * Vector((0, -1, 0))]
            dx[4] += [x[i] + 0.5 * epsilon * Vector((0, 0, 1))]
            dx[5] += [x[i] + 0.5 * epsilon * Vector((0, 0, -1))]

        for j in range(0, 6):
            apply_vert_coords(ob_1, mesh_1_key_verts, dx[j])
            dx[j] = extract_mapped_coords(ob_1, mesh_1_key_verts)

        # take a step in the direction of the gradient
        for i in range(0, len(mesh_1.vertices)):
            epsilon = (targetx[i] - mapx[i]).length

            if epsilon >= threshold:
                Gx = list((dx[0][i] - dx[1][i]) / epsilon)
                Gy = list((dx[2][i] - dx[3][i]) / epsilon)
                Gz = list((dx[4][i] - dx[5][i]) / epsilon)
                G = Matrix((Gx, Gy, Gz))
                Delmorph = (targetx[i] - mapx[i])
                x[i] += G @ Delmorph

        apply_vert_coords(ob_1, mesh_1_key_verts, x)

    ob_1.show_only_shape_key = True
    
    if (flag == True):
    # remove delta of mix-shape key values from new shape key
        key_index = ob_1.active_shape_key_index
        active_key_name = ob_1.active_shape_key.name        
        shape_data = ob_1.active_shape_key.data
        mix_data = mix_shape.data   
        for i in range(0, len(mesh_1.vertices)):
            shape_data[i].co = mesh_1.vertices[i].co + shape_data[i].co - mix_data[i].co        
        update_mesh(ob_1)
        
        ob_1.active_shape_key_index = ob_1.data.shape_keys.key_blocks.keys().index("Mix_shape")
        bpy.ops.object.shape_key_remove()
        ob_1.active_shape_key_index = ob_1.data.shape_keys.key_blocks.keys().index(active_key_name)
        ob_1.data.update()
        ob_1.show_only_shape_key = False
        
    ob_1.active_shape_key.vertex_group = vgroup

    # set the new shape key value to 1.0, so we see the result instantly
    ob_1.active_shape_key.value = 1.0
    update_mesh(ob_1)   
    

class add_corrective_pose_shape(bpy.types.Operator):
    """Adds first object as shape to second object for the current pose """ \
    """while maintaining modifiers """ \
    """(i.e. anisculpt, avoiding crazy space) Beware of slowness!"""

    bl_idname = "object.add_corrective_pose_shape"
    bl_label = "Add object as corrective pose shape"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        selection = context.selected_objects
        if len(selection) != 2:
            self.report({'ERROR'}, "Select source and target objects")
            return {'CANCELLED'}

        target = context.active_object
        if context.active_object == selection[0]:
            source = selection[1]
        else:
            source = selection[0]
            
        delta_flag = False

        func_add_corrective_pose_shape(source, target, delta_flag)

        return {'FINISHED'}
        
class add_corrective_pose_shape_delta (bpy.types.Operator):
    """Adds first object as shape to second object for the current pose """ \
    """while maintaining modifiers and currently used other shape keys""" \
    """with keep other shape key value, generate new shape key which deform to source shape """

    bl_idname = "object.add_corrective_pose_shape_delta"
    bl_label = "Add object as corrective pose shape delta"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        selection = context.selected_objects
        if len(selection) != 2:
            self.report({'ERROR'}, "Select source and target objects")
            return {'CANCELLED'}

        target = context.active_object
        if context.active_object == selection[0]:
            source = selection[1]
        else:
            source = selection[0]
            
        delta_flag = True

        func_add_corrective_pose_shape(source, target, delta_flag)

        return {'FINISHED'}

def unposeMesh(meshObToUnpose, obj, armatureOb):
    psdMeshData = meshObToUnpose

    psdMesh = psdMeshData
    I = Matrix()  # identity matrix

    meshData =obj.data
    mesh = meshData

    armData = armatureOb.data

    pose = armatureOb.pose
    pbones = pose.bones

    for index, v in enumerate(mesh.vertices):
        # above is python shortcut for:index goes up from 0 to tot num of
        # verts in mesh, with index incrementing by 1 each iteration

        psdMeshVert = psdMesh[index]

        listOfBoneNameWeightPairs = []
        for n in mesh.vertices[index].groups:
            try:
                name = obj.vertex_groups[n.group].name
                weight = n.weight
                is_bone = False
                for i in armData.bones:
                    if i.name == name:
                        is_bone = True
                        break
                # ignore non-bone vertex groups
                if is_bone:
                    listOfBoneNameWeightPairs.append([name, weight])
            except:
                print('error')
                pass

        weightedAverageDictionary = {}
        totalWeight = 0
        for pair in listOfBoneNameWeightPairs:
            totalWeight += pair[1]

        for pair in listOfBoneNameWeightPairs:
            if totalWeight > 0:  # avoid divide by zero!
                weightedAverageDictionary[pair[0]] = pair[1] / totalWeight
            else:
                weightedAverageDictionary[pair[0]] = 0

        # Matrix filled with zeros
        sigma = Matrix()
        sigma.zero()

        list = []
        for n in pbones:
            list.append(n)
        list.reverse()

        for pbone in list:
            if pbone.name in weightedAverageDictionary:
                #~ print("found key %s", pbone.name)
                vertexWeight = weightedAverageDictionary[pbone.name]
                m = pbone.matrix_channel.copy()
                #m.transpose()
                sigma += (m - I) * vertexWeight

            else:
                pass
                #~ print("no key for bone " + pbone.name)

        sigma = I + sigma
        sigma.invert()
        psdMeshVert.co = sigma @ psdMeshVert.co
        obj.update_tag()
        bpy.context.view_layer.update()

def func_add_corrective_pose_shape_fast(source, target):
    reset_transform(target)

    # If target object doesn't have Basis shape key, create it.
    if not target.data.shape_keys:
        basis = target.shape_key_add()
        basis.name = "Basis"
        target.data.update()

    if target.active_shape_key_index == 0:
        # Insert new shape key and make it active
        new_shapekey = target.shape_key_add(name="Shape_" + source.name)
        target.active_shape_key_index = len(target.data.shape_keys.key_blocks) - 1

    # else, the active shape will be used (updated)

    target.show_only_shape_key = True

    shape_key_verts = target.data.shape_keys.key_blocks[target.active_shape_key_index].data

    target.active_shape_key.vertex_group = ''

    # copy the local vertex positions to the new shape
    # Mets TODO: Instead of expecting a mesh with modifiers applied, we simply passed the evaluated mesh. No need to re-duplicate the mesh over and over, manually or otherwise.
    # This is a TODO because the same should be done for the other functions, along with some code de-duplication, and merging all 3 into one operator. "fast" mode should be used when only one armature modifier is detected. "delta" option should be an option(select before running, with invoke() )
    verts = source.data.vertices
    for n in range(len(verts)):
        shape_key_verts[n].co = verts[n].co
    target.update_tag() 
    bpy.context.view_layer.update()
    # go to all armature modifies and unpose the shape
    for n in target.modifiers:
        if n.type == 'ARMATURE' and n.show_viewport:
            n.use_bone_envelopes = False
            n.use_deform_preserve_volume = False
            n.use_vertex_groups = True
            armature = n.object
            unposeMesh(shape_key_verts, target, armature)
            break

    # set the new shape key value to 1.0, so we see the result instantly
    target.active_shape_key.value = 1.0
    
    try:
        target.active_shape_key.vertex_group = vgroup
    except:
        pass

    target.show_only_shape_key = False
    target.update_tag() 
    bpy.context.view_layer.update()
    
    target.data.update()
    
class add_corrective_pose_shape_fast(bpy.types.Operator):
    #Adds 1st object as shape to 2nd object as pose shape (only 1 armature)

    bl_idname = "object.add_corrective_pose_shape_fast"
    bl_label = "Add object as corrective shape faster"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        selection = context.selected_objects
        if len(selection) != 2:
            self.report({'ERROR'}, "Select source and target objects")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()

        for o in selection:
            if o == context.object: continue
            object_eval = o.evaluated_get(depsgraph)
            mesh_eval = object_eval.data
            func_add_corrective_pose_shape_fast(object_eval, context.object)

        return {'FINISHED'}

# -----------------------------------------------------------------------------
# GUI

def vgroups_draw(self, context):
    layout = self.layout

    layout.operator("object.add_corrective_pose_shape",
                    text='Add as corrective pose-shape (slow, all modifiers)',
                    icon='COPY_ID')  # icon is not ideal
    layout.operator("object.add_corrective_pose_shape_delta",
                    text='Add as corrective pose-shape delta" (slow, all modifiers + other shape key values)',
                    icon='COPY_ID')  # icon is not ideal

classes = (
    add_corrective_pose_shape,
    add_corrective_pose_shape_delta,
    add_corrective_pose_shape_fast
)

def register():
    from bpy.utils import register_class
    for clss in classes:
        register_class(clss)
    bpy.types.MESH_MT_shape_key_context_menu.append(vgroups_draw)

def unregister():
    from bpy.utils import unregister_class
    for clss in reversed(classes):
        unregister_class(clss)
    bpy.types.MESH_MT_shape_key_context_menu.remove(vgroups_draw)
    
if __name__ == "__main__":
    register()
