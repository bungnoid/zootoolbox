import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx


AUTHOR = '-:macaroniKazoo:-'
VERSION = '1.0'
NODE_NAME = 'twister'
ID = OpenMaya.MTypeId( 0x43899 )


class twister( OpenMayaMPx.MPxNode ):
	aInWorldMatrixA = OpenMaya.MObject()
	aInWorldMatrixB = OpenMaya.MObject()
	aAxisA = OpenMaya.MObject()
	aAxisB = OpenMaya.MObject()
	aDivider = OpenMaya.MObject()
	aOutRotate = OpenMaya.MObject()
	aOutRotateX = OpenMaya.MObject()
	aOutRotateY = OpenMaya.MObject()
	aOutRotateZ = OpenMaya.MObject()
	
	#-------------------
	#DEBUG
	aOutVecA = OpenMaya.MObject()
	aOutVecAX = OpenMaya.MObject()
	aOutVecAY = OpenMaya.MObject()
	aOutVecAZ = OpenMaya.MObject()
	aOutVecB = OpenMaya.MObject()
	aOutVecBX = OpenMaya.MObject()
	aOutVecBY = OpenMaya.MObject()
	aOutVecBZ = OpenMaya.MObject()
	#-------------------
	def __init__( self ):
		OpenMayaMPx.MPxNode.__init__(self)
	def compute( self, plug, data ):
		if plug == self.aOutRotate or plug == self.aOutRotateX or plug == self.aOutRotateY or plug == self.aOutRotateZ or ( plug == self.aOutVecA or plug == self.aOutVecAX or plug == self.aOutVecAY or plug == self.aOutVecAZ or plug == self.aOutVecB or plug == self.aOutVecBX or plug == self.aOutVecBY or plug == self.aOutVecBZ):
			#get handles to the attributes
			hInWorldMatrixA = data.inputValue(self.aInWorldMatrixA)
			matWorldA = hInWorldMatrixA.asMatrix()
			matWorldAinv = matWorldA.inverse()
			xformA = OpenMaya.MTransformationMatrix(matWorldA)

			hInWorldMatrixB = data.inputValue(self.aInWorldMatrixB)
			matWorldB = hInWorldMatrixB.asMatrix()
			xformB = OpenMaya.MTransformationMatrix(matWorldB)

			hAxisA = data.inputValue(self.aAxisA)
			nAxisA = hAxisA.asShort()

			hAxisB = data.inputValue(self.aAxisB)
			nAxisB = hAxisB.asShort()

			hDivider = data.inputValue(self.aDivider)
			dDivider = hDivider.asDouble()
			if dDivider < 0.01: dDivider = 0.01

			#build the vectors to compare
			axes = OpenMaya.MVector(1,0,0),OpenMaya.MVector(0,1,0),OpenMaya.MVector(0,0,1)

			#any index above 2 is just one of the first 3 axes negated - so deal with it
			vVecA = OpenMaya.MVector( axes[nAxisA%3] )  #make copies of the vectors
			vVecB = OpenMaya.MVector( axes[nAxisB%3] )
			if nAxisA > 2: vVecA *= -1
			if nAxisB > 2: vVecB *= -1

			#put the vectors into the space of the input objects and place them at origin
			#vVecA *= matWorldA
			vVecB *= matWorldB
			vVecB *= matWorldAinv
			#posA = xformA.getTranslation(OpenMaya.MSpace.kObject)
			#posB = xformB.getTranslation(OpenMaya.MSpace.kObject)
			#vVecA -= OpenMaya.MVector(posA)
			#vVecB -= OpenMaya.MVector(posB)

			#-------------------
			#DEBUG
			hOutVecAX = data.outputValue( self.aOutVecAX )
			hOutVecAY = data.outputValue( self.aOutVecAY )
			hOutVecAZ = data.outputValue( self.aOutVecAZ )
			hOutVecBX = data.outputValue( self.aOutVecBX )
			hOutVecBY = data.outputValue( self.aOutVecBY )
			hOutVecBZ = data.outputValue( self.aOutVecBZ )
			hOutVecAX.setDouble( vVecA.x )
			hOutVecAY.setDouble( vVecA.y )
			hOutVecAZ.setDouble( vVecA.z )
			hOutVecBX.setDouble( vVecB.x )
			hOutVecBY.setDouble( vVecB.y )
			hOutVecBZ.setDouble( vVecB.z )

			data.setClean(self.aOutVecA)
			data.setClean(self.aOutVecAX)
			data.setClean(self.aOutVecAY)
			data.setClean(self.aOutVecAZ)
			data.setClean(self.aOutVecB)
			data.setClean(self.aOutVecBX)
			data.setClean(self.aOutVecBY)
			data.setClean(self.aOutVecBZ)
			#print 'after pos remove',dDivider,vVecA.x, vVecA.y,vVecA.z,'    ->     ',vVecB.x,vVecB.y,vVecB.z
			#-------------------

			#finally grab the rotation between them and push it out to outRotate
			qRotBetween = OpenMaya.MQuaternion(vVecA,vVecB,(1/dDivider))
			asEuler = qRotBetween.asEulerRotation()

			#grab the output attribute handles and set their values
			hOutRotateX = data.outputValue( self.aOutRotateX )
			hOutRotateY = data.outputValue( self.aOutRotateY )
			hOutRotateZ = data.outputValue( self.aOutRotateZ )

			hOutRotateX.setDouble( asEuler.x )
			hOutRotateY.setDouble( asEuler.y )
			hOutRotateZ.setDouble( asEuler.z )

			#mark all attributes as clean
			data.setClean(self.aOutRotate)
			data.setClean(self.aOutRotateX)
			data.setClean(self.aOutRotateY)
			data.setClean(self.aOutRotateZ)
		else:
			return OpenMaya.MStatus.kUnknownParameter

		return OpenMaya.MStatus.kSuccess


def initializePlugin( mObject ):
	mPlugin = OpenMayaMPx.MFnPlugin( mObject, AUTHOR, VERSION, "Any" )
	mPlugin.registerNode( NODE_NAME, ID, nodeCreator, nodeInitializer )


def uninitializePlugin( mObject ):
	plugin = OpenMayaMPx.MFnPlugin( mObject )
	plugin.deregisterNode( ID )


def nodeCreator():
	return OpenMayaMPx.asMPxPtr( twister() )


def nodeInitializer():
	nAttr = OpenMaya.MFnNumericAttribute()
	mAttr = OpenMaya.MFnMatrixAttribute()
	eAttr = OpenMaya.MFnEnumAttribute()
	cAttr = OpenMaya.MFnCompoundAttribute()

	twister.aInWorldMatrixA = mAttr.create( "inWorldMatrixA", "iwma" )
	twister.aInWorldMatrixB = mAttr.create( "inWorldMatrixB", "iwmb" )

	twister.aAxisA = eAttr.create("axisA", "axa", 0 )
	eAttr.setChannelBox(True)
	eAttr.setKeyable(True)
	eAttr.addField( "X", 0 )
	eAttr.addField( "Y", 1 )
	eAttr.addField( "Z", 2 )
	eAttr.addField( "-X", 3 )
	eAttr.addField( "-Y", 4 )
	eAttr.addField( "-Z", 5 )

	twister.aAxisB = eAttr.create("axisB", "axb", 0 )
	eAttr.setChannelBox(True)
	eAttr.setKeyable(True)
	eAttr.addField( "X", 0 )
	eAttr.addField( "Y", 1 )
	eAttr.addField( "Z", 2 )
	eAttr.addField( "-X", 3 )
	eAttr.addField( "-Y", 4 )
	eAttr.addField( "-Z", 5 )

	twister.aDivider = nAttr.create( "divider", "div", OpenMaya.MFnNumericData.kDouble, 1 )
	nAttr.setChannelBox(True)
	nAttr.setKeyable(True)

	twister.aOutRotateX = nAttr.create( "outRotateX", "orx", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutRotateY = nAttr.create( "outRotateY", "ory", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutRotateZ = nAttr.create( "outRotateZ", "orz", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutRotate = cAttr.create( "outRotate", "or")
	cAttr.addChild( twister.aOutRotateX )
	cAttr.addChild( twister.aOutRotateY )
	cAttr.addChild( twister.aOutRotateZ )

	twister.addAttribute( twister.aInWorldMatrixA )
	twister.addAttribute( twister.aInWorldMatrixB )
	twister.addAttribute( twister.aAxisA )
	twister.addAttribute( twister.aAxisB )
	twister.addAttribute( twister.aDivider )
	twister.addAttribute( twister.aOutRotate )

	#-------------------
	#DEBUG
	twister.aOutVecAX = nAttr.create( "outVecAX", "ovax", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecAY = nAttr.create( "outVecAY", "ovay", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecAZ = nAttr.create( "outVecAZ", "ovaz", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecA = cAttr.create( "outVecA", "ova" )
	cAttr.addChild( twister.aOutVecAX )
	cAttr.addChild( twister.aOutVecAY )
	cAttr.addChild( twister.aOutVecAZ )
	twister.aOutVecBX = nAttr.create( "outVecBX", "ovbx", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecBY = nAttr.create( "outVecBY", "ovby", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecBZ = nAttr.create( "outVecBZ", "ovbz", OpenMaya.MFnNumericData.kDouble, 0.0 )
	twister.aOutVecB = cAttr.create( "outVecB", "ovb" )
	cAttr.addChild( twister.aOutVecBX )
	cAttr.addChild( twister.aOutVecBY )
	cAttr.addChild( twister.aOutVecBZ )
	twister.addAttribute( twister.aOutVecA )
	twister.addAttribute( twister.aOutVecB )
	twister.attributeAffects( twister.aInWorldMatrixA, twister.aOutVecA )
	twister.attributeAffects( twister.aInWorldMatrixB, twister.aOutVecA )
	twister.attributeAffects( twister.aDivider, twister.aOutVecA )
	twister.attributeAffects( twister.aAxisB, twister.aOutVecA )
	twister.attributeAffects( twister.aAxisB, twister.aOutVecA )
	twister.attributeAffects( twister.aInWorldMatrixA, twister.aOutVecB )
	twister.attributeAffects( twister.aInWorldMatrixB, twister.aOutVecB )
	twister.attributeAffects( twister.aDivider, twister.aOutVecB )
	twister.attributeAffects( twister.aAxisB, twister.aOutVecB )
	twister.attributeAffects( twister.aAxisB, twister.aOutVecB )
	#-------------------

	#setup dependency relationships
	twister.attributeAffects( twister.aInWorldMatrixA, twister.aOutRotate )
	twister.attributeAffects( twister.aInWorldMatrixB, twister.aOutRotate )
	twister.attributeAffects( twister.aDivider, twister.aOutRotate )
	twister.attributeAffects( twister.aAxisB, twister.aOutRotate )
	twister.attributeAffects( twister.aAxisB, twister.aOutRotate )