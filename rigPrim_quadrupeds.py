
from rigPrim_ikFkBase import *
from rigPrim_stretchy import StretchRig


class QuadrupedIkFkLeg(IkFkBase):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'QuadrupedFrontLeg' ), SkeletonPart.GetNamedSubclass( 'QuadrupedBackLeg' ) )
	CONTROL_NAMES = 'control', 'poleControl', 'clavicle'

	DISPLAY_NAME = 'Quadruped Leg'

	def _build( self, skeletonPart, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return self.doBuild( *items, **kw )
	def doBuild( self, thigh, knee, ankle, clavicle, **kw ):
		idx = kw[ 'idx' ]
		scale = kw[ 'scale' ]

		parity = Parity( idx )
		parityMult = parity.asMultiplier()

		nameMod = kw.get( 'nameMod', 'front' )
		nameSuffix = '%s%s' % (nameMod.capitalize(), parity.asName())
		colour = self.getParityColour()

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


		#build the leg rig primitive
		self.buildBase( LEG_NAMING_SCHEME )
		legCtrl = self.control
		legFkSpace = self.fkSpace

		parent( legFkSpace, clavCtrl )

		poleSpace = getNodeParent( self.poleControl )
		pointConstraint( legFkSpace, legCtrl, poleSpace )


		### SETUP CLAVICLE AIM ###
		dummyGrp = group( em=True )
		delete( pointConstraint( clavicle, dummyGrp ) )
		parent( dummyGrp, rootControl )

		aimVector = BONE_AIM_VECTOR * parityMult
		sideClavAxis = getObjectAxisInDirection( clavCtrlSpace, BONE_AIM_VECTOR ).asVector()
		sideCtrlAxis = getObjectAxisInDirection( legCtrl, BONE_AIM_VECTOR ).asVector()

		aim = aimConstraint( legCtrl, clavCtrlSpace, aimVector=BONE_AIM_VECTOR, upVector=sideClavAxis, worldUpVector=sideCtrlAxis, worldUpObject=legCtrl, worldUpType='objectrotation', mo=True )[ 0 ]
		aimNode = aimConstraint( dummyGrp, clavCtrlSpace, weight=0, aimVector=BONE_AIM_VECTOR )[ 0 ]

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

		return legCtrl, self.poleControl, clavCtrl


class SatyrLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'SatyrLeg' ), )
	CONTROL_NAMES = 'control', 'poleControl', 'anklePoleControl'

	DISPLAY_NAME = 'Satyr Leg Rig'

	def _build( self, skeletonPart, stretchy=True, **kw ):
		thigh, knee, ankle, toe = skeletonPart[:4]

		idx = kw[ 'idx' ]
		scale = kw[ 'scale' ]

		parity = Parity( idx )
		parityMult = parity.asMultiplier()

		nameMod = kw.get( 'nameMod', 'front' )

		nameSuffix = '_%s%s' % (nameMod.capitalize(), parity.asName())

		colour = ColourDesc( 'red 0.7' ) if parity else ColourDesc( 'green 0.7' )

		#first rotate the foot so its aligned to a world axis
		footCtrlRot = getAnkleToWorldRotation( toe, 'z', False )
		rotate( 0, footCtrlRot[1], 0, toe, ws=True, r=True )

		#determine the root
		partParent, rootControl = getParentAndRootControl( thigh )

		ikHandle = cmd.ikHandle( fs=1, sj=thigh, ee=ankle, solver='ikRPsolver' )[ 0 ]
		footCtrl = buildControl( 'Foot%s' % nameSuffix,
		                         PlaceDesc( toe, PlaceDesc.WORLD ),
		                         PivotModeDesc.MID,
			                     ShapeDesc( 'cube', axis=-AIM_AXIS if parity else AIM_AXIS ),
			                     colour, scale=scale )

		footCtrlSpace = getNodeParent( footCtrl )
		setAttr( '%s.rotateOrder' % footCtrl, 1 )
		setAttr( '%s.v' % ikHandle, 0 )
		attrState( ikHandle, 'v', *LOCK_HIDE )

		#build the pivots for the foot roll/rock attributes
		placers = skeletonPart.getPlacers()
		if placers:
			footRock_fwd = buildNullControl( 'footRock_forward_null', placers[0], parent=footCtrl )
			footRock_back = buildNullControl( 'footRock_backward_null', placers[1], parent=footRock_fwd )
			footRoll_inner = buildNullControl( 'footRoll_inner_null', placers[2], parent=footRock_back )
			footRoll_outer = buildNullControl( 'footRoll_outer_null', placers[3], parent=footRoll_inner )
		else:
			footRock_fwd = buildNullControl( 'footRock_forward_null', toe, parent=footCtrlSpace )
			footRock_back = buildNullControl( 'footRock_backward_null', toe, parent=footCtrlSpace )
			footRoll_inner = buildNullControl( 'footRoll_inner_null', toe, parent=footCtrlSpace )
			footRoll_outer = buildNullControl( 'footRoll_outer_null', toe, parent=footCtrlSpace )
			toePos = xform( toe, q=True, ws=True, rp=True )
			moveIncrement = scale / 2
			move( 0, -toePos[1], moveIncrement, footRock_fwd, r=True, ws=True )
			move( 0, -toePos[1], -moveIncrement, footRock_back, r=True, ws=True )
			move( -moveIncrement * parityMult, -toePos[1], 0, footRoll_inner, r=True, ws=True )
			move( moveIncrement * parityMult, -toePos[1], 0, footRoll_outer, r=True, ws=True )
			cmd.parent( footRock_back, footRock_fwd )
			cmd.parent( footRoll_inner, footRock_back )
			cmd.parent( footRoll_outer, footRoll_inner )

		cmd.parent( footCtrl, footRoll_outer )
		makeIdentity( footCtrl, a=True, t=True )

		addAttr( footCtrl, ln='footRock', at='double', dv=0, min=-10, max=10 )
		attrState( footCtrl, 'footRock', *NORMAL )

		setDrivenKeyframe( '%s.rx' % footRock_fwd, cd='%s.footRock' % footCtrl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rx' % footRock_fwd, cd='%s.footRock' % footCtrl, dv=10, v=90 )
		setDrivenKeyframe( '%s.rx' % footRock_back, cd='%s.footRock' % footCtrl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rx' % footRock_back, cd='%s.footRock' % footCtrl, dv=-10, v=-90 )

		addAttr( footCtrl, ln='bank', at='double', dv=0, min=-10, max=10 )
		attrState( footCtrl, 'bank', *NORMAL )

		setDrivenKeyframe( '%s.rz' % footRoll_inner, cd='%s.bank' % footCtrl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rz' % footRoll_inner, cd='%s.bank' % footCtrl, dv=10, v=90 )
		setDrivenKeyframe( '%s.rz' % footRoll_outer, cd='%s.bank' % footCtrl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rz' % footRoll_outer, cd='%s.bank' % footCtrl, dv=-10, v=-90 )

		#setup the auto ankle
		grpA = buildControl( 'ankle_auto_null', PlaceDesc( toe, ankle ), shapeDesc=SHAPE_NULL, constrain=False, parent=footCtrl )
		grpB = buildAlignedNull( ankle, 'ankle_orientation_null', parent=grpA )

		orientConstraint( grpB, ankle )
		for ax in AXES:
			delete( '%s.t%s' % (toe, ax), icn=True )

		cmd.parent( ikHandle, grpA )
		cmd.parent( footCtrlSpace, self.getWorldControl() )

		grpASpace = getNodeParent( grpA )
		grpAAutoNull = buildAlignedNull( PlaceDesc( toe, ankle ), '%sauto_on_ankle_null%s' % (nameMod, nameSuffix), parent=footCtrl )
		grpAAutoOffNull = buildAlignedNull( PlaceDesc( toe, ankle ), '%sauto_off_ankle_null%s' % (nameMod, nameSuffix), parent=footCtrl )
		grpA_knee_aimVector = betweenVector( grpAAutoNull, knee )
		grpA_knee_aimAxis = getObjectAxisInDirection( grpAAutoNull, grpA_knee_aimVector )
		grpA_knee_upAxis = getObjectAxisInDirection( grpAAutoNull, (1, 0, 0) )
		grpA_knee_worldAxis = getObjectAxisInDirection( footCtrl, (1, 0, 0) )
		aimConstraint( thigh, grpAAutoNull, mo=True, aim=grpA_knee_aimAxis.asVector(), u=grpA_knee_upAxis.asVector(), wu=grpA_knee_worldAxis.asVector(), wuo=footCtrl, wut='objectrotation' )

		autoAimConstraint = orientConstraint( grpAAutoNull, grpAAutoOffNull, grpASpace )[0]
		addAttr( footCtrl, ln='autoAnkle', at='double', dv=1, min=0, max=1 )
		attrState( footCtrl, 'autoAnkle', *NORMAL )

		cAttrs = listAttr( autoAimConstraint, ud=True )
		connectAttr( '%s.autoAnkle' % footCtrl, '%s.%s' % (autoAimConstraint, cAttrs[0]), f=True )
		connectAttrReverse( '%s.autoAnkle' % footCtrl, '%s.%s' % (autoAimConstraint, cAttrs[1]), f=True )

		poleCtrl = buildControl( 'Pole%s' % nameSuffix,
		                         PlaceDesc( knee, PlaceDesc.WORLD ), PivotModeDesc.MID,
		                         shapeDesc=ShapeDesc( 'sphere', axis=-AIM_AXIS if parity else AIM_AXIS ),
		                         colour=colour, constrain=False, scale=scale, parent=self.getPartsNode() )

		poleCtrlSpace = getNodeParent( poleCtrl )
		polePos = findPolePosition( ankle )
		move( polePos[0], polePos[1], polePos[2], poleCtrlSpace, ws=True, rpr=True, a=True )
		pointConstraint( thigh, footCtrl, poleCtrlSpace, mo=True )

		poleVectorConstraint( poleCtrl, ikHandle )

		#build the ankle aim control - its acts kinda like a secondary pole vector
		anklePoleControl = buildControl( 'Ankle%s' % nameSuffix, ankle, shapeDesc=ShapeDesc( 'sphere' ), colour=colour, scale=scale, constrain=False, parent=grpASpace )

		ankleAimVector = betweenVector( grpA, anklePoleControl )
		ankleAimAxis = getObjectAxisInDirection( grpA, ankleAimVector )
		ankleUpAxis = getObjectAxisInDirection( grpA, (1, 0, 0) )
		ankleWorldUpAxis = getObjectAxisInDirection( anklePoleControl, (1, 0, 0) )
		aimConstraint( anklePoleControl, grpA, aim=ankleAimAxis.asVector(), u=ankleUpAxis.asVector(), wu=ankleWorldUpAxis.asVector(), wuo=anklePoleControl, wut='objectrotation' )

		if stretchy:
			StretchRig.Create( self._skeletonPart, footCtrl, (thigh, knee, ankle, toe), '%s.ikBlend' % ikHandle, parity=parity, connectEndJoint=True )
			for ax in CHANNELS:
				delete( '%s.t%s' % (toe, ax), icn=True )

			pointConstraint( footCtrl, toe )

		buildDefaultSpaceSwitching( thigh, footCtrl, reverseHierarchy=True, space=footCtrlSpace )

		return [ footCtrl, poleCtrl, anklePoleControl ]


#end
