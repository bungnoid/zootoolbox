
from rigPrim_ikFkBase import *
from rigPrim_stretchy import StretchRig


class IkFkArm(PrimaryRigPart):
	__version__ = 1
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'Arm' ), )
	CONTROL_NAMES = 'control', 'fkBicep', 'fkElbow', 'fkWrist', 'poleControl', 'clavicle', 'allPurpose', 'poleTrigger'

	def _build( self, skeletonPart, translateClavicle=True, stretchy=True, **kw ):
		return self.doBuild( skeletonPart.bicep, skeletonPart.elbow, skeletonPart.wrist, skeletonPart.clavicle, translateClavicle, stretchy, **kw )
	def doBuild( self, bicep, elbow, wrist, clavicle=None, translateClavicle=True, stretchy=False, **kw ):
		scale = kw[ 'scale' ]

		idx = kw[ 'idx' ]
		parity = Parity( idx )
		getWristToWorldRotation( wrist, True )

		colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

		worldPart = WorldPart.Create()
		worldControl = worldPart.control
		partsControl = worldPart.parts

		parentControl, rootControl = getParentAndRootControl( clavicle or bicep )


		ikFkPart = IkFkBase.Create( self.getSkeletonPart(), **kw )

		#create variables for each control used
		armControl = asMObject( ikFkPart.control )
		ikHandle = asMObject( ikFkPart.ikHandle )
		ikArmSpace = asMObject( ikFkPart.ikSpace )
		fkArmSpace = asMObject( ikFkPart.fkSpace )
		driverBicep = asMObject( ikFkPart.fkUpper )
		driverElbow = asMObject( ikFkPart.fkMid )
		driverWrist = asMObject( ikFkPart.fkLower )
		elbowControl = asMObject( ikFkPart.poleControl )
		fkControls = driverBicep, driverElbow, driverWrist


		#build the clavicle
		if clavicle:
			clavOffset = AX_Y.asVector() * getAutoOffsetAmount( clavicle, listRelatives( clavicle, pa=True ), AX_Y )
			clavControl = buildControl( 'clavicleControl%s' % parity.asName(), PlaceDesc( bicep, clavicle, clavicle ), shapeDesc=ShapeDesc( 'sphere' ), scale=scale*1.25, offset=clavOffset, offsetSpace=SPACE_WORLD, colour=colour )
			clavControlOrient = getNodeParent( clavControl )

			parent( clavControlOrient, parentControl )
			parent( fkArmSpace, clavControl )
			if not translateClavicle:
				attrState( clavControl, 't', *LOCK_HIDE )
		else:
			clavControl = None
			parent( fkArmSpace, parentControl )


		#build space switching
		allPurposeObj = spaceLocator()[ 0 ]
		allPurposeObj = rename( allPurposeObj, "arm_all_purpose_loc%s" % parity.asName() )
		attrState( allPurposeObj, 's', *LOCK_HIDE )
		attrState( allPurposeObj, 'v', *HIDE )
		parent( allPurposeObj, worldControl )

		buildDefaultSpaceSwitching( bicep, armControl, [ allPurposeObj ], [ 'All Purpose' ], True )
		buildDefaultSpaceSwitching( bicep, driverBicep, **spaceSwitching.NO_TRANSLATION )


		#make the limb stretchy?
		if stretchy:
			StretchRig.Create( self._skeletonPart, armControl, fkControls, '%s.ikBlend' % ikHandle, parity=parity )


		return armControl, driverBicep, driverElbow, driverWrist, elbowControl, clavControl, allPurposeObj, ikFkPart.poleTrigger


class IkFkLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'Leg' ), )
	CONTROL_NAMES = 'control', 'fkThigh', 'fkKnee', 'fkAnkle', 'poleControl', 'allPurpose', 'poleTrigger'

	def _build( self, skeletonPart, stretchy=True, **kw ):
		return self.doBuild( skeletonPart.thigh, skeletonPart.knee, skeletonPart.ankle, stretchy=stretchy, **kw )
	def doBuild( self, thigh, knee, ankle, stretchy=True, **kw ):
		skeletonPart = self._skeletonPart
		scale = kw[ 'scale' ]

		idx = kw[ 'idx' ]
		parity = Parity( idx )
		parityMult = parity.asMultiplier()
		suffix = parity.asName()

		colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

		worldPart = WorldPart.Create()
		worldControl = worldPart.control
		partsControl = worldPart.parts


		#first rotate the foot so its aligned to a world axis
		footCtrlRot = Vector( getAnkleToWorldRotation( str( ankle ), 'z', True ) )
		footCtrlRot = (0, -footCtrlRot.y, 0)


		### BUILD THE IKFK BASE
		ikFkPart = IkFkBase.Create( self.getSkeletonPart(), nameScheme=LEG_NAMING_SCHEME, alignEnd=False, addControlsToQss=False, **kw )


		partParent, rootControl = getParentAndRootControl( thigh )

		#if the legs are parented to a root part - which is usually the case but not always - grab the hips and parent the fk control space to the hips
		hipsControl = partParent
		partParentRigPart = RigPart.InitFromItem( partParent )
		if isinstance( partParentRigPart.getSkeletonPart(), Root ):
			hipsControl = partParentRigPart.hips


		#if the part parent in a Root primitive, grab the hips control instead of the root gimbal - for the leg parts this is preferable
		parentRigPart = RigPart.InitFromItem( partParent )
		if isinstance( parentRigPart, Root ):
			partParent = parentRigPart.hips


		#create variables for each control used
		legControl = ikFkPart.control
		legControlSpace = getNodeParent( legControl )

		ikLegSpace = ikFkPart.ikSpace
		fkLegSpace = ikFkPart.fkSpace
		driverThigh = ikFkPart.fkUpper
		driverKnee = ikFkPart.fkMid
		driverAnkle = ikFkPart.fkLower
		ikHandle = ikFkPart.ikHandle
		kneeControl = ikFkPart.poleControl
		kneeControlSpace = getNodeParent( kneeControl )
		toe = listRelatives( ankle, type='joint', pa=True ) or None
		toeTip = None

		if toe:
			toe = toe[0]

		fkControls = driverThigh, driverKnee, driverAnkle


		#if the toe doesn't exist, build a temp one
		if not toe:
			toe = group( em=True )
			parent( toe, ankle, r=True )
			move( 0, -scale, scale, toe, r=True, ws=True )


		toeTip = skeletonPart.endPlacer
		if not toeTip:
			possibleTips = listRelatives( toe, type='joint', pa=True )
			if possibleTips:
				toeTip = possibleTips[ 0 ]



		#build the objects to control the foot
		footControlSpace = buildNullControl( "foot_controlSpace"+ suffix, ankle, parent=legControl )
		heelRoll = buildNullControl( "heel_roll_piv"+ suffix, ankle, offset=(0, 0, -scale) )
		footBankL = buildNullControl( "bank_in_piv"+ suffix, toe )
		footBankR = buildNullControl( "bank_out_piv"+ suffix, toe )
		footRollControl = buildNullControl( "roll_piv"+ suffix, toe )
		toeOrient = buildNullControl( "toe_orient_piv"+ suffix, toe )

		if toeTip:
			toeRoll = buildNullControl( "leg_toe_roll_piv"+ suffix, toeTip )
		else:
			toeRoll = buildNullControl( "leg_toe_roll_piv"+ suffix, toe, offset=(0, 0, scale) )

		select( heelRoll )  #stupid move command doesn't support object naming when specifying a single axis move, so we must selec the object first
		move( 0, 0, 0, rpr=True, y=True )


		#move bank pivots to a good spot on the ground
		placers = skeletonPart.getPlacers()
		numPlacers = len( placers )
		if placers:
			toePos = Vector( xform( toe, q=True, ws=True, rp=True ) )
			if numPlacers >= 2:
				innerPlacer = Vector( xform( placers[1], q=True, ws=True, rp=True ) )
				move( innerPlacer[0], innerPlacer[1], innerPlacer[2], footBankL, a=True, ws=True, rpr=True )

			if numPlacers >= 3:
				outerPlacer = Vector( xform( placers[2], q=True, ws=True, rp=True ) )
				move( outerPlacer[0], outerPlacer[1], outerPlacer[2], footBankR, a=True, ws=True, rpr=True )

			if numPlacers >= 4:
				heelPlacer = Vector( xform( placers[3], q=True, ws=True, rp=True ) )
				move( heelPlacer[0], heelPlacer[1], heelPlacer[2], heelRoll, a=True, ws=True, rpr=True )

		#parent the leg pivots together
		parent( kneeControlSpace, partParent )

		parent( heelRoll, footControlSpace )
		parent( toeRoll, heelRoll )
		parent( footBankL, toeRoll )
		parent( footBankR, footBankL )
		parent( footRollControl, footBankR )
		parent( toeOrient, footBankR )
		if toe:
			orientConstraint( toeOrient, toe, mo=True )

		makeIdentity( heelRoll, apply=True, t=True, r=True )


		#move the knee control so its inline with the leg
		rotate( footCtrlRot[0], footCtrlRot[1], footCtrlRot[2], kneeControlSpace, p=xform( thigh, q=True, ws=True, rp=True ), a=True, ws=True )
		makeIdentity( kneeControl, apply=True, t=True )


		#add attributes to the leg control, to control the pivots
		addAttr( legControl, ln='rollBall', at='double', min=0, max=10, k=True )
		addAttr( legControl, ln='rollToe', at='double', min=-10, max=10, k=True )
		addAttr( legControl, ln='twistFoot', at='double', min=-10, max=10, k=True )
		addAttr( legControl, ln='toe', at='double', min=-10, max=10, k=True )
		addAttr( legControl, ln='bank', at='double', min=-10, max=10, k=True )


		#replace the legControl as a target to teh parent constraint on the endOrient transform so the ikHandle respects the foot slider controls
		footFinalPivot = buildNullControl( "final_piv"+ suffix, ankle, parent=footRollControl )
		endOrientConstraint = listConnections( '%s.tx' % ikFkPart.endOrient, type='constraint', d=False )[ 0 ]
		#replaceConstraintTarget( endOrientConstraint, footFinalPivot )
		for attr in attributeQuery( 'target', node=endOrientConstraint, listChildren=True ):
			for con in listConnections( '%s.target[ 0 ].%s' % (endOrientConstraint, attr), p=True, type='transform', d=False ) or []:
				node = con.split( '.' )[ 0 ]
				if cmpNodes( node, legControl ):
					toks = str( con ).split( '.' )
					toks[ 0 ] = str( footFinalPivot )
					connectAttr( '.'.join( toks ), '%s.target[0].%s' % (endOrientConstraint, attr), f=True )

		delete( parentConstraint( footFinalPivot, ikHandle, mo=True ) )
		parent( ikHandle, footFinalPivot )


		#build the SDK's to control the pivots
		setDrivenKeyframe( '%s.rx' % footRollControl, cd='%s.rollBall' % legControl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rx' % footRollControl, cd='%s.rollBall' % legControl, dv=10, v=90 )
		setDrivenKeyframe( '%s.rx' % footRollControl, cd='%s.rollBall' % legControl, dv=-10, v=-90 )

		setDrivenKeyframe( '%s.rx' % toeRoll, cd='%s.rollToe' % legControl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rx' % toeRoll, cd='%s.rollToe' % legControl, dv=10, v=90 )
		setDrivenKeyframe( '%s.rx' % toeRoll, cd='%s.rollToe' % legControl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rx' % toeRoll, cd='%s.rollToe' % legControl, dv=-10, v=-90 )
		setDrivenKeyframe( '%s.ry' % toeRoll, cd='%s.twistFoot' % legControl, dv=-10, v=-90 )
		setDrivenKeyframe( '%s.ry' % toeRoll, cd='%s.twistFoot' % legControl, dv=10, v=90 )

		setDrivenKeyframe( '%s.rx' % toeOrient, cd='%s.toe' % legControl, dv=-10, v=90 )
		setDrivenKeyframe( '%s.rx' % toeOrient, cd='%s.toe' % legControl, dv=10, v=-90 )

		min = -90 if parity == Parity.LEFT else 90
		max = 90 if parity == Parity.LEFT else -90
		setDrivenKeyframe( '%s.rz' % footBankL, cd='%s.bank' % legControl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rz' % footBankL, cd='%s.bank' % legControl, dv=10, v=max )
		setDrivenKeyframe( '%s.rz' % footBankR, cd='%s.bank' % legControl, dv=0, v=0 )
		setDrivenKeyframe( '%s.rz' % footBankR, cd='%s.bank' % legControl, dv=-10, v=min )


		#build all purpose
		allPurposeObj = spaceLocator( name="leg_all_purpose_loc%s" % suffix )[ 0 ]
		attrState( allPurposeObj, 's', *LOCK_HIDE )
		attrState( allPurposeObj, 'v', *HIDE )
		parent( allPurposeObj, worldControl )


		#build space switching
		parent( fkLegSpace, hipsControl )
		spaceSwitching.build( legControl, (worldControl, hipsControl, rootControl, allPurposeObj), ('World', None, 'Root', 'All Purpose'), space=legControlSpace )
		spaceSwitching.build( kneeControl, (legControl, partParent, rootControl, worldControl), ("Leg", None, "Root", "World"), **spaceSwitching.NO_ROTATION )
		spaceSwitching.build( driverThigh, (hipsControl, rootControl, worldControl), (None, 'Root', 'World'), **spaceSwitching.NO_TRANSLATION )


		#make the limb stretchy
		if stretchy:
			StretchRig.Create( self._skeletonPart, legControl, fkControls, '%s.ikBlend' % ikHandle, parity=parity )
			renameAttr( '%s.elbowPos' % legControl, 'kneePos' )


		return legControl, driverThigh, driverKnee, driverAnkle, kneeControl, allPurposeObj, ikFkPart.poleTrigger


#end
