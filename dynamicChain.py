
from maya.cmds import *
from baseMelUI import *
from common import printWarningStr
from control import attrState, LOCK_HIDE
from mayaDecorators import d_unifyUndo


class DynamicChain(object):
	@classmethod
	@d_unifyUndo
	def Create( cls, objs ):
		node = sets( empty=True, text='zooDynamicChain' )

		addAttr( node, ln='transforms', at='message', indexMatters=True, multi=True )
		for n, obj in enumerate( objs ):
			connectAttr( '%s.message' % obj, '%s.transforms[%d]' % (node, n) )

		self = cls( node )
		self.construct()

		return self
	@classmethod
	def Iter( cls ):
		'''
		iterates over all dynamic chains in the current scene
		'''
		for node in ls( type='objectSet' ):
			if sets( q=True, text=setNode ) == 'zooDynamicChain':
				yield cls( node )

	def __init__( self, container ):
		self._node = container
	def getObjs( self ):
		objs = []
		nControls = getAttr( '%s.transforms' % self._node, size=True )
		for n in range( nControls ):
			cons = listConnections( '%s.transforms[%d]' % (self._node, n), d=False )
			if cons:
				objs.append( cons[0] )

		return objs
	@d_unifyUndo
	def construct( self ):
		'''
		builds the actual dynamic hair network
		'''
		objs = self.getObjs()

		positions = []
		for obj in objs:
			positions.append( xform( obj, q=True, ws=True, rp=True ) )

		#not be in the same hierarchy) so we can drive it via spline IK, which will in turn, drive the objs
		proxyJoints = []
		for obj in objs:
			select( cl=True )
			j = createNode( 'joint' )
			if proxyJoints:
				parent( j, proxyJoints[-1] )

			delete( parentConstraint( obj, j ) )
			proxyJoints.append( j )
			parentConstraint( j, obj )

		#build a linear curve
		linearCurve = curve( d=1, p=positions )
		linearCurveShape = listRelatives( linearCurve, s=True, pa=True )[0]
		select( linearCurve )
		maya.mel.eval( 'makeCurvesDynamicHairs 1 0 1;' )

		#find the dynamic curve shape
		cons = listConnections( '%s.worldSpace' % linearCurveShape, s=False )
		if not cons:
			printWarningStr( "Cannot find follicle" )
			return

		follicleShape = cons[0]
		cons = listConnections( '%s.outHair' % follicleShape, s=False )
		if not cons:
			printWarningStr( "Cannot find hair system!" )
			return

		hairSystemNode = cons[0]
		cons = listConnections( '%s.outCurve' % follicleShape, s=False )
		if not cons:
			printWarningStr( "Cannot find out curve!" )
			return

		dynamicCurveShape = cons[0]

		select( dynamicCurveShape )
		maya.mel.eval( 'displayHairCurves "current" 1;' )

		follicle = listRelatives( linearCurve, p=True, pa=True )[0]
		objParent = listRelatives( objs[0], p=True, pa=True )
		if objParent:
			objParent = objParent[0]
			parent( follicle, objParent )
			parent( proxyJoints[0], objParent )

		#build a control object
		controlShape = createNode( 'implicitSphere' )
		control = listRelatives( controlShape, p=True, pa=True )[0]
		pointConstraint( objs[-1], control )

		#add attributes to the control
		addAttr( control, ln='stiffness', at='double', min=0, max=1, dv=0.001, keyable=True )
		addAttr( control, ln='lengthFlex', at='double', min=0, max=1, dv=0, keyable=True )
		addAttr( control, ln='damping', at='double', min=0, max=100, dv=0, keyable=True )
		addAttr( control, ln='drag', at='double', min=0, max=1, dv=0.05, keyable=True )
		addAttr( control, ln='friction', at='double', min=0, max=1, dv=0.5, keyable=True )
		addAttr( control, ln='gravity', at='double', min=0, max=10, dv=1, keyable=True )
		addAttr( control, ln='turbulence', at='bool', keyable=True )
		addAttr( control, ln='strength', at='double', min=0, max=1, dv=0, keyable=True )
		addAttr( control, ln='frequency', at='double', min=0, max=2, dv=0.2, keyable=True )
		addAttr( control, ln='speed', at='double', min=0, max=2, dv=0.2, keyable=True )

		setAttr( '%s.overrideDynamics' % follicle, 1 )
		setAttr( '%s.pointLock' % follicle, 1 )

		#hook up all the attributes
		connectAttr( '%s.stiffness' % control, '%s.stiffness' % follicle )
		connectAttr( '%s.lengthFlex' % control, '%s.lengthFlex' % follicle )
		connectAttr( '%s.damping' % control, '%s.damp' % follicle )
		connectAttr( '%s.drag' % control, '%s.drag' % hairSystemNode )
		connectAttr( '%s.friction' % control, '%s.friction' % hairSystemNode )
		connectAttr( '%s.gravity' % control, '%s.gravity' % hairSystemNode )
		connectAttr( '%s.strength' % control, '%s.turbulenceStrength' % hairSystemNode )
		connectAttr( '%s.frequency' % control, '%s.turbulenceFrequency' % hairSystemNode )
		connectAttr( '%s.speed' % control, '%s.turbulenceSpeed' % hairSystemNode )

		attrState( control, ('t', 'r', 's', 'v'), *LOCK_HIDE )

		splineIkHandle = ikHandle( sj=proxyJoints[0], ee=proxyJoints[-1], curve=dynamicCurveShape, sol='ikSplineSolver', ccv=False )[0]

		#put all the nodes created into some sort of container object so we can "get at" them later for
		#either editing, muting or deletion
		nodes = proxyJoints + [linearCurve, control, follicle, splineIkHandle]
		for node in nodes:
			sets( node, e=True, add=self._node )
	def mute( self ):
		'''
		deletes the hair nodes but retains the settings and objects involved in the hair
		'''
		delete( sets( self._node, q=True ) )
	def getMuted( self ):
		'''
		returns whether this dynamic chain is muted or not
		'''
		return bool( sets( self._node, q=True ) )
	def bake( self, skipFrames=4 ):
		'''
		if this dynamic chain isn't muted, this will bake the motion to keyframes and mute
		the dynamic hair
		'''
		pass
	def delete( self ):
		'''
		deletes the dynamic chain
		'''
		for node in sets( q=self._node ):
			delete( node )

		delete( self._node )


class DynamicChainLayout(MelVSingleStretchLayout):
	def __init__( self, parent ):
		pass


class DynamicChainWindow(BaseMelWindow):
	WINDOW_NAME = 'zooDynamicChainMaker'
	WINDOW_TITLE = 'Dynamic Chain Maker'

	DEFAULT_SIZE = 400, 300
	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		DynamicChainLayout( self )
		self.show()


#end
