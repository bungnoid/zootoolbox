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

	clavCtrlSpace = clavCtrl.getParent()
	clavCtrl.rotateOrder.set( 1 )

	pymelCore.parent( clavCtrlSpace, partParent )


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
	sideClavAxis = utils.getObjectAxisInDirection( clavCtrlSpace, Vector( 1, 0, 0 ) ).asVector()
	sideCtrlAxis = utils.getObjectAxisInDirection( legCtrl, Vector( 1, 0, 0 ) ).asVector()

	aim = aimConstraint( legCtrl, clavCtrlSpace, aimVector=(1,0,0), upVector=sideClavAxis, worldUpVector=sideCtrlAxis, worldUpObject=legCtrl, worldUpType='objectrotation', mo=True )
	aimNode = aimConstraint( dummyGrp, clavCtrlSpace, weight=0, aimVector=(1,0,0) )

	revNode = createNode( 'reverse' )
	clavCtrl.addAttr( 'autoMotion', at='float', min=0, max=1, dv=1 )
	clavCtrl.autoMotion.setKeyable( True )

	connectAttr( clavCtrl.autoMotion, aimNode.target[0].targetWeight, f=True )
	connectAttr( clavCtrl.autoMotion, revNode.inputX, f=True )
	connectAttr( revNode.outputX, aimNode.target[1].targetWeight, f=True )


	### HOOK UP A FADE FOR THE AIM OFFSET
	mt, measure, la, lb = utils.buildMeasure( str( clavCtrlSpace ), str( legCtrl ) )
	maxLen = utils.chainLength( clavicle, ankle )
	curLen = getAttr( measure.distance )

	pymelCore.parent( la, rootControl )
	pymelCore.parent( mt, rootControl )

	for c in [ mt, la, lb ]:
		c.v.set( False )
		c.v.setLocked( True )

	return legCtrl, ikFkPart.poleControl, clavCtrl


#end
