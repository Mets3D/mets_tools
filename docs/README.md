This addon is my random set of operators that I made to make my rigging workflow as painless as possible.  
There may be some extra stuff beside what's documented - assume that stuff is WIP.  
You can install this like any other Blender Addon - Download as zip, then in Blender go to Preferences->Addons->Install From File and browse the zip you downloaded.

# Weight Painting Operators
These operators have been split to a separate addon: [Easy Weight](https://gitlab.com/blender/easy-weight)
I highly recommend using that addon too, since half of rigging is weight painting. That addon was also written with much higher standards and is much better maintained.

# Rigging Operators

### X-Mirror Constraints
Mirrors all constraints and drivers on a rig, assuming everything ends in .L/.R.  
Driver mirroring is WIP/hardcoded to my workflow and naming, don't rely on it. Constraint mirroring should work really nicely though.

### Setup Action Constraints
This operator is to help rig faces using Action constraints.  
<img src="setup_action_constraints.png" width="700" />  

It shows a popup with settings for the Action constraints that will be created. They will be created on every bone that is keyframed in the active Action.  
If there is already an Action constraint in the rig that targets the currently active Action, it pre-fills the popup with that constraint's settings, so it's easy to modify things after you ran the operator once. They can also be deleted or disabled.  
For bones whose names don't end in .L/.R, we assume they are in the center of the face. It will create two copies of the constraint, one for the left and one for the right side(Changing the target control accordingly), both with an influence of 0.5.  

### Assign Bone Group
This is meant to replace the default Ctrl+G menu in pose mode.  
<img src="assign_bone_group.png" width="250" />  

### Refresh Drivers
Sometimes drivers in Blender decide to just fall asleep, or claim to have an error when they don't. Run this operator to refresh them, to make sure they don't complain about errors that don't exist.  

### Apply Armature Scale
This operator will apply uniform scale to a rigged armature while maintaining its constraints. It also applies the scaling to all actions used by the rig's Action constraints. (Optinally all actions in the whole scene)

### Reload Proxied Library
If you have a linked and proxied character in a scene, you can use this to re-load that linked and proxied rig from another file, another collection, and even another rig, while preserving the rig's action and local constraints.  (Used when renaming directly linked stuff during production)  

# Cleanup Operators
The organization of functionality here could be better, but these should be fairly usable. If you run into straight up errors, let me know.  

### Delete Unused Vertex Groups
Moved to [Easy Weight](https://gitlab.com/blender/easy-weight) addon.

### Delete Unused Material Slots
This just calls the built-in "Remove Unused Slots" operator, except it can work on all selected objects, or all objects, instead of just the active object.

### Clean Up Materials
Deletes unused nodes, centers node graphs, fixes .00x names on materials and textures, sets names and labels for texture nodes, and sets width for texture nodes.

### Clean Up Objects
Renames object datas to "Data_ObjectName", UV maps to "UVMap" when there is only one, and creates missing vertex groups for Mirror modifier. (eg. when your mesh has a Mirror modifier and Leg.L vertex group exists but Leg.R doesn't)

### Clean Up Meshes
Unhide All, Removes Doubles, Quadrangulate(Compare UVs), Weight Normals, Seams From Islands.  
Also removes UV Maps that don't actually contain a UV layout (every UV vertex in default position)

# Misc Operators

### Join As Shape Key By UVs
For when you have two meshes with identical topology and UVs, and want to combine them so you can blend from one to the other with a shape key. Just select both and run the operator.  

### Convert Images
Converts all images of a certain extension referenced by this blend file according to the render settings of the scene.  
Images must be saved outside of the .blend file.  
Could also use a better popup probably, WIP.  