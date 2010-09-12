
from maya.cmds import *
from maya import cmds as cmd
from filesystem import Path
from baseMelUI import *

import api
import names
import rigPrimitives
import rigPrim_base
import rigUtils
import control
import baseMelUI
import spaceSwitchingUI

Axis = rigUtils.Axis

ui = None

#stores UI build methods keyed by arg name
UI_FOR_NAMED_RIG_ARGS = {}

BaseSkeletonPart = rigPrimitives.BaseSkeletonPart
SkeletonPart = rigPrimitives.SkeletonPart
SkeletonPreset = rigPrimitives.SkeletonPreset

ShapeDesc = control.ShapeDesc

class ListEditor(BaseMelWindow):
	WINDOW_NAME = 'parentsEditor'
	WINDOW_TITLE = 'Edit Custom Parents'

	DEFAULT_SIZE = 275, 300
	DEFAULT_MENU = None

	FORCE_DEFAULT_SIZE = True

	def __new__( self, theList, changeCB ):
		return BaseMelWindow.__new__( self )
	def __init__( self, theList, storage ):
		BaseMelWindow.__init__( self )

		f = MelForm( self )
		self.add = MelButton( f, l='add selected item', c=self.on_add )
		self.rem = MelButton( f, l='remove highlighted items', c=self.on_rem )

		self.scroll = MelTextScrollList( f )
		self.scroll.setItems( theList )
		self.storage = storage

		f( e=True,
		   af=((self.add, 'top', 0),
		       (self.add, 'left', 0),
		       (self.rem, 'top', 0),
		       (self.rem, 'right', 0),
		       (self.scroll, 'left', 0),
		       (self.scroll, 'right', 0),
		       (self.scroll, 'bottom', 0)),
		   ap=((self.add, 'right', 0, 45),
		       (self.rem, 'left', 0, 45)),
		   ac=((self.scroll, 'top', 0, self.add)) )

	### EVENT HANDLERS ###
	def on_add( self, *a ):
		sel = cmd.ls( sl=True )
		if sel:
			self.scroll.appendItems( sel )

		self.storage.setValue( self.scroll.getItems() )
		self.storage.cb()
	def on_rem( self, *a ):
		self.scroll.removeSelectedItems()

		self.storage.setValue( self.scroll.getItems() )
		self.storage.cb()


class MelListEditorButton(MelButton):
	def __init__( self, parent, *a, **kw ):
		kw[ 'label' ] = 'define parents'
		kw[ 'c' ] = self.openEditor
		MelButton.__init__( self, parent, *a, **kw )
	def setValue( self, value, executeChangeCB=False ):
		self.value = value
	def getValue( self ):
		return self.value
	def setChangeCB( self, cb ):
		self.cb = cb
	def openEditor( self, *a ):
		win = ListEditor( self.value, self )
		win.show()


#hook up list/tuple types to a button - we don't want a text scroll list showing up in the part UI, but a button to bring up said editor is fine
UI_FOR_PY_TYPES[ list ] = MelListEditorButton
UI_FOR_PY_TYPES[ tuple ] = MelListEditorButton


class MelOptionMenu_SkeletonPart(MelOptionMenu):
	PART_CLASS = BaseSkeletonPart

	def __new__( cls, parent, *a, **kw ):
		self = MelOptionMenu.__new__( cls, parent, *a, **kw )
		self.populate()

		return self
	def populate( self ):
		self.clear()
		for part in self.PART_CLASS.IterAllParts():
			self.append( part.end )
	def setValue( self, value, executeChangeCB=True ):
		if type( value ) is type:
			return

		return MelOptionMenu.setValue( self, value, executeChangeCB )
	def getValue( self ):
		value = MelOptionMenu.getValue( self )
		return self.PART_CLASS.InitFromItem( value )


class MelOptionMenu_Arm(MelOptionMenu_SkeletonPart):
	PART_CLASS = rigPrimitives.Arm


class MelOptionMenu_Shape(MelOptionMenu):
	def __new__( cls, parent, *a, **kw ):
		self = MelOptionMenu.__new__( cls, parent, *a, **kw )
		self.populate()

		return self
	def populate( self ):
		self.clear()
		for shapeName in sorted( rigPrimitives.CONTROL_SHAPE_DICT.keys() ):
			self.append( shapeName )
	def setValue( self, value, executeChangeCB=True ):
		if type( value ) is type:
			return

		if isinstance( value, ShapeDesc ):
			value = value.surfaceType

		return MelOptionMenu.setValue( self, value, executeChangeCB )
	def getValue( self ):
		value = MelOptionMenu.getValue( self )

		return ShapeDesc( value )


class MelOptionMenu_Axis(MelOptionMenu):
	def __new__( cls, parent, *a, **kw ):
		self = MelOptionMenu.__new__( cls, parent, *a, **kw )
		self.populate()

		return self
	def populate( self ):
		self.clear()
		for shapeName in sorted( Axis.AXES ):
			self.append( shapeName )
	def setValue( self, value, executeChangeCB=True ):
		if type( value ) is type:
			return

		if isinstance( value, Axis ):
			value = value.asName()

		return MelOptionMenu.setValue( self, value, executeChangeCB )


baseMelUI.UI_FOR_PY_TYPES[ rigPrimitives.BaseSkeletonPart ] = MelOptionMenu_SkeletonPart
baseMelUI.UI_FOR_PY_TYPES[ rigPrimitives.Arm ] = MelOptionMenu_Arm
baseMelUI.UI_FOR_PY_TYPES[ ShapeDesc ] = MelOptionMenu_Shape
UI_FOR_NAMED_RIG_ARGS[ 'axis' ] = MelOptionMenu_Axis
UI_FOR_NAMED_RIG_ARGS[ 'direction' ] = MelOptionMenu_Axis


setParent = cmd.setParent

class SeparatorLabelLayout(MelForm):
	def __init__( self, parent, label ):
		MelForm.__init__( self, parent )
		self.UI_label = MelLabel( self, label=label, align='left' )
		setParent( self )
		self.UI_separator = cmd.separator( horizontal=True )

		self( e=True,
		      af=((self.UI_label, 'left', 0),
		          (self.UI_separator, 'top', 6),
		          (self.UI_separator, 'right', 0)),
		      ac=((self.UI_separator, 'left', 5, self.UI_label)) )


class SkeletonPartCreateLayout(MelForm):
	'''
	ui for single skeleton part creation
	'''
	ABBRVS_TO_EXPAND = names.ABBRVS_TO_EXPAND.copy()
	ABBRVS_TO_EXPAND[ 'idx' ] = 'index'

	BUTTON_LBL_TEMPLATE = 'Create %s'

	def __new__( cls, parent, partClass, getScaleMethod ):
		return MelForm.__new__( cls, parent )
	def __init__( self, parent, partClass, builderUI ):
		MelForm.__init__( self, parent )

		self.partClass = partClass
		self.builderUI = builderUI
		self.UI_create = cmd.button( l=self.BUTTON_LBL_TEMPLATE % names.camelCaseToNice( partClass.GetPartName() ), c=self.on_create, w=160 )

		#now populate the ui for the part's args
		self.kwarg_UIs = {}  #keyed by arg name
		kwargList = partClass.GetDefaultBuildKwargs()
		self.UI_argsLayout = MelForm( self )

		#everything has a parent attribute, so build it first
		prevUI = None
		for arg, default in kwargList:
			#skip UI for parent - assume selection always
			if arg == 'parent':
				continue

			setParent( self.UI_argsLayout )
			lbl = cmd.text( l=names.camelCaseToNice( arg, self.ABBRVS_TO_EXPAND ) )

			#determine the function to use for building the UI for the arg
			buildMethodFromName = UI_FOR_NAMED_RIG_ARGS.get( arg, None )
			buildMethodFromType = baseMelUI.UI_FOR_PY_TYPES.get( type( default ), baseMelUI.MelTextField )

			buildMethod = buildMethodFromName or buildMethodFromType

			self.kwarg_UIs[ arg ] = argUI = buildMethod( self.UI_argsLayout )
			argUI.setValue( default )

			#perform layout
			if prevUI is None:
				self.UI_argsLayout( e=True, af=((lbl, 'left', 15)) )
			else:
				self.UI_argsLayout( e=True, ac=((lbl, 'left', 15, prevUI)) )

			if isinstance( argUI, MelCheckBox ):
				self.UI_argsLayout( e=True, af=((argUI, 'top', 3)) )

			self.UI_argsLayout( e=True, af=((lbl, 'top', 3)), ac=((argUI, 'left', 5, lbl)) )
			prevUI = argUI

		setParent( self )

		self( e=True, af=((self.UI_create, 'left', 0),
		                  (self.UI_argsLayout, 'right', 0)),
		              ac=((self.UI_argsLayout, 'left', 0, self.UI_create)) )
	def getKwargDict( self ):
		kwargs = {}
		for arg, ui in self.kwarg_UIs.iteritems():
			kwargs[ arg ] = ui.getValue()

		if kwargs.has_key( 'parent' ):
			if not kwargs[ 'parent' ]:
				kwargs[ 'parent' ] = None

		kwargs[ 'partScale' ] = self.builderUI.getScale()

		return kwargs
	def rePopulate( self ):
		for argName, ui in self.kwarg_UIs.iteritems():
			if isinstance( ui, MelOptionMenu_SkeletonPart ):
				ui.populate()
	def on_create( self, e ):
		kwargs = self.getKwargDict()
		self.partClass.Create( **kwargs )
		self.builderUI.rePopulate()


class SkeletonPresetLayout(SkeletonPartCreateLayout):
	BUTTON_LBL_TEMPLATE = 'Build a %s Preset'

	def getKwargDict( self ):
		kwargs = {}
		for arg, ui in self.kwarg_UIs.iteritems():
			kwargs[ arg ] = ui.getValue()

		kwargs[ 'scale' ] = self.builderUI.getScale()

		return kwargs
	def on_create( self, e ):
		kwargs = self.getKwargDict()
		self.partClass( **kwargs )
		self.builderUI.rePopulate()


class SkeletonPartOptionMenu(MelOptionMenu):
	DYNAMIC = False
	STATIC_CHOICES = [ partCls.__name__ for partCls in BaseSkeletonPart.GetSubclasses() if partCls.AVAILABLE_IN_UI ]


class ManualPartCreationLayout(MelHSingleStretchLayout):
	def __init__( self, parent, *a, **kw ):
		MelHSingleStretchLayout.__init__( self, parent, *a, **kw )

		self.UI_partType = SkeletonPartOptionMenu( self )

		self.UI_convert = MelButton( self, l='Convert Selection To Skeleton Part', c=self.on_convert )
		self.setSelectionChangeCB( self.on_selectionChange )

		self.setStretchWidget( self.UI_convert )
		self.layout()

		self.on_selectionChange()

	### EVENT HANDLERS ###
	def on_convert( self, *a ):
		partTypeStr = self.UI_partType.getValue()
		partType = SkeletonPart.GetNamedSubclass( partTypeStr )
		sel = cmd.ls( sl=True )
		newPart = partType( sel )
		newPart.on_manualCreation()
		self.sendEvent( 'manualPartCreated', newPart )
	def on_selectionChange( self, *a ):
		sel = cmd.ls( sl=True )
		if not sel:
			self.UI_convert.disable()
		else:
			self.UI_convert.enable()


class BuilderLayout(MelScrollLayout):
	'''
	ui for skeleton part creation
	'''
	def __init__( self, parent ):
		MelScrollLayout.__init__( self, parent, childResizable=True )

		self.UI_col = MelColumnLayout( self, rowSpacing=4, adj=True )

		scaleForm = MelForm( self.UI_col )
		lbl = cmd.text( l='Skeleton Scale' )
		self.UI_scale = MelFloatField( scaleForm, v=rigPrimitives.SkeletonPart.PART_SCALE, w=75 )
		self.UI_guessScale = MelButton( scaleForm, l='Guess Scale', c=self.on_guess, w=120 )

		scaleForm( e=True,
		           af=((lbl, 'left', 10),
		               (lbl, 'top', 3)),
		           ac=((self.UI_scale, 'left', 4, lbl),
		               (self.UI_guessScale, 'left', 0, self.UI_scale)) )

		setParent( self.UI_col )
		cmd.separator( horizontal=True )
		cmd.text( l='Create Skeleton from Preset', align='left' )
		cmd.text( l='', height=5 )

		self.UI_list = []

		### BUILD THE PRESET CREATION BUTTONS ###
		presets = SkeletonPreset.GetSubclasses()
		for preset in presets:
			if preset.AVAILABLE_IN_UI:
				self.UI_list.append( SkeletonPresetLayout( self.UI_col, preset, self ) )

		setParent( self.UI_col )
		cmd.separator( horizontal=True )
		cmd.text( l='Build Individual Parts', align='left' )
		cmd.text( l='', height=5 )

		### BUILD THE PART CREATION BUTTONS ###
		parts = BaseSkeletonPart.GetSubclasses()
		for part in parts:
			if part.AVAILABLE_IN_UI:
				self.UI_list.append( SkeletonPartCreateLayout( self.UI_col, part, self ) )

		### BUILD UI FOR MANUAL PART CREATION ###
		MelSeparator( self.UI_col )
		MelLabel( self.UI_col, l='Manually Create Part From Existing Joints', align='left' )
		MelLabel( self.UI_col, l='', height=2 )
		ManualPartCreationLayout( self.UI_col )

		self.on_guess()
	def rePopulate( self ):
		for ui in self.UI_list:
			ui.rePopulate()
	def getScale( self ):
		return self.UI_scale.getValue()
	def on_guess( self, e=None ):
		scale = rigPrimitives.getDefaultScale()
		self.UI_scale.setValue( scale )


class CommonButtonsLayout(MelColumn):
	def __init__( self, parent ):
		MelColumn.__init__( self, parent, rowSpacing=4, adj=True )

		### SETUP PART DRIVING RELATIONSHIPS
		SeparatorLabelLayout( self, 'Part Connection Controls' )
		buttonForm = MelForm( self )
		a = MelButton( buttonForm, l='Drive Parts With First Selected Part', c=self.on_drive )
		b = MelButton( buttonForm, l='Break Driver For Selected Parts', c=self.on_breakDrive )

		buttonForm( e=True,
		            af=((a, 'left', 0),
		                (b, 'right', 0)),
		            ap=((a, 'right', 0, 50),
		                (b, 'left', 0, 50)) )


		### SETUP ALIGNMENT CONTROL BUTTONS
		SeparatorLabelLayout( self, 'Part Alignment' )
		buttonForm = MelForm( self )
		a = MelButton( buttonForm, l='Re-Align Selected Part', c=self.on_reAlign )
		b = MelButton( buttonForm, l='Re-Align ALL Parts', c=self.on_reAlignAll )
		c = MelButton( buttonForm, l='Finalize Alignment', c=self.on_finalize )

		buttonForm( e=True,
		            af=((a, 'left', 0),
		                (c, 'right', 0)),
		            ap=((a, 'right', 0, 33),
		                (b, 'left', 0, 33),
		                (b, 'right', 0, 67),
		                (c, 'left', 0, 67)) )


		### SETUP VISUALIZATION CONTROLS
		SeparatorLabelLayout( self, 'Visualization' )
		buttonForm = MelForm( self )
		a = MelButton( buttonForm, l='Visualization ON', c=self.on_visOn )
		b = MelButton( buttonForm, l='Visualization OFF', c=self.on_visOff )

		buttonForm( e=True,
		            af=((a, 'left', 0),
		                (b, 'right', 0)),
		            ap=((a, 'right', 0, 50),
		                (b, 'left', 0, 50)) )


		### SETUP SKINNING CONTROL BUTTONS
		SeparatorLabelLayout( self, 'Skinning Tools' )
		buttonForm = MelForm( self )
		a = self.UI_skinOff = MelButton( buttonForm, l='Turn Skinning Off', c=self.on_skinOff )
		b = self.UI_skinOn = MelButton( buttonForm, l='Turn Skinning On', c=self.on_skinOn )
		c = MelButton( buttonForm, l='Reset All Skin Clusters', c=self.on_resetSkin )
		self.updateSkinButtons()

		buttonForm( e=True,
		            af=((a, 'left', 0),
		                (c, 'right', 0)),
		            ap=((a, 'right', 0, 33),
		                (b, 'left', 0, 33),
		                (b, 'right', 0, 67),
		                (c, 'left', 0, 67)) )
	def updateSkinButtons( self ):
		state = rigUtils.getSkinClusterEnableState()
		self.UI_skinOn( e=True, en=not state )
		self.UI_skinOff( e=True, en=state )

	def on_drive( self, e=None ):
		selParts = rigPrimitives.getPartsFromObjects( cmd.ls( sl=True ) )
		if len( selParts ) <= 1:
			print 'WARNING :: please select two or more parts - the first part selected will drive consequent parts'
			return

		firstPart = selParts.pop( 0 )
		for p in selParts:
			firstPart.driveOtherPart( p )
	def on_breakDrive( self, e=None ):
		for p in rigPrimitives.getPartsFromObjects( cmd.ls( sl=True ) ):
			p.breakDriver()
	def on_reAlign( self, e=None ):
		rigPrimitives.realignSelectedParts()
	def on_reAlignAll( self, e=None ):
		rigPrimitives.realignAllParts()
	def on_finalize( self, e=None ):
		rigPrimitives.finalizeAllParts()
	def on_visOn( self, e=None ):
		for p in rigPrimitives.SkeletonPart.IterAllParts():
			p.visualize()
	def on_visOff( self, e=None ):
		for p in rigPrimitives.SkeletonPart.IterAllParts():
			p.unvisualize()
	def on_skinOff( self, e=None ):
		rigUtils.disableSkinClusters()
		self.updateSkinButtons()
	def on_skinOn( self, e=None ):
		rigUtils.enableSkinClusters()
		self.updateSkinButtons()
	@api.d_showWaitCursor
	def on_resetSkin( self, e=None ):
		for sc in ls( typ='skinCluster' ):
			rigUtils.resetSkinCluster( sc )


class SkeletonPartEditingLayout(MelForm):
	ARGS_TO_HIDE = [ 'parent', 'partScale', 'idx' ]

	def __new__( cls, parent, part ):
		return MelForm.__new__( cls, parent )
	def __init__( self, parent, part ):
		MelForm.__init__( self, parent )

		self.part = part
		self.argUIs = {}

		self.populate()
	def clear( self ):
		MelForm.clear( self )
		self.argUIs = {}
	def populate( self ):
		#remove any existing children
		self.clear()
		part = self.part
		assert isinstance( part, BaseSkeletonPart )

		#pimp out the UI
		lbl = MelButton( self, l=part.getPartName(), w=140, c=self.on_select )

		#grab the args the rigging method takes
		argsForm = MelForm( self )
		argsUIs = []

		buildKwargs = part.getBuildKwargs()
		for arg in self.ARGS_TO_HIDE:
			buildKwargs.pop( arg, None )

		for arg, argValue in buildKwargs.iteritems():
			argLbl = MelLabel( argsForm, label=names.camelCaseToNice( arg ) )

			#determine the function to use for building the UI for the arg
			buildMethodFromName = UI_FOR_NAMED_RIG_ARGS.get( arg, None )
			buildMethodFromType = baseMelUI.UI_FOR_PY_TYPES.get( type( argValue ), baseMelUI.MelTextField )

			buildMethod = buildMethodFromName or buildMethodFromType

			argWidget = buildMethod( argsForm )
			argWidget.setValue( argValue )

			argsUIs.append( argLbl )
			argsUIs.append( argWidget )
			self.argUIs[ arg ] = argWidget

		try:
			inc = 1.0 / len( argsUIs )
		except ZeroDivisionError: inc = 1.0

		for n, ui in enumerate( argsUIs ):
			p = n*inc
			if n:
				argsForm( e=True, ac=((ui, 'left', 5, argsUIs[ n-1 ])) )
			else:
				argsForm( e=True, af=((ui, 'left', 0)) )

		#finally build the "rebuild" button
		reButt = MelButton( self, l="rebuild", c=self.on_rebuild, w=100 )

		#perform layout...
		self.setWidth( 50 )
		argsForm.setWidth( 50 )

		self( e=True,
		      af=((lbl, 'left', 0),
		          (reButt, 'right', 0)),
		      ac=((argsForm, 'left', 5, lbl),
		          (argsForm, 'right', 0, reButt)) )
	def getBuildKwargs( self ):
		kwargs = {}
		for argName, widget in self.argUIs.iteritems():
			kwargs[ argName ] = widget.getValue()

		return kwargs
	def on_rebuild( self, e ):
		self.part.rebuild( **self.getBuildKwargs() )
		self.populate()
	def on_select( self, e=None ):
		cmd.select( self.part.base )


class EditingLayout(MelScrollLayout):
	def __init__( self, parent ):
		MelScrollLayout.__init__( self, parent, childResizable=True )
	def populate( self ):
		self.clear()

		col = MelColumn( self, rowSpacing=4, adj=True )
		self.UI_partForms = []
		for part in SkeletonPart.IterAllPartsInOrder():
			partRigForm = SkeletonPartEditingLayout( col, part )
			self.UI_partForms.append( partRigForm )


class SkeletonPartRiggingLayout(MelForm):
	'''
	ui for single rig primitive
	'''

	def __new__( cls, parent, part ):
		return MelForm.__new__( cls, parent )
	def __init__( self, parent, part ):
		MelForm.__init__( self, parent )

		self.part = part
		self.argUIs = {}

		lbl = MelButton( self, l=part.getPartName(), w=140, c=self.on_select )

		rigKwargs = part.getRigKwargs()

		#build the disable and optionbox for the rig method
		disableState = rigKwargs.get( 'disable', False )
		disable = self.UI_disable = MelCheckBox( self, l='disable' )
		rigTypes = self.rigTypes = [ rigType for rigType in part.RigTypes if rigType.CanRigThisPart( part ) ]

		if len( rigTypes ) > 1:
			opts = MelOptionMenu( self, cc=self.on_rigMethodCB )
			opts.enable( not disableState )
			for method in rigTypes:
				opts.append( method.__name__ )

			rigMethodName = rigKwargs.get( 'rigMethodName', rigTypes[ 0 ].__name__ )
			opts.selectByValue( rigMethodName, False )
			opts.getValue()
		else:
			opts = MelLabel( self, l='' )

		self.UI_options = opts
		argsForm = self.UI_argsForm = MelHRowLayout( self )
		self.UI_manualRig = manRig = MelButton( self, l='Build Rig Now', w=100, c=self.on_manualRig )

		#perform layout...
		self( e=True,
	          af=((lbl, 'left', 0),
	              (manRig, 'right', 0)),
	          ac=((disable, 'left', 3, lbl),
		          (opts, 'left', 0, disable),
	              (argsForm, 'left', 0, opts),
		          (argsForm, 'right', 0, manRig)) )

		#set initial UI state
		disable.setChangeCB( self.on_argCB )
		disable.setValue( disableState, False )

		self.populate()
	def clearArgs( self ):
		self.UI_argsForm.clear()
		self.argUIs = {}
	def populate( self ):
		if not bool( self.rigTypes ):
			self.setVisibility( False )
			return

		#remove any existing children
		self.clearArgs()
		part = self.part

		rigKwargs = part.getRigKwargs()

		#build the disable and optionbox for the rig method
		disableState = rigKwargs.get( 'disable', False )

		#grab the args the rigging method takes
		argsForm = self.UI_argsForm
		argsUIs = []

		rigMethodName = rigKwargs.get( 'rigMethodName', self.rigTypes[ 0 ].__name__ )
		rigClass = rigPrimitives.RigPart.GetNamedSubclass( rigMethodName )

		if rigClass is None:
			rigClass = part.RigTypes[ 0 ]

		zeroWeightTypes = MelCheckBox, MelOptionMenu

		argNamesAndDefaults = rigClass.GetDefaultBuildKwargs()
		for arg, default in argNamesAndDefaults:
			argValue = rigKwargs.get( arg, default )
			argLbl = MelLabel( argsForm, label=names.camelCaseToNice( arg ) )

			#determine the function to use for building the UI for the arg
			buildMethodFromName = UI_FOR_NAMED_RIG_ARGS.get( arg, None )
			buildMethodFromType = baseMelUI.UI_FOR_PY_TYPES.get( type( default ), baseMelUI.MelTextField )

			buildMethod = buildMethodFromName or buildMethodFromType

			argWidget = buildMethod( argsForm )
			argWidget.setValue( argValue, False )
			argWidget.setChangeCB( self.on_argCB )

			argLbl.enable( not disableState )
			argWidget.enable( not disableState )

			argsUIs.append( argLbl )
			argsUIs.append( argWidget )
			self.argUIs[ arg ] = argWidget

		#if there are no args - create an empty text widget otherwise maya will crash.  yay!
		argsUIs.append( MelLabel( argsForm, label='' ) )

		argsForm.layout()
	def getRigKwargs( self ):
		disableState = self.UI_disable.getValue()
		kwargs = { 'disable': disableState, }
		if isinstance( self.UI_options, MelOptionMenu ):
			rigMethod = self.UI_options.getValue()
			if rigMethod:
				kwargs[ 'rigMethodName' ] = rigMethod

		for argName, widget in self.argUIs.iteritems():
			kwargs[ argName ] = widget.getValue()

		self.UI_options.enable( not disableState )
		for child in self.UI_argsForm.getChildren():
			child.enable( not disableState )

		return kwargs
	def on_rigMethodCB( self, e ):
		#set the rig kwargs based on the current UI - it may be wrong however, because the new rig method may have different calling args
		self.part.setRigKwargs( self.getRigKwargs() )

		#rebuild the UI to reflect the possibly new options for the changed rig method
		self.populate()

		#now store the rig kwargs again based on the correct UI
		self.part.setRigKwargs( self.getRigKwargs() )
	def on_argCB( self, e=None ):
		self.part.setRigKwargs( self.getRigKwargs() )
	def on_select( self, e=None ):
		cmd.select( self.part.base )
	def on_manualRig( self, e=None ):
		rigPrimitives.finalizeAllParts()
		self.part.rig()


class RiggingLayout(MelForm):
	'''
	ui for rig primitive creation
	'''
	def __init__( self, parent ):
		MelForm.__init__( self, parent )

		scroll = MelScrollLayout( self, cr=True )
		self.UI_parts = MelColumn( scroll, rowSpacing=4, adj=True )
		self.UI_buttons = MelColumn( self, rowSpacing=4, adj=True )


		### BUILD STATIC BUTTONS
		buttonParent = self.UI_buttons
		setParent( buttonParent )
		optsLbl = MelLabel( buttonParent, label='Rig Build Options', align='left' )
		#optsLbl.bold( True )

		buildRigForm = MelForm( buttonParent )
		self.UI_reference = MelCheckBox( buildRigForm, label='reference model' )
		self.UI_reference.setValue( True )

		buildRigForm( e=True,
		              af=((self.UI_reference, 'left', 0)),
		              ap=((self.UI_reference, 'right', 0, 50)) )

		setParent( buttonParent )
		sep = cmd.separator( horizontal=True )
		but = MelButton( buttonParent, l='BUILD RIG', c=self.on_buildRig, height=35 )


		self( e=True,
		      af=((scroll, 'top', 0),
		          (scroll, 'left', 0),
		          (scroll, 'right', 0),
		          (self.UI_buttons, 'left', 0),
		          (self.UI_buttons, 'right', 0),
		          (self.UI_buttons, 'bottom', 0)),
		      ac=((scroll, 'bottom', 3, self.UI_buttons)) )
	def populate( self ):
		self.UI_parts.clear()

		col = self.UI_parts

		self.UI_partForms = []
		for part in SkeletonPart.IterAllPartsInOrder():
			partRigForm = SkeletonPartRiggingLayout( col, part )
			self.UI_partForms.append( partRigForm )
	def on_buildRig( self, e=None ):
		autoFinalize = True
		curScene = Path( cmd.file( q=True, sn=True ) )

		referenceModel = self.UI_reference.getValue()
		if referenceModel:
			if not curScene:
				api.doConfirm( t='Scene not saved!', m="Looks like your current scene isn't saved\n\nPlease save it first so I know where to save the rig.  thanks!", b=('OK',), db='OK' )
				return

		prefix = rigPrimitives.helpers.stripKnownAssetSuffixes( curScene.name() )

		ret, prefix = api.doPrompt( t='enter name', m='enter the name of the character', tx=prefix, b=('OK', 'Cancel'), db='OK' )
		if ret == 'OK':
			if not prefix:
				raise rigPrimitives.SkeletonError( "Please enter a valid prefix for the character!" )

			rigPrimitives.buildRigForModel( None, autoFinalize, referenceModel )


class SkeletonTabLayout(MelTabLayout):
	def __init__( self, parent, *a, **kw ):
		MelTabLayout.__init__( self, parent, *a, **kw )

		### THE SKELETON CREATION TAB
		insetForm = self.SZ_skelForm = MelForm( self )
		self.UI_builder = ed = BuilderLayout( insetForm )
		self.UI_commonButtons = bts = CommonButtonsLayout( insetForm )

		insetForm( e=True,
		           af=((ed, 'top', 7),
		               (ed, 'left', 5),
		               (ed, 'right', 5),
		               (bts, 'left', 5),
		               (bts, 'right', 5),
		               (bts, 'bottom', 5)),
		           ac=((ed, 'bottom', 5, bts)) )


		### THE EDITING FORM
		insetForm = self.SZ_editForm = MelForm( self )
		self.UI_editor = ed = EditingLayout( insetForm )
		self.UI_commonButtons = bts = CommonButtonsLayout( insetForm )

		insetForm( e=True,
		           af=((ed, 'top', 7),
		               (ed, 'left', 5),
		               (ed, 'right', 5),
		               (bts, 'left', 5),
		               (bts, 'right', 5),
		               (bts, 'bottom', 5)),
		           ac=((ed, 'bottom', 5, bts)) )


		### THE RIGGING TAB
		insetForm = self.SZ_rigForm = MelForm( self )
		self.UI_rigger = ed = RiggingLayout( insetForm )

		insetForm( e=True,
		           af=((ed, 'top', 7),
		               (ed, 'left', 5),
		               (ed, 'right', 5),
		               (ed, 'bottom', 5)) )


		self.setLabel( 0, 'create skeleton' )
		self.setLabel( 1, 'edit skeleton' )
		self.setLabel( 2, 'create rig' )

		self.setSceneChangeCB( self.on_sceneOpen )

	### EVENT HANDLERS ###
	def on_change( self ):
		if self.getSelectedTab() == self.SZ_editForm:
			self.UI_editor.populate()
		elif self.getSelectedTab() == self.SZ_rigForm:
			self.UI_rigger.populate()
	def on_sceneOpen( self, *a ):
		self.setSelectedTabIdx( 0 )


class SkeletonBuilderWindow(BaseMelWindow):
	WINDOW_NAME = 'skeletonBuilder'
	WINDOW_TITLE = 'Skeleton Builder'

	DEFAULT_SIZE = 700, 700
	DEFAULT_MENU = 'Tools'

	HELP_MENU = rigPrimitives.TOOL_NAME, rigPrimitives.__author__, None

	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		filesystem.reportUsageToAuthor( rigPrimitives.__author__ )
		self.editor = SkeletonTabLayout( self )

		tMenu = self.getMenu( 'Tools' )
		cmd.menu( tMenu, e=True, pmc=self.buildToolsMenu )

		#close related windows...
		RigBuilderWindow.Close()
		ControlBuildingWindow.Close()

		self.show()
	def buildToolsMenu( self,  *a ):
		menu = self.getMenu( 'Tools' )
		menu.clear()

		enableState = rigUtils.getSkinClusterEnableState()

		MelMenuItem( menu, l='Enable Skin Clusters', cb=enableState, c=self.on_enable )
		MelMenuItem( menu, l='Disable Skin Clusters', cb=not enableState, c=self.on_disable )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='Reset Skin Clusters', c=self.on_resetSkins )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='Space Switching Tool', c=lambda *a: spaceSwitchingUI.SpaceSwitchingWindow() )
		MelMenuItem( menu, l='Stand Alone Rig Builder Tool', c=lambda *a: RigBuilderWindow() )
		MelMenuItem( menu, l='Control Creation Tool', c=lambda *a: ControlBuildingWindow() )

		def debugToggle( val ):
			rigPrim_base._PART_DEBUG_MODE = val

		MelMenuItem( menu, l='DEBUG MODE', cb=rigPrim_base._PART_DEBUG_MODE, c=debugToggle )
	def on_resetSkins( self, e=None ):
		for sc in cmd.ls( typ='skinCluster' ):
			rigUtils.resetSkinCluster( sc )
	def on_enable( self, e=None ):
		rigUtils.enableSkinClusters()
	def on_disable( self, e=None ):
		rigUtils.disableSkinClusters()

SkeletonBuilderUI = SkeletonBuilderWindow


def load():
	global ui
	ui = SkeletonBuilderWindow()


##############################
### STANDALONE RIG BUILDER ###
##############################


class RigBuilderLayout(MelVSingleStretchLayout):
	def __init__( self, parent, *a, **kw ):
		MelVSingleStretchLayout.__init__( self, parent, *a, **kw )

		MelLabel( self, l="""Select the part's joints in hierarchical order, choose the part type, and hit the convert button.""" )
		ManualPartCreationLayout( self )
		scroll = MelScrollLayout( self )

		self.UI_remove = MelButton( self, l='Remove Skeleton Builder Markup From Selection', c=self.on_remove )

		self.setStretchWidget( scroll )
		self.layout()

		self.UI_partLayouts = []
		self.SZ_partLayout = col = MelColumnLayout( scroll, rowSpacing=3 )
		self.populate()

		self.setSelectionChangeCB( self.on_select )
		self.setSceneChangeCB( self.on_scene )
	def populate( self ):
		self.SZ_partLayout.clear()
		for part in SkeletonPart.IterAllPartsInOrder():
			self.appendNewPart( part )
	def appendNewPart( self, newPart ):
		partLayout = SkeletonPartRiggingLayout( self.SZ_partLayout, newPart )
		self.UI_partLayouts.append( partLayout )
	def manualPartCreated( self, newPart ):
		self.appendNewPart( newPart )
		self.sendEvent( 'layout' )

	### EVENT HANDLERS ###
	def on_remove( self, *a ):
		for item in cmd.ls( sl=True ):
			for attrName in listAttr( item, ud=True ):
				if attrName.startswith( '_skeletonPart' ) or attrName.startswith( '_skeletonFinalize' ):
					cmd.deleteAttr( '%s.%s' % (item, attrName) )

		self.populate()
	def on_select( self, *a ):
		sel = cmd.ls( sl=True )
		if sel:
			self.UI_remove.enable()
		else:
			self.UI_remove.disable()
	def on_scene( self, *a ):
		self.populate()


class RigBuilderWindow(BaseMelWindow):
	WINDOW_NAME = 'rigBuilderTool'
	WINDOW_TITLE = 'Manual Rig Builder Tool'

	DEFAULT_SIZE = 475, 300
	DEFAULT_MENU = None

	def __init__( self ):
		BaseMelWindow.__init__( self )
		padding = MelSingleLayout( self, 5 )
		RigBuilderLayout( padding )
		padding.layout()
		self.show()



###############################
### CONTROL BUILDING WINDOW ###
###############################


class ControlBuildingLayout(MelForm):
	def __init__( self, parent, *a, **kw ):
		width = 60
		self.UI_place = UI_place = MelObjectSelector( self, label='place at->', labelWidth=width )
		self.UI_parent = UI_parent = MelObjectSelector( self, label='parent to->', labelWidth=width )
		self.UI_align = UI_align = MelObjectSelector( self, label='align to->', labelWidth=width )
		self.UI_pivot = UI_pivot = MelObjectSelector( self, label='pivot to->', labelWidth=width )

		self.UI_build = UI_build = MelButton( self, l='build control', c=self.on_build )

		self( e=True,
		      af=(
		          (UI_place, 'left', 0),
		          (UI_parent, 'right', 0),
		          (UI_align, 'left', 0),
		          (UI_pivot, 'right', 0),
		          (UI_build, 'left', 0),
		          (UI_build, 'right', 0),
		          (UI_build, 'bottom', 0),
		          ),
		      ac=(
		          (UI_align, 'top', 0, UI_place),
		          (UI_pivot, 'top', 0, UI_place),
		          ),
		      ap=(
		          (UI_place, 'right', 0, 50),
		          (UI_parent, 'left', 0, 50),
		          (UI_align, 'right', 0, 50),
		          (UI_pivot, 'left', 0, 50),
		          )
		      )
	def on_build( self, *a ):
		place = self.UI_place.getValue()
		parent = self.UI_parent.getValue()
		align = self.UI_align.getValue()
		pivot = self.UI_pivot.getValue()

		args = []
		if place:
			args.append( place )

		if align:
			args.append( align )

		if pivot:
			args.append( pivot )

		control.buildControl( '%sControl' % place, control.PlaceDesc( *args ) )


class ControlBuildingWindow(BaseMelWindow):
	WINDOW_NAME = 'controlBuildingWindow'
	WINDOW_TITLE = 'Control Builder'

	DEFAULT_SIZE = 400, 350
	DEFAULT_MENU = 'Help'
	DEFAULT_MENU_IS_HELP = True

	HELP_MENU = rigPrimitives.TOOL_NAME, rigPrimitives.__author__, None

	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		self.editor = ControlBuildingLayout( self )
		self.show()


#end
