
from baseMelUI import *
from maya.mel import eval as evalMel
from filesystem import Path

import maya

try:
	#try to connect to wing - otherwise don't worry
	import wingdbstub
except ImportError: pass


def setupZooToolBox():
	#all the files for zooToolBox should live in the same directory as this script, including plug-ins
	thisFile = Path( __file__ )
	thisPath = thisFile.up()

	existingPlugPathStr = maya.mel.eval( 'getenv MAYA_PLUG_IN_PATH;' )
	existingPlugPaths = existingPlugPathStr.split( ';' )

	newPlugPaths = []
	pathsAlreadyInList = set()

	zooPlugPathAdded = False
	for path in existingPlugPaths:
		path = Path( path )
		if path in pathsAlreadyInList:
			continue

		pathsAlreadyInList.add( path )
		newPlugPaths.append( path.unresolved() )

		if path == thisPath:
			zooPlugPathAdded = True

	if not zooPlugPathAdded:
		newPlugPaths.append( thisPath )

	newPlugPathStr = ';'.join( newPlugPaths )

	maya.mel.eval( 'putenv MAYA_PLUG_IN_PATH "%s";' % newPlugPathStr )


def loadZooPlugin( pluginName ):
	try:
		cmd.loadPlugin( pluginName, quiet=True )
	except:
		setupZooToolBox()
		try:
			cmd.loadPlugin( pluginName, quiet=True )
		except:
			maya.OpenMaya.MGlobal.displayError( 'Failed to load zooMirror.py plugin - is it in your plugin path?' )


def loadSkeletonBuilderUI( *a ):
	import skeletonBuilderUI
	skeletonBuilderUI.SkeletonBuilderWindow()


def loadSkinPropagation( *a ):
	import refPropagation
	refPropagation.propagateWeightChangesToModel_confirm()


def loadPicker( *a ):
	import picker
	picker.PickerWindow()


class ToolCB(object):
	def __init__( self, melStr ):
		self.cmdStr = melStr
	def __call__( self, *a ):
		evalMel( self.cmdStr )


#this describes the tools to display in the UI - the nested tuples contain the name of the tool as displayed
#in the UI, and a tuple containing the annotation string and the button press callback to invoke when that
#tool's toolbox button is pressed.
#NOTE: the press callback should take *a as its args
TOOL_CATS = ( ('rigging', (('Skeleton Builder - the new CST', "Skeleton Builder is what zooCST initially set out to be", loadSkeletonBuilderUI),
						   ('Skinning Propagation', "Propagates skinning changes made to referenced geometry to the file it lives in", loadSkinPropagation),
                           ('zooCST', 'The ghetto version of Skeleton Builder', None),
                           ('zooTriggered', 'zooTriggered is one of the most powerful rigging companions around.  It allows the rigger to attach name independent MEL commands to an object.  These commands can be run either on the selection of the object, or by right clicking over that object.\n\nIt allows context sensitive scripted commands to be added to a character rig, which allows the rigger to create more intuitive rigs.  Being able to add name independent MEL scripts to a rig can open up entire new worlds of possibilities, as does selection triggered MEL commands.', None),
                           #('zooTriggerator', '''zooTriggerator is an interface for building and managing triggered viewport interfaces.  It builds collapsible, in-viewport folders that contain selection triggers.\n\nThey can be used to build selection triggers for complex rigs to make an easy to use interface for animators to use.''', None),
                           ('zooKeymaster', 'keymaster gives you a heap of tools to manipulate keyframes - scaling around curve pivots, min/max scaling of curves/keys etc...', ToolCB( 'source zooKeymaster; zooKeymasterWin;' )),
                           ('zooSurgeon', 'zooSurgeon will automatically cut up a skinned mesh and parent the cut up "proxy" objects to the skeleton.  This allows for near instant creation of a fast geometrical representation of a character.', None),
                           ('zooVisMan', 'visMan is a tool for creating and using heirarchical visibility sets in your scene.  a visibility set holds a collection of items, be it components, objects or anything else that normally fits into a set.  the sets can be organised heirarchically, and easily collapsed, and selected in a UI to show only certain objects in your viewports.  its great for working with large sets, or breaking a character up into parts to focus on', None))),

              ('animation', (('zooPicker', 'Picker tool - provides a way to create buttons that select scene objects, or run arbitrary code', loadPicker),
							 ('zooAnimStore', '', None),
                             ('zooXferAnim', 'zooXferAnim is an animation transfer utility.  It allows transfer of animation using a variety of different methods, instancing, duplication, copy/paste, import/export and tracing.  Its also fully externally scriptable for integration into an existing production pipeline.', None),
                             ('zooGraphFilter', 'zooGraphFilter provides a quick and easy way of filtering out certain channels on many objects in the graph editor.', None),
                             ('zooKeyCommands', 'zooKeyCommands is a simple little tool that lets you run a MEL command on an object for each keyframe the object has.  It basically lets you batch a command for each keyframe.', None),
                             ('zooGreaseMonkey', 'zooGreaseMonkey is a neat little script that allows you to draw in your camera viewport.  It lets you add as many frames as you want at various times in your scene.  You can use it to thumbnail your animation in your viewport, you can use it to plot paths, you could even use it to do a simple 2d based animation if you wanted.', None),
                             ('zooShots', 'zooShots is a camera management tool.  It lets you create a bunch of cameras in your scene, and "edit" them together in time.  The master camera then cuts between each "shot" camera.  All camera attributes are maintained over the cut - focal length, clipping planes, fstop etc...\n\nThe interface allows you to associate notes with each shot, colour shots in the UI to help group like shots, shot numbering etc...', None),
                             ('zooHUDCtrl', 'zooHUDCtrl lets you easily add stuff to your viewport HUD.  It supports custom text, filename, current frame, camera information, object attribute values, and if you are using zooShots, it will also print out shot numbers to your HUD.', None))),

              ('general', (('zooAutoSave', '''zooAutoSave is a tool that will automatically save your scene after a certain number of selections.  Maya doesn't provide a timer, so its not possible to write a time based autosave tool, but it makes more sense to save automatically after you've done a certain number of "things".  You can easily adjust the threshold, and have the tool automatically start when maya starts if you wish.''', None),
                           #('zooReblender', '', None),
                           )),

              ('hotkeys', (('zooAlign',
                            'snaps two objects together - first select the master object, then the object you want to snap, then hit the hotkey',
                            ToolCB( 'zooHotkeyer zooAlign "{zooAlign \"-load 1\";\nstring $sel[] = `ls -sl`;\nfor( $n=1; $n<`size $sel`; $n++ ) zooAlignSimple $sel[0] $sel[$n];}" "" "-default a -alt 1 -enableMods 1 -ann aligns two objects"')),
                           ('zooSetMenu',
                            'zooSetMenu us a marking menu that lets you quickly interact with all quick selection sets in your scene.',
                            ToolCB( "zooHotkeyer zooSetMenu \"zooSetMenu;\" \"zooSetMenuKillUI;\" \"-default y -enableMods 0 -ann zooSetMenu lets you quickly interact with selection sets in your scene through a marking menu interface\";" )),
                           ('zooTangentWks',
                            'zooTangentWks is a marking menu script that provides super fast access to common tangent based operations.  Tangent tightening, sharpening, change tangent types, changing default tangents etc...',
                            ToolCB( "zooHotkeyer zooTangentWks \"zooTangentWks;\" \"zooTangentWksKillUI;\" \"-default q -enableMods 0 -ann tangent works is a marking menu script to speed up working with the graph editor\";" )),
                           ('zooSetkey',
                            'zooSetKey is a tool designed to replace the set key hotkey.  It is a marking menu script that lets you perform a variety of set key based operations - such as push the current key to the next key, perform a euler filter on all selected objects etc...',
                            ToolCB( "zooHotkeyer zooSetkey \"zooSetkey;\" \"zooSetkeyKillUI;\" \"-default s -enableMods 0 -ann designed to replace the set key hotkey, this marking menu script lets you quickly perform all kinda of set key operations\";" )),
                           ('zooCam',
                            'zooCam is a marking menu that lets you quickly swap between any camera in your scene.  It is integrated tightly with zooShots, so you can quickly navigate between shot cameras, master cameras, or any other in-scene camera.',
                            ToolCB( "zooHotkeyer zooCam \"zooCam;\" \"zooCamKillUI;\" \"-default l -enableMods 0 -ann zooCam marking menu script for managing in scene cameras\";" )),
                           ('toggle_shading',
                            'toggles viewport shading',
                            ToolCB( "zooHotkeyer toggleShading \"zooToggle shading;\" \"\" \"-default 1 -enableMods 1 -ann toggles viewport shading\"" )),
                           ('toggle_texturing',
                            'toggles viewport texturing',
                            ToolCB( "zooHotkeyer toggleTexture \"zooToggle texturing;\" \"\" \"-default 2 -enableMods 1 -ann toggles viewport texturing\"" )),
                           ('toggle_lights',
                            'toggles viewport lighting',
                            ToolCB( "zooHotkeyer toggleLights \"zooToggle lighting;\" \"\" \"-default 3 -enableMods 1 -ann toggles viewport lighting\"" )))) )


class ToolboxTab(MelColumnLayout):
	def __new__( cls, parent, toolTuples ):
		return MelColumnLayout.__new__( cls, parent )
	def __init__( self, parent, toolTuples ):
		MelColumnLayout.__init__( self, parent )

		for toolStr, annStr, pressCB in toolTuples:
			if pressCB is None:
				pressCB = ToolCB( '%s;' % toolStr )

			MelButton( self, l=toolStr, ann=annStr, c=pressCB )


class ToolboxTabs(MelTabLayout):
	def __init__( self, parent ):
		n = 0
		for toolCatStr, toolTuples in TOOL_CATS:
			ui = ToolboxTab( self, toolTuples )
			self.setLabel( n, toolCatStr )
			n += 1


class ToolboxWindow(BaseMelWindow):
	WINDOW_NAME = 'zooToolBox'
	WINDOW_TITLE = 'zooToolBox    ::macaroniKazoo::'

	DEFAULT_SIZE = 400, 300
	FORCE_DEFAULT_SIZE = True

	DEFAULT_MENU = None

	def __init__( self ):
		setupZooToolBox()
		ToolboxTabs( self )
		self.show()


#end
