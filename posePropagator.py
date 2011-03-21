
try:
	import wingdbstub
except ImportError: pass


from baseMelUI import *
from maya.cmds import *

#this dict stores attribute values for the selection - attributeChange scriptjobs fire when an attribute changes
#but don't pass in pre/post values, or even the name of the attribute that has changed.  So when the scriptjobs
#are first setup, their attribute values are stored in this dict and are updated when they change
PRE_ATTR_VALUES = {}


def attrChangeCallbackFactory( attrpath ):
	'''
	returns a callback function that gets executed when the value of the attrpath changes
	'''

	#setup the initial value of the attrpath in the global attr value dict
	PRE_ATTR_VALUES[ attrpath ] = getAttr( attrpath )

	def onChange():
		preValue = PRE_ATTR_VALUES[ attrpath ]
		curValue = getAttr( attrpath )
		valueDelta = curValue - preValue

		#reset the value in the attr dict
		PRE_ATTR_VALUES[ attrpath ] = curValue

		#update keyframe not on this frame
		time = currentTime( q=True )
		keyTimes = keyframe( attrpath, q=True, tc=True )
		if keyTimes is None:
			return

		if time in keyTimes:
			keyTimes.remove( time )

		for keyTime in keyTimes:
			keyValue = keyframe( attrpath, q=True, t=(keyTime,), vc=True )
			keyframe( attrpath, e=True, t=(keyTime,), vc=keyValue + valueDelta )

	return onChange


class PosePropagatorLayout(MelHLayout):
	def __init__( self, parent ):
		MelHLayout.__init__( self, parent )

		self._state = False

		self.UI_dummyParent = None
		self.UI_on = MelButton( self, l='turn ON' )
		self.UI_off = MelButton( self, l='turn OFF' )

		self.layout()
		self.updateState()

		#fire the selection change to update the current selection state
		self.on_selectionChange()
		self.setSelectionChangeCB( self.on_selectionChange )
		self.setTimeChangeCB( self.on_timeChange )
	def setState( self, state=True ):
		self._state = state
		self.updateState()
	def updateState( self ):
		self.UI_on.setEnabled( self._state )
		self.UI_off.setEnabled( not self._state )

	### EVENT HANDLERS ###
	def on_selectionChange( self ):
		'''
		delete the old attribute change callbacks and add new ones for the current selection
		'''
		if self.UI_dummyParent is not None:
			self.UI_dummyParent.delete()
			PRE_ATTR_VALUES.clear()

		#create a dummy piece of UI to "hold" on to the scriptjobs
		self.UI_dummyParent = UI_dummyParent = MelButton( self, l='', w=1, h=1, vis=False )
		for obj in ls( sl=True ):
			for attr in listAttr( obj, keyable=True ):
				attrpath = '%s.%s' % (obj, attr)
				UI_dummyParent.setAttributeChangeCB( attrpath, attrChangeCallbackFactory( attrpath ) )
	def on_timeChange( self ):
		'''
		when the time changes we need to refresh the values in the PRE_ATTR_VALUES dict
		'''
		for attrpath in PRE_ATTR_VALUES.keys():
			PRE_ATTR_VALUES[ attrpath ] = getAttr( attrpath )


class PosePropagatorWindow(BaseMelWindow):
	WINDOW_NAME = 'posePropagatorWindow'
	WINDOW_TITLE = 'Pose Propagator'

	DEFAULT_MENU = None
	DEFAULT_SIZE = 275, 60
	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		self.UI_editor = PosePropagatorLayout( self )
		self.UI_editor.setState( True )
		self.show()


#end
