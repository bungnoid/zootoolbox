
from maya.cmds import *

from baseMelUI import *
from filesystem import removeDupes
from rigUtils import MATRIX_ROTATION_ORDER_CONVERSIONS_FROM, MATRIX_ROTATION_ORDER_CONVERSIONS_TO, \
     MAYA_ROTATION_ORDERS, ROO_XYZ, ROO_YZX, ROO_ZXY, ROO_XZY, ROO_YXZ, ROO_ZYX
from profileDecorators import d_timer
from mayaDecorators import d_disableViews, d_noAutoKey, d_unifyUndo, d_restoreTime
from common import printWarningStr

ROTATION_ORDER_STRS = XYZ, YZX, ZXY, XZY, YXZ, ZYX = 'xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx'


@d_unifyUndo
@d_disableViews
@d_noAutoKey
@d_restoreTime
def changeRo( objs=None, ro=XYZ ):
	if ro not in ROTATION_ORDER_STRS:
		raise TypeError( "need to specify a valid rotation order - one of: %s" % ' '.join( ROTATION_ORDER_STRS ) )

	if objs is None:
		objs = ls( sl=True, type='transform' )

	roIdx = list( ROTATION_ORDER_STRS ).index( ro )

	#filter out objects that don't have all 3 rotation axes settable and while we're at it store the rotation orders for each object
	#in a dict - since accessing a python dict is WAY faster than doing a getAttr for each frame in the loop below
	RO_DICT = {}
	objsWithAllChannelsSettable = []

	for obj in objs:
		if not getAttr( '%s.r' % obj, se=True ):
			printWarningStr( "Not all rotation axes on the object %s are settable - skipping!" % obj )
			continue

		objRo = getAttr( '%s.ro' % obj )

		#if the rotation order of this object is the same as what we're changing it to - skip the object entirely
		if objRo == roIdx:
			printWarningStr( "The object %s already has the rotation order %s - skipping!" % (obj, ro) )
			continue

		RO_DICT[ obj ] = objRo
		objsWithAllChannelsSettable.append( obj )

	#early out if we have no objects to work on
	objs = objsWithAllChannelsSettable
	if not objs:
		printWarningStr( "No objects to act on - exiting" )
		return

	#first we need to make sure that any frame with a rotation key needs to have a key on ALL rotation axes - so make this happen
	keyTimes = keyframe( objs, q=True, at='r', tc=True )
	if not keyTimes:
		printWarningStr( "No keys found on the objects - nothing to do!" )
		return

	#remove duplicate key times and sort them
	keyTimes = removeDupes( keyTimes )
	keyTimes.sort()

	#cache out the conversion method
	convertToMethod = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ roIdx ]

	#store the objects that each have keys at each key time in a dict so we don't have to query maya again. maya queries are slower than accessing python data structures
	timeObjs = {}
	for time in keyTimes:
		currentTime( time, e=True )
		timeObjs[ time ] = objsWithKeysAtThisTime = []
		for obj in objs:
			keyOnCurrentTime = keyframe( obj, q=True, t=(time,), kc=True )
			if keyOnCurrentTime:
				setKeyframe( obj, at='r' )
				objsWithKeysAtThisTime.append( obj )

	#now that we're secured the rotation poses with keys on all axes, fix up each rotation value to use the desired rotation order
	for time, objsWithKeysAtThisTime in timeObjs.iteritems():
		currentTime( time, e=True )
		for obj in objsWithKeysAtThisTime:
			currentRoIdx = RO_DICT[ obj ]

			rot = getAttr( '%s.r' % obj )[0]
			rotMatrix = MATRIX_ROTATION_ORDER_CONVERSIONS_FROM[ currentRoIdx ]( degrees=True, *rot )

			newRot = convertToMethod( rotMatrix, True )
			setAttr( '%s.r' % obj, *newRot )
			setKeyframe( obj, at='r' )

	#now change the rotation order to what it should be
	for obj in objs:
		setAttr( '%s.ro' % obj, roIdx )


class ChangeRoLayout(MelColumnLayout):
	def __init__( self, parent ):
		hLayout = MelHLayout( self )
		lbl = MelLabel( hLayout, l='New Rotate Order', h=25 )
		self.UI_rotateOrders = UI_rotateOrders = MelOptionMenu( hLayout )

		for roStr in ROTATION_ORDER_STRS:
			UI_rotateOrders.append( roStr )

		hLayout.layout()
		hLayout( e=True, af=((lbl, 'top', 0), (lbl, 'bottom', 0)) )

		self.UI_go = MelButton( self, l='Change Rotate Order', c=self.on_go )

		#setup selection change callbacks and trigger it for the initial selection
		self.on_selectionChange()
		self.setSelectionChangeCB( self.on_selectionChange )

	### EVENT HANDLERS ###
	def on_selectionChange( self, *a ):
		for obj in ls( sl=True, type='transform' ) or []:
			if objExists( '%s.ro' % obj ):
				ro = getAttr( '%s.ro' % obj )
				self.UI_rotateOrders.selectByIdx( ro )

				self.UI_go.setEnabled( True )

				return

		self.UI_go.setEnabled( False )
	def on_go( self, *a ):
		roStr = self.UI_rotateOrders.getValue()
		changeRo( ro=roStr )


class ChangeRoWindow(BaseMelWindow):
	WINDOW_NAME = 'ChangeRooTool'
	WINDOW_TITLE = 'Change Rotate Order For Animated Nodes'

	DEFAULT_SIZE = 375, 90
	DEFAULT_MENU = None

	def __init__( self ):
		self.UI_editor = ChangeRoLayout( self )
		self.show()


#end
