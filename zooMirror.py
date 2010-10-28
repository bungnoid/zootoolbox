
from vectors import Matrix, Vector, Axis

import maya.cmds as cmd
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

import apiExtensions

from maya.OpenMaya import MObject, MFnMatrixAttribute, MFnCompoundAttribute, \
     MFnEnumAttribute, MFnNumericAttribute, MFnNumericData, MFnDependencyNode, \
     MPoint, MVector, MSyntax, MArgDatabase

from maya.OpenMayaMPx import MPxNode

MPxCommand = OpenMayaMPx.MPxCommand
kUnknownParameter = OpenMaya.kUnknownParameter


class MirrorNode(MPxNode):

	NODE_ID = OpenMaya.MTypeId( 0x00115940 )
	NODE_TYPE_NAME = "rotationMirror"

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
	MIRROR_DEFAULT = M_MIRROR

	@classmethod
	def Creator( cls ):
		return OpenMayaMPx.asMPxPtr( cls() )
	@classmethod
	def Init( cls ):
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
		cls.inWorldMatrix = attrInWorldMatrix.create( "inWorldMatrix", "iwm" )

		cls.addAttribute( cls.inWorldMatrix )


		#create the local matrix
		cls.inParentMatrixInv = attrInWorldMatrix.create( "inParentInverseMatrix", "ipmi" )

		cls.addAttribute( cls.inParentMatrixInv )


		#create the mirror axis
		cls.mirrorAxis = attrMirrorAxis.create( "mirrorAxis", "m" )
		attrMirrorAxis.addField( 'x', 0 )
		attrMirrorAxis.addField( 'y', 1 )
		attrMirrorAxis.addField( 'z', 2 )
		attrMirrorAxis.setDefault( 'x' )
		attrMirrorAxis.setKeyable( False )
		attrMirrorAxis.setChannelBox( True )

		cls.addAttribute( cls.mirrorAxis )


		#create the mirror axis
		cls.mirrorTranslation = attrMirrorTranslation.create( "mirrorTranslation", "mt" )
		for modeName, modeIdx in zip( cls.MIRROR_MODE_NAMES, cls.MIRROR_MODES ):
			attrMirrorTranslation.addField( modeName, modeIdx )

		attrMirrorTranslation.setDefault( cls.MIRROR_DEFAULT )
		attrMirrorTranslation.setKeyable( False )
		attrMirrorTranslation.setChannelBox( True )

		cls.addAttribute( cls.mirrorTranslation )


		#create the out world matrix inverse
		cls.targetParentMatrixInv = attrTargetParentMatrixInv.create( "targetParentInverseMatrix", "owm" )

		cls.addAttribute( cls.targetParentMatrixInv )


		#create the joint orient compensation attributes
		cls.targetJointOrient = attrTargetJointOrient.create( "targetJointOrient", "tjo" )
		cls.targetJointOrientX = attrTargetJointOrientX.create( "targetJointOrientX", "tjox", MFnNumericData.kDouble )
		cls.targetJointOrientY = attrTargetJointOrientY.create( "targetJointOrientY", "tjoy", MFnNumericData.kDouble )
		cls.targetJointOrientZ = attrTargetJointOrientZ.create( "targetJointOrientZ", "tjoz", MFnNumericData.kDouble )

		attrTargetJointOrient.addChild( cls.targetJointOrientX )
		attrTargetJointOrient.addChild( cls.targetJointOrientY )
		attrTargetJointOrient.addChild( cls.targetJointOrientZ )
		cls.addAttribute( cls.targetJointOrient )


		#create the out translate attributes
		cls.outTranslate = attrOutTranslate.create( "outTranslate", "ot" )
		cls.outTranslateX = attrOutTranslateX.create( "outTranslateX", "otx", MFnNumericData.kDouble )
		cls.outTranslateY = attrOutTranslateY.create( "outTranslateY", "oty", MFnNumericData.kDouble )
		cls.outTranslateZ = attrOutTranslateZ.create( "outTranslateZ", "otz", MFnNumericData.kDouble )

		attrOutTranslate.addChild( cls.outTranslateX )
		attrOutTranslate.addChild( cls.outTranslateY )
		attrOutTranslate.addChild( cls.outTranslateZ )
		cls.addAttribute( cls.outTranslate )


		#create the out rotation attributes
		cls.outRotate = attrOutRotate.create( "outRotate", "or" )
		cls.outRotateX = attrOutRotateX.create( "outRotateX", "orx", MFnNumericData.kDouble )
		cls.outRotateY = attrOutRotateY.create( "outRotateY", "ory", MFnNumericData.kDouble )
		cls.outRotateZ = attrOutRotateZ.create( "outRotateZ", "orz", MFnNumericData.kDouble )

		attrOutRotate.addChild( cls.outRotateX )
		attrOutRotate.addChild( cls.outRotateY )
		attrOutRotate.addChild( cls.outRotateZ )
		cls.addAttribute( cls.outRotate )


		#setup attribute dependency relationships
		cls.attributeAffects( cls.inWorldMatrix, cls.outTranslate )
		cls.attributeAffects( cls.inWorldMatrix, cls.outRotate )

		cls.attributeAffects( cls.inParentMatrixInv, cls.outTranslate )
		cls.attributeAffects( cls.inParentMatrixInv, cls.outRotate )

		cls.attributeAffects( cls.mirrorAxis, cls.outTranslate )
		cls.attributeAffects( cls.mirrorAxis, cls.outRotate )

		cls.attributeAffects( cls.mirrorTranslation, cls.outTranslate )
		cls.attributeAffects( cls.mirrorTranslation, cls.outRotate )

		cls.attributeAffects( cls.targetParentMatrixInv, cls.outTranslate )
		cls.attributeAffects( cls.targetParentMatrixInv, cls.outRotate )

		cls.attributeAffects( cls.targetJointOrient, cls.outRotate )

	def compute( self, plug, dataBlock ):
		dh_mirrorTranslation = dataBlock.inputValue( self.mirrorTranslation )
		mirrorTranslation = Axis( dh_mirrorTranslation.asShort() )

		inWorldMatrix = dataBlock.inputValue( self.inWorldMatrix ).asMatrix()
		inParentInvMatrix = dataBlock.inputValue( self.inParentMatrixInv ).asMatrix()

		dh_mirrorAxis = dataBlock.inputValue( self.mirrorAxis )
		axis = Axis( dh_mirrorAxis.asShort() )

		### DEAL WITH ROTATION AND POSITION SEPARATELY ###
		R, S = inWorldMatrix.asPy( 3 ).decompose()  #this gets just the 3x3 rotation and scale matrices
		x, y, z = R  #extract basis vectors

		#mirror the rotation axes and construct the mirrored rotation matrix
		idxA, idxB = axis.otherAxes()
		x[ idxA ] = -x[ idxA ]
		x[ idxB ] = -x[ idxB ]

		y[ idxA ] = -y[ idxA ]
		y[ idxB ] = -y[ idxB ]

		z[ idxA ] = -z[ idxA ]
		z[ idxB ] = -z[ idxB ]

		#factor scale back into the matrix
		mirroredMatrix = Matrix( x + y + z, 3 ) * S
		mirroredMatrix = mirroredMatrix.expand( 4 )

		#now put the rotation matrix in the space of the target object
		dh_targetParentMatrixInv = dataBlock.inputValue( self.targetParentMatrixInv )
		tgtParentMatrixInv = dh_targetParentMatrixInv.asMatrix()
		matInv = tgtParentMatrixInv.asPy()

		#put the rotation in the space of the target's parent
		mirroredMatrix = mirroredMatrix * matInv

		#if there is a joint orient, make sure to compensate for it
		tgtJoX = dataBlock.inputValue( self.targetJointOrientX ).asDouble()
		tgtJoY = dataBlock.inputValue( self.targetJointOrientY ).asDouble()
		tgtJoZ = dataBlock.inputValue( self.targetJointOrientZ ).asDouble()

		jo = Matrix.FromEulerXYZ( tgtJoX, tgtJoY, tgtJoZ )
		joInv = jo.inverse()
		joInv = joInv.expand( 4 )
		mirroredMatrix = mirroredMatrix * joInv

		#grab euler values
		R, S = mirroredMatrix.decompose()  #we need to decompose again to extract euler angles...
		eulerXYZ = outX, outY, outZ = R.ToEulerXYZ()

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


class CreateMirrorNode(MPxCommand):
	CMD_NAME = 'rotationMirror'
	_ARG_SPEC = [ ('-h', '-help', MSyntax.kNoArg, 'prints help'),
	              ('-ax', '-axis', MSyntax.kString, 'the axis to mirror across (defaults to x)'),
	              ('-m', '-translationMode', MSyntax.kString, 'the mode in which translation is mirrored - %s (defaults to %s)' % (' '.join( MirrorNode.MIRROR_MODE_NAMES ), MirrorNode.MIRROR_MODE_NAMES[ MirrorNode.MIRROR_DEFAULT ])),
	              #('-s', '-space', MSyntax.kString, 'which space to mirror in - world or local (defaults to world)') ]
	              ]

	kFlagHelp = _ARG_SPEC[ 0 ][ 0 ]
	kFlagAxis = _ARG_SPEC[ 1 ][ 0 ]
	kFlagMode = _ARG_SPEC[ 2 ][ 0 ]

	@classmethod
	def SyntaxCreator( cls ):
		syntax = OpenMaya.MSyntax()

		for shortFlag, longFlag, syntaxType, h in cls.IterArgSpec():
			syntax.addFlag( shortFlag, longFlag, syntaxType )

		syntax.useSelectionAsDefault( True )
		syntax.setObjectType( MSyntax.kSelectionList, 1, 3 )

		syntax.enableQuery( True )
		syntax.enableEdit( True )

		return syntax
	@classmethod
	def Creator( cls ):
		return OpenMayaMPx.asMPxPtr( cls() )
	@classmethod
	def IterArgSpec( cls ):
		for data in cls._ARG_SPEC:
			if len( data ) != 4:
				yield data + ('<no help available>',)
			else:
				yield data

	def grabArgDb( self, mArgs ):
		try:
			argData = MArgDatabase( self.syntax(), mArgs )
		except RuntimeError:
			return True, None

		if argData.isFlagSet( self.kFlagHelp ):
			self.printHelp()
			return True, None

		return False, argData
	def printHelp( self ):
		longestFlag = 5
		for shortFlag, longFlag, syntaxType, h in self.IterArgSpec():
			longestFlag = max( longestFlag, len(longFlag) )

		self.displayInfo( '%s - USAGE' % self.CMD_NAME )

		printStr = '*%5s  %'+ str( longestFlag ) +'s: %s'
		for shortFlag, longFlag, syntaxType, h in self.IterArgSpec():
			self.displayInfo( printStr % (shortFlag, longFlag, h) )
	def doIt( self, mArgs ):
		ret, argData = self.grabArgDb( mArgs )
		if ret:
			return

		sel = OpenMaya.MSelectionList()
		argData.getObjects( sel )

		objs = []
		for n in range( sel.length() ):
			obj = MObject()
			sel.getDependNode( n, obj )
			objs.append( obj )

		#
		if argData.isQuery():
			rotNode = objs[0]

			if argData.isFlagSet( self.kFlagAxis ):
				self.setResult( cmd.getAttr( '%s.mirrorAxis' % rotNode ) )

			elif argData.isFlagSet( self.kFlagMode ):
				self.setResult( cmd.getAttr( '%s.mirrorTranslation' % rotNode ) )

			return

		#if we're in edit mode, find the node
		elif argData.isEdit():
			rotNode = objs[0]

		#otherwise we're in creation mode - so build the node and connect things up
		else:
			obj, tgt = objs

			#see if there is already a node connected
			existing = cmd.listConnections( '%s.t' % tgt, '%s.r' % tgt, type=MirrorNode.NODE_TYPE_NAME )
			if existing:
				self.displayWarning( "There is a %s node already connected - use edit mode!" % MirrorNode.NODE_TYPE_NAME )
				self.setResult( existing[ 0 ] )

				return
			else:
				rotNode = cmd.createNode( 'rotationMirror' )
				cmd.connectAttr( '%s.worldMatrix' % obj, '%s.inWorldMatrix' % rotNode )
				cmd.connectAttr( '%s.parentInverseMatrix' % obj, '%s.inParentInverseMatrix' % rotNode )

				cmd.connectAttr( '%s.parentInverseMatrix' % tgt, '%s.targetParentInverseMatrix' % rotNode )

				joAttrpath = '%s.jo' % tgt
				if cmd.objExists( joAttrpath ):
					cmd.connectAttr( joAttrpath, '%s.targetJointOrient' % rotNode )

				cmd.connectAttr( '%s.outTranslate' % rotNode, '%s.t' % tgt )
				cmd.connectAttr( '%s.outRotate' % rotNode, '%s.r' % tgt )
				cmd.select( obj )

		#set the result to the node created...
		self.setResult( rotNode )

		#set any attributes passed in from the command-line
		if argData.isFlagSet( self.kFlagAxis ):
			axisInt = Axis.FromName( argData.flagArgumentString( self.kFlagAxis, 0 ) )
			cmd.setAttr( '%s.mirrorAxis' % rotNode, axisInt )

		if argData.isFlagSet( self.kFlagMode ):
			modeStr = argData.flagArgumentString( self.kFlagMode, 0 )
			modeIdx = list( MirrorNode.MIRROR_MODE_NAMES ).index( modeStr )
			cmd.setAttr( '%s.mirrorTranslation' % rotNode, modeIdx )
	def undoIt( self ):
		pass
	def isUndoable( self ):
		return True


classesToRegister = [ CreateMirrorNode ]

def initializePlugin( mobject ):
	mplugin = OpenMayaMPx.MFnPlugin( mobject, 'macaronikazoo', '1' )
	mplugin.registerNode( MirrorNode.NODE_TYPE_NAME, MirrorNode.NODE_ID, MirrorNode.Creator, MirrorNode.Init )

	for cls in classesToRegister:
		cmdName = cls.CMD_NAME

		try:
			mplugin.registerCommand( cmdName, cls.Creator, cls.SyntaxCreator )
			mplugin.registerCommand( cmdName.lower(), cls.Creator, cls.SyntaxCreator )
		except:
			self.displayError( "Failed to register command: %s\n" % cmdName )
			raise


def uninitializePlugin( mobject ):
	mplugin = OpenMayaMPx.MFnPlugin( mobject )
	mplugin.deregisterNode( MirrorNode.NODE_ID )

	for cls in classesToRegister:
		cmdName = cls.CMD_NAME

		try:
			mplugin.deregisterCommand( cmdName )
			mplugin.deregisterCommand( cmdName.lower() )
		except:
			self.displayError( "Failed to unregister command: %s\n" % cmdName )
			raise


#end
