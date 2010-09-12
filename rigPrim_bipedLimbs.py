from rigPrim_ikFkBase import *


class IkFkArm(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Arm, )
	CONTROL_NAMES = 'control', 'fkBicep', 'fkElbow', 'fkWrist', 'poleControl', 'clavicle', 'allPurpose', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, stretchy=False, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return ikFkArm( stretchy=stretchy, *items, **kw )


def ikFkArm( bicep, elbow, wrist, clavicle=None, stretchy=True, **kw ):
	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	getWristToWorldRotation( wrist, True )

	colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts

	parentControl, rootControl = getParentAndRootControl( clavicle or bicep )


	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, bicep, elbow, wrist, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )

	#create variables for each control used
	armControl = ikFkPart.control
	ikHandle = ikFkPart.ikHandle
	ikArmSpace = ikFkPart.ikSpace
	fkArmSpace = ikFkPart.fkSpace
	driverBicep = ikFkPart.fkUpper
	driverElbow = ikFkPart.fkMid
	driverWrist = ikFkPart.fkLower
	elbowControl = ikFkPart.poleControl
	fkControls = driverBicep, driverElbow, driverWrist


	#build the clavicle
	if clavicle:
		clavOffset = AX_Y.asVector() * getAutoOffsetAmount( clavicle, clavicle.getChildren(), AX_Y )
		clavControl = buildControl( 'clavicleControl%s' % parity.asName(), PlaceDesc( bicep, clavicle, clavicle ), shapeDesc=ShapeDesc( 'sphere' ), scale=scale*1.25, offset=clavOffset, offsetSpace=WORLD, colour=colour )
		clavControlOrient = clavControl.getParent()

		parent( clavControlOrient, parentControl )
		parent( fkArmSpace, clavControl )
		attrState( clavControl, 't', *LOCK_HIDE )
	else:
		clavControl = None
		parent( fkArmSpace, parentControl )


	#build space switching
	allPurposeObj = spaceLocator()
	allPurposeObj.rename( "arm_all_purpose_loc%s" % parity.asName() )
	parent( allPurposeObj, worldControl )

	buildDefaultSpaceSwitching( bicep, armControl, [ allPurposeObj ], [ 'All Purpose' ], True )
	buildDefaultSpaceSwitching( bicep, driverBicep, **spaceSwitching.NO_TRANSLATION )


	##make the limb stretchy?
	#if stretchy:
		#makeStretchy( armControl, ikHandle, "-axis x -parts %s" % str( partsControl ) )


	return armControl, driverBicep, driverElbow, driverWrist, elbowControl, clavControl, allPurposeObj, ikFkPart.poleTrigger


def makeStretchy( control, ikHandle, axis=BONE_AIM_AXIS, startObj=None, endObj=None, parity=Parity.LEFT, elbowPos=1 ):
	'''
	creates stretch attribs on the $control object, and makes all joints controlled by the ikHandle stretchy
	-------

	$control - the character prefix used to identify the character
	$parity - which side is the arm on?  l (left) or r (right)
	$ikHandle - the bicep, upper arm, or humerous
	$optionStr - standard option string - see technical docs for info on option strings

	option flags
	-------
	-axis [string]			the stretch axis used by the joints in the limb.  default: x
	-scale [float]			scale factor to apply to the control (purely a visual thing - scale is frozen).  default: 1
	-startObj [string]	the beginning of the measure node is attached to the start object.  if its not specified, then the script assumes the start object is the start of the ik chain (usally the case)
	-endObj [string]		this is the object the end of the measure is attached to - by default its the
	-invert [int]				use this flag if the script inverts the limb when adding stretch
	-parts [string]		the parts node is simply an object that miscellanous dag nodes are parented under - if not specified, miscellanous objects are simply left in worldspace
	// -dampen [float]				this flag allows control over the dampen range - lower values cause the dampening to happen over a shorter range.  setting to zero turns damping off.  its technical range is 0-100, but in practice, its probably best to keep between 0-25.  defaults to 12
	// -dampstrength [float]		this is the strength of the dampening - ie how much the arm gets elongated as it nears maximum extension.  the technical range is 0-100, but in reality, you'd probably never go beyond 10.  default is 2

	It is reccommended that this proc has a "root" control, a "chest" control and a "head" control already
	built (and branded with these names) as it uses them as dynamic parents for the actual arm control.

	For example:
	zooCSTMakeStretchy primoBoy_arm_ctrl_L l primoBoy_arm_ctrl_L "-axis x -scale 0.5";
	'''
	#float $dampRange = 12.0
	#float $dampStrength = 2.0;
	#int $elbowpos = 1;
	#if( $dampRange <= 0 ) $dampstrength = 0;
	#$dampRange = abs($dampRange);
	#$dampStrength = abs($dampStrength);
	#$dampRange /= 200.0;  //divide by 200 because we want the input range to be 0-100, but internally it needs to range from 0-0.5
	#$dampStrength /= 100.0;


	#setup some current unit variables, and take parity into account
	stretchAuto = "autoStretch"
	stretchName = "stretch"
	parityFactor = parity.asMultiplier()

	control.addAttr( stretchAuto, at='double', min=0, max=1, dv=1 )
	control.addAttr( stretchName, at='double', min=0, max=10, dv=0 )
	attrState( control, (stretchAuto, stretchName), keyable=True )


	#build the network for distributing stretch from the fk controls to the actual joints
	plusNodes = []
	initialNodes = []
	fractionNodes = []
	clients = []
	allNodes = []

	clients = pymelCore.ikHandle( ikHandle, q=True, jl=True )
	if axis is None:
		raise NotImplemented( 'axis support not written yet - complain loudly!' )
		#axis = `zooCSTJointDirection $clients[1]`;  #if no axis is specified, assume the second joint in the chain has the correct axis set

	#get the end joint in the chain...
	cons = getattr( ikHandle, 't'+ axis.asCleanName() ).listConnections( s=False )
	clients.append( cons[ 0 ] )

	for c in clients:
		md = shadingNode( 'multiplyDivide', asUtility=True, name='%s_fraction_pos' % str( c ) )
		fractionNodes.append( md )

	if startObj is None:
		startObj = clients[ 0 ]

	if endObj is None:
		endObj = ikHandle


	clientLengths = []
	totalLength = 0
	for n, c in enumerate( clients[ :-1 ] ):
		thisPos = Vector( xform( c, q=True, ws=True, rp=True ) )
		nextPos = Vector( xform( clients[ n+1 ], q=True, ws=True, rp=True ) )
		l = (thisPos - nextPos).length()
		clientLengths.append( l )
		totalLength += l


	#build the network to measure limb length
	loc_a = group( empty=True )
	loc_b = group( empty=True )
	measure = loc_b

	parent( loc_b, loc_a )
	constraint_a = pointConstraint( startObj, loc_a )

	aim = aimConstraint( endObj, loc_a, aimVector=(1,0,0) )
	loc_b.tx.set( totalLength )
	makeIdentity( loc_b, a=True, t=True)  #by doing this, the zero point for the null is the max extension for the limb
	constraint_b = pointConstraint( endObj, loc_b )
	attrState( [ loc_a, loc_b ], ('t', 'r'), *LOCK_HIDE )


	#create the stretch network
	stretchEnable = shadingNode( 'multiplyDivide', asUtility=True, n='stretch_enable' )  #blends the auto length smooth back to zero when blending to fk
	fkikBlend = shadingNode( 'multiplyDivide', asUtility=True, n='fkik_stretch_blend' )  #blends the auto length smooth back to zero when blending to fk
	actualLength = shadingNode( 'plusMinusAverage', asUtility=True, n='actual_length' )  #adds the length mods to the normal limb length
	lengthMods = shadingNode( 'plusMinusAverage', asUtility=True, n='length_mods' )  #adds all lengths together
	finalLength = shadingNode( 'clamp', asUtility=True, n='final_length' )  #clamps the length the limb can be
	manualStretchMult = shadingNode( 'multiplyDivide', asUtility=True, n='manualStretch_range_multiplier' )  #multiplys manual stretch to a sensible range
	dampen = createNode( 'animCurveUU', n='dampen' )

	#for n, cl in enumerate( clientLengths ):  #if any of the lengths are negative, the stretch will still be wrong, but will be easier to fix manually if this number is correct
	setKeyframe( dampen, f=totalLength * -0.5, v=0 )
	setKeyframe( dampen, f=totalLength * -dampRange, v=totalLength * dampStrength )
	setKeyframe( dampen, f=totalLength * dampRange, v=0 )
	keyTangent( dampen, f=":", itt='flat', ott='flat' )

	#NOTE: the second term attribute of the length condition node holds the initial length for the limb, and is thus connected to the false attribute of all condition nodes
	manualStretchMult.input2X.set( totalLength / 10 )
	actualLength.input1D[ 0 ].set( totalLength )
	actualLength.input1D[ 0 ].set( totalLength )
	finalLength.minR.set( totalLength )
	finalLength.maxR.set( totalLength * 3 )
	connectAttr( measure.tx, dampen.input, f=True )
	connectAttr( lengthMods.output1D, fkikBlend.input1X, f=True )
	connectAttr( ikHandle.ikBlend, fkikBlend.input2X, f=True )
	connectAttr( fkikBlend.outputX, stretchEnable.input1X, f=True )
	connectAttr( getattr( control, stretchAuto ), stretchEnable.input2X, f=True )
	connectAttr( measure.tx, lengthMods.input1D[ 0 ], f=True )
	connectAttr( getattr( control, stretchName ), manualStretchMult.input1X, f=True )
	connectAttr( manualStretchMult.outputX, lengthMods.input1D[ 1 ], f=True )
	connectAttr( dampen.output, lengthMods.input1D[ 2 ], f=True )
	connectAttr( stretchEnable.outputX, actualLength.input1D[ 1 ], f=True )
	connectAttr( actualLength.output1D, finalLength.inputR, f=True )


	#connect the stretch distribution network up - NOTE this loop starts at 1 because we don't need to connect the
	#start of the limb chain (ie the bicep or the thigh) as it doesn't move
	for n, c in enumerate( clients ):
		if n == 0: continue
		fractionNodes[ n ].input2X.set( clientLengths[ n ] / totalLength * parityFactor )

		#now connect the inital coords to the plus node - then connect the
		connectAttr( finalLength.outputR, fractionNodes[ n ].input1X, f=True )

		#then connect the result of the plus node to the t(axis) pos of the limb joints
		clients[ n ].tx.setLocked( False )
		connectAttr( fractionNodes[ n ].outputX, clients[ n ].tx, f=True )


	#now if we have only 3 clients, that means we have a simple limb structure
	#in which case, lets build an elbow pos network
	if len( clients ) == 3 and elbowPos:
		default = clientLengths[ 1 ] / totalLength * parityFactor
		isNeg = default < 0

		default = abs( default )
		control.addAttr( 'elbowPos', at='double', min=0, max=1, dv=default )
		control.elbowPos.setKeyable( True )

		elbowPos = shadingNode( 'reverse', asUtility=True, n='%s_elbowPos' % clients[ 1 ] )
		if isNeg:
			mult = shadingNode( 'multiplyDivide', asUtility=True )
			mult.input2.set( (-1, -1, -1) )
			connectAttr( control.elbowPos, elbowPos.inputX, f=True )
			connectAttr( control.elbowPos, mult.input1X, f=True )
			connectAttr( elbowPos.outputX, mult.input1Y, f=True )
			connectAttr( mult.outputY, fractionNodes[2].input2X, f=True )
			connectAttr( mult.outputX, fractionNodes[1].input2X, f=True )
		else:
			connectAttr( control.elbowPos, elbowPos.inputX, f=True )
			connectAttr( elbowPos.outputX, fractionNodes[2].input2X, f=True )
			connectAttr( control.elbowPos, fractionNodes[1].input2X, f=True )


class IkFkLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Leg, )
	CONTROL_NAMES = 'control', 'fkThigh', 'fkKnee', 'fkAnkle', 'poleControl', 'allPurpose', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, stretchy=False, **kw ):
		return ikFkLeg( skeletonPart.thigh, skeletonPart.knee, skeletonPart.ankle, stretchy=stretchy, **kw )


def ikFkLeg( thigh, knee, ankle, stretchy=True, **kw ):
	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	suffix = parity.asName()

	colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts


	#first rotate the foot so its aligned to a world axis
	footCtrlRot = Vector( getAnkleToWorldRotation( str( ankle ), 'z', True ) )
	footCtrlRot = (0, -footCtrlRot.y, 0)


	### BUILD THE IKFK BASE
	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, thigh, knee, ankle, LEG_NAMING_SCHEME, False, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )


	partParent, rootControl = getParentAndRootControl( thigh )


	#if the part parent in a Root primitive, grab the hips control instead of the root gimbal - for the leg parts this is preferable
	parentRigPart = RigPart.InitFromItem( partParent )
	if isinstance( parentRigPart, Root ):
		print 'FOUND ZE HIPS!'
		partParent = parentRigPart.hips


	#create variables for each control used
	legControl = ikFkPart.control
	legControlSpace = legControl.getParent()

	ikLegSpace = ikFkPart.ikSpace
	fkLegSpace = ikFkPart.fkSpace
	driverThigh = ikFkPart.fkUpper
	driverKnee = ikFkPart.fkMid
	driverAnkle = ikFkPart.fkLower
	ikHandle = ikFkPart.ikHandle
	kneeControl = ikFkPart.poleControl
	kneeControlSpace = kneeControl.getParent()
	toe = listRelatives( ankle, type='joint' ) or None
	toeTip = None

	if toe:
		toe = toe[0]

	fkControls = driverThigh, driverKnee, driverAnkle


	#if the toe doesn't exist, build a temp one
	if not toe:
		toe = group( em=True )
		parent( toe, ankle, r=True )
		move( toe, 0, -scale, scale, r=True, ws=True )

	possibleTips = listRelatives( toe, type='joint' )
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
	move( (0, 0, 0), rpr=True, y=True )


	#move bank pivots to a good spot on the ground
	toePos = toe.getRotatePivot( 'world' )
	sideOffset = -scale if parity == Parity.LEFT else scale
	move( footBankL, (toePos.x+sideOffset, 0, toePos.z), a=True, ws=True, rpr=True )
	move( footBankR, (toePos.x-sideOffset, 0, toePos.z), a=True, ws=True, rpr=True )


	#parent the leg pivots together
	parent( kneeControlSpace, partParent )

	parent( heelRoll, footControlSpace )
	parent( toeRoll, heelRoll )
	parent( footBankL, toeRoll )
	parent( footBankR, footBankL )
	parent( footRollControl, footBankR )
	parent( toeOrient, footBankR )
	if toe: orientConstraint( toeOrient, toe, mo=True )
	makeIdentity( heelRoll, apply=True, t=True, r=True )


	#move the knee control so its inline with the leg
	#move( kneeControlSpace, newPos, a=True, ws=True, rpr=True )
	rotate( kneeControlSpace, footCtrlRot, p=thigh.getRotatePivot( 'world' ), a=True, ws=True )
	makeIdentity( kneeControl, apply=True, t=True )


	#add attributes to the leg control, to control the pivots
	legControl.addAttr( 'rollBall', at='double', min=0, max=10, k=True )
	legControl.addAttr( 'rollToe', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'twistFoot', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'toe', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'bank', at='double', min=-10, max=10, k=True )


	#replace the legControl as a target to teh parent constraint on the endOrient transform so the ikHandle respects the foot slider controls
	footFinalPivot = buildNullControl( "final_piv"+ suffix, ankle, parent=footRollControl )
	endOrientConstraint = ikFkPart.endOrient.tx.listConnections( type='constraint', d=False )[ 0 ]
	for attr in endOrientConstraint.target[ 0 ].getChildren():
		for con in attr.listConnections( p=True, type='transform', d=False ):
			if con.node() == legControl:
				#footFinalPivot.attr( con.shortName() ) >> attr  ##there is a bug here - instantiating a rotatePivot doesn't return an Attribute instance - so we need to go back to dealing with strings...

				toks = str( con ).split( '.' )
				toks[ 0 ] = str( footFinalPivot )
				connectAttr( '.'.join( toks ), attr, f=True )

	delete( parentConstraint( footFinalPivot, ikHandle, mo=True ) )
	parent( ikHandle, footFinalPivot )


	#build the SDK's to control the pivots
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=0, v=0 )
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=10, v=90 )
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=-10, v=-90 )

	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=0, v=0 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=10, v=90 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=0, v=0 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=-10, v=-90 )
	setDrivenKeyframe( toeRoll.ry, cd=legControl.twistFoot, dv=-10, v=-90 )
	setDrivenKeyframe( toeRoll.ry, cd=legControl.twistFoot, dv=10, v=90 )

	setDrivenKeyframe( toeOrient.ry, cd=legControl.toe, dv=-10, v=90 )
	setDrivenKeyframe( toeOrient.ry, cd=legControl.toe, dv=10, v=-90 )

	min = -90 if parity == Parity.LEFT else 90
	max = 90 if parity == Parity.LEFT else -90
	setDrivenKeyframe( footBankL.rz, cd=legControl.bank, dv=0, v=0 )
	setDrivenKeyframe( footBankL.rz, cd=legControl.bank, dv=10, v=max )
	setDrivenKeyframe( footBankR.rz, cd=legControl.bank, dv=0, v=0 )
	setDrivenKeyframe( footBankR.rz, cd=legControl.bank, dv=-10, v=min )


	#build all purpose
	allPurposeObj = spaceLocator( name="leg_all_purpose_loc%s" % suffix )
	parent( allPurposeObj, worldControl )


	#build space switching
	parent( fkLegSpace, partParent )
	spaceSwitching.build( legControl, (worldControl, partParent, rootControl, allPurposeObj), ('World', None, 'Root', 'All Purpose'), space=legControlSpace )
	spaceSwitching.build( kneeControl, (legControl, partParent, rootControl, worldControl), ("Leg", None, "Root", "World"), **spaceSwitching.NO_ROTATION )
	spaceSwitching.build( driverThigh, (partParent, rootControl, worldControl), (None, 'Root', 'World'), **spaceSwitching.NO_TRANSLATION )


	#make the limb stretchy
	#makeStretchy( legControl, ikHandle, parity=parity )  #( $optionStr +" -startObj "+ $thigh +" -endObj "+ $legControl +" -register 1 -primitive "+ $primitive +" -axis "+ zooCSTJointDirection($ankle) +" -prefix "+ $prefix +" -parts "+ $partsControl )
	#renameAttr( legControl.elbowPos, 'kneePos' )


	#hide attribs, objects and cleanup
	attrState( legControl, 'kneePos', *LOCK_HIDE )


	return legControl, driverThigh, driverKnee, driverAnkle, kneeControl, allPurposeObj, ikFkPart.poleTrigger


#end
