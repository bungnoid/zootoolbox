
from __future__ import with_statement

from maya.cmds import *
from baseMelUI import *
from vectors import Vector, Colour
from common import printErrorStr, printWarningStr

import re
import names
import colours
import presetsUI

eval = __builtins__[ 'eval' ]  #otherwise this gets clobbered by the eval in maya.cmds

TOOL_NAME = 'zooPicker'
TOOL_EXTENSION = filesystem.presets.DEFAULT_XTN
VERSION = 0

MODIFIERS = SHIFT, CAPS, CTRL, ALT = 2**0, 2**1, 2**2, 2**3
ADDITIVE = CTRL | SHIFT


def getTopPickerSet():
	existing = [ node for node in ls( type='objectSet', r=True ) or [] if sets( node, q=True, text=True ) == TOOL_NAME ]

	if existing:
		return existing[ 0 ]
	else:
		pickerNode = createNode( 'objectSet', n='picker' )
		sets( pickerNode, e=True, text=TOOL_NAME )

		return pickerNode


def resolveCmdStr( cmdStr, obj, connects, optionals=[] ):
	'''
	NOTE: both triggered and xferAnim use this function to resolve command strings as well
	'''
	INVALID = '<invalid connect>'
	cmdStr = str( cmdStr )

	#resolve # tokens - these represent self
	cmdStr = cmdStr.replace( '#', str( obj ) )

	#resolve ranged connect array tokens:  @<start>,<end> - these represent what is essentially a list slice - although they're end value inclusive unlike python slices...
	compile = re.compile
	arrayRE = compile( '(@)([0-9]+),(-*[0-9]+)' )
	def arraySubRep( matchobj ):
		char,start,end = matchobj.groups()
		start = int( start )
		end = int( end ) + 1
		if end == 0:
			end = None

		try:
			return '{ "%s" }' % '","'.join( connects[ start:end ] )
		except IndexError:
			return "<invalid range: %s,%s>" % (start, end)

	cmdStr = arrayRE.sub( arraySubRep, cmdStr )

	#resolve all connect array tokens:  @ - these are represent a mel array for the entire connects array excluding self
	allConnectsArray = '{ "%s" }' % '","'.join( [con for con in connects[1:] if con != INVALID] )
	cmdStr = cmdStr.replace( '@', allConnectsArray )

	#resolve all single connect tokens:  %<x> - these represent single connects
	connectRE = compile('(%)(-*[0-9]+)')
	def connectRep( matchobj ):
		char, idx = matchobj.groups()
		try:
			return connects[ int(idx) ]
		except IndexError:
			return INVALID

	cmdStr = connectRE.sub( connectRep, cmdStr )

	#finally resolve any optional arg list tokens:  %opt<x>%
	optionalRE = compile( '(\%opt)(-*[0-9]+)(\%)' )
	def optionalRep( matchobj ):
		charA, idx, charB = matchobj.groups()
		try:
			return optionals[ int(idx) ]
		except IndexError:
			return '<invalid optional>'

	cmdStr = optionalRE.sub( optionalRep, cmdStr )

	return cmdStr


class Button(object):
	'''
	A Button instance is a "container" for a button within a picker.  To instantiate a button you need to pass the set node
	that contains the button data.  You can create a new set node using Button.Create.

	A button, when pressed, by default selects the contents of the set based on the keyboard modifiers pressed.  But a button
	can also define its own press command.  Button press commands are stored on the cmdStr string attribute on the set node
	and can be most easily edited using the editor tab created by the PickerLayout UI.
	'''

	SELECTION_STATES = NONE, PARTIAL, COMPLETE = range( 3 )
	DEFAULT_SIZE = 14, 14
	DEFAULT_COLOUR = tuple( Colour( (0.25, 0.25, 0.3) ).asRGB() )
	AUTO_COLOUR = None
	COLOUR_PARTIAL, COLOUR_COMPLETE = (1, 0.6, 0.5), Colour( 'white' ).asRGB()

	@classmethod
	def Create( cls, character, pos, size=DEFAULT_SIZE, colour=AUTO_COLOUR, label=None, objs=(), cmdStr=None, cmdIsPython=False ):
		node = sets( em=True, text='zooPickerButton' )
		if objs:
			node = rename( node, '%s_picker' % objs[0] )
		else:
			node = rename( node, 'picker' )

		sets( node, e=True, add=character.getNode() )

		addAttr( node, ln='posSize', dt='string' )  #stuff pos and size into a single str attr - so lazy...
		addAttr( node, ln='colour', dt='string' )
		addAttr( node, ln='label', dt='string' )
		addAttr( node, ln='cmdStr', dt='string' )
		addAttr( node, ln='cmdIsPython', at='bool', dv=cmdIsPython )

		self = cls( node )
		self.setPosSize( pos, size )
		self.setLabel( label )
		self.setObjs( objs )
		self.setCmdStr( cmdStr )

		#if the colour is set to "AUTO_COLOUR" then try to determine the button colour based off the object's colour
		if colour is cls.AUTO_COLOUR:
			self.setColour( cls.DEFAULT_COLOUR )
			self.setAutoColour()
		else:
			self.setColour( colour )

		return self

	def __init__( self, node ):
		self._node = node
	def __repr__( self ):
		return "%s( '%s' )" % (type( self ).__name__, self.getNode())
	__str__ = __repr__
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
	def getCharacter( self ):
		cons = listConnections( self.getNode(), type='objectSet', s=False )
		if cons:
			return Character( cons[0] )
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
		return sets( self.getNode(), q=True ) or []
	def getCmdStr( self ): return getAttr( '%s.cmdStr' % self.getNode() )
	def getCmdIsPython( self ): return getAttr( '%s.cmdIsPython' % self.getNode() )
	def getResolvedCmdStr( self ):
		cmdStr = self.getCmdStr()
		if self.getCmdIsPython():
			return cmdStr % locals()
		else:
			return resolveCmdStr( cmdStr, self.getNode(), self.getObjs() )
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

		if not val:
			return

		sets( e=True, clear=self.getNode() )
		sets( val, e=True, add=self.getNode() )
	def setCmdStr( self, val ):
		if val is None:
			val = ''

		setAttr( '%s.cmdStr' % self.getNode(), val, type='string' )
	def setCmdIsPython( self, val ):
		setAttr( '%s.cmdIsPython' % self.getNode(), val )
	def setAutoColour( self ):
		objs = self.getObjs()
		for obj in objs:
			colour = colours.getObjColour( obj )
			if colour:
				self.setColour( colour )
				return
	def select( self, forceModifiers=None ):
		if forceModifiers is None:
			mods = getModifiers()
		else:
			mods = forceModifiers

		objs = self.getObjs()
		if objs:
			if mods & SHIFT and mods & CTRL:
				select( objs, add=True )
			elif mods & SHIFT:
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
		cmdStr = self.getResolvedCmdStr()
		if cmdStr:
			try:
				if self.getCmdIsPython():
					return eval( cmdStr )
				else:
					return maya.mel.eval( "{%s;}" % cmdStr )
			except:
				printErrorStr( 'Executing command "%s" on button "%s"' % (cmdStr, self.getNode()) )

		#if there is no cmdStr then just select the nodes in this button set
		else:
			self.select()
	def duplicate( self ):
		dupe = self.Create( self.getCharacter(), self.getPos(), self.getSize(),
		                    self.getColour(), self.getLabel(), self.getObjs(),
		                    self.getCmdStr(), self.getCmdIsPython() )

		return dupe
	def mirrorObjs( self ):
		'''
		replaces the objects in this button with their name based opposites - ie if this button contained the
		object ctrl_L, this method would replace the objects with ctrl_R.  It uses names.swapParity
		'''
		oppositeObjs = []
		for obj in self.getObjs():
			opposite = names.swapParity( obj )
			if opposite:
				oppositeObjs.append( opposite )

		self.setObjs( oppositeObjs )
	def delete( self ):
		delete( self.getNode() )


class Character(object):
	'''
	A Character is made up of many Button instances to select the controls or groups of controls that
	comprise a puppet rig.  A Character is also stored as a set node in the scene.  New Character nodes
	can be created using Character.Create, or existing ones instantiated by passing the set node to
	Character.
	'''

	DEFAULT_BG_IMAGE = 'pickerGrid.bmp'

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
		addAttr( node, ln='filepath', dt='string' )

		setAttr( '%s.version' % node, VERSION )
		setAttr( '%s.name' % node, name, type='string' )
		setAttr( '%s.bgImage' % node, cls.DEFAULT_BG_IMAGE, type='string' )
		setAttr( '%s.bgColour' % node, '0,0,0', type='string' )

		#lock the node - this stops maya from auto-deleting it if all buttons are removed
		lockNode( node )

		self = cls( node )
		allButton = self.createButton( (5, 5), (25, 14), (1, 0.65, 0.25), 'all', [], '%(self)s.getCharacter().selectAllButtonObjs()', True )

		return self

	def __init__( self, node ):
		self._node = node
	def __repr__( self ):
		return "%s( '%s' )" % (type( self ).__name__, self.getNode())
	__str__ = __repr__
	def __eq__( self, other ):
		return self._node == other._node
	def __ne__( self, other ):
		return not self.__eq__( other )
	def getNode( self ):
		return self._node
	def getButtons( self ):
		buttonNodes = sets( self.getNode(), q=True ) or []

		return [ Button( node ) for node in buttonNodes ]
	def getName( self ):
		return getAttr( '%s.name' % self.getNode() )
	def getBgImage( self ):
		return getAttr( '%s.bgImage' % self.getNode() )
	def getBgColour( self ):
		colStr = getAttr( '%s.bgColour' % self.getNode() )

		return Colour( [ float( c ) for c in colStr.split( ',' ) ] ).asRGB()
	def getFilepath( self ):
		return getAttr( '%s.filepath' % self.getNode() )
	def setName( self, val ):
		setAttr( '%s.name' % self.getNode(), str( val ), type='string' )
	def setBgImage( self, val ):
		setAttr( '%s.bgImage' % self.getNode(), val, type='string' )
	def setBgColour( self, val ):
		valStr = ','.join( map( str, val ) )
		setAttr( '%s.bgColour' % self.getNode(), valStr, type='string' )
	def setFilepath( self, filepath ):
		setAttr( '%s.filepath' % self.getNode(), filepath, type='string' )
	def createButton( self, pos, size, colour=None, label=None, objs=(), cmdStr=None, cmdIsPython=False ):
		'''
		appends a new button to the character - a new Button instance is returned
		'''
		return Button.Create( self, pos, size, colour, label, objs, cmdStr, cmdIsPython )
	def removeButton( self, button, delete=True ):
		'''
		given a Button instance, will remove it from the character
		'''
		for aButton in self.getButtons():
			if button == aButton:
				sets( button.getNode(), e=True, remove=self.getNode() )
				if delete:
					button.delete()

				return
	def selectAllButtonObjs( self ):
		for button in self.getButtons():
			button.select( ADDITIVE )
	def delete( self ):
		for button in self.getButtons():
			button.delete()

		node = self.getNode()
		lockNode( node, lock=False )
		delete( node )
	def saveToPreset( self, filepath ):
		'''
		stores this picker character out to disk
		'''
		filepath = filesystem.Path( filepath )
		if filepath.exists:
			filepath.editoradd()

		with open( filepath, 'w' ) as fOpen:
			infoDict = {}
			infoDict[ 'version' ] = VERSION
			infoDict[ 'name' ] = self.getName()
			infoDict[ 'bgImage' ] = self.getBgImage() or ''
			infoDict[ 'bgColour' ] = tuple( self.getBgColour() )
			fOpen.write( str( infoDict ) )
			fOpen.write( '\n' )

			#the preset just needs to contain a list of buttons
			for button in self.getButtons():
				buttonDict = {}
				pos, size = button.getPosSize()
				buttonDict[ 'pos' ] = tuple( pos )
				buttonDict[ 'size' ] = tuple( size )
				buttonDict[ 'colour' ] = tuple( button.getColour() )
				buttonDict[ 'label' ] = button.getLabel()
				buttonDict[ 'objs' ] = button.getObjs()
				buttonDict[ 'cmdStr' ] = button.getCmdStr()
				buttonDict[ 'cmdIsPython' ] = button.getCmdIsPython()

				fOpen.write( str( buttonDict ) )
				fOpen.write( '\n' )

		#store the filepath on the character node
		self.setFilepath( filepath.unresolved() )

	@classmethod
	def LoadFromPreset( cls, filepath, namespaceHint=None ):
		'''
		'''
		filepath = filesystem.Path( filepath )

		buttonDicts = []
		with open( filepath ) as fOpen:
			lineIter = iter( fOpen )
			try:
				infoLine = lineIter.next()
				infoDict = eval( infoLine.strip() )
				while True:
					buttonLine = lineIter.next()
					buttonDict = eval( buttonLine.strip() )
					buttonDicts.append( buttonDict )
			except StopIteration: pass

		version = infoDict.pop( 'version', 0 )

		newCharacter = cls.Create( infoDict.pop( 'name', 'A Picker' ) )
		newCharacter.setBgImage( infoDict.pop( 'bgImage', cls.DEFAULT_BG_IMAGE ) )
		newCharacter.setBgColour( infoDict.pop( 'bgColour', (0, 0, 0) ) )

		#if there is still data in the infoDict print a warning - perhaps new data was written to the file that was handled when loading the preset?
		if infoDict:
			printWarningStr( 'Not all info was loaded from %s on to the character: %s still remains un-handled' % (filepath, infoDict) )

		for buttonDict in buttonDicts:
			newButton = Button.Create( newCharacter, buttonDict.pop( 'pos' ),
			                           buttonDict.pop( 'size' ),
			                           buttonDict.pop( 'colour', Button.DEFAULT_COLOUR ),
			                           buttonDict.pop( 'label', '' ) )

			newButton.setCmdStr( buttonDict.pop( 'cmdStr', '' ) )
			newButton.setCmdIsPython( buttonDict.pop( 'cmdIsPython', False ) )

			#now handle objects - this is about the only tricky part - we want to try to match the objects stored to file to objects in this scene as best we can
			objs = buttonDict.pop( 'objs', [] )
			realObjs = []
			for obj in objs:
				if objExists( obj ):
					realObjs.append( obj )
					continue

				if namespaceHint:
					objNs = '%s:%s' % (namespaceHint, obj)
					if objExists( objNs ):
						realObjs.append( objNs )
						continue

				anyMatches = ls( obj )
				if anyMatches:
					realObjs.append( anyMatches[0] )
					if not namespaceHint:
						namespaceHint = ':'.join( anyMatches[0].split( ':' )[ :-1 ] )

			newButton.setObjs( realObjs )

			#print a warning if there is still data in the buttonDict - perhaps new data was written to the file that was handled when loading the preset?
			if buttonDict:
				printWarningStr( 'Not all info was loaded from %s on to the character: %s still remains un-handled' % (filepath, infoDict) )

		return newCharacter


def _drag( *a ):
	'''
	passes the local coords the widget is being dragged from
	'''
	return [a[-3], a[-2]]


def _drop( src, tgt, msgs, x, y, mods ):
	'''
	this is the drop handler used by everything in this module
	'''
	src = BaseMelUI.FromStr( src )
	tgt = BaseMelUI.FromStr( tgt )
	if isinstance( src, ButtonUI ) and isinstance( tgt, DragDroppableFormLayout ):
		srcX, srcY = map( int, msgs )
		x -= srcX
		y -= srcY

		src.button.setPos( (x, y) )
		src.updateGeometry()
	elif isinstance( src, CreatePickerButton ) and isinstance( tgt, DragDroppableFormLayout ):
		pickerLayout = src.getParentOfType( PickerLayout )
		characterUI = pickerLayout.getCurrentCharacterUI()
		newButton = characterUI.createButton( (x, y) )


class CmdEditorLayout(MelVSingleStretchLayout):
	def __init__( self, parent, button ):
		self.button = button
		self.UI_cmd = MelTextScrollField( self, text=button.getCmdStr() or '' )
		self.UI_isPython = MelCheckBox( self, l='Command is Python', v=button.getCmdIsPython() )

		hLayout = MelHLayout( self )
		self.UI_save = MelButton( hLayout, l='Save and Close', c=self.on_saveClose )
		self.UI_delete = MelButton( hLayout, l='Delete and Close', c=self.on_deleteClose )
		self.UI_cancel = MelButton( hLayout, l='Cancel', c=self.on_cancel )
		hLayout.layout()

		self.setStretchWidget( self.UI_cmd )
		self.layout()

	### EVENT HANDLERS ###
	def on_saveClose( self, *a ):
		self.button.setCmdStr( self.UI_cmd.getValue() )
		self.button.setCmdIsPython( self.UI_isPython.getValue() )
		for ui in PickerLayout.IterInstances():
			ui.updateEditor()

		self.sendEvent( 'delete' )
	def on_deleteClose( self, *a ):
		self.button.setCmdStr( None )
		for ui in PickerLayout.IterInstances():
			ui.updateEditor()

		self.sendEvent( 'delete' )
	def on_cancel( self, *a ):
		self.sendEvent( 'delete' )


class CmdEditorWindow(BaseMelWindow):
	WINDOW_NAME = 'PickerButtonCommandEditor'
	WINDOW_TITLE = 'Command Editor'

	DEFAULT_MENU = None
	DEFAULT_SIZE = 450, 200
	FORCE_DEFAULT_SIZE = True

	def __init__( self, button ):
		self.UI_editor = CmdEditorLayout( self, button )
		self.show()


class ButtonUI(MelIconButton):
	def __init__( self, parent, button ):
		MelIconButton.__init__( self, parent )

		assert isinstance( button, Button )
		self.button = button

		self( e=True, dgc=_drag, dpc=_drop, style='textOnly', c=self.on_press )
		self.POP_menu = MelPopupMenu( self, pmc=self.buildMenu )

		self.update()
	def buildMenu( self, *a ):
		menu = self.POP_menu

		menu.clear()
		MelMenuItem( menu, l='ADD selection to button', c=self.on_add )
		MelMenuItem( menu, l='REPLACE button with selection', c=self.on_replace )
		MelMenuItem( menu, l='REMOVE selection from button', c=self.on_remove )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='mirror duplicate button', c=self.on_mirrorDupe )
		MelMenuItem( menu, l='move to mirror position', c=self.on_mirrorThis )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='edit this button', c=self.on_edit )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='DELETE button', c=self.on_delete )
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
	def mirrorDuplicate( self ):
		dupe = self.button.duplicate()
		dupe.mirrorObjs()
		dupe.setAutoColour()

		self.mirrorPosition( dupe )

		self.sendEvent( 'appendButton', dupe, True )
	def mirrorPosition( self, button=None ):
		if button is None:
			button = self.button

		pickerLayout = self.getParentOfType( PickerLayout )
		pickerWidth = pickerLayout( q=True, w=True )

		pos, size = button.getPosSize()
		buttonCenterX = pos.x + (size.x / 2)

		newPosX = pickerWidth - buttonCenterX - size.x
		newPosX = min( max( newPosX, 0 ), pickerWidth )
		button.setPos( (newPosX, pos.y) )

	### EVENT HANDLERS ###
	def on_press( self, *a ):
		self.button.executeCmd()
		self.sendEvent( 'buttonSelected', self )
	def on_add( self, *a ):
		objs = self.button.getObjs()
		objs += ls( sl=True ) or []
		self.button.setObjs( objs )
	def on_replace( self, *a ):
		self.button.setObjs( ls( sl=True ) or [] )
	def on_remove( self, *a ):
		objs = self.button.getObjs()
		objs += ls( sl=True ) or []
		self.button.setObjs( objs )
	def on_mirrorDupe( self, *a ):
		self.mirrorDuplicate()
	def on_mirrorThis( self, *a ):
		self.mirrorPosition()
		self.updateGeometry()
	def on_edit( self, *a ):
		self.sendEvent( 'buttonSelected', self )
		self.sendEvent( 'showEditPanel' )
	def on_delete( self, *a ):
		self.delete()
		self.button.delete()
		self.sendEvent( 'refreshImage' )


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

		self.setDeletionCB( self.on_close )
	def populate( self ):
		for button in self.character.getButtons():
			self.appendButton( button )
	def createButton( self, pos, size=Button.DEFAULT_SIZE, colour=Button.AUTO_COLOUR, label='', objs=None ):
		if objs is None:
			objs = ls( sl=True, type='transform' )

		newButton = Button.Create( self.character, pos, size, colour, label, objs )

		#we want the drop position to be the centre of the button, not its edge - so we need to factor out the size, which we can only do after instantiating the button so we can query its size
		x, y = pos
		size = newButton.getSize()
		newButton.setPos( (x - (size.x / 2), y - (size.y / 2)) )

		self.appendButton( newButton, True )

		return newButton
	def appendButton( self, button, select=False ):
		ui = ButtonUI( self.UI_buttonLayout, button )
		if select:
			self.buttonSelected( ui )

		return ui
	def highlightButtons( self ):
		for buttonUI in self.UI_buttonLayout.getChildren():
			buttonUI.updateHighlightState()
	def refreshImage( self ):
		self.UI_picker.setVisibility( False )
		self.UI_picker.setVisibility( True )
	def buttonSelected( self, button ):
		self.currentSelection = button
		self.sendEvent( 'updateEditor' )
	def delete( self ):
		self.character.delete()
		MelHLayout.delete( self )

	### EVENT HANDLERS ###
	def on_close( self, *a ):
		CmdEditorWindow.Close()


class CreatePickerButton(MelButton):
	'''
	this class exists purely so we can test for it instead of having to test against
	a more generic "MelButton" instance when handling drop callbacks
	'''
	pass


class MelColourSlider(BaseMelWidget):
	WIDGET_CMD = colorSliderGrp
	KWARG_VALUE_NAME = 'rgb'
	KWARG_VALUE_LONG_NAME = 'rgbValue'


class PickerLayout(MelVSingleStretchLayout):
	def __init__( self, parent ):
		self.UI_tabs = tabs = MelTabLayout( self )
		self.UI_tabs.setChangeCB( self.on_tabChange )
		self.UI_editor = UI_editor = MelFrameLayout( self, l='Button Editor', cll=True, cl=True )
		UI_editor.setExpandCB( self.on_editPanelExpand )

		lblWidth = 40
		self.SZ_editor = SZ_editor = MelVSingleStretchLayout( self.UI_editor )
		self.UI_buttonLbl = MelLabel( SZ_editor, align='center' )
		self.UI_new = CreatePickerButton( SZ_editor, l='Create Button: drag to place', dgc=_drag, dpc=_drop )
		MelSeparator( SZ_editor )
		self.UI_selectedLabel = LabelledTextField( SZ_editor, llabel='label:', llabelWidth=lblWidth )
		self.UI_selectedColour = MelColourSlider( SZ_editor, label='colour:', cw=(1, lblWidth), columnAttach=((1, 'left', 0), (2, 'left', 0), (3, 'left', 0)), adj=3 )

		#UI for position
		SZ_lblPos = MelHSingleStretchLayout( SZ_editor )
		lbl = MelLabel( SZ_lblPos, l='pos:', w=lblWidth )
		SZ_pos = MelHLayout( SZ_lblPos )
		SZ_lblPos.setStretchWidget( SZ_pos )
		SZ_lblPos.layout()

		self.UI_selectedPosX = MelIntField( SZ_pos, min=0, step=1, cc=self.on_saveButton )
		self.UI_selectedPosY = MelIntField( SZ_pos, min=0, step=1, cc=self.on_saveButton )
		SZ_pos.layout()

		#UI for size
		SZ_lblSize = MelHSingleStretchLayout( SZ_editor )
		lbl = MelLabel( SZ_lblSize, l='scale:', w=lblWidth )
		SZ_size = MelHLayout( SZ_lblSize )
		SZ_lblSize.setStretchWidget( SZ_size )
		SZ_lblSize.layout()

		self.UI_selectedScaleX = MelIntField( SZ_size, min=5, max=50, step=1, cc=self.on_saveButton )
		self.UI_selectedScaleY = MelIntField( SZ_size, min=5, max=50, step=1, cc=self.on_saveButton )
		SZ_size.layout()

		#setup change callbacks
		self.UI_selectedLabel.ui.setChangeCB( self.on_saveButton )
		self.UI_selectedColour.setChangeCB( self.on_saveButton )

		#add UI to edit the button set node
		self.UI_selectedObjects = MelSetMemebershipList( SZ_editor, h=75 )
		self.UI_selectedCmdButton = MelButton( SZ_editor, l='', c=self.on_openCmdEditor )
		SZ_editor.padding = 0
		SZ_editor.setStretchWidget( self.UI_selectedObjects )
		SZ_editor.layout()

		self.setStretchWidget( tabs )
		self.layout()

		self.populate()

		#update button state when the selection changes
		self.setSelectionChangeCB( self.on_selectionChange )

		#make sure the UI gets updated when the scene changes
		self.setSceneChangeCB( self.on_sceneChange )
	def populate( self ):
		self.UI_tabs.clear()
		for character in Character.IterAll():
			self.appendCharacter( character )
	def appendCharacter( self, character ):
		idx = len( self.UI_tabs.getChildren() )
		ui = CharacterUI( self.UI_tabs, character )
		self.UI_tabs.setLabel( idx, character.getName() )
	def getCurrentCharacterUI( self ):
		selUI = self.UI_tabs.getSelectedTab()
		if selUI:
			return CharacterUI.FromStr( selUI )

		return None
	def getSelectedButtonUI( self ):
		selectedTab = self.UI_tabs.getSelectedTab()
		if selectedTab:
			currentCharacter = CharacterUI.FromStr( selectedTab )
			if currentCharacter:
				selectedButton = currentCharacter.currentSelection
				if selectedButton:
					return selectedButton

		return None
	def selectCharacter( self, character ):
		for idx, ui in enumerate( self.UI_tabs.getChildren() ):
			if ui.character == character:
				self.UI_tabs.setSelectedTabIdx( idx )
	def updateEditor( self ):
		if self.UI_editor.getCollapse():
			return

		currentCharacterUI = self.getCurrentCharacterUI()
		if not currentCharacterUI:
			self.UI_buttonLbl.setLabel( 'create a character first!' )
			self.UI_new.setEnabled( False )
			return

		self.UI_new.setEnabled( True )

		selectedButton = self.getSelectedButtonUI()
		if selectedButton:
			button = selectedButton.button
			pos, size = button.getPosSize()

			self.UI_buttonLbl.setLabel( 'editing button "%s"' % button.getNode() )
			self.UI_selectedLabel.setValue( button.getLabel(), False )
			self.UI_selectedPosX.setValue( pos.x, False )
			self.UI_selectedPosY.setValue( pos.y, False )
			self.UI_selectedScaleX.setValue( size.x, False )
			self.UI_selectedScaleY.setValue( size.y, False )
			self.UI_selectedColour.setValue( button.getColour(), False )

			self.UI_selectedObjects.setSets( [button.getNode()] )

			cmdStr = button.getCmdStr()
			if cmdStr:
				self.UI_selectedCmdButton.setLabel( '***EDIT*** Press Command' )
			else:
				self.UI_selectedCmdButton.setLabel( 'CREATE Press Command' )
		else:
			self.UI_buttonLbl.setLabel( 'no button selected!' )
	def showEditPanel( self ):
		self.UI_editor.setCollapse( False )
	def loadPreset( self, preset, *a ):  #*a exists only because this gets directly called by a menuItem - and menuItem's always pass a bool arg for some reason...  check state maybe?
		newCharacter = Character.LoadFromPreset( preset )
		if newCharacter:
			self.appendCharacter( newCharacter )

	### EVENT HANDLERS ###
	def on_editPanelExpand( self, *a ):
		if not self.UI_editor.getCollapse():
			self.updateEditor()
	def on_saveButton( self, *a ):
		buttonUI = self.getSelectedButtonUI()
		if buttonUI:
			button = buttonUI.button
			button.setLabel( self.UI_selectedLabel.getValue() )
			button.setPos( (self.UI_selectedPosX.getValue(), self.UI_selectedPosY.getValue()) )
			button.setSize( (self.UI_selectedScaleX.getValue(), self.UI_selectedScaleY.getValue()) )
			button.setColour( self.UI_selectedColour.getValue() )
			buttonUI.update()
	def on_openCmdEditor( self, *a ):
		buttonUI = self.getSelectedButtonUI()
		if buttonUI:
			CmdEditorWindow( buttonUI.button )
	def on_tabChange( self, *a ):
		self.on_selectionChange()
	def on_sceneChange( self, *a ):
		self.populate()
	def on_selectionChange( self, *a ):
		charUIStr = self.UI_tabs.getSelectedTab()
		if charUIStr:
			charUI = CharacterUI.FromStr( charUIStr )
			charUI.highlightButtons()


class PickerWindow(BaseMelWindow):
	WINDOW_NAME = 'zooPicker'
	WINDOW_TITLE = 'Picker Tool'

	DEFAULT_SIZE = 285, 525
	DEFAULT_MENU = 'File'
	DEFAULT_MENU_IS_HELP = False

	FORCE_DEFAULT_SIZE = True

	HELP_MENU = 'hamish@macaronikazoo.com', TOOL_NAME, None

	def __init__( self ):
		fileMenu = self.getMenu( 'File' )
		fileMenu( e=True, pmc=self.buildFileMenu )

		self.UI_editor = PickerLayout( self )
		self.show()
	def buildFileMenu( self ):
		menu = self.getMenu( 'File' )
		menu.clear()

		currentCharUI = self.UI_editor.getCurrentCharacterUI()
		charSelected = bool( currentCharUI )
		charSelectedIsReferenced = True
		if charSelected:
			charSelectedIsReferenced = referenceQuery( currentCharUI.character.getNode(), inr=True )

		MelMenuItem( menu, l='New Picker Tab', c=self.on_create )
		MelMenuItem( menu, en=not charSelectedIsReferenced, l='Remove Current Picker Tab', c=self.on_remove )
		MelMenuItemDiv( menu )

		MelMenuItem( menu, en=charSelected, l='Save Picker Preset', c=self.on_save )
		self.SUB_presets = MelMenuItem( menu, l='Load Picker Preset', sm=True, pmc=self.buildLoadablePresets )
	def buildLoadablePresets( self, *a ):
		menu = self.SUB_presets

		man = filesystem.PresetManager( TOOL_NAME, TOOL_EXTENSION )
		presets = man.listAllPresets()
		for loc, locPresets in presets.iteritems():
			for p in locPresets:
				pName = p.name()
				MelMenuItem( menu, l=pName, c=Callback( self.UI_editor.loadPreset, p ) )

		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='manage presets', c=self.on_loadPresetManager )

	### EVENT HANDLERS ###
	def on_create( self, *a ):
		BUTTONS = OK, CANCEL = 'Ok', 'Cancel'

		defaultName = filesystem.Path( file( q=True, sn=True ) ).name()
		import namingHelpers
		defaultName = namingHelpers.stripKnownAssetSuffixes( defaultName )
		ret = promptDialog( t='Create Picker Tab', m='Enter a name for the new picker tab:', text=defaultName, b=BUTTONS, db=OK )

		if ret == OK:
			name = promptDialog( q=True, text=True )
			if name:
				newCharacter = Character.Create( name )
				self.UI_editor.populate()
				self.UI_editor.selectCharacter( newCharacter )
				self.UI_editor.showEditPanel()
	def on_remove( self, *a ):
		currentCharacterUI = self.UI_editor.getCurrentCharacterUI()
		if currentCharacterUI:
			currentCharacterUI.delete()
	def on_save( self, *a ):
		currentChar = self.UI_editor.getCurrentCharacterUI()
		if currentChar:
			BUTTONS = OK, CANCEL = 'Ok', 'Cancel'
			ret = promptDialog( t='Preset Name', m='enter the name of the preset', tx=currentChar.character.getName(), b=BUTTONS, db=OK )
			if ret == OK:
				presetName = promptDialog( q=True, tx=True )
				if presetName:
					currentChar.character.saveToPreset( filesystem.Preset( filesystem.GLOBAL, TOOL_NAME, presetName, TOOL_EXTENSION ) )
	def on_loadPresetManager( self, *a ):
		presetsUI.load( TOOL_NAME, ext=TOOL_EXTENSION )


#end
