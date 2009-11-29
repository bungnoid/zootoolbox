import maya.cmds as cmd
import utils
import weakref


class MelUIError(Exception): pass

class BaseMelWidget(str):
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
	WIDGET_CMD = None

	#if not None, this is used to set the default width of the widget when created
	DEFAULT_WIDTH = None

	#this is the name of the kwarg used to set and get the "value" of the widget - most widgets use the "value" or "v" kwarg, but others have special names.  three cheers for mel!
	KWARG_VALUE_NAME = 'v'
	KWARG_VALUE_LONG_NAME = 'value'

	#this is the name of the "main" change command kwarg.  some widgets have multiple change callbacks that can be set, and they're not abstracted, but this is the name of the change cb name you want to be referenced by the setChangeCB method
	KWARG_CHANGE_CB_NAME = 'c'

	#track instances so we can send them update messages -
	_INSTANCE_LIST = []

	def __new__( cls, parent, *a, **kw ):
		cmd.setParent( parent )

		#
		width = kw.pop( 'w', kw.pop( 'width', cls.DEFAULT_WIDTH ) )
		if isinstance( width, int ):
			kw[ 'width' ] = width

		#strip off the path crap to the widget - mel doesn't really provide any easy way to handle ui name resolution.  it always returns the fullpath
		#to a widget at creation time regardless of whether the leaf name is unique, it has no way to query ui hierarchy so you cannot build a fullpath
		#to a piece of UI manually, nor can you ask maya to compare two ui names to see if they're equivalent...  so if you're naming your widgets
		#manually (and you shouldn't be) then you may run into trouble because of this...
		uiFullpath = cls.WIDGET_CMD( *a, **kw )
		uiLeafname = uiFullpath.split( '|' ) [ -1 ]

		new = str.__new__( cls, uiLeafname )
		new.longName = uiFullpath
		cls._INSTANCE_LIST.append( new )

		return new
	def __init__( self, parent, *a, **kw ):
		#make sure kw args passed to init are executed as edit commands (which should have been passed
		#to the cmd on creation, but we can't do that because we're inheriting from str, and we don't
		#want to force all subclasses to implement a __new__ method...
		self( edit=True, **kw )

		self.parent = parent
	def __call__( self, *a, **kw ):
		return self.WIDGET_CMD( self, *a, **kw )
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
	@classmethod
	def FromStr( cls, theStr ):
		'''
		given a ui name, this will cast the string as a widget instance
		'''
		return str.__new__( cls, theStr )
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
	def clear( self ):
		'''
		deletes all children from the layout
		'''
		children = self( q=True, ca=True )
		if children is not None:
			for childUI in children:
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

class MelButton(BaseMelWidget): WIDGET_CMD = cmd.button
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
                    basestring: MelTextField }

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


class BaseMelWindow(str):
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

	def __new__( cls, **kw ):
		kw.setdefault( 'title', cls.WINDOW_TITLE )
		kw.setdefault( 'widthHeight', cls.DEFAULT_SIZE )
		kw.setdefault( 'menuBar', True )

		if cmd.window( cls.WINDOW_NAME, ex=True ):
			cmd.deleteUI( cls.WINDOW_NAME )

		new = str.__new__( cls, cmd.window( cls.WINDOW_NAME, **kw ) )
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