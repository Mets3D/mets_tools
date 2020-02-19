# MetsTools addon for Blender
# Copyright (C) 2019 Demeter Dzadik
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO
#	Mirror selected bones (names, transforms, constraints, drivers, settings)
# 	Copy Cloth Settings (for some reason Copy Attributes doesn't do this)
#	Maybe use Jacques's auto-register.

bl_info = {
	"name": "MetsTools",
	"author": "Mets3D",
	"version": (2,3),
	"blender": (2, 81, 0),
	"location": "View3D > Search ",
	"description": "Random collection of tools I built for myself",
	"category": "3D View"}
	
import bpy

from . import create_lightmap_uvs
from . import mark_sharp_by_autosmooth
from . import make_physics_bones
from . import cleanup_blend
from . import make_modifiers_consistent
from . import cleanup_mesh
from . import weighted_normals
from . import convert_images
from . import smart_weight_transfer
from . import join_as_shape_key_by_uvs
from . import force_apply_mirror
from . import rename_skeleton_to_metsrig
from . import mirror_constraints
from . import make_right_vgroups
from . import setup_action_constraints
from . import toggle_weight_paint
from . import change_brush
from . import mirror_rig
from . import armature_apply_scale
from . import scale_control_to_bbone_handles
from . import assign_bone_group
from . import refresh_drivers
from . import weld_normals

def register():
	from bpy.utils import register_class
	#create_lightmap_uvs.register()
	mark_sharp_by_autosmooth.register()
	make_physics_bones.register()
	cleanup_blend.register()
	make_modifiers_consistent.register()
	cleanup_mesh.register()
	weighted_normals.register()
	convert_images.register()
	smart_weight_transfer.register()
	join_as_shape_key_by_uvs.register()
	force_apply_mirror.register()
	rename_skeleton_to_metsrig.register()
	mirror_constraints.register()
	make_right_vgroups.register()
	setup_action_constraints.register()
	toggle_weight_paint.register()
	change_brush.register()
	mirror_rig.register()
	armature_apply_scale.register()
	scale_control_to_bbone_handles.register()
	assign_bone_group.register()
	refresh_drivers.register()
	weld_normals.register()

	#bpy.types.VIEW3D_MT_pose_specials.append(draw_func_MakePhysicsBones)
	#bpy.types.VIEW3D_MT_edit_mesh.append(draw_func_MarkSharpByAutoSmooth)
	#bpy.types.VIEW3D_MT_uv_map.append(draw_func_CreateLightMapUVs)

def unregister():
	from bpy.utils import unregister_class
	#create_lightmap_uvs.unregister()
	mark_sharp_by_autosmooth.unregister()
	make_physics_bones.unregister()
	cleanup_blend.unregister()
	make_modifiers_consistent.unregister()
	cleanup_mesh.unregister()
	weighted_normals.unregister()
	convert_images.unregister()
	smart_weight_transfer.unregister()
	join_as_shape_key_by_uvs.unregister()
	force_apply_mirror.unregister()
	rename_skeleton_to_metsrig.unregister()
	mirror_constraints.unregister()
	make_right_vgroups.unregister()
	setup_action_constraints.unregister()
	toggle_weight_paint.unregister()
	change_brush.unregister()
	mirror_rig.unregister()
	armature_apply_scale.unregister()
	scale_control_to_bbone_handles.unregister()
	assign_bone_group.unregister()
	refresh_drivers.unregister()
	weld_normals.unregister()
	
	#bpy.types.VIEW3D_MT_pose_specials.remove(draw_func_MakePhysicsBones)
	#bpy.types.VIEW3D_MT_edit_mesh.remove(draw_func_MarkSharpByAutoSmooth)
	#bpy.types.VIEW3D_MT_uv_map.remove(draw_func_CreateLightMapUVs)