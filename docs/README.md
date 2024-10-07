This addon is a staging ground for features that I use or made, to boost my rigging workflow.  
Over time, functionality moves to my other add-ons, found on the [Extensions Platform](https://extensions.blender.org/author/1321/).  
Not much remains in this add-on, and some more of it will be moved elsewhere soon.

# Current Functions
There is some extra stuff beside what's documented.  

### Refresh Drivers
Sometimes drivers in Blender decide to just fall asleep, or claim to have an error when they don't. Run this operator to refresh them, to make sure they don't complain about errors that don't exist.  
This will be moved to the Blender Log add-on.

### Apply Armature Scale
This operator will apply uniform scale to a rigged armature while maintaining its constraints. It also applies the scaling to all actions used by the rig's Action constraints. (Optinally all actions in the whole scene)
This will be moved to CloudRig.

### Create Transform Constraint
Create transform constraint on the active bone, targeting the selected one, based on current local transforms of the active bone.
Not sure if this will be moved anywhere yet.

### Setup Action Constraints
Automatically manage action constraints of one action on all bones in an armature.
This will be moved to CloudRig.

### Add Vertex Weights to Active
Add vertex weights of all selected pose bones to the active one.
This may be moved to CloudRig as a "Merge Bones" operator.

---

# Removed Functions
Functionality that hasn't moved to any other add-on but isn't actively maintained (because I don't need it anymore) lives inside the legacy folder of this repo.

### Weight Painting Operators
These operators have been split out to the [Easy Weight](https://extensions.blender.org/add-ons/easyweight/) add-on. I highly recommend it.

### Symmetrize Selected Bones
An improved version of this operator is now available as part of the [CloudRig](https://extensions.blender.org/add-ons/cloudrig/) extension. Press X in pose mode to summon the pie menu. See the [documentation](https://studio.blender.org/pipeline/addons/cloudrig/workflow-enhancements#bone-specials-pie-x) for details.

### Assign Bone Group
Bone Groups were removed in Blender 4.0, so I removed this operator.