from rigPrim_ikFkBase import *


class QuadrupedIkFkLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( QuadrupedFrontLeg, QuadrupedBackLeg )
	CONTROL_NAMES = 'control', 'poleControl', 'clavicle'

	DISPLAY_NAME = 'Quadruped Leg'

	@classmethod
	def _build( cls, skeletonPart, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return quadrupedIkFkLeg( *items, **kw )


def quadrupedIkFkLeg( thigh, knee, ankle, clavicle, **kw ):
	idx = kw[ 'idx' ]
	scale = kw[ 'scale' ]

	parity = Parity( idx )
	parityMult = parity.asMultiplier()

	nameMod = kw.get( 'nameMod', 'front' )

	worldPart = WorldPart.Create()
	worldControl, partsControl = worldPart.control, worldPart.parts

	nameSuffix = '%s%s' % (nameMod.capitalize(), parity.asName())

	colour = ColourDesc( 'red 0.7' ) if parity else ColourDesc( 'green 0.7' )

	#determine the root
	partParent, rootControl = getParentAndRootControl( clavicle )

	#build out the control for the clavicle
	clavCtrl = buildControl( 'quadClavicle%s' % nameSuffix,
                             PlaceDesc( clavicle ),
                             PivotModeDesc.BASE,
                             ShapeDesc( 'cylinder', axis=-AIM_AXIS if parity else AIM_AXIS ),
                             colour, scale=scale )

	clavCtrlSpace = getNodeParent( clavCtrl )
	setAttr( '%s.rotateOrder' % clavCtrl, 1 )

	cmd.parent( clavCtrlSpace, partParent )


	### BUILD THE LEG RIG PRIMITIVE ###
	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, thigh, knee, ankle, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )

	legCtrl = ikFkPart.control
	legFkSpace = ikFkPart.fkSpace

	parent( legFkSpace, clavCtrl )


	### SETUP CLAVICLE AIM ###
	dummyGrp = group( em=True )
	delete( pointConstraint( clavicle, dummyGrp ) )
	parent( dummyGrp, rootControl )

	aimVector = BONE_AIM_AXIS * parityMult
	sideClavAxis = getObjectAxisInDirection( clavCtrlSpace, Vector( (1, 0, 0) ) ).asVector()
	sideCtrlAxis = getObjectAxisInDirection( legCtrl, Vector( (1, 0, 0) ) ).asVector()

	aim = aimConstraint( legCtrl, clavCtrlSpace, aimVector=(1,0,0), upVector=sideClavAxis, worldUpVector=sideCtrlAxis, worldUpObject=legCtrl, worldUpType='objectrotation', mo=True )[ 0 ]
	aimNode = aimConstraint( dummyGrp, clavCtrlSpace, weight=0, aimVector=(1,0,0) )[ 0 ]

	revNode = createNode( 'reverse' )
	addAttr( clavCtrl, ln='autoMotion', at='float', min=0, max=1, dv=1 )
	setAttr( '%s.autoMotion' % clavCtrl, keyable=True )

	connectAttr( '%s.autoMotion' % clavCtrl, '%s.target[0].targetWeight' % aimNode, f=True )
	connectAttr( '%s.autoMotion' % clavCtrl, '%s.inputX' % revNode, f=True )
	connectAttr( '%s.outputX' % revNode, '%s.target[1].targetWeight' % aimNode, f=True )


	### HOOK UP A FADE FOR THE AIM OFFSET
	mt, measure, la, lb = buildMeasure( str( clavCtrlSpace ), str( legCtrl ) )
	maxLen = chainLength( clavicle, ankle )
	curLen = getAttr( '%s.distance' % measure )

	cmd.parent( la, rootControl )
	cmd.parent( mt, rootControl )

	for c in [ mt, la, lb ]:
		setAttr( '%s.v' % c, False )
		setAttr( '%s.v' % c, lock=True )

	return legCtrl, ikFkPart.poleControl, clavCtrl


#end
