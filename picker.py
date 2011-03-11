
from maya.cmds import *
from baseMelUI import *
from vectors import Vector, Colour
from common import printErrorStr

TOOL_NAME = 'zooPicker'
VERSION = 0

DEFAULT_COLOUR = 'blue'


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
	'''

	@classmethod
	def Create( cls, character, pos, size, colour=None, label=None, objs=(), cmdStr=None, cmdIsPython=False ):
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
	def selectCb( self ):
		existingObjs = []
		for obj in self.getObjs():
			if objExists( obj ):
				existingObjs.append( obj )
			elif objExists( '%s:%s' % (self.character.getNamespace(), obj) ):
				existingObjs.append( obj )

		select( existingObjs )
	def executeCmd( self ):
		if self.cmdStr:
			if self.cmdIsPython:
				try:
					return eval( self.cmdStr )
				except:
					printErrorStr( 'Executing command "%s" on %s button at %s' % (self.cmdStr, self.colour, self.pos) )


class Character(object):
	'''
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


class ButtonUI(MelIconButton):
	def __init__( self, parent, button ):
		self.button = button

		assert isinstance( button, Button )

		pos, size = button.getPosSize()
		self( e=True, style='iconAndTextCentered', image1=button.getColour(), mw=0, mh=0, label=button.getLabel(), w=size.x, h=size.y, command=button.selectCb, dragCallback=self.on_drag, dropCallback=self.on_drop )
		parent( e=True, ap=((self, 'left', pos.x, 0), (self, 'top', pos.y, 0)), dropCallback=self.on_drop )
	def buildMenu( self ):
		pass

	### EVENT HANDLERS ###
	def on_drag( self, *a ):
		print a
	def on_drop( self, *a ):
		print a


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
	def populate( self ):
		self.buttonUIs = []
		for button in self.character.getButtons():
			ui = ButtonUI( self, button )
			self.buttonUIs.append( ui )


class PickerLayout(MelVSingleStretchLayout):
	def __init__( self, parent ):
		self.characterUIs = []

		self.UI_tabs = tabs = MelTabLayout( self )
		self.UI_editor = MelFrameLayout( self, l='Edit Current Picker', cll=True, cl=True )

		self.setStretchWidget( tabs )
		self.layout()

		self.populate()

		#make sure the UI gets updated when the scene changes
		self.setSceneChangeCB( self.on_sceneChange )
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
	def on_sceneChange( self, *a ):
		self.populate()


class PickerWindow(BaseMelWindow):
	WINDOW_NAME = ''
	WINDOW_TITLE = ''

	DEFAULT_SIZE = 275, 525
	DEFAULT_MENU = 'Help'
	DEFAULT_MENU_IS_HELP = True

	FORCE_DEFAULT_SIZE = True

	HELP_MENU = 'hamish@valvesoftware.com', TOOL_NAME, None

	def __init__( self ):
		self.UI_editor = PickerLayout( self )
		self.show()


#end
