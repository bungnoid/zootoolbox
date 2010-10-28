
from baseRigPrimitive import *
from skeletonPart_arbitraryChain import ArbitraryChain
from LIBrary import SKELeton as SKEL


class ControlHierarchy(PrimaryRigPart):
	__version__ = 0

	#part doesn't have a CONTROL_NAMES list because parts are dynamic - use indices to refer to controls
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'ArbitraryChain' ), )

	def _build( self, part, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=False, parents=(), rigOrphans=False, **kw ):
		joints = list( part ) + (part.getOrphanJoints() if rigOrphans else [])
		return controlChain( self, joints, controlShape, spaceSwitchTranslation, parents, rigOrphans, **kw )


class WeaponControlHierarchy(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'WeaponRoot' ), )

	def _build( self, part, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=True, parents=(), **kw ):
		return controlChain( self, part.selfAndOrphans(), controlShape, spaceSwitchTranslation, parents, True, **kw )


def controlChain( rigPart, joints, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=False, parents=(), rigOrphans=False, **kw ):
	scale = kw[ 'scale' ]

	worldPart = WorldPart.Create()
	worldControl = worldPart.control

	#discover parent nodes
	namespace = ''
	try:
		namespace = getNamespaceFromReferencing( joints[ 0 ] )
	except IndexError: pass

	parents = tuple( '%s%s' % (namespace, p) for p in parents )

	### DETERMINE THE PART'S PARENT CONTROL AND THE ROOT CONTROL ###
	parentControl, rootControl = getParentAndRootControl( joints[ 0 ] )

	ctrls = []
	prevParent = parentControl

	for item in joints:
		ctrl = buildControl( '%s_ctrl' % item, item, PivotModeDesc.BASE, controlShape, size=AUTO_SIZE )
		ctrlSpace = getNodeParent( ctrl )

		#do parenting
		parent( ctrlSpace, prevParent )

		#stuff objects into appropriate variables
		prevParent = ctrl
		ctrls.append( ctrl )

		#lock un-needed axes
		if not spaceSwitchTranslation:
			attrState( ctrl, 't', *LOCK_HIDE )


	#setup space switching
	buildKwargs = {} if spaceSwitchTranslation else spaceSwitching.NO_TRANSLATION
	for n, (ctrl, j) in enumerate( zip( ctrls, joints ) ):
		buildDefaultSpaceSwitching( j, ctrl, parents, reverseHierarchy=False, **buildKwargs )


	createLineOfActionMenu( joints, ctrls )


	return ctrls



class SplineIkTail(PrimaryRigPart):
	__version__ = 0
	PRIORITY = 12

	#part doesn't have a CONTROL_NAMES list because parts are dynamic - use indices to refer to controls
	SKELETON_PRIM_ASSOC = ( SkeletonPart.GetNamedSubclass( 'ArbitraryChain' ), )

	def _build( self, skeletonPart, numOfControls=3, **kw ):
		return splineIkTailRig( skeletonPart.base, skeletonPart.endPlacer, (), numOfControls, **kw )


def splineIkTailRig( base, end, parents=(), numOfControls=3, **kw ):
	partName = kw[ 'partName' ]
	allCons = []
	allPCons = []
	allSCons = []


	#discover parent nodes
	namespace = ''
	try:
		namespace = getNamespaceFromReferencing( base )
	except IndexError: pass

	parents = tuple( '%s%s' % (namespace, p) for p in parents )

	### DETERMINE THE PART'S PARENT CONTROL AND THE ROOT CONTROL ###
	parentControl, rootControl = getParentAndRootControl( base )


	worldPart = WorldPart.Create()
	partsControl = worldPart.parts


	if numOfControls < 2:
		numOfControls = 2

	scale = kw[ 'scale' ]

	oldJoints = [ end ]
	if base != end:
		while True:
			p = getNodeParent( oldJoints[ -1 ] )
			oldJoints.append( p )
			if p == base: break

		oldJoints.reverse()

	# build control joints
	ctrlJoints = []
	cmd.select( cl=True )
	for jnt in oldJoints:
		j = cmd.joint( p=(0,0,0), n=( 'CTRL_%s' % jnt ) )
		pCon = cmd.parentConstraint( jnt, j, mo=False )
		cmd.delete( pCon[0] )
		ctrlJoints.append( j )

	cmd.select( cl=True )

	for jnt in ctrlJoints:
		SKEL.rotateToJointOrient( jnt )

	SKEL.zeroOutJoints( ctrlJoints[ len( ctrlJoints ) - 1 ] )        # create controls


	# just the quick version--nothing fancy here
	# there are better ways of doing this instead of binding to the curve (like building the curve specifically and adding a CON per cv)
	# but for now...the simple way....

	# create splineIK
	ik = cmd.ikHandle( sj=ctrlJoints[0], ee=ctrlJoints[len(ctrlJoints)-1], sol='ikSplineSolver', n='%sIkHandle' % partName )
	cmd.setAttr( '%s.v' % ik[0], 0 )
	ikCrv = cmd.rename( ik[2], '%sCRV' % partName )
	s = cmd.listRelatives( ikCrv, s=True, pa=True )

	# create controls
	controlSpaces = []
	controllers = []
	startColour = ColourDesc( (1, 0.3, 0, 0.65) )
	endColour = ColourDesc( (0.8, 1, 0, 0.65) )
	conColour = startColour
	colourInc = (endColour - startColour) / float( numOfControls )

	div = 1.0/ (numOfControls-1)

	poc = cmd.createNode( 'pointOnCurveInfo' )
	cmd.setAttr( '%s.top' % poc, 1 )
	cmd.connectAttr( '%s.worldSpace' % s[0], '%s.ic' % poc )
	posLoc = cmd.spaceLocator( p=(0,0,0) )
	cmd.connectAttr( '%s.position' % poc, '%s.t' % posLoc[0] )
	oCon = cmd.orientConstraint( ( ctrlJoints[0], ctrlJoints[ len( ctrlJoints ) -1 ] ), posLoc[0] )


	envJoints = []
	color = 1
	for i in range( 0, numOfControls ):
		p = div * i
		cmd.setAttr( '%s.pr' % poc, p )
		cmd.setAttr( '%s.%sW0' % (oCon[0], ctrlJoints[0]), 1.0 - p)
		cmd.setAttr( '%s.%sW1' % (oCon[0], ctrlJoints[ len( ctrlJoints ) -1 ]), p)

		c = buildControl( "'%s_%d_CON" % (partName, i+1), posLoc[0], PivotModeDesc.MID, ShapeDesc( 'sphere2', axis=AX_Z ), colour=conColour, parent=parentControl, scale=scale*1.5, niceName='%s %d Control' % ( partName, i+1) )
		cSpace = getNodeParent( c )

		cmd.color( c, ud=color )
		color += 1
		if color > 8:
			color = 1

		j = createJoint( '%s_ENV' % c )
		cmd.setAttr( '%s.v' % j, 0 )

		envJoints.append( cmd.parent( j, c, r=True )[0] )

		pCons = cmd.listConnections( '%s.tx' % posLoc[0], s=True, d=False, type='parentConstraint', scn=True )
		if pCons:
			for pc in pCons:
				cmd.delete( pc )

		controllers.append( c )
		controlSpaces.append( cSpace )
		conColour+=colourInc


	cmd.delete( poc, posLoc[0] )

	## hide the first control
	#cmd.setAttr( '%s.v' % controllers[0], 0 )




	# for spine twists
	loc = cmd.spaceLocator( p=(0,0,0), n='%s_BaseTwistNUL' % partName )
	pCon = cmd.parentConstraint( ctrlJoints[0], loc[0] )
	cmd.delete( pCon[0] )
	baseTwistNUL = cmd.parent( loc[0], controllers[0] )
	cmd.setAttr( '%s.ty' % baseTwistNUL[0], scale)
	#cmd.setAttr( '%s.v' % baseTwistNUL[0], 0 )

	loc = cmd.spaceLocator( p=(0,0,0), n='%s_EndTwistNUL' % partName )
	pCon = cmd.parentConstraint( ctrlJoints[len(ctrlJoints)-1], loc[0] )
	cmd.delete( pCon[0] )
	endTwistNUL = cmd.parent( loc[0], controllers[len(controllers)-1] )
	cmd.setAttr( '%s.ty' % endTwistNUL[0], scale)
	#cmd.setAttr( '%s.v' % endTwistNUL[0], 0 )

	cmd.setAttr( '%s.dTwistControlEnable' % ik[0], 1 )
	cmd.setAttr( '%s.dWorldUpType' % ik[0], 2 )
	cmd.connectAttr( '%s.worldMatrix[0]' % baseTwistNUL[0], '%s.dWorldUpMatrix' % ik[0], f=True )
	cmd.connectAttr( '%s.worldMatrix[0]' % endTwistNUL[0], '%s.dWorldUpMatrixEnd' % ik[0], f=True )



	# bind the ikCurve to the env joints
	cmd.skinCluster( envJoints, ikCrv, tsb=True )




	# setConstraints for driverDriven rigs
	for i in range( 0, len( oldJoints ) ):
		allPCons.append( cmd.parentConstraint( ctrlJoints[ i ], oldJoints[ i ], mo=False ) )
		allSCons.append( cmd.scaleConstraint( ctrlJoints[ i ], oldJoints[ i ], mo=False ) )




	## for endPlacer attachment
	#allPCons.append( cmd.parentConstraint( ctrlJoints[ -1 ], end, mo=False ) )
	#allSCons.append( cmd.scaleConstraint( ctrlJoints[ -1 ], end, mo=False ) )



	# setup stretch into translations on joints
	ci = cmd.createNode( 'curveInfo' )
	cmd.connectAttr( '%s.worldSpace' % s[0], '%s.inputCurve' % ci )

	md = cmd.createNode( 'multiplyDivide' )
	cmd.setAttr( '%s.operation' % md, 2 )
	al = cmd.getAttr( '%s.arcLength' % ci )
	cmd.connectAttr( '%s.arcLength' % ci, '%s.input1X' % md )
	cmd.setAttr( '%s.input2X' % md, al )


	for i in range( 1, len( ctrlJoints ) ):
		newMd = cmd.createNode( 'multiplyDivide' )
		# most likely need to get the actual axis from a variable?! but for now hardcoded to x
		transAttr = 'tx'
		transVal = cmd.getAttr( '%s.%s' % ( ctrlJoints[i], transAttr ) )
		cmd.setAttr( '%s.input1X' % newMd, transVal )
		cmd.connectAttr( '%s.outputX' % md, '%s.input2X' % newMd )
		cmd.connectAttr( '%s.outputX' % newMd, '%s.%s' % ( ctrlJoints[i], transAttr ) )




	# space switching
	parentJoint = cmd.listRelatives( base, p=True, pa=True )
	sSwitchTo = []
	if parentJoint:
		sSwitchTo.append( parentJoint[0] )
	sSwitchTo.append( parentControl )
	spaceSwitching.build( controllers[0], sSwitchTo )


	for i in range( 1, len( controllers ) ):
		addParents = []
		if i is not 0:
			addParents.append( controllers[ i - 1 ] )
			buildDefaultSpaceSwitching( base, controllers[i], additionalParents=addParents, reverseHierarchy=True )



	# clean up
	cmd.setAttr( '%s.v' % ctrlJoints[0], 0 )
	cmd.setAttr( '%s.v' % ikCrv, 0 )

	cmd.parent( ( ctrlJoints[0], ikCrv, ik[0] ), partsControl )

	cmd.select( cl=True )

	return controllers #, ctrlJoints, ikCrv, ik[0], allPCons, allSCons


#end
