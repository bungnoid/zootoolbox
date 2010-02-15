'''
this module is simply a miscellaneous module for rigging support code - most of it is maya specific convenience code
for determining things like aimAxes, aimVectors, rotational offsets for controls etc...
'''

from pymel.core import *
from vectors import *

import maya.cmds as cmd
import meshUtils
import api
import vectors
import random
import pymel.core as pymelCore

from maya import OpenMaya

#this are strings because pymel uses strings for space defines as well
WORLD = 'world'
LOCAL = 'transform'
OBJECT = 'object'

ENGINE_FWD   = MAYA_SIDE  = MAYA_X = Vector(1, 0, 0)
ENGINE_UP    = MAYA_FWD   = MAYA_Z = Vector(0, 0, 1)
ENGINE_SIDE  = MAYA_UP    = MAYA_Y = Vector(0, 1, 0)

#pull in some globals...
MPoint = OpenMaya.MPoint
MVector = OpenMaya.MVector
MMatrix = OpenMaya.MMatrix
MTransformationMatrix = OpenMaya.MTransformationMatrix
MBoundingBox = OpenMaya.MBoundingBox

MSpace = OpenMaya.MSpace
kWorld = MSpace.kWorld
kTransform = MSpace.kTransform
kObject = MSpace.kObject


class Axis(int):
	BASE_AXES = 'x', 'y', 'z'
	AXES = ['x', 'y', 'z',\
	        '-x', '-y', '-z']

	def __new__( cls, idx ):
		return int.__new__( cls, idx )
	def __neg__( self ):
		return Axis( (self + 3) % 6 )
	@classmethod
	def FromName( cls, name ):
		idx = cls.AXES.index( name.lower().replace( '_', '-' ) )
		return cls( idx )
	@classmethod
	def FromVector( cls, vector ):
		'''
		returns the closest axis to the given vector
		'''
		assert len( cls.BASE_AXES ) >= len( vector )

		listV = list( vector )
		idx, value = 0, listV[ 0 ]
		for n, v in enumerate( listV ):
			if v > value:
				value = v
				idx = n

		return cls( idx )
	def asVector( self ):
		v = Vector( [0, 0, 0] )
		v[ self % 3 ] = 1 if self < 3 else -1

		return v
	def isNegative( self ):
		return self > 2
	def asName( self ):
		return self.AXES[ self ]
	def asCleanName( self ):
		'''
		returns the axis name without a negative regardless
		'''
		return self.AXES[ self ].replace( '-', '' )
	def asEncodedName( self ):
		'''
		returns the axis name, replacing the - with an _
		'''
		return self.asName().replace( '-', '_' )
	def otherAxes( self ):
		'''
		returns the other two axes that aren't this axis
		'''
		allAxes = [ 0, 1, 2 ]
		allAxes.remove( self % 3 )

		return list( map( Axis, allAxes ) )


def getObjectBasisVectors( obj ):
	'''
	returns 3 world space orthonormal basis vectors that represent the orientation of the given object
	'''
	xPrime, yPrime, zPrime = api.getObjectBases( obj )

	return Vector([xPrime.x, xPrime.y, xPrime.z]), Vector([yPrime.x, yPrime.y, yPrime.z]), Vector([zPrime.x, zPrime.y, zPrime.z])


def getLocalBasisVectors( obj ):
	'''
	returns 3 world space orthonormal basis vectors that represent the local coordinate system of the given object
	'''
	xPrime, yPrime, zPrime = api.getLocalBases( obj )

	return Vector([xPrime.x, xPrime.y, xPrime.z]), Vector([yPrime.x, yPrime.y, yPrime.z]), Vector([zPrime.x, zPrime.y, zPrime.z])


def getPlaneNormalForObjects( objA, objB, objC, defaultVector=MAYA_UP ):
	posA = Vector( xform( objA, q=True, ws=True, rp=True ) )
	posB = Vector( xform( objB, q=True, ws=True, rp=True ) )
	posC = Vector( xform( objC, q=True, ws=True, rp=True ) )

	vecA, vecB = posB - posA, posC - posB
	normal = vecA.cross( vecB )

	#if the normal is too small, just return world axes
	if normal.mag < 1e-2:
		normal = defaultVector

	return normal


def largestT( obj ):
	'''
	returns the index of the translation axis with the highest absolute value
	'''
	pos = cmd.getAttr( '%s.t' % obj )[0]
	idx = indexOfLargest( pos )
	if pos[ idx ] < 0:
		idx += 3

	return idx


def indexOfLargest( iterable ):
	'''
	returns the index of the largest absolute valued component in an iterable
	'''
	iterable = [(x, n) for n, x in enumerate( map(abs, iterable) )]
	iterable.sort()

	return Axis( iterable[-1][1] )


def betweenVector( obj1, obj2 ):
	'''
	returns the vector between two objects
	'''
	posA = Vector( cmd.xform(obj1, q=True, ws=True, rp=True) )
	posB = Vector( cmd.xform(obj2, q=True, ws=True, rp=True) )

	return posB - posA


def getAimVector( obj ):
	children = cmd.listRelatives(obj, path=True, typ='transform')
	if len( children ) == 1:
		return betweenVector(obj, children[0])
	else:
		axisIdx = largestT( obj )
		axisVector = Axis( axisIdx ).asVector()

		#now just return the axis vector in world space
		mat = api.getWorldSpaceMatrix( obj )
		axisVector = api.MVectorToVector( api.VectorToMVector( axisVector ) * mat )

		return axisVector


def getObjectAxisInDirection( obj, compareVector, defaultAxis=Axis(0) ):
	'''
	returns the axis (an Axis instance) representing the closest object axis to
	the given vector

	the defaultAxis is returned if the compareVector is zero or too small to provide
	meaningful directionality
	'''
	xPrime, yPrime, zPrime = getObjectBasisVectors( obj )
	try:
		dots = compareVector.dot( xPrime, True ), compareVector.dot( yPrime, True ), compareVector.dot( zPrime, True )
	except ZeroDivisionError:
		return defaultAxis

	idx = indexOfLargest( dots )
	if dots[ idx ] < 0: idx += 3

	return Axis( idx )


def getLocalAxisInDirection( obj, compareVector ):
	xPrime, yPrime, zPrime = getLocalBasisVectors( obj )
	dots = compareVector.dot( xPrime, True ), compareVector.dot( yPrime, True ), compareVector.dot( zPrime, True )

	idx = indexOfLargest( dots )
	if dots[ idx ] < 0: idx += 3

	return Axis( idx )


def getAnkleToWorldRotation( ankle, fwdAxisName='z', performRotate=False ):
	'''
	ankles are often not world aligned and cannot be world aligned on all axes, as the ankle needs to aim toward
	toe joint.  for the purposes of rigging however, we usually want the foot facing foward (or along one of the primary axes
	'''
	fwd = Vector.Axis( fwdAxisName )

	#flatten aim vector into the x-z plane
	aimVector = getAimVector( ankle )
	aimVector[ 1 ] = 0
	aimVector = aimVector.normalize()

	#now determine the rotation between the flattened aim vector, and the fwd axis
	angle = aimVector.dot( fwd )
	angle = Angle( math.acos( angle ), radian=True ).degrees

	#determine the directionality of the rotation
	direction = 1
	sideAxisName = 'x' if fwdAxisName[-1] == 'z' else 'z'
	if aimVector.dot( Vector.Axis( sideAxisName ) ) > 0:
		direction = -1

	angle *= direction

	#do the rotation...
	if performRotate:
		cmd.rotate(0, angle, 0, ankle, r=True, ws=True)

	return (0, angle, 0)


def getWristToWorldRotation( wrist, performRotate=False ):
	'''
	'''
	basis = map(api.MVectorToVector, api.getObjectBases( wrist ))
	rots = [0, 0, 0]
	for n, axis in enumerate( Axis.AXES[ :3 ] ):
		axis = Vector.Axis( axis )
		if axis.dot( basis[n] ) < 0:
			rots[n] = 180

	if performRotate:
		rots.append( wrist )
		cmd.rotate(rots[0], rots[1], rots[2], str( wrist ), a=True, ws=True)

	return tuple( rots )


def isVisible( dag ):
	'''
	returns whether a dag item is visible or not - it walks up the hierarchy and checks both parent visibility
	as well as layer visibility
	'''
	parent = dag
	while True:
		if not cmd.getAttr( '%s.v' % parent ):
			return False

		#check layer membership
		layers = cmd.listConnections( parent, t='displayLayer' )
		if layers is not None:
			for l in layers:
				if not cmd.getAttr( '%s.v' % l ):
					return False

		try:
			parent = cmd.listRelatives( parent, p=True, pa=True )[0]
		except TypeError:
			break

	return True


def areSameObj( objA, objB ):
	'''
	given two objects, returns whether they're the same object or not - object path names make this tricker than it seems
	'''
	try:
		return cmd.ls( objA ) == cmd.ls( objB )
	except TypeError:
		return False


def getBounds( objs ):
	minX, minY, minZ = [], [], []
	maxX, maxY, maxZ = [], [], []

	for obj in objs:
		tempMN = cmd.getAttr( '%s.bbmn' % obj )[ 0 ]
		tempMX = cmd.getAttr( '%s.bbmx' % obj )[ 0 ]
		minX.append( tempMN[ 0 ] )
		minY.append( tempMN[ 1 ] )
		minZ.append( tempMN[ 2 ] )
		maxX.append( tempMX[ 0 ] )
		maxY.append( tempMX[ 1 ] )
		maxZ.append( tempMX[ 2 ] )

	minX.sort()
	minY.sort()
	minZ.sort()
	maxX.sort()
	maxY.sort()
	maxZ.sort()

	return minX[ 0 ], minY[ 0 ], minZ[ 0 ], maxX[ -1 ], maxY[ -1 ], maxZ[ -1 ]


def getObjsScale( objs ):
	mnX, mnY, mnZ, mxX, mxY, mxZ = getBounds( objs )
	x = abs( mxX - mnX )
	y = abs( mxY - mnY )
	z = abs( mxZ - mnZ )

	return (x + y + z) / 3.0 * 0.75  #this is kinda arbitrary


def getJointBounds( joints, threshold=0.65, space=OBJECT ):
	'''
	if useLocalSpace is True then the b
	'''

	global MVector, MTransformationMatrix, Vector

	if not isinstance( joints, (list, tuple) ):
		joints = [ joints ]

	theJoint = joints[ 0 ]
	verts = []

	for j in joints:
		verts += meshUtils.jointVertsForMaya( j, threshold )

	jointDag = api.getMDagPath( theJoint )

	if space == OBJECT:
		jointMatrix = jointDag.inclusiveMatrix()
	elif space == LOCAL:
		jointMatrix = jointDag.exclusiveMatrix()
	elif space == WORLD:
		jointMatrix = OpenMaya.MMatrix()
	else: raise TypeError( "Invalid space specified" )

	vJointPos = MTransformationMatrix( jointMatrix ).rotatePivot( kWorld ) + MTransformationMatrix( jointMatrix ).getTranslation( kWorld )
	vJointPos = Vector( [vJointPos.x, vJointPos.y, vJointPos.z] )

	vJointBasisX = MVector(-1,0,0) * jointMatrix
	vJointBasisY = MVector(0,-1,0) * jointMatrix
	vJointBasisZ = MVector(0,0,-1) * jointMatrix

	bbox = MBoundingBox()
	for vert in verts:
		#get the position relative to the joint in question
		vPos = Vector( xform( vert, query=True, ws=True, t=True ) )
		vPos = vJointPos - vPos

		#now transform the joint relative position into the coordinate space of that joint
		#we do this so we can get the width, height and depth of the bounds of the verts
		#in the space oriented along the joint
		vPosInJointSpace = Vector( vPos )
		vPosInJointSpace.change_space( vJointBasisX, vJointBasisY, vJointBasisZ )

		bbox.expand( MPoint( *vPosInJointSpace ) )

	return bbox.min(), bbox.max()


def getJointSize( joints, threshold=0.65, space=OBJECT ):
	minB, maxB = getJointBounds( joints, threshold, space )
	vec = minB - maxB

	return Vector( map( abs, [vec.x, vec.y, vec.z] ) )


def ikSpringSolver( start, end, *a, **kw ):
	'''
	creates an ik spring solver - this is wrapped simply because its not default
	maya functionality, and there is potential setup work that needs to be done
	to ensure its possible to create an ik chain using the spring solver
	'''
	cmd.loadPlugin( 'ikSpringSolver', quiet=True )
	if not cmd.ls( typ='ikSpringSolver' ):
		cmd.createNode( 'ikSpringSolver' )

	kw[ 'solver' ] = 'ikSpringSolver'

	cmd.select( start, end, replace=True )
	return cmd.ikHandle( *a, **kw )


def resetSkinCluster( skinCluster ):
	'''
	splats the current pose of the skeleton into the skinCluster - ie whatever
	the current pose is becomes the bindpose
	'''
	nInf = len( listConnections( skinCluster.matrix, destination=False ) )
	for n in range( nInf ):
		try:
			cons = listConnections( skinCluster.matrix[ n ], destination=False )
			slotNJoint = cons[ 0 ]
		except IndexError: continue

		matrixAsStr = ' '.join( map( str, cmd.getAttr( '%s.worldInverseMatrix' % slotNJoint ) ) )
		melStr = 'setAttr -type "matrix" %s.bindPreMatrix[ %d ] %s' % (skinCluster, n, matrixAsStr)
		mel.eval( melStr )

		#reset the stored pose in any dagposes that are conn
		for dPose in listConnections( skinCluster, d=False, type='dagPose' ):
			dagPose( slotNJoint, reset=True, n=dPose )


def enableSkinClusters():
	for c in ls( type='skinCluster' ):
		resetSkinCluster( c )
		c.nodeState = 0


def disableSkinClusters():
	for c in ls( type='skinCluster' ):
		c.nodeState = 1


def getSkinClusterEnableState():
	for c in ls( type='skinCluster' ):
		if c.nodeState.get() == 1:
			return False

	return True


def buildMeasure( startNode, endNode ):
	measure = createNode( 'distanceDimShape', n='%s_to_%s_measureShape#' % (startNode, endNode) )
	measureT = measure.getParent()

	locA = spaceLocator()
	locB = spaceLocator()
	pymelCore.parent( locA, startNode, r=True )
	pymelCore.parent( locB, endNode, r=True )

	locAShape = locA.getShape()
	locBShape = locB.getShape()

	connectAttr( locAShape.worldPosition[ 0 ], measure.startPoint, f=True )
	connectAttr( locBShape.worldPosition[ 0 ], measure.endPoint, f=True )

	return measureT, measure, locA, locB


def buildAnnotation( obj, text='' ):
	'''
	like the distance command above, this is a simple wrapper for creating annotation nodes,
	and having the nodes you actually want returned to you.  whoever wrote these commands
	should be shot.  with a large gun

	returns a 3 tuple containing the start transform, end transform, and annotation shape node
	'''
	obj = str( obj )  #cast as string just in case we've been passed a PyNode instance

	rand = random.randint
	end = spaceLocator()
	shape = PyNode( annotate( end, p=(rand(0, 1000000), rand(1000000, 2000000), 2364), tx=text ) )

	start = shape.getParent()
	endShape = end.getShape()

	delete( parentConstraint( obj, end ) )
	for ax in Axis.AXES[ :3 ]:
		start.attr( "t"+ ax ).set( 0 )

	endShape.v.set( 0 )
	endShape.v.setLocked( True )
	pymelCore.parent( end, obj )

	return start, end, shape


def chainLength( startNode, endNode ):
	'''
	measures the length of the chain were it to be straightened out
	'''
	length = 0
	curNode = endNode
	for p in api.iterParents( endNode ):
		curPos = Vector( xform( curNode, q=True, ws=True, rp=True ) )
		parPos = Vector( xform( p, q=True, ws=True, rp=True ) )
		dif = curPos - parPos
		length += dif.get_magnitude()

		if p == startNode:
			break

		curNode = p

	return length


def switchToFK( control, ikHandle=None, onCmd=None, offCmd=None ):
	'''
	this proc will align the bones controlled by an ik chain to the fk chain

		ikHandle  this flag specifies the name of the ikHandle to work on
		onCmd     this flag tells the script what command to run to turn the ik handle on - it is often left blank because its assumed we're already in ik mode
		offCmd    this flag holds the command to turn the ik handle off, and switch to fk mode

	NOTE: if the offCmd isn't specified, it defaults to:  lambda c, ik: c.ikBlend.set( 0 )

	both on and off callbacks take 2 args - the control and the ikHandle

	example:
	switchToFK( ikHandle1, onCmd=lambda ctrl, ik: ik.ikBlend.set( 1 ), offCmd=lambda c, ik: setAttr ik.ikBlend.set( 0 ) )
	'''
	if ikHandle is None:
		ikHandle = control

	if onCmd is None:
		onCmd = lambda c, ik: c.ikBlend.set( 0 )

	control, ikHandle = map( PyNode, [ control, ikHandle ] )

	if callable( onCmd ):
		onCmd( control, ikHandle )

	joints = map( PyNode, pymelCore.ikHandle( ikHandle, q=True, jl=True ) )
	effector = PyNode( pymelCore.ikHandle( ikHandle, q=True, ee=True ) )
	effectorCtrl = effector.tx.listConnections( d=False )[ 0 ]
	jRotations = [ j.r.get() for j in joints ]

	#if alignEnd: pass #zooAlign ( "-key 1 -src "+ $ikHandle +" -tgt "+ $effectorCtrl[0] );
	if callable( offCmd ):
		offCmd( control, ikHandle )

	for j, rot in zip( joints, jRotations ):
		if j.rx.isSettable(): j.rx.set( rot[ 0 ] )
		if j.ry.isSettable(): j.ry.set( rot[ 1 ] )
		if j.rz.isSettable(): j.rz.set( rot[ 2 ] )


def switchToIK( control, ikHandle=None, poleControl=None, onCmd=None, offCmd=None ):
	'''
	this proc will align the IK controller to its fk chain
	flags used:
	-control   this is the actual control being used to move the ikHandle - it is assumed to be the same object as the ikHandle, but if its different (ie if the ikHandle is constrained to a controller) use this flag
	-pole      tells the script the name of the pole controller - if there is no pole vector control, leave this flag out
	-ikHandle  this flag specifies the name of the ikHandle to work on
	-onCmd     this flag tells the script what command to run to turn the ik handle on - it is often left blank because its assumed we're already in ik mode
	-offCmd    this flag holds the command to turn the ik handle off, and switch to fk mode
	NOTE: if the offCmd isn't specified, it defaults to:  if( `getAttr -se ^.ikb` ) setAttr ^.ikb 1;

	symbols to use in cmd strings:
	 ^  refers to the ikHandle
	 #  refers to the control object

	example:
	zooAlignIK "-control somObj -ikHandle ikHandle1 -offCmd setAttr #.fkMode 0";
	'''
	if ikHandle is None:
		ikHandle = control

	if callable( onCmd ):
		onCmd( control, ikHandle, poleControl )

	joints = pymelCore.ikHandle( ikHandle, q=True, jl=True )
	effector = pymelCore.ikHandle( ikHandle, q=True, ee=True )
	effectorCtrl = effector.tx.listConnections( d=False )[ 0 ]

	mel.zooAlign( "-src %s -tgt %s" % (effectorCtrl, control) )
	if poleControl is not None and objExists( poleControl ):
		pos = mel.zooFindPolePosition( "-start %s -mid %s -end %s" % (joints[ 0 ], joints[ 1 ], effectorCtrl) )
		move( poleControl, a=True, ws=True, rpr=True, *pos )

	if callable( offCmd ):
		offCmd( control, ikHandle, poleControl )

'''
//transfers the pose on a child to its parent
global proc zooChildToParent( string $child ) {
	string $sel[] = `ls -sl`;
	string $parent = zooGetElement_str(0,`listRelatives -f -p $child`);
	string $loc = zooGetElement_str(0,`spaceLocator`);

	zooAlign ( "-src "+ $child +" -tgt "+ $loc );
	zooResetAttrs $child;
	zooAlign ( "-src "+ $loc +" -tgt "+ $parent );
	delete $loc;
	select $sel;
	}


global proc string zooGetPostTraceCmd( string $obj ) {
	if( `objExists ( $obj +".xferPostTraceCmd" )`) return `getAttr ( $obj +".xferPostTraceCmd" )`;
	return "";
	}


global proc zooSetPostTraceCmd( string $obj, string $cmd ) {
	if( $cmd == "" ) return;
	if( !`objExists ( $obj +".xferPostTraceCmd" )`) addAttr -dt "string" -ln xferPostTraceCmd $obj;
	setAttr -type "string" ( $obj +".xferPostTraceCmd" ) $cmd;
	}
'''


del( control )

#end
