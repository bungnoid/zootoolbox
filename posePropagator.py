
try:
	import wingdbstub
except ImportError: pass


from baseMelUI import *
from maya.cmds import *

#this dict stores attribute values for the selection - attributeChange scriptjobs fire when an attribute changes
#but don't pass in pre/post values, or even the name of the attribute that has changed.  So when the scriptjobs
#are first setup, their attribute values are stored in this dict and are updated when they change
PRE_ATTR_VALUES = {}


class AttrpathCallback(object):
	'''
	callable object that gets executed when the value of the attrpath changes
	'''

	#defines whether the instance should early out when called or not
	ENABLED = True

	def __init__( self, attrpath ):
		self.attrpath = attrpath

		#setup the initial value of the attrpath in the global attr value dict
		time = currentTime( q=True )
		PRE_ATTR_VALUES[ (time, attrpath) ] = getAttr( attrpath )
	def __call__( self ):
		if not self.ENABLED:
			return

		attrpath = self.attrpath
		time = currentTime( q=True )

		#if the time/attrpath tuple isn't in PRE_ATTR_VALUES, bail
		if (time, attrpath) not in PRE_ATTR_VALUES:
			return

		preValue = PRE_ATTR_VALUES[ (time, attrpath) ]
		curValue = getAttr( attrpath )
		valueDelta = curValue - preValue

		#if there was no delta, bail
		if not valueDelta:
			return

		#reset the value in the attr dict
		PRE_ATTR_VALUES[ (time, attrpath) ] = curValue

		#update keyframe not on this frame
		keyTimes = keyframe( attrpath, q=True, tc=True )
		if keyTimes is None:
			return

		if time in keyTimes:
			keyTimes.remove( time )

		for keyTime in keyTimes:
			keyValue = keyframe( attrpath, q=True, t=(keyTime,), vc=True )[0]
			keyframe( attrpath, e=True, t=(keyTime,), vc=keyValue + valueDelta )


class PosePropagatorLayout(MelHLayout):
	def __init__( self, parent ):
		MelHLayout.__init__( self, parent )

		self._state = False

		self.UI_dummyParent = None
		self.UI_on = MelButton( self, l='turn ON', c=self.on_enable )
		self.UI_off = MelButton( self, l='turn OFF', c=self.on_disable )

		self.layout()
		self.updateState()

		#fire the selection change to update the current selection state
		self.on_selectionChange()
		self.setSelectionChangeCB( self.on_selectionChange )
		self.setTimeChangeCB( self.on_timeChange )
	def setEnableState( self, state=True ):
		AttrpathCallback.ENABLED = state
		self.updateState()
	def updateState( self ):
		self.UI_on.setEnabled( not AttrpathCallback.ENABLED )
		self.UI_off.setEnabled( AttrpathCallback.ENABLED )

	### EVENT HANDLERS ###
	def on_enable( self, *a ):
		self.setEnableState( True )
	def on_disable( self, *a ):
		self.setEnableState( False )
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
				if objExists( attrpath ):
					UI_dummyParent.setAttributeChangeCB( attrpath, AttrpathCallback( attrpath ) )
	def on_timeChange( self ):
		'''
		when the time changes we need to refresh the values in the PRE_ATTR_VALUES dict
		'''
		time = currentTime( q=True )
		PRE_ATTR_VALUES.clear()
		for attrpath in PRE_ATTR_VALUES.keys():
			PRE_ATTR_VALUES[ (time, attrpath) ] = getAttr( attrpath )


class PosePropagatorWindow(BaseMelWindow):
	WINDOW_NAME = 'posePropagatorWindow'
	WINDOW_TITLE = 'Pose Propagator'

	DEFAULT_MENU = None
	DEFAULT_SIZE = 275, 60
	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		self.UI_editor = PosePropagatorLayout( self )
		self.UI_editor.setEnableState( AttrpathCallback.ENABLED )
		self.show()


#end
