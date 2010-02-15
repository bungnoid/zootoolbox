import maya.cmds as cmd
import utils
import weakref
import filesystem


class MelUIError(Exception): pass


#this maps ui type strings to actual command objects - they're not always called the same
TYPE_NAMES_TO_CMDS = { 'staticText': cmd.text }

class BaseMelWidget(filesystem.trackableClassFactory( unicode )):
	'''
	This is a wrapper class for a mel widget to make it behave a little more like an object.  It
	inherits from str because thats essentially what a mel widget is - a name coupled with a mel
	command.  To interact with the widget the mel command is called with the UI name as the first arg.

	As a shortcut objects of this type are callable - the args taken depend on the specific command,
	and can be found in the mel docs.

	example:
	class AButtonClass(BaseMelWidget):
		WIDGET_CMD = cmd.button

	aButton = AButtonClass( parentName, label='hello' )
	aButton( edit=True, label='new label!' )
	'''

	#this should be set to the mel widget command used by this widget wrapped - ie cmd.button, or cmd.formLayout
	WIDGET_CMD = cmd.control

	#if not None, this is used to set the default width of the widget when created
	DEFAULT_WIDTH = None

	#this is the name of the kwarg used to set and get the "value" of the widget - most widgets use the "value" or "v" kwarg, but others have special names.  three cheers for mel!
	KWARG_VALUE_NAME = 'v'
	KWARG_VALUE_LONG_NAME = 'value'

	#this is the name of the "main" change command kwarg.  some widgets have multiple change callbacks that can be set, and they're not abstracted, but this is the name of the change cb name you want to be referenced by the setChangeCB method
	KWARG_CHANGE_CB_NAME = 'cc'

	#track instances so we can send them update messages -
	_INSTANCE_LIST = []

	def __new__( cls, parent, *a, **kw ):
		cmd.setParent( parent )
		WIDGET_CMD = cls.WIDGET_CMD

		#
		width = kw.pop( 'w', kw.pop( 'width', cls.DEFAULT_WIDTH ) )
		if isinstance( width, int ):
			kw[ 'width' ] = width

		#this has the potential to be slow: it generates a unique name for the widget we're about to create, the benefit of doing this is that we're
		#guaranteed the widget LEAF name will be unique.  I'm assuming maya also does this, but I'm unsure.  if there are weird ui naming conflicts
		#it might be nessecary to uncomment this code
		baseName, n = WIDGET_CMD.__name__, 0
		uniqueName = '%s%d' % (baseName, n)
		while WIDGET_CMD( uniqueName, q=True, exists=True ):
			n += 1
			uniqueName = '%s%d' % (baseName, n)

		WIDGET_CMD( uniqueName, **kw )

		new = unicode.__new__( cls, uniqueName )
		cls._INSTANCE_LIST.append( new )

		return new
	def __init__( self, parent, *a, **kw ):
		#make sure kw args passed to init are executed as edit commands (which should have been passed
		#to the cmd on creation, but we can't do that because we're inheriting from str, and we don't
		#want to force all subclasses to implement a __new__ method...
		self( edit=True, **kw )

		self._changeCB = None

		self.parent = parent
	def __call__( self, *a, **kw ):
		return self.WIDGET_CMD( self, *a, **kw )
	def getVisibility( self ):
		return self( q=True, vis=True )
	def setVisibility( self, visibility=True ):
		self( e=True, vis=visibility )
	def setValue( self, value ):
		try:
			kw = { 'e': True, self.KWARG_VALUE_NAME: value }
			self.WIDGET_CMD( self, **kw )
		except TypeError, x:
			print self.WIDGET_CMD
			raise
	def getValue( self ):
		kw = { 'q': True, self.KWARG_VALUE_NAME: True }
		return self.WIDGET_CMD( self, **kw )
	def setChangeCB( self, cb ):
		kw = { 'e': True, self.KWARG_CHANGE_CB_NAME: cb }
		self.WIDGET_CMD( self, **kw )
		self._changeCB = cb
	def getChangeCB( self ):
		return self._changeCB
	def enable( self, state=True ):
		try: self( e=True, enable=state )
		except: pass
	def disable( self ):
		self.enable( False )
	def editable( self, state=True ):
		try: self( e=True, editable=state )
		except: pass
	@classmethod
	def FromStr( cls, theStr ):
		'''
		given a ui name, this will cast the string as a widget instance
		'''
		assert cmd.control( theStr, exists=True )

		candidates = []
		uiTypeStr = cmd.objectTypeUI( theStr )
		uiCmd = TYPE_NAMES_TO_CMDS.get( uiTypeStr, getattr( cmd, uiTypeStr, None ) )

		#print cmd.objectTypeUI( theStr )  ##NOTE: the typestr isn't ALWAYS the same name as the function used to interact with said control, so this debug line can be useful for spewing object type names...

		if uiCmd is not None:
			for subCls in BaseMelWidget.GetSubclasses():
				if subCls.WIDGET_CMD is None: continue
				if subCls.WIDGET_CMD is uiCmd:
					candidates.append( subCls )

		theCls = cls
		if candidates:
			theCls = candidates[ 0 ]

		new = unicode.__new__( theCls, theStr )
		cls._INSTANCE_LIST.append( new )

		return new
	@classmethod
	def IterInstances( cls ):
		existingInstList = []
		for inst in cls._INSTANCE_LIST:
			if not isinstance( inst, cls ):
				continue

			if cls.WIDGET_CMD( inst, q=True, exists=True ):
				existingInstList.append( inst )
				yield inst

		cls._INSTANCE_LIST = existingInstList


class MelLayout(BaseMelWidget):
	WIDGET_CMD = cmd.layout

	def getChildren( self ):
		'''
		returns a list of all children UI items
		'''
		children = self( q=True, ca=True ) or []
		children = [ BaseMelWidget.FromStr( c ) for c in children ]

		return children
	def clear( self ):
		'''
		deletes all children from the layout
		'''
		for childUI in self.getChildren():
			cmd.deleteUI( childUI )


class MelForm(MelLayout): WIDGET_CMD = cmd.formLayout
class MelColumn(MelLayout): WIDGET_CMD = cmd.columnLayout
class MelRow(MelLayout): WIDGET_CMD = cmd.rowLayout
class MelScrollLayout(MelLayout):
	WIDGET_CMD = cmd.scrollLayout

	def __new__( cls, parent, *a, **kw ):
		kw.setdefault( 'childResizable', kw.pop( 'cr', True ) )

		return MelLayout.__new__( cls, parent, *a, **kw )


class MelTabLayout(MelLayout):
	WIDGET_CMD = cmd.tabLayout

	def __new__( cls, parent, *a, **kw ):
		kw.setdefault( 'childResizable', kw.pop( 'cr', True ) )

		return MelLayout.__new__( cls, parent, *a, **kw )
	def __init__( self, parent, *a, **kw ):
		kw.setdefault( 'selectCommand', kw.pop( 'sc', self.on_select ) )
		kw.setdefault( 'changeCommand', kw.pop( 'cc', self.on_change ) )
		kw.setdefault( 'preSelectCommand', kw.pop( 'psc', self.on_preSelect ) )
		kw.setdefault( 'doubleClickCommand', kw.pop( 'dcc', self.on_doubleClick ) )

		MelLayout.__init__( self, parent, *a, **kw )
	def numTabs( self ):
		return self( q=True, numberOfChildren=True )
	__len__ = numTabs
	def setLabel( self, idx, label ):
		self( e=True, tabLabelIndex=(idx+1, label) )
	def getLabel( self, idx ):
		self( q=True, tabLabelIndex=idx+1 )
	def getSelectedTab( self ):
		return self( q=True, selectTab=True )
	def on_select( self ):
		'''
		automatically hooked up if instantiated using this class - subclass to override
		'''
		pass
	def on_change( self ):
		'''
		automatically hooked up if instantiated using this class - subclass to override
		'''
		pass
	def on_preSelect( self ):
		'''
		automatically hooked up if instantiated using this class - subclass to override
		'''
		pass
	def on_doubleClick( self ):
		'''
		automatically hooked up if instantiated using this class - subclass to override
		'''
		pass


class MelLabel(BaseMelWidget):
	WIDGET_CMD = cmd.text
	KWARG_VALUE_NAME = 'l'
	KWARG_VALUE_LONG_NAME = 'label'

	def bold( self, state=True ):
		self( e=True, font='boldLabelFont' if state else 'plainLabelFont' )


class MelButton(BaseMelWidget):
	WIDGET_CMD = cmd.button
	KWARG_CHANGE_CB_NAME = 'c'

class MelCheckBox(BaseMelWidget):
	WIDGET_CMD = cmd.checkBox

	def __new__( cls, parent, *a, **kw ):
		#this craziness is so we can default the label to nothing instead of the widget's name...  dumb, dumb, dumb
		labelArgs = 'l', 'label'
		for f in kw.keys():
			if f == 'label':
				kw[ 'l' ] = kw.pop( 'label' )
				break

		kw.setdefault( 'l', '' )

		return BaseMelWidget.__new__( cls, parent, *a, **kw )


class MelIntField(BaseMelWidget):
	WIDGET_CMD = cmd.intField
	DEFAULT_WIDTH = 30

class MelFloatField(BaseMelWidget): WIDGET_CMD = cmd.floatField
class MelTextField(BaseMelWidget):
	WIDGET_CMD = cmd.textField
	DEFAULT_WIDTH = 150
	KWARG_VALUE_NAME = 'tx'
	KWARG_VALUE_LONG_NAME = 'text'

	def setValue( self, value ):
		if not isinstance( value, str ):
			value = str( value )

		BaseMelWidget.setValue( self, value )


class MelScrollField(MelTextField):
	WIDGET_CMD = cmd.scrollField


class MelTextScrollList(BaseMelWidget):
	WIDGET_CMD = cmd.textScrollList
	KWARG_CHANGE_CB_NAME = 'sc'

	def __getitem__( self, idx ):
		return self.getItems()[ idx ]
	def __setitem__( self, idx, value ):
		itemNames = self.getItems()
		return self( q=True, ai=True )
	def __len__( self ):
		return self( q=True, numberOfItems=True )
	def setItems( self, items ):
		self.clear()
		for i in items:
			self.append( i )
	def getItems( self ):
		return self( q=True, ai=True )
	def getSelectedItems( self ):
		return self( q=True, si=True ) or []
	def getSelectedIdxs( self ):
		return [ idx-1 for idx in self( q=True, sii=True ) or [] ]
	def selectByIdx( self, idx ):
		self( e=True, selectIndexedItem=idx+1 )  #indices are 1-based in mel land - fuuuuuuu alias!!!
	def selectByValue( self, value ):
		self( e=True, selectItem=value )
	def append( self, item ):
		self( e=True, append=item )
	def appendItems( self, items ):
		for i in items: self.append( i )
	def removeByIdx( self, idx ):
		self( e=True, removeIndexedItem=idx+1 )
	def removeByValue( self, value ):
		self( e=True, removeItem=value )
	def removeSelectedItems( self ):
		for idx in self.getSelectedIdxs():
			self.removeByIdx( idx )
	def clear( self ):
		self( e=True, ra=True )
	def clearSelection( self ):
		self( e=True, deselectAll=True )


class MelOptionMenu(BaseMelWidget):
	WIDGET_CMD = cmd.optionMenu
	KWARG_CHANGE_CB_NAME = 'cc'

	def __getitem__( self, idx ):
		return self.getItems()[ idx ]
	def __setitem__( self, idx, value ):
		menuItemNames = self.getMenuItemNames()
		cmd.menuItem( menuItemNames[ idx ], e=True, l=value )
	def __len__( self ):
		return self( q=True, numberOfItems=True )
	def selectByIdx( self, idx ):
		self( e=True, select=idx+1 )  #indices are 1-based in mel land - fuuuuuuu alias!!!
	def selectByValue( self, value ):
		idx = self.getItems().index( value )
		self.selectByIdx( idx )
	def getMenuItemNames( self ):
		return self( q=True, itemListLong=True ) or []
	def getItems( self ):
		return [ cmd.menuItem( menuName, q=True, l=True ) for menuName in self.getMenuItemNames() ]
	def append( self, strToAppend ):
		cmd.setParent( self, m=True )
		cmd.menuItem( label=strToAppend )
	def clear( self ):
		for menuItem in self.getMenuItemNames():
			cmd.deleteUI( menuItem )


UI_FOR_PY_TYPES = { bool: MelCheckBox,
                    int: MelIntField,
                    float: MelFloatField,
                    basestring: MelTextField,
                    list: MelTextScrollList,
                    tuple: MelTextScrollList }

def buildUIForObject( obj, parent, typeMapping=None ):
	'''
	'''
	if typeMapping is None:
		typeMapping = UI_FOR_PY_TYPES

	objType = obj if type( obj ) is type else type( obj )

	#first see if there is an exact type match in the dict
	buildClass = None
	try: buildClass = typeMapping[ objType ]
	except KeyError:
		#if not, see if there is an inheritance match
		for aType, aBuildClass in typeMapping.iteritems():
			if issubclass( objType, aType ):
				buildClass = aBuildClass
				break

	if buildClass is None:
		raise MelUIError( "there is no build class defined for object's of type %s (%s)" % (type( obj ), obj) )

	ui = buildClass( parent )
	ui.setValue( obj )

	return ui


class BaseMelWindow(unicode):
	'''
	This is a wrapper class for a mel window to make it behave a little more like an object.  It
	inherits from str because thats essentially what a mel widget is.

	Objects of this class are callable.  Calling an object is basically the same as passing the given
	args to the cmd.window maya command:

	aWindow = BaseMelWindow()
	aWindow( q=True, exists=True )

	is the same as doing:
	aWindow = cmd.window()
	cmd.window( aWindow, q=True, exists=True )
	'''
	WINDOW_NAME = 'unnamed_window'
	WINDOW_TITLE = 'Unnamed Tool'

	DEFAULT_SIZE = None
	DEFAULT_MENU = 'File'
	DEFAULT_MENU_IS_HELP = False

	FORCE_DEFAULT_SIZE = False

	def __new__( cls, *a, **kw ):
		kw.setdefault( 'title', cls.WINDOW_TITLE )
		kw.setdefault( 'widthHeight', cls.DEFAULT_SIZE )
		kw.setdefault( 'menuBar', True )

		if cmd.window( cls.WINDOW_NAME, ex=True ):
			cmd.deleteUI( cls.WINDOW_NAME )

		new = unicode.__new__( cls, cmd.window( cls.WINDOW_NAME, **kw ) )
		if cls.DEFAULT_MENU is not None:
			cmd.menu( l=cls.DEFAULT_MENU, helpMenu=cls.DEFAULT_MENU_IS_HELP )

		return new
	def __call__( self, *a, **kw ):
		return cmd.window( self, *a, **kw )
	def setTitle( self, newTitle ):
		cmd.window( self.WINDOW_NAME, e=True, title=newTitle )
	def getMenu( self, menuName, createIfNotFound=True ):
		'''
		returns the UI name for the menu with the given name
		'''
		menus = self( q=True, menuArray=True )
		if menus is None:
			return

		for m in menus:
			if cmd.menu( m, q=True, label=True ) == menuName:
				return m

		if createIfNotFound:
			return cmd.menu( l=menuName, helpMenu=menuName.lower()=='help' )
	def show( self, state=True ):
		if state:
			cmd.showWindow( self )
		else:
			self( e=True, visible=False )

		if self.FORCE_DEFAULT_SIZE:
			self( e=True, widthHeight=self.DEFAULT_SIZE )


#end