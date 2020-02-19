import bpy
from bpy.props import *

class ConvertImages(bpy.types.Operator):
	""" Convert images with one or any extension to whatever you have set in your render output settings. Uses Image.save_as_render(). """
	bl_idname = "image.convert_images"
	bl_label = "Convert Images"
	bl_options = {'REGISTER', 'UNDO'}

	from_ext: StringProperty(
		name="From Extension",
		default="dds",
		description="Images with this file extension will be converted. The old images will still be in their original directory, but will no longer be referenced by this .blend file. Leaving this empty will convert all images. The target format is defined by your render output settings."
	)

	rename_files: BoolProperty(
		name="Rename Files",
		default=False,
		description="If enabled, rename the converted files to the name of the image datablock (the name displayed in the image editor's header) - IMPORTANT: Image datablock name should NOT contain extension ",
		options={'SKIP_SAVE'}
	)

	start: BoolProperty(
		name="Go",
		default=False,
		description="Tick to begin converting. DO NOT TOUCH THIS PANEL ONCE YOU'RE DONE!",
		options={'SKIP_SAVE'}
	)

	def execute(self, context):
		# Saving view settings
		view_settings = context.scene.view_settings
		org_view_transform = view_settings.view_transform
		org_exposure = view_settings.exposure
		org_gamma = view_settings.gamma
		org_look = view_settings.look
		org_curve = view_settings.use_curve_mapping
		
		# Resetting view settings to default values
		view_settings.view_transform = 'Standard'
		view_settings.exposure = 0
		view_settings.gamma = 1
		view_settings.look = 'None'
		view_settings.use_curve_mapping = False

		to_format = context.scene.render.image_settings.file_format
		to_ext = to_format.lower()
		ext_dict = {
			'IRIS' : 'rgb',
			'JPEG' : 'jpg',
			'JPEG2000' : 'jp2',
			'TARGA' : 'tga',
			'TARGA_RAW' : 'tga',
			'CINEON' : 'cin',
			'OPEN_EXR_MULTILAYER' : 'exr',
			'OPEN_EXR' : 'exr',
			'TIFF' : 'tif'
		}

		if(to_format in ext_dict.keys()):
			to_ext = to_format[ext_dict]

		assert bpy.data.is_saved, "Please save your file, open the system console, and make a backup of your textures before running this operator."
		# Check some things first, to make sure conversion will go smoothly.
		for img in bpy.data.images:
			if(not img.filepath.endswith(self.from_ext)): continue

			assert len(img.packed_files) == 0, "Image has packed files:\n" + img.filepath +"\nPlease unpack all files (ideally pack everything first, then unpack all to current directory)"
			if(self.rename_files):
				assert "." not in img.name, "It looks like you want to rename files to the image datablock's name, but your image datablock contains an extension:\n" + img.name + "\nMake sure your image names don't contain a period."

		if(not self.start):
			return {'FINISHED'}

		for img in bpy.data.images:
			if(not img.filepath.endswith(self.from_ext)): continue

			print("Working on: "+img.filepath)
			old_path = img.filepath					   # Full path
			old_name = img.filepath.split("\\")[-1]	   # Name with extension
			old_ext = old_name.split(".")[-1]
			if(old_ext == self.from_ext):
				new_path = old_path.replace("."+self.from_ext, "."+to_ext)
				# Optional: Change file name to the image object's name (make sure image object names do not contain extension)
				if(self.rename_files):
					old_name_no_ext = old_name[:-(len(old_ext)+1)]
					new_path = new_path.replace(old_name_no_ext, img.name)
				
				if new_path == old_path:
					print('Skipping ' + img.filepath )
					continue
				try:
					# Convert the image
					img.save_render(bpy.path.abspath(new_path))
					# Load the converted image over the old one
					img.filepath = new_path
				except RuntimeError:
					print( "FAILED:" )
					print( "...Dimensions: " + str(i.size[0]) + " x " + str(i.size[1]) ) # If it's 0x0 then the .dds failed to be read by Blender to begin with, nothing we can do(these textures are usually bogus anyways, don't need them). Otherwise, something's gone wrong.
		
		# Resetting view settings to original values
		view_settings.view_transform = org_view_transform
		view_settings.exposure = org_exposure
		view_settings.gamma = org_gamma
		view_settings.look = org_look
		view_settings.use_curve_mapping = org_curve

		bpy.context.scene.view_settings.view_transform = org_view_transform
		print("FIN")
		return {'FINISHED'}

def register():
	from bpy.utils import register_class
	register_class(ConvertImages)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(ConvertImages)