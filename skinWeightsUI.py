
from filesystem import Path, removeDupes
from api import mel
from names import getCommonPrefix
from utils import Callback
from baseMelUI import *

import maya.cmds as cmd
import mappingEditor
import skinWeights
import meshUtils
import rigUtils
import time
import api


def isMesh( item ):
	shapes = cmd.listRelatives( item, shapes=True, pa=True )
	if shapes is None:
		return None

	for s in shapes:
		if cmd.nodeType( s ) == 'mesh':
			return s


class LockJointsLayout(MelForm):
	SUSPEND_UPDATE = False

	def __init__( self, parent ):
		MelForm.__init__( self, parent )

		self._mesh = None
		self._prefix = ''

		class JointList(MelObjectScrollList):
			def itemAsStr( tsl, item ):
				locked = cmd.getAttr( '%s.liw' % item )
				prefix = '# ' if locked else '   '

				return '%s%s' % (prefix, item.replace( self._prefix, '' ))

		self.UI_tsl = JointList( self, ams=True, sc=self.on_selectJoint, dcc=self.on_dcc )
		self.POP_tsl = cmd.popupMenu( b=3, p=self.UI_tsl, pmc=self.build_tslMenu )

		self.UI_lock = cmd.button( l="lock", c=self.on_lock )
		self.UI_unlock = cmd.button( l="unlock", c=self.on_unlock )

		self.UI_lockAll = cmd.button( l="LOCK ALL", c=self.on_lockAll )
		self.UI_unlockAll = cmd.button( l="UNLOCK ALL", c=self.on_unlockAll )

		self( e=True,
		      af=((self.UI_tsl, 'top', 0),
		          (self.UI_tsl, 'left', 0),
		          (self.UI_tsl, 'right', 0),
		          (self.UI_lock, 'left', 0),
		          (self.UI_unlock, 'right', 0),
		          (self.UI_lockAll, 'left', 0),
		          (self.UI_lockAll, 'bottom', 0),
		          (self.UI_unlockAll, 'right', 0),
		          (self.UI_unlockAll, 'bottom', 0)),
		      ap=((self.UI_lock, 'right', 0, 50),
		          (self.UI_unlock, 'left', 0, 50),
		          (self.UI_lockAll, 'right', 0, 50),
		          (self.UI_unlockAll, 'left', 0, 50)),
		      ac=((self.UI_tsl, 'bottom', 0, self.UI_lock),
		          (self.UI_lock, 'bottom', 0, self.UI_lockAll),
		          (self.UI_unlock, 'bottom', 0, self.UI_unlockAll)) )

		self.setSelectionChangeCB( self.on_selectionChange )
		self.on_selectionChange()
	@classmethod
	def Update( cls ):
		for inst in cls.IterInstances():
			inst.syncSelection()
	def iterSelected( self ):
		return iter( self.UI_tsl.getSelectedItems() )
	def attachToMesh( self, mesh ):
		self._mesh = mesh
		self._skinCluster = mel.findRelatedSkinCluster( mesh )

		joints = cmd.skinCluster( self._skinCluster, q=True, inf=True )

		self._prefix = getCommonPrefix( joints )
		self.UI_tsl.setItems( joints )

		self.on_updateState()
	def updateJointState( self, joint ):
		self.UI_tsl.update()
	def setLockStateForSelected( self, state=True, updateUI=True ):
		for j in self.iterSelected():
			cmd.setAttr( '%s.liw' % j, state )

		if updateUI:
			self.on_updateState()
	def setLockStateForAll( self, state=True, updateUI=True ):
		for j in self.UI_tsl:
			cmd.setAttr( '%s.liw' % j, state )

		if updateUI:
			self.on_updateState()
	def smoothBetweenSelectedJoints( self ):
		'''
		performs a flood smooth between the selected joints
		'''

		#grab initial state
		initialLockState = [ cmd.getAttr( '%s.liw' % j ) for j in self.UI_tsl ]
		initMode = cmd.artAttrSkinPaintCtx( cmd.currentCtx(), q=True, sao=True )
		initOpacity = cmd.artAttrSkinPaintCtx( cmd.currentCtx(), q=True, opacity=True )
		initValue = cmd.artAttrSkinPaintCtx( cmd.currentCtx(), q=True, value=True )

		self.setLockStateForAll( True, False )
		self.setLockStateForSelected( False, False )


		#perform the smooth
		cmd.artAttrSkinPaintCtx( cmd.currentCtx(), e=True, sao='smooth' )
		j = self.iterSelected().next()
		if j is not None:
			cmd.artAttrSkinPaintCtx( cmd.currentCtx(), e=True, value=1, opacity=1, clear=True )


		#restore state
		cmd.artAttrSkinPaintCtx( cmd.currentCtx(), e=True, sao=initMode )
		cmd.artAttrSkinPaintCtx( cmd.currentCtx(), e=True, opacity=initOpacity )
		cmd.artAttrSkinPaintCtx( cmd.currentCtx(), e=True, value=initValue )
		for j, state in zip( self.UI_tsl, initialLockState ):
			cmd.setAttr( '%s.liw' % j, state )
	def syncSelection( self ):
		'''
		syncs the list selection with the existing paint skin weights UI
		'''
		cur = cmd.artAttrSkinPaintCtx( cmd.currentCtx(), q=True, inf=True )
		if cur is None:
			return

		self.UI_tsl.clearSelection()
		self.UI_tsl.selectByValue( cur )

	### MENU BUILDERS ###
	def build_tslMenu( self, *a ):
		cmd.setParent( a[ 0 ], m=True )
		cmd.menu( a[ 0 ], e=True, dai=True )

		numSelected = sum(( 1 for j in self.iterSelected() ))

		cmd.menuItem( l="Select Verts For Joint", c=self.on_selectVerts )
		if numSelected > 1:
			cmd.menuItem( l="Select Verts Shared By Selected", c=self.on_selectIntersectingVerts )

		cmd.menuItem( l="Select Whole Mesh", c=self.on_selectMesh )
		cmd.menuItem( d=True )
		#cmd.menuItem( l="Smooth Between Selected Joints", c=self.on_smooth )

	### EVENT HANDLERS ###
	def on_selectionChange( self, *a ):
		self.syncSelection()


		sel = cmd.ls( sl=True )
		for s in sel:
			mesh = isMesh( s )

			#its already setup!  bail!
			if self._mesh == mesh:
				return

			if mesh:
				self.attachToMesh( mesh )
				return
	def on_updateState( self, *a ):
		if self.SUSPEND_UPDATE:
			return

		self.UI_tsl.update()
	def on_selectJoint( self, *a ):
		if cmd.currentCtx() == 'artAttrSkinContext':
			selJ = self.iterSelected().next()
			if selJ is None:
				return

			mel.artSkinSelectInfluence( 'artAttrSkinPaintCtx', selJ, selJ )
	def on_dcc( self, *a ):
		cmd.select( cl=True )
		for j in self.iterSelected():
			cmd.select( j, add=True )
	def on_lock( self, *a ):
		self.setLockStateForSelected()
	def on_unlock( self, *a ):
		self.setLockStateForSelected( False )
	def on_lockAll( self, *a ):
		self.setLockStateForAll()
	def on_unlockAll( self, *a ):
		self.setLockStateForAll( False )
	def on_selectVerts( self, *a ):
		selJoints = self.UI_tsl.getSelectedItems()
		if not selJoints:
			return

		verts = []
		for j in selJoints:
			verts += meshUtils.jointVertsForMaya( j )

		if verts:
			cmd.hilite( [ self._mesh ] )
			cmd.select( verts )
			mel.artAttrSkinToolScript( 4 )
	def on_selectIntersectingVerts( self, *a ):
		selJoints = self.UI_tsl.getSelectedItems()
		if not selJoints:
			return

		allVerts = []
		jointVerts = {}

		for j in selJoints:
			jointVerts[ j ] = verts = meshUtils.jointVertsForMaya( j )
			allVerts += verts

		allVerts = set( allVerts )

		commonVerts = []
		for j, jVerts in jointVerts.iteritems():
			commonVerts += allVerts.intersection( set( jVerts ) )

		if commonVerts:
			cmd.hilite( [ self._mesh ] )
			cmd.select( commonVerts )
			mel.artAttrSkinToolScript( 4 )
	def on_selectMesh( self, *a ):
		cmd.hilite( unHilite=True )
		cmd.select( self._mesh )
		mel.artAttrSkinToolScript( 4 )
	def on_smooth( self, *a ):
		self.smoothBetweenSelectedJoints()


class LockJointsWindow(BaseMelWindow):

	WINDOW_NAME = 'lockWeightEditor'
	WINDOW_TITLE = 'weight locker'

	DEFAULT_SIZE = 300, 400
	DEFAULT_MENU = None

	FORCE_DEFAULT_SIZE = True

	def __new__( cls, **kw ):
		return BaseMelWindow.__new__( cls, resizeToFitChildren=True, maximizeButton=False, sizeable=True )
	def __init__( self ):
		BaseMelWindow.__init__( self )
		self.editor = LockJointsLayout( self )
		self.show()


class SectionLabel(MelHSingleStretchLayout):
	def __init__( self, parent, label ):
		MelHSingleStretchLayout.__init__( self, parent )
		MelSeparator( self, w=25, h=20 )
		MelLabel( self, l=label, h=20 )
		s = MelSeparator( self, h=20 )
		self.setStretchWidget( s )
		self.layout()


class Spacer(MelLabel):
	def __new__( cls, parent, size=10 ):
		return MelLabel.__new__( cls, parent, w=size, h=size, l='' )
	def __init__( self, parent, size=10 ):
		MelLabel.__init__( self, parent, size )


class SkinButtonsLayout(MelHLayout):
	def __init__( self, parent ):
		MelHLayout.__init__( self, parent )

		a = self.UI_skinOff = MelButton( self, l='Turn Skinning Off', c=self.on_skinOff )
		b = self.UI_skinOn = MelButton( self, l='Turn Skinning On', c=self.on_skinOn )
		c = MelButton( self, l='Reset All Skin Clusters', c=self.on_resetSkin )
		self.updateSkinButtons()
		self.layout()
	def updateSkinButtons( self ):
		state = rigUtils.getSkinClusterEnableState()
		self.UI_skinOn( e=True, en=not state )
		self.UI_skinOff( e=True, en=state )

	def on_skinOff( self, e=None ):
		rigUtils.disableSkinClusters()
		self.updateSkinButtons()
	def on_skinOn( self, e=None ):
		rigUtils.enableSkinClusters()
		self.updateSkinButtons()
	def on_resetSkin( self, e=None ):
		for sc in ls( typ='skinCluster' ):
			rigUtils.resetSkinCluster( sc )


class MeshMappingEditor(mappingEditor.MappingEditor):
	WINDOW_NAME = 'skinWeightsMeshMapper'
	WINDOW_TITLE = 'Mesh Re-Map Editor'


class JointMappingEditor(mappingEditor.MappingEditor):
	WINDOW_NAME = 'skinWeightsJointMapper'
	WINDOW_TITLE = 'Joint Re-Map Editor'



class SkinWeightsLayout(MelColumnLayout):
	LBL_MESH_REMAP_BUTTON_HASMAP = "define mesh re-mapping (map defined)"
	LBL_MESH_REMAP_BUTTON_NOMAP = "define mesh re-mapping"

	LBL_JOINT_REMAP_BUTTON_HASMAP = "define joint re-mapping (map defined)"
	LBL_JOINT_REMAP_BUTTON_NOMAP = "define joint re-mapping"

	def __init__( self, parent, *a, **kw ):
		MelColumnLayout.__init__( self, parent, *a, **kw )

		SectionLabel( self, 'store options' )
		hLayout = MelHSingleStretchLayout( self )
		self.UI_fileLbl = MelLabel( hLayout, l="weight file (optional)" )
		self.UI_file = MelTextField( hLayout )
		hLayout.setStretchWidget( self.UI_file )
		hLayout.layout()

		MelPopupMenu( self.UI_file, pmc=self.build_popup )

		self.UI_storeA = MelButton( self, l="store selection to file", c=self.on_storeA )
		#self.UI_storeB = MelButton( self, l="store joint volumes to file", c=self.on_storeB )

		Spacer( self )
		SectionLabel( self, 'restore options' )
		hLayout = MelHSingleStretchLayout( self )
		self.UI_average = MelCheckBox( hLayout, l="average found verts", v=1 )
		self.UI_ratioLbl = MelLabel( hLayout, l="max ratio" )
		self.UI_ratio = MelFloatField( hLayout, v=2, w=50 )
		hLayout.setStretchWidget( self.UI_ratio )
		hLayout.layout()

		self.UI_mirror = MelCheckBox( self, l="mirror on restore", v=0 )

		self.UI_meshMapping = MelButton( self, l=self.LBL_MESH_REMAP_BUTTON_NOMAP, c=self.on_meshMap )
		self.UI_jointMapping = MelButton( self, l=self.LBL_JOINT_REMAP_BUTTON_NOMAP, c=self.on_jointMap )
		self.UI_meshMapping.hide()
		self.UI_jointMapping.hide()

		#SectionLabel( mainLayout, 'restore options' )
		#self.UI_restoreById = MelCheckBox( mainLayout, l="restore by id", v=0, cc=self.on_changeRestoreMode )

		self.UI_restore = MelButton( self, l="restore from tmp file", c=self.on_restore )

		self.on_changeRestoreMode()
	def getMeshRemapDict( self ):
		try:
			return self._UI_meshMap.getMapping().asFlatDict()
		except AttributeError:
			return None
	def getJointRemapDict( self ):
		try:
			return self._UI_jointMap.getMapping().asFlatDict()
		except AttributeError:
			return None

	### MENU BUILDERS ###
	def build_popup( self, parent, *a ):
		cmd.setParent( parent, m=True )
		cmd.menu( parent, e=True, dai=True )

		thisFile = Path( cmd.file( q=True, sn=True ) )

		#if the file doesn't exist, then use teh cwd
		if not thisFile.exists:
			thisFile = thisFile.getcwd() / "tmp.ma"

		dir = thisFile.up()
		curFile = Path( cmd.textField( self.UI_file, q=True, tx=True ) )

		for f in dir.files():
			if f.hasExtension( skinWeights.EXTENSION ):
				cmd.menuItem( l=f.name(), cb=f==curFile, c=api.Callback( cmd.textField, self.UI_file, e=True, tx=f ) )

		cmd.menuItem( d=True )
		cmd.menuItem( l="browse", c=self.on_browseWeightFile )
		cmd.menuItem( d=True )
		cmd.menuItem( l="clear", c=lambda *a: cmd.textField( self.UI_file, e=True, tx='' ) )
		if curFile.exists:
			cmd.menuItem( d=True )
			api.addExploreToMenuItems( curFile )

	### EVENT HANDLERS ###
	def on_changeRestoreMode( self, *a ):
		#if self.UI_restoreById.getValue():
			#self.UI_average.disable()
			##self.UI_doPreview.disable()
			#self.UI_ratio.disable()
			#self.UI_mirror.disable()
			#self.UI_meshMapping.enable()
			#self.UI_jointMapping.disable()
		#else:
		self.UI_average.enable()
		#self.UI_doPreview.enable()
		self.UI_ratio.enable()
		self.UI_mirror.enable()
		self.UI_meshMapping.disable()
		self.UI_jointMapping.enable()
	def on_meshMap( self, *a ):
		try:
			mapping = self._UI_meshMap.getMapping()

			self._UI_meshMap = MeshMappingEditor()
			self._UI_meshMap.editor.setMapping( mapping )
			self._UI_meshMap.editor.ALLOW_MULTI_SELECTION = False
		except AttributeError:
			filepath = self.getFilepath()
			data = WeightSaveData( filepath.unpickle() )
			meshes = list( data.getUsedMeshes() )

			sceneMeshes = cmd.ls( typ='mesh' )
			if sceneMeshes:
				sceneMeshes = cmd.listRelatives( sceneMeshes, p=True, pa=True )

			mapping = names.Mapping( meshes, sceneMeshes, threshold=0.1 )

			self._UI_meshMap = MeshMappingEditor()
			self._UI_meshMap.editor.setMapping( mapping )
			self._UI_meshMap.editor.ALLOW_MULTI_SELECTION = False

			self.on_mappingUIStatus()
	def on_jointMap( self, *a ):
		try:
			mapping = self._UI_jointMap.getMapping()

			self._UI_jointMap = MeshMappingEditor()
			self._UI_jointMap.editor.setMapping( mapping )
			self._UI_jointMap.editor.ALLOW_MULTI_SELECTION = False
		except AttributeError:
			filepath = self.getFilepath()
			data = WeightSaveData( filepath.unpickle() )
			joints = list( data.getUsedJoints() )

			sceneJoints = cmd.ls( typ='joint' )
			mapping = names.Mapping( joints, sceneJoints, threshold=0.1 )

			self._UI_jointMap = JointMappingEditor()
			self._UI_jointMap.editor.setMapping( mapping )
			self._UI_jointMap.editor.ALLOW_MULTI_SELECTION = False

			self.on_mappingUIStatus()
	def on_browseWeightFile( self, *a ):
		startDir = getDefaultPath().up()

		filepath = cmd.fileDialog( directoryMask= startDir / "/*.weights" )
		if filepath:
			cmd.textField( self.UI_file, e=True, tx=filepath )
	def on_storeA( self, *a ):
		kw = {}
		if self.UI_file.getValue():
			kw[ 'filepath' ] = Path( self.UI_file.getValue() )

		skinWeights.saveWeights( cmd.ls( sl=True ), **kw )
	def on_storeB( self, *a ):
		kw = {}
		if self.UI_file.getValue():
			kw[ 'filepath' ] = Path( self.UI_file.getValue() )

		joints = cmd.ls( type='joint', r=True )
		jointMeshes = removeDupes( cmd.listRelatives( joints, ad=True, pa=True, type='mesh' ) )

		skinWeights.saveWeights( jointMeshes, **kw )
	def on_restore( self, *a ):
		filepath = None
		if self.UI_file.getValue():
			filepath = Path( self.UI_file.getValue() )

		skinWeights.loadWeights( cmd.ls( sl=True ),
		                         filepath,
		                         True, #not self.UI_restoreById.getValue(),
		                         self.UI_ratio.getValue(),
		                         (-1,) if self.UI_mirror.getValue() else None,
		                         averageVerts=self.UI_average.getValue(),
		                         doPreview=False, #self.UI_doPreview.getValue(),
		                         meshNameRemapDict=self.getMeshRemapDict(),
		                         jointNameRemapDict=self.getJointRemapDict() )
	def on_mappingUIStatus( self, *a ):
		#do we have a mesh re-map?
		try:
			self._UI_meshMap
			self.UI_meshMapping( e=True, l=self.LBL_MESH_REMAP_BUTTON_HASMAP )
		except AttributeError:
			self.UI_meshMapping( e=True, l=self.LBL_MESH_REMAP_BUTTON_NOMAP )

		#do we have a joint re-map?
		try:
			self.UI_jointMapping( e=True, l=self.LBL_JOINT_REMAP_BUTTON_HASMAP )
		except AttributeError:
			self.UI_jointMapping( e=True, l=self.LBL_JOINT_REMAP_BUTTON_NOMAP )


class SkinWeightsWindow(BaseMelWindow):
	WINDOW_NAME = 'weightSave'
	WINDOW_TITLE = 'weight save'

	DEFAULT_SIZE = 200, 30
	DEFAULT_MENU = None
	HELP_MENU = WINDOW_NAME, 'hamish@macaronikazoo.com', None

	FORCE_DEFAULT_SIZE = False

	def __init__( self ):
		BaseMelWindow.__init__( self )

		scroll = MelScrollLayout( self )
		col = MelColumnLayout( scroll, rs=5 )

		SkinWeightsLayout( col )

		Spacer( col )
		SectionLabel( col, 'skinning control' )
		SkinButtonsLayout( col )

		import smoothWeights
		frame = MelFrameLayout( col, label='smoothing tool', cll=True, cl=True )
		PyFuncLayout( frame, smoothWeights.smoothByInfluenceMask )

		self.show()
		self.layout()


#end
