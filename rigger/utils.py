'''
this module is simply a miscellaneous module for rigging support code - most of it is maya specific convenience code
for determining things like aimAxes, aimVectors, rotational offsets for controls etc...
'''

import maya.cmds as cmd, api, vectors
from vectors import *


AXES = ['x', 'y', 'z',\
		'-x', '-y', '-z']

def do():
	a = 'pCone1'
	b = 'model:bip_foot_L'


def getBasisVectors( obj ):
	'''
	returns 3 world space orthonormal basis vectors that represent the orientation of the given object
	'''
	xPrime, yPrime, zPrime = api.getBases( obj )

	return Vector([xPrime.x, xPrime.y, xPrime.z]), Vector([yPrime.x, yPrime.y, yPrime.z]), Vector([zPrime.x, zPrime.y, zPrime.z])


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

	return iterable[-1][1]


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
		axisVector = Vector.Axis( AXES[ axisIdx ] )

		#now just return the axis vector in world space
		mat = api.getWorldSpaceMatrix( obj )
		axisVector = api.MVectorToVector( api.VectorToMVector( axisVector ) * mat )

		return axisVector


def getAxisInDirection( obj, compareVector ):
	xPrime, yPrime, zPrime = getBasisVectors( obj )
	dots = compareVector.dot( xPrime, True ), compareVector.dot( yPrime, True ), compareVector.dot( zPrime, True )

	return indexOfLargest( dots )


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
	basis = map(api.MVectorToVector, api.getBases( wrist ))
	rots = [0, 0, 0]
	for n, axis in enumerate( AXES[:3] ):
		axis = Vector.Axis( axis )
		if axis.dot( basis[n] ) < 0:
			rots[n] = 180

	if performRotate:
		rots.append( wrist )
		cmd.rotate(rots[0], rots[1], rots[2], wrist, a=True, ws=True)

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


#end