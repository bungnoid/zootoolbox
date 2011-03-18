
from baseRigPrimitive import *
from spaceSwitching import build, NO_TRANSLATION, NO_ROTATION


class SplineIK(PrimaryRigPart):
	__version__ = 1
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'ArbitraryChain' ), )
	PRIORITY = 11

	@classmethod
	def CanRigThisPart( cls, skeletonPart ):
		return len( skeletonPart ) >= 3
	def _build( self, skeletonPart, **kw ):
		objs = skeletonPart.items

		worldPart = WorldPart.Create()
		worldControl = worldPart.control
		partsNode = worldPart.parts

		fittedCurve, linearCurve, proxies, controls, halfIdx = buildControls( objs, worldControl, **kw )
		buildDefaultSpaceSwitching( objs[0], controls[0] )
		buildDefaultSpaceSwitching( objs[0], controls[-1] )


		parent( proxies, partsNode )
		parent( fittedCurve, linearCurve, partsNode )

		return controls


def buildControls( objs, controlParent=None, name='control', midName='midControl', **kw ):
	numObjs = numControls = len( objs )
	if numObjs < 3:
		raise RigPartError( "Need to specify more than 3 objects to use spline IK" )

	scale = kw.get( 'scale', 15 )
	fittedCurve, linearCurve, proxies = buildCurveThroughObjs( objs, False )
	fittedCurveShape = listRelatives( fittedCurve, s=True, pa=True )[0]


	#hook up a curve info node
	curveMeasure = createNode( 'curveInfo' )
	curveMeasure = rename( curveMeasure, 'curve_measure#' )

	connectAttr( '%s.worldSpace[0]' % fittedCurveShape, '%s.inputCurve' % curveMeasure, f=True )
	knots = getAttr( '%s.knots' % curveMeasure )[ 0 ][ 2:-2 ]


	#figure out which control should be the "mid" control
	halfWayKnotValue = knots[-1] / 2
	halfIdx = numObjs / 2
	for idx, knot in enumerate( knots ):
		if knot < halfWayKnotValue:
			halfIdx = idx
		else:
			#is this value closer to the mid knot value?  if so use it
			deltas = [ (abs( knots[ halfIdx ] - halfWayKnotValue ), halfIdx), (abs( knots[ idx ] - halfWayKnotValue ), idx) ]
			deltas.sort()
			halfIdx = deltas[0][1]
			break


	#now build the controls
	controls = []
	controlParent = controlParent
	name, midName = '%s_%%d' % name, '%s_%%d' % midName
	for n, obj in enumerate( objs ):
		isHalfCtrl = n == halfIdx
		ctrlName = midName % n if isHalfCtrl else name % n
		ctrlScale = scale*1.3 if n in (isHalfCtrl, 0, numControls-1) else scale
		ctrlColour = ColourDesc( 'darkblue' ) if isHalfCtrl else ColourDesc( 'blue' )
		nControl = buildControl( ctrlName, obj, PivotModeDesc.MID, 'sphere2', ctrlColour, constrain=False, parent=controlParent, scale=ctrlScale, asJoint=True )  #need to be joints to use for skinning below
		control.setItemRigControl( obj, nControl )
		controls.append( nControl )

	halfWayControl = controls[ halfIdx ]


	#setup the middle controls to be constrained between all controls
	constraintMethod = pointConstraint
	if numObjs >= 5:
		midControlsA = controls[ 1:halfIdx ]
		fWeightInc = 1.0 / ( len( midControlsA ) + 1 )
		for n, ctrl in enumerate( midControlsA ):
			ctrlParent = listRelatives( ctrl, p=True, pa=True )[0]
			baseWeight = (n + 1) * fWeightInc
			constraintMethod( controls[0], ctrlParent, w=1-baseWeight, mo=True )
			constraintMethod( halfWayControl, ctrlParent, w=baseWeight, mo=True )

		midControlsB = controls[ halfIdx + 1:-1 ]
		fWeightInc = 1.0 / ( len( midControlsB ) + 1 )
		for n, ctrl in enumerate( midControlsB ):
			ctrlParent = listRelatives( ctrl, p=True, pa=True )[0]
			baseWeight = (n + 1) * fWeightInc
			constraintMethod( halfWayControl, ctrlParent, w=1-baseWeight, mo=True )
			constraintMethod( controls[-1], ctrlParent, w=baseWeight, mo=True )

		ctrlParent = listRelatives( halfWayControl, p=True, pa=True )[0]
		baseWeight = halfWayKnotValue / float( knots[-1] )
		constraintMethod( controls[0], ctrlParent, w=1-baseWeight, mo=True )
		constraintMethod( controls[-1], ctrlParent, w=baseWeight, mo=True )
	else:
		midControls = controls[ 1:-1 ]
		for n, ctrl in enumerate( midControls ):
			ctrlParent = listRelatives( ctrl, p=True, pa=True )[0]
			baseWeight = (n+1) / float( numControls-1 )
			constraintMethod( controls[0], ctrlParent, w=1-baseWeight, mo=True )
			constraintMethod( controls[-1], ctrlParent, w=baseWeight, mo=True )

	for knot, j, proxy in zip( knots, objs, proxies ):
		pointConstraint( proxy, j, mo=True )
		mpath = createNode( 'pointOnCurveInfo' )

		#connect axes individually so they can be broken easily if we need to...
		connectAttr( '%s.worldSpace' % fittedCurveShape, '%s.inputCurve' % mpath )
		for ax in AXES:
			connectAttr( '%s.p%s' % (mpath, ax), '%s.t%s' % (proxy, ax) )

		#were using (knot / unitComp) but it seems this is buggy - invalid knot values are returned for a straight curve...  so it seems assuming knot is valid works in all test cases I've tried...
		setAttr( '%s.parameter' % mpath, knot )
		delete( orientConstraint( objs[ n ], proxy ) )


	#setup aim constraints to control twisting and orientation along the spline
	for n in range( numObjs - 1 ):
		obj, nextObj = objs[n], proxies[n + 1]
		v = betweenVector( obj, nextObj )

		#now get all the axis information to build an aim constraint
		aimAxis = getObjectAxisInDirection( obj, v )

		otherAxes = aimAxis.otherAxes()
		upAxis = otherAxes[0]
		upVector = getObjectBasisVectors( obj )[ upAxis ]
		upObj = controls[n]
		upObjAxis = getObjectAxisInDirection( upObj, upVector )

		aimConstraint( nextObj, obj, aim=aimAxis.asVector(), upVector=upAxis.asVector(), wuo=upObj, wut='objectrotation', worldUpVector=upObjAxis.asVector(), mo=True )

	orientConstraint( controls[-1], objs[-1], mo=True )


	#now skin the linear curve to the controls and setup skinning
	lineCluster = skinCluster( controls, linearCurve, tsb=True )[0]
	for cvIdx, ctrl in enumerate( controls ):
		skinPercent( lineCluster, '%s.cv[%d]' % (linearCurve, cvIdx), transformValue=(ctrl, 1) )


	#turn off inherit transforms for the proxy objects and curves so the user can parent them to whatever is needed
	for node in proxies:
		setAttr( '%s.inheritsTransform' % node, False )

	setAttr( '%s.inheritsTransform' % linearCurve, False )
	setAttr( '%s.inheritsTransform' % fittedCurve, False )


	return fittedCurve, linearCurve, proxies, controls, halfIdx


def buildNumControls( objs, numControls=3, **kw ):
	scale = kw.get( 'scale', 15 )
	fittedCurve, linearCurve, proxies = buildCurveThroughObjs( objs )
	fittedCurveShape = listRelatives( fittedCurve, s=True, pa=True )[0]


	#make sure the numControls is properly bounded:  3 <= numControls <= numObjects
	numControls = min( numControls, len( objs ) )
	numControls = max( numControls, 3 )


	partParent = listRelatives( objs, p=True, pa=True )[0]

	#build the spline ik node
	ikHandle, ikEffector = cmd.ikHandle( sj=proxies[0], ee=proxies[-1], sol='ikSplineSolver', curve=fittedCurve, createCurve=False )
	setAttr( '%s.dTwistControlEnable' % ikHandle, True )
	setAttr( '%s.dWorldUpType' % ikHandle, 4 )
	connectAttr( '%s.worldMatrix' % partParent, '%s.dWorldUpMatrix' % ikHandle, f=True )


	#
	halfWayPath = createNode( 'pointOnCurveInfo' )
	halfWayPos = group( em=True, n="half" )
	arcLength = getAttr( '%s.maxValue' % fittedCurveShape ) - getAttr( '%s.minValue' % fittedCurveShape )

	connectAttr( '%s.worldSpace' % fittedCurveShape, '%s.inputCurve' % halfWayPath )
	connectAttr( '%s.p' % halfWayPath, '%s.t' % halfWayPos )
	maxParam = getAttr( '%s.spans' % fittedCurveShape )
	paramInc = maxParam / float( numControls-1 )


	#now build the controls
	controls = []
	controlParent = None
	for n in range( numControls ):
		setAttr( '%s.parameter' % halfWayPath, n * paramInc )
		nControl = buildControl( "control_%d" % n, halfWayPos, PivotModeDesc.MID, 'sphere', ColourDesc( 'darkblue' ), constrain=False, parent=controlParent, scale=scale, asJoint=True )
		controlParent = nControl
		controls.append( nControl )

	connectAttr( '%s.worldMatrix' % controls[-1], '%s.dWorldUpMatrixEnd' % ikHandle, f=True )
	orientConstraint( controls[-1], objs[-1], mo=True )


	#now skin the linear curve to the controls and setup skinning
	lineCluster = skinCluster( controls, linearCurve, tsb=True )[0]
	cvIdxs = range( len( objs ) )  #there is one cv per input object
	cvsPerControl = float( len( objs ) ) / (numControls - 1)  #there is one cv per input object
	for n in range( numControls-1 ):
		cvsForThisControl = int( round( cvsPerControl * n ) )
		weightInc = 1.0 / (cvsForThisControl - 1)
		c1, c2 = controls[n], controls[n+1]
		cvIdxs = range( n * cvsForThisControl, (n + 1) * cvsForThisControl )
		for i, cvIdx in enumerate( cvIdxs ):
			weight = 1 - (i * weightInc)
			skinPercent( lineCluster, '%s.cv[%d]' % (linearCurve, cvIdx), transformValue=((c1, weight), (c2, 1.0-weight)) )


	#now delete the nodes for the motion path - we're done with them
	delete( halfWayPath, halfWayPos )


def setupSquish( curve, joints ):
	#scaling?  create a network to dynamically scale the objects based on the length
	#of the segment.  there are two curve segments - start to mid, mid to end.  this
	#scaling is done via SDK so we get control over the in/out of the scaling
	"""squishNodes = []
	if squish:
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


def buildCurveThroughObjs( objs, parentProxies=True ):

	#first we need to build a curve - we build an ep curve so that it goes exactly through the joint pivots
	numObjs = len( objs )
	cmdKw = { 'd': 1 }

	cmdKw[ 'p' ] = tuple( xform( obj, q=True, ws=True, rp=True ) for obj in objs )
	cmdKw[ 'k' ] = range( numObjs )

	baseCurve = curve( **cmdKw )

	fittedCurve = fitBspline( baseCurve, ch=True, tol=0.005 )[ 0 ]
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

	for n, obj in enumerate( objs ):
		select( cl=True )
		j = joint( n='%s_proxy' % objs[ n ] )
		delete( parentConstraint( obj, j ) )
		proxies[ obj ] = j

	proxiesList = [ proxies[obj] for obj in objs ]
	for n, j in enumerate( proxiesList ):
		if n == 0:
			continue

		if parentProxies:
			parent( j, proxiesList[n-1] )

		makeIdentity( j, a=True, r=True )


	#build a motionpath to get positions along the path - mainly useful for finding the half way mark
	halfWayPath = createNode( 'pointOnCurveInfo' )
	halfWayPos = group( em=True, n="half" )
	arcLength = getAttr( '%s.maxValue' % curveShape ) - getAttr( '%s.minValue' % curveShape )

	connectAttr( '%s.worldSpace' % curveShape, '%s.inputCurve' % halfWayPath )
	connectAttr( '%s.p' % halfWayPath, '%s.t' % halfWayPos )
	setAttr( '%s.parameter' % halfWayPath, knots[ -1 ] / 2.0 )

	delete( halfWayPos )
	delete( infoNode )
	baseCurve = rename( baseCurve, "pointCurve#" )
	fittedCurve = rename( fittedCurve, "mPath#" )

	return fittedCurve, baseCurve, proxiesList


#end
