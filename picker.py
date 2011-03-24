
from maya.cmds import *
from baseMelUI import *
from vectors import Vector, Colour
from common import printErrorStr

TOOL_NAME = 'zooPicker'
VERSION = 0

MODIFIERS = SHIFT, CAPS, CTRL, ALT = 2**0, 2**1, 2**2, 2**3


def test( dragControl, dropControl, messages, x, y, dragType ):
	print 'dropped!'


def getTopPickerSet():
	existing = [ node for node in ls( type='objectSet', r=True ) or [] if sets( node, q=True, text=True ) == TOOL_NAME ]

	if existing:
		return existing[ 0 ]
	else:
		pickerNode = createNode( 'objectSet', n='picker' )
		sets( pickerNode, e=True, text=TOOL_NAME )

		return pickerNode


class Button(object):
	'''
	A Button instance is a "container" for a selection preset
	'''

	SELECTION_STATES = NONE, PARTIAL, COMPLETE = range( 3 )
	DEFAULT_COLOUR = Colour( 'blue' ).asRGB()
	COLOUR_PARTIAL, COLOUR_COMPLETE = (1, 0.6, 0.5), Colour( 'white' ).asRGB()

	@classmethod
	def Create( cls, character, pos, size=(18, 18), colour=DEFAULT_COLOUR, label=None, objs=(), cmdStr=None, cmdIsPython=False ):
		node = sets( em=True, text='zooPickerButton' )
		node = rename( node, 'pickerButton' )

		sets( node, e=True, add=character.getNode() )

		addAttr( node, ln='posSize', dt='string' )  #stuff pos and size into a single str attr - so lazy...
		addAttr( node, ln='colour', dt='string' )
		addAttr( node, ln='label', dt='string' )
		addAttr( node, ln='cmdStr', dt='string' )
		addAttr( node, ln='cmdIsPython', at='bool' )

		self = cls( node )
		self.setPosSize( pos, size )
		self.setColour( colour )
		self.setLabel( label )
		self.setObjs( objs )
		self.setCmdStr( cmdStr )
		self.setCmdIsPython( cmdIsPython )

		return self

	def __init__( self, node ):
		self._node = node
		self._character = character
	def __eq__( self, other ):
		'''
		two buttons are equal on if all their attributes are the same
		'''
		return self.getCharacter() == other.getCharacter() and \
		       self.getPos() == other.getPos() and \
		       self.getSize() == other.getSize() and \
		       self.getColour() == other.getColour() and \
		       self.getLabel() == other.getLabel() and \
		       self.getObjs() == other.getObjs() and \
		       self.getCmdStr() == other.getCmdStr() and \
		       self.getCmdIsPython() == other.getCmdIsPython()
	def __ne__( self, other ):
		return not self.__eq__( other )
	def getNode( self ):
		return self._node
	def getCharacter( self ): return self._character
	def getPosSize( self ):
		valStr = getAttr( '%s.posSize' % self.getNode() )
		posStr, sizeStr = valStr.split( ';' )

		pos = Vector( [ int( p ) for p in posStr.split( ',' ) ] )
		size = Vector( [ int( p ) for p in sizeStr.split( ',' ) ] )

		return pos, size
	def getPos( self ): return self.getPosSize()[0]
	def getSize( self ): return self.getPosSize()[1]
	def getColour( self ):
		rgb = getAttr( '%s.colour' % self.getNode() ).split( ',' )
		rgb = map( float, rgb )

		return Colour( rgb )
	def getLabel( self ):
		return getAttr( '%s.label' % self.getNode() )
	def getNiceLabel( self ):
		labelStr = self.getLabel()

		#if there is no label AND the button has objects, communicate this to the user
		if not labelStr:
			if len( self.getObjs() ) > 1:
				return '+'

		return labelStr
	def getObjs( self ):
		return sets( self.getNode(), q=True )
	def getCmdStr( self ): return getAttr( '%s.cmdStr' % self.getNode() )
	def getCmdIsPython( self ): return getAttr( '%s.cmdIsPython' % self.getNode() )
	def setPosSize( self, pos, size ):
		posStr = ','.join( map( str, pos ) )
		sizeStr = ','.join( map( str, size ) )

		valStr = setAttr( '%s.posSize' % self.getNode(), '%s;%s' % (posStr, sizeStr), type='string' )
	def setPos( self, val ):
		if not isinstance( val, Vector ):
			val = Vector( val )

		p, s = self.getPosSize()
		self.setPosSize( val, s )
	def setSize( self, val ):
		if not isinstance( val, Vector ):
			val = Vector( val )

		p, s = self.getPosSize()
		self.setPosSize( p, val )
	def setColour( self, val ):
		if val is None:
			val = self.DEFAULT_COLOUR

		valStr = ','.join( map( str, val ) )
		setAttr( '%s.colour' % self.getNode(), valStr, type='string' )
	def setLabel( self, val ):
		if val is None:
			val = ''

		setAttr( '%s.label' % self.getNode(), val, type='string' )
	def setObjs( self, val ):
		if isinstance( val, basestring ):
			val = [ val ]

		sets( e=True, clear=self.getNode() )
		sets( val, e=True, add=self.getNode() )
	def setCmdStr( self, val ):
		if val is None:
			val = ''

		setAttr( '%s.cmdStr' % self.getNode(), val, type='string' )
	def setCmdIsPython( self, val ):
		setAttr( '%s.cmdIsPython' % self.getNode(), val )
	def select( self ):
		'''
		deals with selecting the button
		'''
		objs = self.getObjs()
		mods = getModifiers()

		if mods & (SHIFT | CTRL):
			select( objs, add=True )
		if mods & SHIFT:
			select( objs, toggle=True )
		elif mods & CTRL:
			select( objs, deselect=True )
		else:
			select( objs )
	def selectedState( self ):
		'''
		returns whether this button is partially or fully selected - return values are one of the
		values in self.SELECTION_STATES
		'''
		objs = self.getObjs()
		sel = ls( objs, sl=True )

		if not sel:
			return self.NONE
		elif len( objs ) == len( sel ):
			return self.COMPLETE

		return self.PARTIAL
	def executeCmd( self ):
		'''
		executes the command string for this button
		'''
		cmdStr = self.getCmdStr()
		if cmdStr:
			try:
				if self.getCmdIsPython():
					return eval( cmdStr )
				else:
					return maya.mel.eval( cmdStr )
			except:
				printErrorStr( 'Executing command "%s" on button "%s"' % (cmdStr, self.getNode()) )

		#if there is no cmdStr then just select the nodes in this button set
		else:
			mods = getModifiers()
			objs = self.getObjs()
			if objs:
				if mods & CTRL & SHIFT:
					select( objs, add=True )
				elif mods & SHIFT:
					select( objs, toggle=True )
				elif mods & CTRL:
					select( objs, deselect=True )
				else:
					select( objs )


class Character(object):
	'''
	A Character is made up of many Button instances to select the controls or groups of controls that
	comprise a puppet rig
	'''

	@classmethod
	def IterAll( cls ):
		for node in ls( type='objectSet' ):
			if sets( node, q=True, text=True ) == 'zooPickerCharacter':
				yield cls( node )
	@classmethod
	def Create( cls, name ):
		'''
		creates a new character for the picker tool
		'''
		node = sets( em=True, text='zooPickerCharacter' )
		node = rename( node, name )

		sets( node, e=True, add=getTopPickerSet() )

		addAttr( node, ln='version', at='long' )
		addAttr( node, ln='name', dt='string' )
		addAttr( node, ln='bgImage', dt='string' )
		addAttr( node, ln='bgColour', dt='string' )

		setAttr( '%s.version' % node, VERSION )
		setAttr( '%s.name' % node, name, type='string' )
		setAttr( '%s.bgImage' % node, 'pickerGrid.bmp', type='string' )
		setAttr( '%s.bgColour' % node, '0,0,0', type='string' )

		return cls( node )

	def __init__( self, node ):
		self._node = node
	def __eq__( self, other ):
		return self._node == other._node
	def __ne__( self, other ):
		return not self.__eq__( other )
	def getNode( self ):
		return self._node
	def getButtons( self ):
		buttonNodes = sets( self.getNode(), q=True )

		return [ Button( node ) for node in buttonNodes ]
	def getName( self ):
		return getAttr( '%s.name' % self.getNode() )
	def getBgImage( self ):
		return getAttr( '%s.bgImage' % self.getNode() )
	def getBgColour( self ):
		colStr = getAttr( '%s.bgColour' % self.getNode() )

		return Colour( [ float( c ) for c in colStr.split( ',' ) ] )
	def setName( self, val ):
		setAttr( '%s.name' % self.getNode(), str( val ), type='string' )
	def setBgImage( self, val ):
		setAttr( '%s.bgImage' % self.getNode(), val, type='string' )
	def setBgColour( self, val ):
		valStr = ','.join( val )
		setAttr( '%s.bgColour' % self.getNode(), valStr, type='string' )
	def createButton( self, pos, size, colour=None, label=None, objs=(), cmdStr=None, cmdIsPython=False ):
		'''
		appends a new button to the character - a new Button instance is returned
		'''
		return Button.Create( self, pos, size, colour, label, objs, cmdStr, cmdIsPython )
	def removeButton( self, button ):
		'''
		given a Button instance, will remove it from the character
		'''
		for aButton in self.getButtons():
			if button == aButton:
				sets( button.getNode(), e=True, remove=self.getNode() )
				return


def _drag( *a ):
	'''
	passes the local coords the widget is being dragged from
	'''
	return [a[-3], a[-2]]


def _drop( src, tgt, msgs, x, y, mods ):
	srcX, srcY = map( int, msgs )
	x -= srcX
	y -= srcY
	src = BaseMelUI.FromStr( src )
	tgt = BaseMelUI.FromStr( tgt )
	if isinstance( src, ButtonUI ) and isinstance( tgt, DragDroppableFormLayout ):
		src.button.setPos( (x, y) )
		src.updateGeometry()


class ButtonUI(MelIconButton):
	def __init__( self, parent, button ):
		MelIconButton.__init__( self, parent )

		assert isinstance( button, Button )
		self.button = button

		self( e=True, dgc=_drag, dpc=_drop, style='textOnly', c=self.on_press )
		self.POP_menu = MelPopupMenu( self, b=2, pmc=self.buildMenu )

		self.update()
	def buildMenu( self ):
		self.POP_menu.clear()
		MelMenuItem( self.POP_menu, l='apples' )
	def updateHighlightState( self ):
		selectedState = self.button.selectedState()
		if selectedState == Button.PARTIAL:
			self.setColour( Button.COLOUR_PARTIAL )
		elif selectedState == Button.COMPLETE:
			self.setColour( Button.COLOUR_COMPLETE )
		else:
			self.setColour( self.button.getColour() )
	def update( self ):
		self.updateGeometry()
		self.updateAppearance()
	def updateGeometry( self ):
		pos, size = self.button.getPosSize()
		x, y = pos

		#clamp the pos to the size of the parent
		parent = self.getParent()
		maxX, maxY = parent.getSize()
		#x = min( max( x, 0 ), maxX )  #NOTE: this is commented out because it seems maya reports the size of the parent to be 0, 0 until there are children...
		#y = min( max( y, 0 ), maxY )

		parent( e=True, ap=((self, 'top', y, 0), (self, 'left', x, 0)) )

		self.setSize( size )
		self.sendEvent( 'refreshImage' )
	def updateAppearance( self ):
		self.setLabel( self.button.getNiceLabel() )

	### EVENT HANDLERS ###
	def on_press( self, *a ):
		self.button.executeCmd()
		self.sendEvent( 'buttonSelected', self )


class MelPicture(BaseMelWidget):
	WIDGET_CMD = picture

	def getImage( self ):
		return self( q=True, i=True )
	def setImage( self, image ):
		self( e=True, i=image )


class DragDroppableFormLayout(MelFormLayout):
	def __init__( self, parent, **kw ):
		MelFormLayout.__init__( self, parent, **kw )
		self( e=True, dgc=_drag, dpc=_drop )


class CharacterUI(MelHLayout):
	def __init__( self, parent, character ):
		self.character = character
		self.currentSelection = None

		self.UI_picker = MelPicture( self, en=False, dgc=_drag, dpc=_drop )
		self.UI_picker.setImage( character.getBgImage() )
		self.layout()

		self.UI_buttonLayout = UI_buttonLayout = DragDroppableFormLayout( self )
		self( e=True, af=((UI_buttonLayout, 'top', 0), (UI_buttonLayout, 'left', 0), (UI_buttonLayout, 'right', 0), (UI_buttonLayout, 'bottom', 0)) )

		self.populate()
		self.highlightButtons()
	def populate( self ):
		self.buttonUIs = []
		for button in self.character.getButtons():
			ui = ButtonUI( self.UI_buttonLayout, button )
			self.buttonUIs.append( ui )
	def highlightButtons( self ):
		for buttonUI in self.buttonUIs:
			buttonUI.updateHighlightState()
	def refreshImage( self ):
		self.UI_picker.setVisibility( False )
		self.UI_picker.setVisibility( True )
	def buttonSelected( self, button ):
		self.currentSelection = button
		self.sendEvent( 'updateEditor' )


class PickerLayout(MelVSingleStretchLayout):
	def __init__( self, parent ):
		self.characterUIs = []

		self.UI_tabs = tabs = MelTabLayout( self )
		self.UI_tabs.setChangeCB( self.on_tabChange )
		self.UI_editor = UI_editor = MelFrameLayout( self, l='Edit Current Picker', cll=True, cl=True )

		lblWidth = 50
		self.SZ_editor = SZ_editor = MelVSingleStretchLayout( self.UI_editor )
		self.UI_selectedLabel = LabelledTextField( SZ_editor, llabel='label:', llabelWidth=lblWidth )
		self.UI_selectedColour = LabelledTextField( SZ_editor, llabel='colour:', llabelWidth=lblWidth )

		SZ_lblPos = MelHSingleStretchLayout( SZ_editor )
		lbl = MelLabel( SZ_lblPos, l='pos x, y:', w=lblWidth )
		SZ_pos = MelHLayout( SZ_lblPos )
		SZ_lblPos.setStretchWidget( SZ_pos )
		SZ_lblPos.layout()

		self.UI_selectedPosX = MelIntField( SZ_pos )
		self.UI_selectedPosX = MelIntField( SZ_pos )
		SZ_pos.layout()

		self.UI_selectedObjects = MelSetMemebershipList( SZ_editor, h=150 )
		SZ_editor.setStretchWidget( self.UI_selectedObjects )
		SZ_editor.layout()

		self.setStretchWidget( tabs )
		self.layout()

		self.populate()

		#make sure the UI gets updated when the scene changes
		self.setSceneChangeCB( self.on_sceneChange )

		#update button state when the selection changes
		self.setSelectionChangeCB( self.on_selectionChange )
	def populate( self ):
		self.characterUIs = []
		self.UI_tabs.clear()
		for idx, character in enumerate( Character.IterAll() ):
			ui = CharacterUI( self.UI_tabs, character )
			self.characterUIs.append( ui )
			self.UI_tabs.setLabel( idx, character.getName() )
	def selectCharacter( self, character ):
		for idx, ui in enumerate( self.characterUIs ):
			if ui.character == character:
				self.UI_tabs.setSelectedTabIdx( idx )
	def updateEditor( self ):
		currentCharacter = CharacterUI.FromStr( self.UI_tabs.getSelectedTab() )
		if currentCharacter:
			selectedButton = currentCharacter.currentSelection
			if selectedButton:
				button = selectedButton.button
				self.UI_selectedLabel.setValue( button.getLabel() )
				self.UI_selectedObjects.setSets( [button.getNode()] )

	### EVENT HANDLERS ###
	def on_tabChange( self, *a ):
		self.on_selectionChange()
	def on_sceneChange( self, *a ):
		self.populate()
	def on_selectionChange( self, *a ):
		idx = self.UI_tabs.getSelectedTabIdx()
		ui = self.characterUIs[ idx ]
		ui.highlightButtons()


class PickerWindow(BaseMelWindow):
	WINDOW_NAME = 'zooPicker'
	WINDOW_TITLE = 'Picker Tool'

	DEFAULT_SIZE = 275, 525
	DEFAULT_MENU = 'Help'
	DEFAULT_MENU_IS_HELP = True

	FORCE_DEFAULT_SIZE = True

	HELP_MENU = 'hamish@valvesoftware.com', TOOL_NAME, None

	def __init__( self ):
		self.show()
		self.UI_editor = PickerLayout( self )


#end
