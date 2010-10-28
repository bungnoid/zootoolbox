
from baseRigPrimitive import *
from spaceSwitching import build, NO_TRANSLATION, NO_ROTATION


class BaseSplineIK(PrimaryRigPart):
	__version__ = 0
	PRIORITY = 11
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'ArbitraryChain' ), )
	CONTROL_NAMES = 'base', 'mid', 'end'

	@classmethod
	def CanRigThisPart( cls, skeletonPart ):
		return len( skeletonPart ) >= 3
	def _build( self, skeletonPart, **kw ):
		return buildControlsForMPath( skeletonPart.base, skeletonPart.end, **kw )


def range2( count, start=0 ):
	n = start
	while n < count:
		yield n
		n += 1


def buildMPath( objs, squish=True, **kw ):

	#first we need to build a curve - we build an ep curve so that it goes exactly through the joint pivots
	numObjs = len( objs )
	cmdKw = { 'd': 1 }

	cmdKw[ 'p' ] = tuple( xform( obj, q=True, ws=True, rp=True ) for obj in objs )
	cmdKw[ 'k' ] = range( numObjs )

	baseCurve = curve( **cmdKw )

	fittedCurve = fitBspline( baseCurve, ch=True, tol=0.001 )[ 0 ]
	curveShape = listRelatives( fittedCurve, s=True, pa=True )[ 0 ]
	infoNode = createNode( 'curveInfo' )

	connectAttr( '%s.worldSpace[ 0 ]' % curveShape, '%s.inputCurve' % infoNode, f=True )
	knots = getAttr( '%s.knots' % infoNode )[ 0 ][ 2:-2 ]


	#now build the actual motion path nodes that keep the joints attached to the curve
	#there is one proxy for each joint.  the original joints get constrained to
	#the proxies, which in turn get stuck to the motion path and oriented properly
	#then three joints get created, which are used to deform the motion path
	mpaths = {}
	proxies = {}
	unitComp = 1.0

	if currentUnit( q=True, l=True ) == "m":
		unitComp = 100.0

	for n in range( 1, numObjs ):
		mpath = createNode( 'pointOnCurveInfo' )
		proxy = group( em=True, n='%s_proxy' % objs[ n ] )

		#connect axes individually so they can be broken easily if we need to...
		connectAttr( '%s.worldSpace' % curveShape, '%s.inputCurve' % mpath )
		connectAttr( '%s.px' % mpath, '%s.tx' % proxy )
		connectAttr( '%s.py' % mpath, '%s.ty' % proxy )
		connectAttr( '%s.pz' % mpath, '%s.tz' % proxy )
		setAttr( '%s.parameter' % mpath, knots[ n-1 ] )  #were using ($knots[$n]/$unitComp) but it seems this is buggy - invalid knot values are returned for a straight curve...  so it seems assuming $n is valid works in all test cases I've tried...
		delete( orientConstraint( objs[ n ], proxy ) )

		mpaths[ objs[ n ] ] = mpath
		proxies[ objs[ n ] ] = proxy

	proxiesList = [ proxies[ obj ] for obj in objs[ 1: ] ]


	#build a motionpath to get positions along the path - mainly useful for finding the half way mark
	halfWayPath = createNode( 'pointOnCurveInfo' )
	halfWayPos = group( em=True, n="half" )
	arcLength = getAttr( '%s.maxValue' % curveShape ) - getAttr( '%s.minValue' % curveShape )

	connectAttr( '%s.worldSpace' % curveShape, '%s.inputCurve' % halfWayPath )
	connectAttr( '%s.p' % halfWayPath, '%s.t' % halfWayPos )
	setAttr( '%s.parameter' % halfWayPath, knots[ -1 ] / 2.0 )


	#now build the control stucture and place then
	deformJoints = []
	half = numObjs / 2

	select( d=True )
	deformJoints.append( joint() ); select( d=True )
	deformJoints.append( joint() ); select( d=True )
	deformJoints.append( joint() ); select( d=True )
	delete( parentConstraint( objs[ 0 ], deformJoints[ 0 ] ) )
	delete( parentConstraint( halfWayPos, deformJoints[ 1 ] ) )
	delete( parentConstraint( objs[ -1 ], deformJoints[ 2 ] ) )


	#orient the middle deform object - this is harder than in sounds because the object doesn't actually correspond to
	#any of the proxies so what we do is find the closest proxies and average their orientations based on their proximity
	#it looks pretty complicated, but thats all thats going on - proximity based orient constraint weighting
	midObjs = []
	distancesToObjs = []
	isOdd = numObjs % 2


	#if there is an odd number of objs in the chain, we want the surrounding three - NOTE one is almost certain to be very close, whcih is why we
	#do the proximity based weighting - the closest one should have the greatest effect on orientation
	if isOdd:
		midObjs = [ objs[ half-1 ],
		            objs[ half ],
		            objs[ half+1 ] ]

		distancesToObjs = [ betweenVector( midObjs[ 0 ], deformJoints[ 1 ] ).magnitude(),
		                    betweenVector( midObjs[ 1 ], deformJoints[ 1 ] ).magnitude(),
		                    betweenVector( midObjs[ 2 ], deformJoints[ 1 ] ).magnitude() ]

	#but if there are an even number of objs in the chain, we only want the mid two
	else:
		n = (numObjs - 1) / 2
		midObjs = [ objs[ n ],
		            objs[ n+1 ] ]

		distancesToObjs = [ betweenVector( midObjs[ 0 ], deformJoints[ 1 ] ).magnitude(),
		                    betweenVector( midObjs[ 1 ], deformJoints[ 1 ] ).magnitude() ]

	total = sum( distancesToObjs )
	distancesToObjs = [ total / d for d in distancesToObjs ]

	tempConstraint = orientConstraint( midObjs, deformJoints[1] )[ 0 ]
	for obj, weight in zip( midObjs, distancesToObjs ):
		orientConstraint( obj, tempConstraint, e=True, w=weight )

	delete( tempConstraint )
	makeIdentity( deformJoints, a=True, r=True )


	#now weight the curve to the controls - the weighting is just based on a linear
	#falloff from the start to mid joint, and then from the mid joint to the end
	theSkinCluster = skinCluster( deformJoints, baseCurve )[ 0 ]

	#set the weights to 1 for the bottom and mid joint
	for n in range2( half ):
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[ 0 ], 1) )

	for n in range2( numObjs, half ):
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[ 1 ], 1) )

	#now figure out the positional mid point
	midToStart = betweenVector( deformJoints[ 1 ], deformJoints[ 0 ] ).magnitude()
	startPos = Vector( xform( deformJoints[ 0 ], q=True, ws=True, rp=True ) )
	halfByPos = 0

	for n in range( numObjs ):
		pointPos = Vector( pointPosition( '%s.cv[%d]' % (baseCurve, n) ) )
		relToStart = pointPos - startPos
		distFromStart = relToStart.magnitude()

		if distFromStart > midToStart:
			halfByPos = n
			break

	#set the weights initially fully to the end deform joints - then figure out the of each point from the mid joint, and apply a weight falloff
	midPos = Vector( xform( deformJoints[1], q=True, ws=True, rp=True ) )
	midToEnd = betweenVector( deformJoints[2], deformJoints[1] ).magnitude()

	for n in range2( halfByPos ):
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[0], 1) )

	for n in range2( numObjs, halfByPos ):
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[2], 1) )

	for n in range2( halfByPos, 1 ):
		pointPos = Vector( pointPosition( '%s.cv[%d]' % (baseCurve, n) ) )
		pointToMid = pointPos - midPos
		weight = 1 - (pointToMid.magnitude() / midToStart)
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[1], weight) )

	for n in range2( numObjs, halfByPos ):
		pointPos = Vector( pointPosition( '%s.cv[%d]' % (baseCurve, n) ) )
		pointToMid = pointPos - midPos
		weight = 1 - (pointToMid.magnitude() / midToEnd)
		skinPercent( theSkinCluster, '%s.cv[%d]' % (baseCurve, n), tv=(deformJoints[1], weight) )

	parentConstraint( deformJoints[0], objs[0] )
	pointConstraint( proxiesList[-1], objs[-1] )
	orientConstraint( deformJoints[-1], objs[-1] )


	#build the aim constraints for the proxies
	third_1st = round( numObjs / 3.0 )
	third_2nd = round( ( numObjs*2.0 ) / 3.0 )

	objProxyDict = dict( (proxy,obj) for obj, proxy in proxies.iteritems() )
	for n in range2( len( proxiesList )-1 ):
		#we're using z as the aim axis for the proxies, and y for the up axis
		upObj = deformJoints[0]
		aim_float = 0, 0, 1.0
		up_float = 0, 1.0, 0

		if n >= third_1st and n < third_2nd:
			upObj = deformJoints[1]

		elif n >= third_2nd:
			upObj = deformJoints[2]

		thisProxy = proxiesList[ n ]
		nextProxy = proxiesList[ n+1 ]

		#now that we have an aim vector, build the aimconstraint, then we'll need to find the up vector - we need the
		#proxy to be aimed at its target first however, so we can get an accurate up axis to use on the deform obj
		#because all this is just a proxy rig that the real skeleton is constrained to, axes are all arbitrary...
		delete( aimConstraint( nextProxy, thisProxy, aim=aim_float, u=up_float, wu=up_float, wuo=upObj, wut='objectrotation' ) )

		#now we have to figure out which axis on the deform obj to use as the up axis - we do this by using the x axis on
		#the proxy (an arbitrary choice - could just as easily have been y) then seeing what axis is closest to that vector on the deform obj
		proxyUpVector = Vector( up_float ) * Matrix( xform( thisProxy, q=True, m=True ) )  #get aim axis relative to the proxy - we need this so we can figure out which axis on the up object points in that direction
		upObjUpAxis = getLocalAxisInDirection( upObj, proxyUpVector )

		#now edit the constraint to use the up vector we've determined
		thisAim = aimConstraint( nextProxy, thisProxy, mo=True, aim=aim_float, u=up_float, wu=upObjUpAxis.asVector(), wuo=upObj, wut='objectrotation' )[ 0 ]
		parentConstraint( thisProxy, objProxyDict[ thisProxy ], mo=True )


	#scaling?  create a network to dynamically scale the objects based on the length
	#of the segment.  there are two curve segments - start to mid, mid to end.  this
	#scaling is done via SDK so we get control over the in/out of the scaling
	squishNodes = []
	"""if squish:
		curveInfo = createNode( 'curveInfo' )
		scaleFac = shadingNode( n='squishCalculator', asUtility='multiplyDivide' )
		adder = shadingNode( n='now_add_one', asUtility='plusMinusAverage' )
		sdkScaler = createNode( 'animCurveUU', n='squish_sdk' )
		initialLength = 0
		maxScale = 2.0
		minScale = 0.25

		addAttr -k 1 -ln length -at double -min 0 -max 1 -dv 1 $deformJoints[0];
		addAttr -k 1 -ln squishFactor -at double -min 0 -max 1 -dv 0 $deformJoints[0];
		setAttr -k 1 ( $deformJoints[0] +".length" );
		setAttr -k 1 ( $deformJoints[0] +".squishFactor" );
		connectAttr -f ( $curveShape +".worldSpace[0]" ) ( $curveInfo +".inputCurve" );
		initialLength = `getAttr ( $curveInfo +".arcLength" )`;

		setAttr ( $adder +".input1D[0]" ) 1;
		select -cl;

		setKeyframe -f $initialLength -v 0 $sdkScaler;
		setKeyframe -f( $initialLength/100 ) -v( $maxScale-1 ) $sdkScaler;
		setKeyframe -f( $initialLength*2 ) -v( $minScale-1 ) $sdkScaler;
		keyTangent -in 0 -itt flat -ott flat $sdkScaler;
		keyTangent -in 2 -itt flat -ott flat $sdkScaler;
		connectAttr -f ( $curveInfo +".arcLength" ) ( $sdkScaler +".input" );
		connectAttr -f ( $scaleFac +".outputX" ) ( $adder +".input1D[1]" );
		connectAttr -f ( $sdkScaler +".output" ) ( $scaleFac +".input1X" );
		connectAttr -f ( $deformJoints[0] +".squishFactor" ) ( $scaleFac +".input2X" );
		for( $n=0; $n<$numObjs; $n++ ) for( $ax in {"x","y","z"} ) connectAttr -f ( $adder +".output1D" ) ( $objs[$n] +".s"+ $ax );

		lengthMults = []
		for n in range( numObjs, 1 ):
			posOnCurve = getAttr( '%s.parameter' % mpaths[ n ] )
			lengthMults[$n] = `shadingNode -n( "length_multiplier"+ $n ) -asUtility multiplyDivide`;
			setAttr ( $lengthMults[$n] +".input1X" ) $posOnCurve;
			connectAttr -f ( $deformJoints[0] +".length" ) ( $lengthMults[$n] +".input2X" );
			connectAttr -f ( $lengthMults[$n] +".outputX" ) ( $mpaths[$n] +".parameter" );

	$squishNodes = [ curveInfo, scaleFac, adder, sdkScaler} $lengthMults`;"""


	#rename the curves
	baseCurve = rename( baseCurve, "pointCurve" )
	fittedCurve = rename( fittedCurve, "mPath" )

	delete( halfWayPos )
	select( deformJoints )

	return deformJoints


def buildControlsForMPath( spineBase, spineEnd, squish=True, **kw ):
	scale = kw[ 'scale' ]

	spineBase, spineEnd = spineBase, spineEnd

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts


	partParent, rootControl = getParentAndRootControl( spineBase )

	#find the names of relevant joints
	joints = [ spineEnd ] + list( iterParents( spineEnd, spineBase ) )
	joints.reverse()


	#build the sub primitive
	splineIKNodes, splineIKControls = getNodesCreatedBy( buildMPath, joints, squish, **kw )
	ikFkPart = buildContainer( BaseSplineIK, kw, splineIKNodes, splineIKControls )

	baseJoint = ikFkPart.base
	midJoint = ikFkPart.mid
	endJoint = ikFkPart.end


	#build the controls
	axis = getLocalAxisInDirection( endJoint, MAYA_FWD )


	shapeDesc = ShapeDesc( 'pin', axis=getLocalAxisInDirection( baseJoint, -MAYA_FWD ) )
	baseControl = buildControl( "baseControl", baseJoint, PivotModeDesc.BASE, shapeDesc, ColourDesc( 'darkblue' ), parent=partParent, scale=scale )

	shapeDesc = ShapeDesc( 'pin', axis=getLocalAxisInDirection( midJoint, -MAYA_FWD ) )
	midControl = buildControl( "midControl", midJoint, PivotModeDesc.BASE, shapeDesc, ColourDesc( 'darkblue' ), parent=baseControl, scale=scale )

	shapeDesc = ShapeDesc( 'pin', axis=getLocalAxisInDirection( endJoint, -MAYA_FWD ) )
	chestControl = buildControl( "chestControl", endJoint, PivotModeDesc.BASE, shapeDesc, ColourDesc( 'darkblue' ), parent=midControl, scale=scale )

	setItemRigControl( spineBase, baseControl )
	setItemRigControl( spineEnd, chestControl )


	#add LOA right click menu
	createLineOfActionMenu( (baseControl, midControl, chestControl), joints )

	#do space switching
	outsideControls = removeDupes( [ partParent, rootControl, worldControl ] )
	spaceSwitching.build( baseControl, outsideControls, **NO_TRANSLATION )
	spaceSwitching.build( midControl, [ baseControl ] + outsideControls )
	spaceSwitching.build( chestControl, [ midControl, baseControl ] + outsideControls )


	return baseControl, midControl, chestControl


#end
