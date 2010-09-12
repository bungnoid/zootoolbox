from rigPrim_ikFkBase import *


class IkFkArm(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Arm, )
	CONTROL_NAMES = 'control', 'fkBicep', 'fkElbow', 'fkWrist', 'poleControl', 'clavicle', 'allPurpose', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, translateClavicle=True, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return ikFkArm( translateClavicle=translateClavicle, stretchy=False, *items, **kw )


def ikFkArm( bicep, elbow, wrist, clavicle=None, translateClavicle=True, stretchy=True, **kw ):
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

	addAttr( control, ln=stretchAuto, at='double', min=0, max=1, dv=1 )
	addAttr( control, ln=stretchName, at='double', min=0, max=10, dv=0 )
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
	constraint_a = pointConstraint( startObj, loc_a )[ 0 ]

	aim = aimConstraint( endObj, loc_a, aimVector=(1,0,0) )[ 0 ]
	setAttr( '%s.tx' % loc_b, totalLength )
	makeIdentity( loc_b, a=True, t=True )  #by doing this, the zero point for the null is the max extension for the limb
	constraint_b = pointConstraint( endObj, loc_b )[ 0 ]
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
	setAttr( '%s.input2X' % manualStretchMult, totalLength / 10 )
	setAttr( '%s.input1D[ 0 ]' % actualLength, totalLength )
	setAttr( '%s.minR' % finalLength, totalLength )
	setAttr( '%s.maxR' % finalLength, totalLength * 3 )
	connectAttr( '%s.tx' % measure, '%s.input' % dampen, f=True )
	connectAttr( '%s.output1D' % lengthMods, '%s.input1X' % fkikBlend, f=True )
	connectAttr( '%s.ikBlend' % ikHandle, '%s.input2X' % fkikBlend, f=True )
	connectAttr( '%s.outputX' % fkikBlend, '%s.input1X' % stretchEnable, f=True )
	connectAttr( '%s.%s' % (control, stretchAuto), '%s.input2X' % stretchEnable, f=True )
	connectAttr( '%s.tx' % measure, '%s.input1D[ 0 ]' % lengthMods, f=True )
	connectAttr( '%s.%s' % (control, stretchName), '%s.input1X' % manualStretchMult, f=True )
	connectAttr( '%s.outputX' % manualStretchMult, '%s.input1D[ 1 ]' % lengthMods, f=True )
	connectAttr( '%s.output' % dampen, '%s.input1D[ 2 ]' % lengthMods, f=True )
	connectAttr( '%s.outputX' % stretchEnable, '%s.input1D[ 1 ]' % actualLength, f=True )
	connectAttr( '%s.output1D' % actualLength, '%s.inputR' % finalLength, f=True )


	#connect the stretch distribution network up - NOTE this loop starts at 1 because we don't need to connect the
	#start of the limb chain (ie the bicep or the thigh) as it doesn't move
	for n, c in enumerate( clients ):
		if n == 0: continue
		setAttr( '%s.input2X' % fractionNodes[ n ], clientLengths[ n ] / totalLength * parityFactor )

		#now connect the inital coords to the plus node - then connect the
		connectAttr( '%s.outputR' % finalLength, '%s.input1X' % fractionNodes[ n ], f=True )

		#then connect the result of the plus node to the t(axis) pos of the limb joints
		setAttr( '%s.tx' % clients[ n ], lock=False )
		connectAttr( '%s.outputX' % fractionNodes[ n ], '%s.tx' % clients[ n ], f=True )


	#now if we have only 3 clients, that means we have a simple limb structure
	#in which case, lets build an elbow pos network
	if len( clients ) == 3 and elbowPos:
		default = clientLengths[ 1 ] / totalLength * parityFactor
		isNeg = default < 0

		default = abs( default )
		addAttr( control, ln='elbowPos', at='double', min=0, max=1, dv=default )
		setAttr( '%s.elbowPos' % control, keyable=True )

		elbowPos = shadingNode( 'reverse', asUtility=True, n='%s_elbowPos' % clients[ 1 ] )
		if isNeg:
			mult = shadingNode( 'multiplyDivide', asUtility=True )
			setAttr( '%s.input2' % mult, -1, -1, -1 )
			connectAttr( '%s.elbowPos' % control, '%s.inputX' % elbowPos, f=True )
			connectAttr( '%s.elbowPos' % control, '%s.input1X' % mult, f=True )
			connectAttr( '%s.outputX' % elbowPos, '%s.input1Y' % mult, f=True )
			connectAttr( '%s.outputY' % mult, '%s.input2X' % fractionNodes[2], f=True )
			connectAttr( '%s.outputX' % mult, '%s.input2X' % fractionNodes[1], f=True )
		else:
			connectAttr( '%s.elbowPos' % control, '%s.inputX' % elbowPos, f=True )
			connectAttr( '%s.outputX' % elbowPos, '%s.input2X' % fractionNodes[2], f=True )
			connectAttr( '%s.elbowPos' % control, '%s.input2X' % fractionNodes[1], f=True )


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
	toePos = Vector( xform( toe, q=True, ws=True, rp=True ) )
	sideOffset = -scale if parity == Parity.LEFT else scale
	move( toePos.x+sideOffset, 0, toePos.z, footBankL, a=True, ws=True, rpr=True )
	move( toePos.x-sideOffset, 0, toePos.z, footBankR, a=True, ws=True, rpr=True )


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
	#attrState( legControl, 'kneePos', *LOCK_HIDE )


	return legControl, driverThigh, driverKnee, driverAnkle, kneeControl, allPurposeObj, ikFkPart.poleTrigger


#end
