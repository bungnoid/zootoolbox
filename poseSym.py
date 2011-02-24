
from vectors import Vector, Matrix, Axis, AX_X, AX_Y, AX_Z
from rigUtils import MATRIX_ROTATION_ORDER_CONVERSIONS_FROM, MATRIX_ROTATION_ORDER_CONVERSIONS_TO
from maya.cmds import *
from maya.OpenMaya import MGlobal

import maya

AXES = Axis.BASE_AXES

#try to load the zooMirror.py plugin
try:
	loadPlugin( 'zooMirror.py', quiet=True )
except:
	MGlobal.displayError( 'Failed to load zooMirror.py plugin - is it in your plugin path?' )


def getLocalRotMatrix( obj ):
	'''
	returns the local matrix for the given obj
	'''
	localMatrix = Matrix( getAttr( '%s.matrix' % obj ), 4 )
	localMatrix.set_position( (0, 0, 0) )

	return localMatrix


def getWorldRotMatrix( obj ):
	'''
	returns the world matrix for the given obj
	'''
	worldMatrix = Matrix( getAttr( '%s.worldMatrix' % obj ), 4 )
	worldMatrix.set_position( (0, 0, 0) )

	return worldMatrix


def setWorldRotMatrix( obj, matrix ):
	'''
	given a world matrix, will set the transforms of the object
	'''
	parentInvMatrix = Matrix( getAttr( '%s.parentInverseMatrix' % obj ) )
	localMatrix = matrix * parentInvMatrix

	setLocalRotMatrix( obj, localMatrix )


def setLocalRotMatrix( obj, matrix ):
	'''
	given a world matrix, will set the transforms of the object
	'''

	roo = getAttr( '%s.rotateOrder' % obj )
	rot = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ roo ]( matrix, True )

	setAttr( '%s.r' % obj, *rot )


def mirrorMatrix( matrix, axis=AX_X, orientAxis=AX_X ):
	'''
	axis is the axis things are flipped across
	orientAxis is the axis that gets flipped when mirroring orientations
	'''
	assert isinstance( matrix, Matrix )
	mirroredMatrix = Matrix( matrix )

	#make sure we've been given a Axis instances...  don't bother testing, just do it, and make it absolute (non-negative - mirroring in -x is the same as mirroring in x)
	mirrorAxis = abs( Axis( axis ) )
	axisA = abs( Axis( orientAxis ) )

	#flip all axes
	axisB, axisC = axisA.otherAxes()
	mirroredMatrix[ axisB ][ mirrorAxis ] = -matrix[ axisB ][ mirrorAxis ]
	mirroredMatrix[ axisC ][ mirrorAxis ] = -matrix[ axisC ][ mirrorAxis ]

	#the above flipped all axes - but this results in a changing of coordinate system handed-ness, so flip one of the axes back
	nonMirrorAxisA, nonMirrorAxisB = mirrorAxis.otherAxes()
	mirroredMatrix[ axisA ][ nonMirrorAxisA ] = -mirroredMatrix[ axisA ][ nonMirrorAxisA ]
	mirroredMatrix[ axisA ][ nonMirrorAxisB ] = -mirroredMatrix[ axisA ][ nonMirrorAxisB ]

	#if the input matrix was a 4x4 then mirror translation
	if matrix.size == 4:
		mirroredMatrix[3][ mirrorAxis ] = -matrix[3][ mirrorAxis ]

	return mirroredMatrix


class ControlPair(object):
	'''
	sets up a relationship between two controls so that they can mirror/swap/match one
	another's poses.

	NOTE: when you construct a ControlPair setup (using the Create classmethod)
	'''

	#NOTE: these values are copied from the zooMirror script - they're copied because the plugin generally doesn't exist on the pythonpath so we can't rely on an import working....
	FLIP_AXES = (), (AX_X, AX_Y), (AX_X, AX_Z), (AX_Y, AX_Z)

	@classmethod
	def GetPairNode( cls, obj ):
		'''
		given a transform will return the pair node the control is part of
		'''

		if obj is None:
			return None

		if objectType( obj, isAType='transform' ):
			cons = listConnections( '%s.message' % obj, s=False, type='controlPair' )
			if not cons:
				return None

			return cons[0]

		if nodeType( obj ) == 'controlPair':
			return obj

		return None
	@classmethod
	def Create( cls, controlA, controlB=None, axis=None ):
		'''
		given two controls will setup the relationship between them

		NOTE: if controlB isn't given then it will only be able to mirror its current
		pose.  This is usually desirable on "central" controls like spine, head and
		neck controls
		'''

		#make sure we've been given transforms - mirroring doesn't make a whole lotta sense on non-transforms
		if not objectType( controlA, isAType='transform' ):
			return None

		if controlB:
			if not objectType( controlB, isAType='transform' ):
				return None

		#see if we have a pair node for the controls already
		pairNode = cls.GetPairNode( controlA )
		if pairNode:
			#if no controlB has been given see whether the pairNode we've already got also has no controlB - if so, we're done
			if not controlB:
				new = cls( pairNode )
				if not new.controlB:
					return new

			#if controlB HAS been given, check whether to see whether it has the same pairNode - if so, we're done
			if controlB:
				pairNodeB = cls.GetPairNode( controlB )
				if pairNode == pairNodeB:
					return cls( pairNode )

		#otherwise create a new one
		pairNode = createNode( 'controlPair' )
		connectAttr( '%s.message' % controlA, '%s.controlA' % pairNode )
		if controlB:
			connectAttr( '%s.message' % controlB, '%s.controlB' % pairNode )

		#name the node
		nodeName = '%s_mirrorConfig' if controlB is None else '%s_%s_exchangeConfig' % (controlA, controlB)
		pairNode = rename( pairNode, nodeName )

		#instantiate it and run the initial setup code over it
		new = cls( pairNode )
		new.setup( axis )

		return new

	def __init__( self, pairNodeOrControl ):
		self.node = pairNode = self.GetPairNode( pairNodeOrControl )
		self.controlA = None
		self.controlB = None

		cons = listConnections( '%s.controlA' % pairNode, d=False )
		if cons:
			self.controlA = cons[0]

		cons = listConnections( '%s.controlB' % pairNode, d=False )
		if cons:
			self.controlB = cons[0]

		#make sure we have a control A
		if self.controlA is None:
			raise TypeError( "Could not find controlA - need to!" )
	def __eq__( self, other ):
		if isinstance( other, ControlPair ):
			other

		return self.node == other.node
	def __ne__( self, other ):
		return not self.__eq__( other )
	def __hash__( self ):
		return hash( self.node )
	def getAxis( self ):
		return Axis( getAttr( '%s.axis' % self.node ) )
	def setAxis( self, axis ):
		setAttr( '%s.axis' % self.node, axis )
	def getFlips( self ):
		axes = getAttr( '%s.flipAxes' % self.node )
		return list( self.FLIP_AXES[ axes ] )
	def setFlips( self, flips ):
		if isinstance( flips, int ):
			setAttr( '%s.flipAxes' % self.node, flips )
	def isSingular( self ):
		return self.controlB is None
	def setup( self, axis=None ):
		'''
		sets up the initial state of the pair node
		'''

		if axis:
			axis = abs( Axis( axis ) )
			setAttr( '%s.axis' % self.node, axis )

		#if we have two controls try to auto determine the orientAxis and the flipAxes
		if self.controlA and self.controlB:
			worldMatrixA = getWorldRotMatrix( self.controlA )
			worldMatrixB = getWorldRotMatrix( self.controlB )

			#so restPoseB = restPoseA * offsetMatrix
			#restPoseAInv * restPoseB = restPoseAInv * restPoseA * offsetMatrix
			#restPoseAInv * restPoseB = I * offsetMatrix
			#thus offsetMatrix = restPoseAInv * restPoseB
			offsetMatrix = worldMatrixA.inverse() * worldMatrixB

			AXES = AX_X.asVector(), AX_Y.asVector(), AX_Z.asVector()
			flippedAxes = []
			for n in range( 3 ):
				axisNVector = Vector( offsetMatrix[ n ][ :3 ] )
				if axisNVector.dot( AXES[n] ) < 0:
					flippedAxes.append( n )

			for n, flipAxes in enumerate( self.FLIP_AXES ):
				if tuple( flippedAxes ) == flipAxes:
					setAttr( '%s.flipAxes' % self.node, n )
					break

		#this is a bit of a hack - and not always true, but generally singular controls built by skeleton builder will work with this value
		elif self.controlA:
			setAttr( '%s.flipAxes' % self.node, 1 )
	def mirrorMatrix( self, matrix ):
		matrix = mirrorMatrix( matrix, self.getAxis() )
		for flipAxis in self.getFlips():
			matrix.setRow( flipAxis, -Vector( matrix.getRow( flipAxis ) ) )

		return matrix
	def swap( self ):
		'''
		mirrors the pose of each control, and swaps them
		'''

		#if there is no controlB, then perform a mirror instead...
		if not self.controlB:
			self.mirror()
			return

		#restPoseB = restPoseA * offsetMatrix
		#and similarly:
		#so restPoseB * offsetMatrixInv = restPoseA
		worldMatrixA = getWorldRotMatrix( self.controlA )
		worldMatrixB = getWorldRotMatrix( self.controlB )

		newB = self.mirrorMatrix( worldMatrixA )
		newA = self.mirrorMatrix( worldMatrixB )

		setWorldRotMatrix( self.controlA, newA )
		setWorldRotMatrix( self.controlB, newB )

		#do position
		axis = self.getAxis()
		newPosA = xform( self.controlB, q=True, ws=True, rp=True )
		newPosA[ axis ] = -newPosA[ axis ]

		newPosB = xform( self.controlA, q=True, ws=True, rp=True )
		newPosB[ axis ] = -newPosB[ axis ]

		move( newPosA[0], newPosA[1], newPosA[2], self.controlA, ws=True, rpr=True )
		move( newPosB[0], newPosB[1], newPosB[2], self.controlB, ws=True, rpr=True )
	def mirror( self, controlAIsSource=True ):
		'''
		mirrors the pose of controlA (or controlB if controlAIsSource is False) and
		puts it on the "other" control

		NOTE: if controlAIsSource is True, then the pose of controlA is mirrored
		and put on to controlB, otherwise the reverse is done
		'''
		if self.isSingular():
			worldMatrix = getWorldRotMatrix( self.controlA )
			pos = xform( self.controlA, q=True, ws=True, rp=True )
			control = self.controlA
		else:
			#NOTE:
			#restPoseB = restPoseA * offsetMatrix
			#and similarly:
			#so restPoseB * offsetMatrixInv = restPoseA

			if controlAIsSource:
				worldMatrix = getWorldRotMatrix( self.controlA )
				pos = xform( self.controlA, q=True, ws=True, rp=True )
				control = self.controlB
			else:
				worldMatrix = getWorldRotMatrix( self.controlB )
				pos = xform( self.controlB, q=True, ws=True, rp=True )
				control = self.controlA

		newControlMatrix = self.mirrorMatrix( worldMatrix )
		setWorldRotMatrix( control, newControlMatrix )

		#do position
		pos[ self.getAxis() ] = -pos[ self.getAxis() ]
		move( pos[0], pos[1], pos[2], control, ws=True, rpr=True )
	def match( self, controlAIsSource=True ):
		'''
		pushes the pose of controlA (or controlB if controlAIsSource is False) to the
		"other" control

		NOTE: if controlAIsSource is True, then the pose of controlA is mirrored and
		copied and put on to controlB, otherwise the reverse is done
		'''

		#if this is a singular pair, bail - there's nothing to do
		if self.isSingular():
			return

		#NOTE:
		#restPoseB = restPoseA * offsetMatrix
		#and similarly:
		#so restPoseB * offsetMatrixInv = restPoseA

		if controlAIsSource:
			worldMatrix = getWorldRotMatrix( self.controlA )
			control = self.controlB
		else:
			worldMatrix = getWorldRotMatrix( self.controlB )
			control = self.controlA

		newControlMatrix = self.mirrorMatrix( worldMatrix )

		setWorldRotMatrix( control, newControlMatrix, t=False )
		setWorldRotMatrix( control, worldMatrix, r=False )


def getPairNodesFromObjs( objs ):
	'''
	given a list of objects, will return a minimal list of pair nodes
	'''
	pairs = set()
	for obj in objs:
		pairNode = ControlPair.GetPairNode( obj )
		if pairNode:
			pairs.add( pairNode )

	return list( pairs )


def getPairsFromObjs( objs ):
	return [ ControlPair( pair ) for pair in getPairNodesFromObjs( objs ) ]


def getPairsFromSelection():
	return getPairsFromObjs( ls( sl=True ) )


def iterPairAndObj( objs ):
	'''
	yields a 2-tuple containing the pair node and the initializing object
	'''
	pairNodesVisited = set()
	for obj in objs:
		pairNode = ControlPair.GetPairNode( obj )
		if pairNode:
			if pairNode in pairNodesVisited:
				continue

			pair = ControlPair( pairNode )

			yield pair, obj
			pairNodesVisited.add( pairNode )


#end
