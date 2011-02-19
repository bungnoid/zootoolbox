
from vectors import Vector, Matrix, Axis, AX_X
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


def getLocalMatrix( obj, includeRotatePivot=True ):
	'''
	returns the local matrix for the given obj
	'''
	localMatrix = Matrix( getAttr( '%s.matrix' % obj ), 4 )
	#if includeRotatePivot:
		#rp = Vector( getAttr( '%s.rp' % obj )[0] )
		#localMatrix.set_position( localMatrix.get_position() + rp )

	return localMatrix


def getWorldMatrix( obj, includeRotatePivot=True ):
	'''
	returns the world matrix for the given obj
	'''
	worldMatrix = Matrix( getAttr( '%s.worldMatrix' % obj ), 4 )
	if includeRotatePivot:
		#get teh rotation pivot
		rp = Vector( getAttr( '%s.rp' % obj )[0] )

		#transform it to be in the same space as the object
		rp = Matrix( getAttr( '%s.matrix' % obj ), 4 ).crop( 3 ) * rp
		worldMatrix.set_position( worldMatrix.get_position() + rp )

	return worldMatrix


def setWorldMatrix( obj, matrix, t=True, r=True, matrixIncludesRotatePivot=True ):
	'''
	given a world matrix, will set the transforms of the object
	'''
	parentInvMatrix = Matrix( getAttr( '%s.parentInverseMatrix' % obj ) )
	localMatrix = matrix * parentInvMatrix

	setLocalMatrix( obj, localMatrix, t, r, matrixIncludesRotatePivot )


def setLocalMatrix( obj, matrix, t=True, r=True, matrixIncludesRotatePivot=True ):
	'''
	given a world matrix, will set the transforms of the object
	'''
	attrs = []
	if t:
		pos = Vector( matrix.get_position() )
		#if matrixIncludesRotatePivot:
			#pos = pos - Vector( getAttr( '%s.rp' % obj )[0] )

		attrs.append( ('t', pos) )

	if r:
		roo = getAttr( '%s.rotateOrder' % obj )
		rot = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ roo ]( matrix, True )
		attrs.append( ('r', rot) )

	for c, vals in attrs:
		for ax, val in zip( AXES, vals):
			attrpath = '%s.%s%s' % (obj, c, ax)
			if getAttr( attrpath, se=True ):
				setAttr( attrpath, val )


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


def mirrorTransform( obj, axis=AX_X, orientAxis=AX_X ):
	'''
	this is basically a convenience function to do mirroring on the given object
	'''

	#grab the world matrix and mirror it across the world X axis
	worldMat = getWorldMatrix( obj )
	mirroredWorldMat = mirrorMatrix( worldMat, axis, orientAxis )

	setWorldMatrix( obj, mirroredWorldMat )


class ControlPair(object):
	'''
	sets up a relationship between two controls so that they can mirror/swap/match one
	another's poses.

	NOTE: when you construct a ControlPair setup (using the Create classmethod)
	'''

	@classmethod
	def GetPairNode( cls, obj ):
		'''
		given a transform will return the pair node the control is part of
		'''

		objType = nodeType( obj )
		if objType == 'transform':
			cons = listConnections( '%s.message' % obj, s=False, type='controlPair' )
			if not cons:
				return None

			return cons[0]

		if objType == 'controlPair':
			return obj

		return None
	@classmethod
	def Create( cls, controlA, controlB=None, axis=None, orientAxis=None ):
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
		new.setup( axis, orientAxis )

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
	def __hash__( self ):
		return hash( self.node )
	def getOffsetMatrix( self ):
		return Matrix( getAttr( '%s.offsetMatrix' % self.node ) )
	def getAxis( self ):
		return Axis( getAttr( '%s.axis' % self.node ) )
	def getOrientAxis( self ):
		return Axis( getAttr( '%s.orientationAxis' % self.node ) )
	def isSingular( self ):
		return self.controlB is None
	def setup( self, axis=None, orientAxis=None ):
		'''
		sets up the initial state of the pair node - this basically just stores the
		initial offsets of each pose on the pair node
		'''

		#only do this if the instance has both a controlA and a controlB
		if self.controlA and self.controlB:
			worldMatrixA = getWorldMatrix( self.controlA )
			worldMatrixB = getWorldMatrix( self.controlB )

			#so restPoseB = restPoseA * offsetMatrix
			#restPoseAInv * restPoseB = restPoseAInv * restPoseA * offsetMatrix
			#restPoseAInv * restPoseB = I * offsetMatrix
			#thus offsetMatrix = restPoseAInv * restPoseB
			offsetMatrix = worldMatrixA.inverse() * worldMatrixB
			offsetMatrix.cullSmallValues( 1e-5 )

			#throw away the position
			offsetMatrix.set_position( (0, 0, 0) )

			maya.mel.eval( 'setAttr -type "matrix" %s.offsetMatrix %s' % (self.node, ' '.join( map( str, offsetMatrix.as_list() ) )) )
			#setAttr( '%s.offsetMatrix' % self.node, type='matrix', *offsetMatrix.as_list() )  #this doesn't work 'coz maya is teh gheyz

		if axis:
			axis = abs( Axis( axis ) )
			setAttr( '%s.axis' % self.node, axis )

		if orientAxis:
			orientAxis = abs( Axis( orientAxis ) )
			setAttr( '%s.orientationAxis' % self.node, orientAxis )
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
		worldMatrixA = getWorldMatrix( self.controlA )
		worldMatrixB = getWorldMatrix( self.controlB )


		offsetMatrix = self.getOffsetMatrix()
		newB = mirrorMatrix( worldMatrixA, self.getAxis(), self.getOrientAxis() ) * offsetMatrix
		newA = mirrorMatrix( worldMatrixB, self.getAxis(), self.getOrientAxis() ) * offsetMatrix.inverse()

		setWorldMatrix( self.controlA, newA )
		setWorldMatrix( self.controlB, newB )
	def mirror( self, controlAIsSource=True ):
		'''
		mirrors the pose of controlA (or controlB if controlAIsSource is False) and
		puts it on the "other" control

		NOTE: if controlAIsSource is True, then the pose of controlA is mirrored
		and put on to controlB, otherwise the reverse is done
		'''
		if self.isSingular():
			mirrorTransform( self.controlA, self.getAxis(), self.getOrientAxis() )
		else:
			#NOTE:
			#restPoseB = restPoseA * offsetMatrix
			#and similarly:
			#so restPoseB * offsetMatrixInv = restPoseA

			if controlAIsSource:
				worldMatrix = getWorldMatrix( self.controlA )
				offsetMatrix = self.getOffsetMatrix()
				control = self.controlB
			else:
				worldMatrix = getWorldMatrix( self.controlB )
				offsetMatrix = self.getOffsetMatrix().inverse()
				control = self.controlA

			newControlMatrix = mirrorMatrix( worldMatrix, self.getAxis(), self.getOrientAxis() ) * offsetMatrix
			setWorldMatrix( control, newControlMatrix )
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
			worldMatrix = getWorldMatrix( self.controlA )
			offsetMatrix = self.getOffsetMatrix()
			control = self.controlB
		else:
			worldMatrix = getWorldMatrix( self.controlB )
			offsetMatrix = self.getOffsetMatrix().inverse()
			control = self.controlA

		newControlMatrix = mirrorMatrix( worldMatrix, self.getAxis(), self.getOrientAxis() ) * offsetMatrix
		setWorldMatrix( control, newControlMatrix, t=False )
		setWorldMatrix( control, worldMatrix, r=False )


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


#end
