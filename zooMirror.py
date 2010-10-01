
from vectors import Matrix, Vector, Axis

import maya.cmds as cmd
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

from maya.OpenMaya import MObject, MFnMatrixAttribute, MFnCompoundAttribute, \
     MFnEnumAttribute, MFnNumericAttribute, MFnNumericData, MFnDependencyNode, \
     MPoint, MVector

from maya.OpenMayaMPx import MPxNode

kUnknownParameter = OpenMaya.kUnknownParameter


nodeTypeName = "rotationMirror"
nodeID = OpenMaya.MTypeId( 0x00115940 )


class MirrorNode(MPxNode):

	inWorldMatrix = MObject()  #this is the input world matrix; the one we want mirrored
	inParentMatrixInv = MObject()  #this is the input parent inverse matrix. ie the parent inverse matrix of the transform we want mirrored

	mirrorAxis = MObject()  #which axis are we mirroring on?
	mirrorTranslation = MObject()  #boolean to determine whether translation mirroring happens in world space or local space

	targetJointOrient = MObject()  #this is the joint orient attribute for the target joint - so it can be compensated for
	targetJointOrientX = MObject()
	targetJointOrientY = MObject()
	targetJointOrientZ = MObject()

	targetParentMatrixInv = MObject()  #this is the parent inverse matrix for the target transform

	outTranslate = MObject()  #the output translation
	outTranslateX = MObject()
	outTranslateY = MObject()
	outTranslateZ = MObject()

	outRotate = MObject()  #the output rotation
	outRotateX = MObject()
	outRotateY = MObject()
	outRotateZ = MObject()

	MIRROR_MODES = M_COPY, M_INVERT, M_MIRROR = range( 3 )
	MIRROR_MODE_NAMES = 'copy', 'invert', 'mirror'

	def compute( self, plug, dataBlock ):
		dh_mirrorTranslation = dataBlock.inputValue( self.mirrorTranslation )
		mirrorTranslation = Axis( dh_mirrorTranslation.asShort() )

		inWorldMatrix = dataBlock.inputValue( self.inWorldMatrix ).asMatrix()
		inParentInvMatrix = dataBlock.inputValue( self.inParentMatrixInv ).asMatrix()

		dh_mirrorAxis = dataBlock.inputValue( self.mirrorAxis )
		axis = Axis( dh_mirrorAxis.asShort() )

		### DEAL WITH ROTATION AND POSITION SEPARATELY ###

		#construct the rotation matrix
		x = [inWorldMatrix(0,0), inWorldMatrix(0,1), inWorldMatrix(0,2)]
		y = [inWorldMatrix(1,0), inWorldMatrix(1,1), inWorldMatrix(1,2)]
		z = [inWorldMatrix(2,0), inWorldMatrix(2,1), inWorldMatrix(2,2)]

		#mirror the rotation axes and construct the mirrored rotation matrix
		idxA, idxB = axis.otherAxes()
		x[ idxA ] = -x[ idxA ]
		x[ idxB ] = -x[ idxB ]

		y[ idxA ] = -y[ idxA ]
		y[ idxB ] = -y[ idxB ]

		z[ idxA ] = -z[ idxA ]
		z[ idxB ] = -z[ idxB ]

		mirroredMatrix = Matrix( x + y + z, 3 )

		#now put the rotation matrix in the space of the target object
		dh_targetParentMatrixInv = dataBlock.inputValue( self.targetParentMatrixInv )
		tgtParentMatrixInv = dh_targetParentMatrixInv.asMatrix()
		matInv = Matrix( [ tgtParentMatrixInv(0,0), tgtParentMatrixInv(0,1), tgtParentMatrixInv(0,2),
		                   tgtParentMatrixInv(1,0), tgtParentMatrixInv(1,1), tgtParentMatrixInv(1,2),
		                   tgtParentMatrixInv(2,0), tgtParentMatrixInv(2,1), tgtParentMatrixInv(2,2) ], 3 )


		#put the rotation in the space of the target's parent
		mirroredMatrix = mirroredMatrix * matInv

		#if there is a joint orient, make sure to compensate for it
		tgtJoX = dataBlock.inputValue( self.targetJointOrientX ).asDouble()
		tgtJoY = dataBlock.inputValue( self.targetJointOrientY ).asDouble()
		tgtJoZ = dataBlock.inputValue( self.targetJointOrientZ ).asDouble()

		jo = Matrix.FromEulerXYZ( tgtJoX, tgtJoY, tgtJoZ )
		joInv = jo.inverse()
		mirroredMatrix = mirroredMatrix * joInv

		#grab euler values
		eulerXYZ = outX, outY, outZ = mirroredMatrix.ToEulerXYZ()

		dh_outRX = dataBlock.outputValue( self.outRotateX )
		dh_outRY = dataBlock.outputValue( self.outRotateY )
		dh_outRZ = dataBlock.outputValue( self.outRotateZ )

		#set the rotation
		dh_outRX.setDouble( outX )
		dh_outRY.setDouble( outY )
		dh_outRZ.setDouble( outZ )

		dataBlock.setClean( plug )


		### NOW DEAL WITH POSITION ###

		#set the position
		if mirrorTranslation == self.M_COPY:
			inLocalMatrix = inWorldMatrix * inParentInvMatrix
			pos = MPoint( inLocalMatrix(3,0), inLocalMatrix(3,1), inLocalMatrix(3,2) )
		elif mirrorTranslation == self.M_INVERT:
			inLocalMatrix = inWorldMatrix * inParentInvMatrix
			pos = MPoint( -inLocalMatrix(3,0), -inLocalMatrix(3,1), -inLocalMatrix(3,2) )
		elif mirrorTranslation == self.M_MIRROR:
			pos = MPoint( inWorldMatrix(3,0), inWorldMatrix(3,1), inWorldMatrix(3,2) )
			pos = [ pos.x, pos.y, pos.z ]
			pos[ axis ] = -pos[ axis ]
			pos = MPoint( *pos )
			pos = pos * tgtParentMatrixInv

		else:
			return

		dh_outTX = dataBlock.outputValue( self.outTranslateX )
		dh_outTY = dataBlock.outputValue( self.outTranslateY )
		dh_outTZ = dataBlock.outputValue( self.outTranslateZ )

		dh_outTX.setDouble( pos[0] )
		dh_outTY.setDouble( pos[1] )
		dh_outTZ.setDouble( pos[2] )


def nodeCreator():
	return OpenMayaMPx.asMPxPtr( MirrorNode() )


def nodeInit():
	attrInWorldMatrix = MFnMatrixAttribute()
	attrInParentMatrixInv = MFnMatrixAttribute()

	attrMirrorAxis = MFnEnumAttribute()
	attrMirrorTranslation = MFnEnumAttribute()

	attrTargetParentMatrixInv = MFnMatrixAttribute()

	attrOutTranslate = MFnCompoundAttribute()
	attrOutTranslateX = MFnNumericAttribute()
	attrOutTranslateY = MFnNumericAttribute()
	attrOutTranslateZ = MFnNumericAttribute()

	attrOutRotate = MFnCompoundAttribute()
	attrOutRotateX = MFnNumericAttribute()
	attrOutRotateY = MFnNumericAttribute()
	attrOutRotateZ = MFnNumericAttribute()

	attrTargetJointOrient = MFnCompoundAttribute()
	attrTargetJointOrientX = MFnNumericAttribute()
	attrTargetJointOrientY = MFnNumericAttribute()
	attrTargetJointOrientZ = MFnNumericAttribute()

	#create the world matrix
	MirrorNode.inWorldMatrix = attrInWorldMatrix.create( "inWorldMatrix", "iwm" )

	MirrorNode.addAttribute( MirrorNode.inWorldMatrix )


	#create the local matrix
	MirrorNode.inParentMatrixInv = attrInWorldMatrix.create( "inParentInverseMatrix", "ipmi" )

	MirrorNode.addAttribute( MirrorNode.inParentMatrixInv )


	#create the mirror axis
	MirrorNode.mirrorAxis = attrMirrorAxis.create( "mirrorAxis", "m" )
	attrMirrorAxis.addField( 'x', 0 )
	attrMirrorAxis.addField( 'y', 1 )
	attrMirrorAxis.addField( 'z', 2 )
	attrMirrorAxis.setDefault( 'x' )
	attrMirrorAxis.setKeyable( False )
	attrMirrorAxis.setChannelBox( True )

	MirrorNode.addAttribute( MirrorNode.mirrorAxis )


	#create the mirror axis
	MirrorNode.mirrorTranslation = attrMirrorTranslation.create( "mirrorTranslation", "mt" )
	for modeName, modeIdx in zip( MirrorNode.MIRROR_MODE_NAMES, MirrorNode.MIRROR_MODES ):
		attrMirrorTranslation.addField( modeName, modeIdx )

	attrMirrorTranslation.setDefault( MirrorNode.M_INVERT )
	attrMirrorTranslation.setKeyable( False )
	attrMirrorTranslation.setChannelBox( True )

	MirrorNode.addAttribute( MirrorNode.mirrorTranslation )


	#create the out world matrix inverse
	MirrorNode.targetParentMatrixInv = attrTargetParentMatrixInv.create( "targetParentInverseMatrix", "owm" )

	MirrorNode.addAttribute( MirrorNode.targetParentMatrixInv )


	#create the joint orient compensation attributes
	MirrorNode.targetJointOrient = attrTargetJointOrient.create( "targetJointOrient", "tjo" )
	MirrorNode.targetJointOrientX = attrTargetJointOrientX.create( "targetJointOrientX", "tjox", MFnNumericData.kDouble )
	MirrorNode.targetJointOrientY = attrTargetJointOrientY.create( "targetJointOrientY", "tjoy", MFnNumericData.kDouble )
	MirrorNode.targetJointOrientZ = attrTargetJointOrientZ.create( "targetJointOrientZ", "tjoz", MFnNumericData.kDouble )

	attrTargetJointOrient.addChild( MirrorNode.targetJointOrientX )
	attrTargetJointOrient.addChild( MirrorNode.targetJointOrientY )
	attrTargetJointOrient.addChild( MirrorNode.targetJointOrientZ )
	MirrorNode.addAttribute( MirrorNode.targetJointOrient )


	#create the out translate attributes
	MirrorNode.outTranslate = attrOutTranslate.create( "outTranslate", "ot" )
	MirrorNode.outTranslateX = attrOutTranslateX.create( "outTranslateX", "otx", MFnNumericData.kDouble )
	MirrorNode.outTranslateY = attrOutTranslateY.create( "outTranslateY", "oty", MFnNumericData.kDouble )
	MirrorNode.outTranslateZ = attrOutTranslateZ.create( "outTranslateZ", "otz", MFnNumericData.kDouble )

	attrOutTranslate.addChild( MirrorNode.outTranslateX )
	attrOutTranslate.addChild( MirrorNode.outTranslateY )
	attrOutTranslate.addChild( MirrorNode.outTranslateZ )
	MirrorNode.addAttribute( MirrorNode.outTranslate )


	#create the out rotation attributes
	MirrorNode.outRotate = attrOutRotate.create( "outRotate", "or" )
	MirrorNode.outRotateX = attrOutRotateX.create( "outRotateX", "orx", MFnNumericData.kDouble )
	MirrorNode.outRotateY = attrOutRotateY.create( "outRotateY", "ory", MFnNumericData.kDouble )
	MirrorNode.outRotateZ = attrOutRotateZ.create( "outRotateZ", "orz", MFnNumericData.kDouble )

	attrOutRotate.addChild( MirrorNode.outRotateX )
	attrOutRotate.addChild( MirrorNode.outRotateY )
	attrOutRotate.addChild( MirrorNode.outRotateZ )
	MirrorNode.addAttribute( MirrorNode.outRotate )


	#setup attribute dependency relationships
	MirrorNode.attributeAffects( MirrorNode.inWorldMatrix, MirrorNode.outTranslate )
	MirrorNode.attributeAffects( MirrorNode.inWorldMatrix, MirrorNode.outRotate )

	MirrorNode.attributeAffects( MirrorNode.inParentMatrixInv, MirrorNode.outTranslate )
	MirrorNode.attributeAffects( MirrorNode.inParentMatrixInv, MirrorNode.outRotate )

	MirrorNode.attributeAffects( MirrorNode.mirrorAxis, MirrorNode.outTranslate )
	MirrorNode.attributeAffects( MirrorNode.mirrorAxis, MirrorNode.outRotate )

	MirrorNode.attributeAffects( MirrorNode.mirrorTranslation, MirrorNode.outTranslate )
	MirrorNode.attributeAffects( MirrorNode.mirrorTranslation, MirrorNode.outRotate )

	MirrorNode.attributeAffects( MirrorNode.targetParentMatrixInv, MirrorNode.outTranslate )
	MirrorNode.attributeAffects( MirrorNode.targetParentMatrixInv, MirrorNode.outRotate )

	MirrorNode.attributeAffects( MirrorNode.targetJointOrient, MirrorNode.outRotate )


def initializePlugin( mobject ):
	mplugin = OpenMayaMPx.MFnPlugin( mobject, 'macaronikazoo', '1' )
	mplugin.registerNode( nodeTypeName, nodeID, nodeCreator, nodeInit )


def uninitializePlugin( mobject ):
	mplugin = OpenMayaMPx.MFnPlugin( mobject )
	mplugin.deregisterNode( nodeID )


#end
