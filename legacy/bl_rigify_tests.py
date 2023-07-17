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

"""
Tests to make sure rigs generated from a metarig using Rigify come out as they should.

The tests are meant to catch mistakes in changes that aren't meant to affect Rigify behaviour.

If Rigify behaviour is expected to change, then these tests are expected to fail.
In this case, rigify_tests.blend should be updated by regenerating the rigs.

To use, launch blender with command line arguments:
./blender --background -noaudio --factory-startup --python ../../blender_master/tests/python/bl_rigify_tests.py
NOTE: This requires "rigify_tests.blend" to be next to this file.
"""

import argparse
import bpy
import unittest
import os
from mathutils import Vector, Matrix

# This test file contains metarigs and their generated rigs.
# We generate one metarig, compare the result to the pre-existing generated rig, then reload the file and move on to the next.
# TODO: If I want to pull request this unit test to master, ask a dev to put this blend file onto the unittest svn: https://svn.blender.org/svnroot/bf-blender/trunk/lib/tests/
filename = "rigify_tests.blend"
filedir = os.path.dirname(os.path.realpath(__file__))
filepath = os.path.join(filedir, filename)

class AbstractRigTest(unittest.TestCase):
	"""Rig equality testing utilities."""

	def reset(self):
		"""Reset Blender and reload the test file."""
		# TODO: Seems like if there are any addons enabled that register properties into bpy.types.Object or bpy.types.Armature,
		# things can go wrong. I don't understand why, when I load factory settings each time before reloading the file.

		bpy.ops.wm.read_factory_settings()
		bpy.ops.wm.open_mainfile(filepath=filepath)

	def matching_properties(self, thing1, thing2, skip=[]):
		"""Test if two objects have matching properties."""
		# This is a bit messy but it's good enough.
		for prop in dir(thing1):
			if "__" in prop: continue
			if prop in skip: continue

			try:
				# Odd. In some armature datablocks, dir() returns a list that has "group" in it, but when trying to access it, it doesn't exist.
				getattr(thing1, prop)
			except:
				continue

			val1 = getattr(thing1, prop)
			val2 = getattr(thing2, prop)

			if callable(val1): continue
			try:
				setattr(thing1, prop, val1)
			except AttributeError:
				continue

			type1 = type(val1)
			type2 = type(val2)
			self.assertEqual(type1, type2, f"Property type mismatch: {prop}\n{thing1}: {type1}\n{thing2}: {type2}")
			if val1==val2:
				continue

			# Skip blender internal types.
			if 'bpy.types' in str(type1) or 'bpy_types' in str(type1):
				continue

			if type1 in [float]:
				# Demanding any more precision will cause Stretch To constraints' rest_length property to mismatch after subsequent generations.
				self.assertAlmostEqual(val1, val2, places=5, msg=f"Float Property mismatch within 5 decimal places:  {prop}\n{thing1}: {str(val1)}\n{thing2}: {str(val2)}")
			elif type1 in [int, bool, str]:
				self.assertEqual(val1, val2, f"Property mismatch: {prop}\n{thing1}: {val1}\n{thing2}: {val2}")
			else:
				# Check for iterables.
				is_iterable = False
				try:
					val1 = val1[:]
					val2 = val2[:]
					self.assertEqual(len(val1), len(val2))
					if val1==val2:
						continue

					print(f"What to do with {prop}? It's iterable, but its contents do not match.")
					is_iterable = True
				except TypeError:
					pass

				if not is_iterable:
					print(f"Skipping comparison of unsupported type: {prop}, {type1}")

	def matching_constraints(self, b1, b2):
		"""Test if two bones have the same constraints.
		Constraint type, name, properties.
		"""
		self.assertEqual(len(b1.constraints), len(b2.constraints), f"Constraint count mismatch on {b1.name}: {len(b1.constraints)} vs {len(b2.constraints)}")
		for i, c1 in enumerate(b1.constraints):
			c2 = b2.constraints[i]
			self.assertEqual(c1.name, c2.name, f"Constraint name mismatch on {b1.name}:\n{c1.name}\n{c2.name}")
			self.assertEqual(c1.type, c2.type, f"Constraint type mismatch on {b1.name}, {c1.name}: {c1.type} vs {c2.type}")
			self.matching_properties(c1, c2, skip=['target', 'targets', 'active'])
			if c1.type=='ARMATURE':
				self.assertEqual(len(c1.targets), len(c2.targets), f"Armature Constraint target count mismatch on {b1.name}, {c1.name}.")
				for i, t in enumerate(c1.targets):
					self.assertEqual(t.subtarget, c2.targets[i].subtarget, f"Armature Constraint subtarget mismatch on {b1.name}, {c1.name}.")
					self.assertEqual(t.weight, c2.targets[i].weight, f"Armature Constraint weight mismatch on {b1.name}, {c1.name}.")

	def matching_custom_properties(self, thing1, thing2):
		"""Test if two blender datablocks have the same custom properties."""
		self.assertEqual(len(thing1.keys()), len(thing2.keys()), f"Custom Property count mismatch:\n{thing1}: {thing1.keys()}\n{thing2}: {thing2.keys()}")

		for key in thing1.keys():
			val1 = thing1[key]
			self.assertTrue(key in thing2, f"Custom Property {key} of {thing1} not found on {thing2}")
			val2 = thing2[key]
			self.assertEqual(type(val1), type(val2), f"Custom Property type mismatch:\n{thing1}: {type(val1)}\n{thing2}: {type(val2)}")
			if type(val1) in [int, float]:
				self.assertEqual(val1, val2, f"Custom Property value mismatch:\n{thing1}: {val1}\n{thing2}: {val2}")
			else:
				pass #TODO: Vectors, lists, dictionaries, API-defined properties.

			# Check for settings of the custom property, like its min, max, soft_min, soft_max, etc.
			if '_RNA_UI' in thing1:
				self.assertTrue('_RNA_UI' in thing2)
				rna1 = thing1['_RNA_UI'].to_dict()
				rna2 = thing2['_RNA_UI'].to_dict()
				self.assertEqual(rna1, rna2, f"Custom Properties settings mismatch:\n{thing1}: {rna1}\n{thing2}: {rna2}")
				# Compare library overridable-ness of the custom properties.
				for prop in rna1.keys():
					self.assertEqual(thing1.is_property_overridable_library(f'["{prop}"]'), thing2.is_property_overridable_library(f'["{prop}"]'), f"Custom Properties library overridable mismatch:{prop}: {thing1}, {thing2}")

	def matching_drivers(self, thing1, thing2):
		"""Test if things have identical drivers. These things must be top-level datablocks with an animaiton_data property."""

		assert hasattr(thing1, "animation_data") and hasattr(thing2, "animation_data"), "Cannot compare drivers, no animation_data attribute."

		# If either thing has no anim data, make sure the other doesn't either.
		if thing1.animation_data==None or thing2.animation_data==None:
			self.assertEquals(thing1.animation_data, thing2.animation_data)

		# Compare number of drivers
		count1 = len(thing1.animation_data.drivers)
		count2 = len(thing2.animation_data.drivers)
		self.assertEqual(count1, count2, f"Driver count mismatch:\n{thing1}: {count1}\n{thing2}: {count2}")

		# Compare individual drivers
		for fc1 in thing1.animation_data.drivers:
			fc2 = thing2.animation_data.drivers.find(fc1.data_path, index=fc1.array_index)
			self.assertIsNotNone(fc2, f"Driver mismatch: {fc1.data_path} (index {fc1.array_index}) not found in drivers of {thing2}.")
			# TODO: compare fcurve points and modifiers.

			d1 = fc1.driver
			d2 = fc2.driver
			self.assertEqual(d1.type, d2.type, f"Driver type mismatch: {thing1}, {fc1.data_path}, {fc1.array_index}: {d1.type} vs {d2.type}.")
			self.assertEqual(d1.expression, d2.expression, f"Driver expression mismatch: {thing1}, {fc1.data_path}, {fc1.array_index}: {d1.type} vs {d2.type}.")
			self.assertEqual(len(d1.variables), len(d2.variables), f"Driver variable count mismatch: {thing1}, {fc1.data_path}, {fc1.array_index}.")
			# Compare driver variables
			for i, v1 in enumerate(d1.variables):
				v2 = d2.variables[i]
				self.matching_properties(v1, v2)
				# Compare driver variable targets
				for j, t1 in enumerate(v1.targets):
					t2 = v2.targets[j]
					self.matching_properties(t1, t2)

	def matching_pose_bones(self, bone1, bone2):
		"""Test if two pose bones have matching properties.
		Bone name, transforms, constraints, properties, custom properties, drivers.
		"""
		self.matching_constraints(bone1, bone2)
		self.matching_custom_properties(bone1, bone2)

class AbstractRigifyTest(AbstractRigTest):
	"""Rigify testing utilities."""

	def reset(self):
		"""Reload the test file and make sure Rigify addon is enabled."""
		bpy.ops.wm.read_factory_settings()
		bpy.ops.preferences.addon_enable(module="rigify")
		bpy.ops.wm.open_mainfile(filepath=filepath)

	def regenerate_and_test(self, metarig):
		"""Regenerate a rig from a metarig that was previously generated, then compare the two generated rigs."""
		compare_rig = metarig.data.rigify_target_rig
		assert compare_rig, "Metarigs should have an existing target rig that will be used for comparison."
		compare_rig.name = "compare_rig"

		bpy.context.view_layer.objects.active = metarig
		metarig.data.rigify_target_rig = None

		bpy.ops.pose.rigify_generate()
		rig = bpy.data.objects["rig"]
		self.assertIs(rig, bpy.context.object)
		self.assertEqual(len(rig.pose.bones), len(compare_rig.pose.bones))

		for b in rig.pose.bones:
			# TODO: This should be hierarchical, so we can detect not only bone name changes but bone hierarchy changes.
			compare_b = compare_rig.pose.bones.get(b.name)
			self.assertIsNotNone(compare_b)
			self.matching_pose_bones(b, compare_b)

		self.matching_properties(rig, compare_rig, skip=[
			'mode', 'name', 'name_full', 'users', 'bound_box', 'matrix_basis', 'matrix_world', 'matrix_local', 'location', 'rotation', 'scale', 'rotation_w', 'instance_collection'
		])
		self.matching_properties(rig.data, compare_rig.data, skip=['name'])

		# TODO: Bone groups! And maybe selection sets.

		self.matching_custom_properties(rig, compare_rig)
		# self.matching_custom_properties(rig.data, compare_rig.data)   # TODO: _RNA_UI of the newly generated rig for some reason contains all the rigify settings, when for the pre-generated ones, it does not. I don't get it.

		self.matching_drivers(rig, compare_rig)
		self.matching_drivers(rig.data, compare_rig.data)

class RigifyGenerateTest(AbstractRigifyTest):
	"""Test rig generation results match an existing rig."""

	def test_all_metarigs(self):
		# Might get better reporting if we split this up into separate tests for each metarig.
		all_metarigs_names = [
			"basic_quadruped",
			"wolf",
			"human",
			"basic_human",
			"bird",
			"cat",
			"horse",
			"shark",
		]

		for name in all_metarigs_names:
			self.reset()
			print("\n"+name)
			metarig = bpy.data.objects["metarig_"+name]
			self.regenerate_and_test(metarig)


if __name__ == '__main__':
	import sys
	# I don't know what this does, but without this it doesn't work!
	sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
	unittest.main()