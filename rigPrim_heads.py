from rigPrim_base import *


class Head(RigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( skeletonBuilderCore.Head, )
	CONTROL_NAMES = 'control', 'gimbal', 'neck'

	@classmethod
	def _build( cls, skeletonPart, **kw ):
		return head( skeletonPart.head, **kw )


def head( head, neckCount=1, **kw ):
	scale = kw[ 'scale' ]

	partParent, rootControl = getParentAndRootControl( head )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts

	colour = ColourDesc( 'blue' )
	lightBlue = ColourDesc( 'lightblue' )


	#build the head controls - we always need them
	headControl = buildControl( "headControl", head,
	                            shapeDesc=Shape_Skin( [head] + listRelatives( head, ad=True, type='joint' ) ),
	                            colour=colour, scale=scale )

	headControlSpace = headControl.getParent()
	headGimbal = buildControl( "head_gimbalControl", head, shapeDesc=ShapeDesc( None, 'starCircle' ), colour=colour, oriented=False, scale=scale, autoScale=True, parent=headControl, niceName='Head' )


	#now find the neck joints
	neckJoints = []
	curParent = head
	for n in range( neckCount ):
		curParent = curParent.getParent()
		neckJoints.append( curParent )

	neckJoints.reverse()


	#determine an offset amount for the neck controls based on the geometry skinned to the necks and head joint
	neckOffset = AX_Z.asVector() * getAutoOffsetAmount( head, neckJoints )


	#build the controls for them
	neckControls = []
	theParent = partParent
	for n, j in enumerate( neckJoints ):
		c = buildControl( 'neck_%d_Control' % n, j, PivotModeDesc.BASE, ShapeDesc( 'pin', axis=AX_Z ), colour=lightBlue, scale=scale*1.5, offset=neckOffset, parent=theParent, niceName='Neck %d' % n )
		attrState( c, 't', *LOCK_HIDE )

		theParent = c
		neckControls.append( c )

	if neckCount == 1:
		neckControls[ 0 ].rename( 'neckControl' )
		setNiceName( neckControls[ 0 ], 'Neck' )
	elif neckCount >= 2:
		setNiceName( neckControls[ 0 ], 'Neck Base' )
		setNiceName( neckControls[ -1 ], 'Neck End' )

	if neckCount:
		parent( headControlSpace, neckControls[ -1 ] )
	else:
		parent( headControlSpace, partParent )


	#build space switching
	spaceSwitching.build( headControl,
	                      (neckControls[ 0 ], partParent, rootControl, worldControl),
	                      space=headControlSpace, **spaceSwitching.NO_TRANSLATION )

	for c in neckControls:
		spaceSwitching.build( c,
		                      (partParent, rootControl, worldControl),
			                  **spaceSwitching.NO_TRANSLATION )


	#add right click menu to turn on the gimbal control
	gimbalIdx = Trigger( headControl ).connect( headGimbal )
	Trigger.CreateMenu( headControl,
		                "toggle gimbal control",
		                "string $shapes[] = `listRelatives -f -s %%%d`;\nint $vis = `getAttr ( $shapes[0] +\".v\" )`;\nfor( $s in $shapes ) setAttr ( $s +\".v\" ) (!$vis);" % gimbalIdx )


	#turn unwanted transforms off, so that they are locked, and no longer keyable, and set rotation orders
	gimbalShapes = listRelatives( headGimbal, s=True )
	for s in gimbalShapes:
		s.v.set( 0 )

	headControl.ro.set( 3 )
	headGimbal.ro.set( 3 )

	attrState( (headControl, headGimbal), 't', *LOCK_HIDE )


	return [ headControl, headGimbal ] + neckControls


#end
