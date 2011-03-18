
from maya.cmds import *
from baseMelUI import *
from vectors import Vector, Colour
from common import printErrorStr

TOOL_NAME = 'zooPicker'
VERSION = 0

DEFAULT_COLOUR = 'blue'
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
	IMG_PARTIAL, IMG_COMPLETE = 'pickerPartialSelect.bmp', 'pickerFullSelect.bmp'

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
	def getColour( self ): return getAttr( '%s.colour' % self.getNode() )
	def getImage( self ):
		return '%s.bmp' % self.getColour()
	def getLabel( self ):
		labelStr = getAttr( '%s.label' % self.getNode() )

		#if there is no label AND the button has objects, communicate this to the user
		if not labelStr:
			if self.getObjs():
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
			val = DEFAULT_COLOUR

		setAttr( '%s.colour' % self.getNode(), val, type='string' )
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
		if self.cmdStr:
			try:
				if self.cmdIsPython:
					return eval( self.cmdStr )
				else:
					return maya.mel.eval( self.getCmdStr() )
			except:
				printErrorStr( 'Executing command "%s" on %s button at %s' % (self.cmdStr, self.colour, self.pos) )


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


class ButtonUI(unicode):
	_DRAG_MEL_CMD_STR = r"""global proc string[] buttonDrag( string $drag, int $x, int $y, int $mods ) {
	print ("draggage (" + $drag + ") from position " + $x + ", " + $y);
	python( "import baseMelUI; ui = baseMelUI.BaseMelWidget.FromStr( '"+ $drag +"' ); print ui.on_drag; ui.on_drag( '"+ $drag +"', "+ $x +", "+ $y +", "+ $mods +" );" );
	string $messages[] = {};
	return $messages;
	}"""

	_DROP_MEL_CMD_STR = r"""global proc buttonDrop( string $drag, string $drop, string $msgs[], int $x, int $y, int $mods ) {
	print ("dropperized (" + $drag + ") onto (" + $drop + ")\n");
	print ("at position " + $x + ", " + $y + "\n");
	python( "import baseMelUI; ui = baseMelUI.BaseMelWidget.FromStr( '"+ $drag +"' ); print ui.on_drop; ui.on_drop( '"+ $drag +"', '"+ $drop +"', "+ $x +", "+ $y +", "+ $mods +" );" );
	}"""

	maya.mel.eval( _DRAG_MEL_CMD_STR )
	maya.mel.eval( _DROP_MEL_CMD_STR )
	del( _DRAG_MEL_CMD_STR )
	del( _DROP_MEL_CMD_STR )

	def __new__( cls, parent, button ):
		assert isinstance( button, Button )

		pos, size = button.getPosSize()
		uiStr = maya.mel.eval( 'iconTextButton -p %s -i "%s" -label "%s" -w %s -h %s -docTag ButtonUI -dgc buttonDrag -dpc buttonDrop' % (parent, button.getImage(), button.getLabel(), size.x, size.y) )
		self = unicode.__new__( cls, uiStr )
		self.button = button

		parent( e=True, ap=((self, 'left', pos.x, 0), (self, 'top', pos.y, 0)) )

		self.POP_menu = popupMenu( p=self, b=2, pmc=self.buildMenu )

		return self
	def __call__( self, *a, **kw ):
		return iconTextButton( self, *a, **kw )
	def buildMenu( self ):
		pass
	def updateHighlightState( self ):
		selectedState = self.button.selectedState()
		if selectedState == Button.PARTIAL:
			self( e=True, i=Button.IMG_PARTIAL )
		elif selectedState == Button.COMPLETE:
			self( e=True, i=Button.IMG_COMPLETE )
		else:
			self( e=True, i=self.button.getImage() )

	### EVENT HANDLERS ###
	def on_drag( self, *a ):
		print 'sweet - this shit is working', a
	def on_drop( self, *a ):
		print 'dropped', a


class MelPicture(BaseMelWidget):
	WIDGET_CMD = picture

	def getImage( self ):
		return self( q=True, i=image )
	def setImage( self, image ):
		self( e=True, i=image )


class CharacterUI(MelHLayout):
	def __init__( self, parent, character ):
		self.character = character

		self.UI_picker = MelPicture( self, en=False )
		self.UI_picker.setImage( character.getBgImage() )
		self.layout()

		self.populate()
		self.highlightButtons()
	def populate( self ):
		self.buttonUIs = []
		for button in self.character.getButtons():
			#maya.mel.eval( r"""global proc string[] yay( string $n, int $x, int $y, int $m ) { print( "dragged\n" ); return {}; }""" )
			#maya.mel.eval( r"""global proc boo( string $dgc, string $dpc, string $msgs[], int $x, int $y, int $type ) { print( "dropped\n" ); }""" )
			#maya.mel.eval( """iconTextButton -style "iconAndTextCentered" -mw 0 -mh 0 -w 20 -h 20 -dgc testDrag -dropCallback "testDrop";""" )
			ui = ButtonUI( self, button )
			self.buttonUIs.append( ui )
	def highlightButtons( self ):
		for buttonUI in self.buttonUIs:
			buttonUI.updateHighlightState()


class PickerLayout(MelVSingleStretchLayout):
	def __init__( self, parent ):
		self.characterUIs = []

		self.UI_tabs = tabs = MelTabLayout( self )
		self.UI_tabs.setChangeCB( self.on_tabChange )
		self.UI_editor = MelFrameLayout( self, l='Edit Current Picker', cll=True, cl=True )

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
		self.UI_editor = PickerLayout( self )
		self.show()


#end
