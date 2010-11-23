
import filesystem

from maya.cmds import *
from maya import cmds as cmd
from rigUtils import *
from control import *
from names import Parity, Name, camelCaseToNice, stripParity
from skeletonBuilder import *
from vectors import Vector, Matrix

import apiExtensions
import skeletonBuilder
import spaceSwitching
import triggered
import vectors
import control
import api

__author__ = 'hamish@macaronikazoo.com'

Trigger = triggered.Trigger
AXES = Axis.BASE_AXES
Vector = vectors.Vector

AIM_AXIS = AX_X
ROT_AXIS = AX_Y

#make sure all setDrivenKeys have linear tangents
setDrivenKeyframe = lambda *a, **kw: cmd.setDrivenKeyframe( inTangentType='linear', outTangentType='linear', *a, **kw )


class RigPartError(Exception): pass


def createRigPartContainer( name ):
	return sets( em=True, n=name, text='rigPrimitive' )


def isRigPartContainer( node ):
	if objectType( node, isType='objectSet' ):
		return sets( node, q=True, text=True ) == 'rigPrimitive'

	return False


def getRigPartContainers( compatabilityMode=False ):
	existingContainers = [ node for node in ls( type='objectSet', r=True ) or [] if sets( node, q=True, text=True ) == 'rigPrimitive' ]
	if compatabilityMode:
		existingContainers += [ node.split( '.' )[0] for node in ls( '*._rigPrimitive', r=True ) ]

	return existingContainers


def getNodesCreatedBy( function, *args, **kwargs ):
	'''
	returns a 2-tuple containing all the nodes created by the passed function, and
	the return value of said function

	NOTE: if any container nodes were created, their contents are omitted from the
	resulting node list - the container itself encapsulates them
	'''

	newNodes, ret = apiExtensions.getNodesCreatedBy( function, *args, **kwargs )

	#now remove nodes from all containers from the newNodes list
	newContainers = apiExtensions.filterByType( newNodes, apiExtensions.MFn.kSet )

	#NOTE: nodes are MObject instances at this point
	newNodes = set( [ node for node in newNodes if node is not None ] )
	for c in newContainers:
		for n in sets( c, q=True ) or []:
			if n in newNodes:
				newNodes.remove( n )


	#containers contained by other containers don't need to be returned (as they're already contained by a parent)
	newTopLevelContainers = []
	for c in newContainers:
		parentContainer = sets( c, q=True, parentContainer=True )
		if parentContainer:
			continue

		newTopLevelContainers.append( c )
		newNodes.add( c )


	return newNodes, ret


def buildContainer( typeClass, kwDict, nodes, controls ):
	'''
	builds a container for the given nodes, and tags it with various attributes to record
	interesting information such as rig primitive version, and the args used to instantiate
	the rig.  it also registers control objects with attributes, so the control nodes can
	queried at a later date by their name
	'''

	#if typeClass is an instance, then set its container attribute, otherwise instantiate an instance and return it
	if isinstance( typeClass, RigPart ):
		theInstance = typeClass
		typeClass = type( typeClass )
	elif issubclass( typeClass, RigPart ):
		theInstance = typeClass( None )

	#build the container, and add the special attribute to it to
	theContainer = createRigPartContainer( '%s_%s' % (typeClass.__name__, kwDict.get( 'idx', 'NOIDX' )) )
	theInstance.container = theContainer

	addAttr( theContainer, ln='_rigPrimitive', attributeType='compound', numberOfChildren=6 )
	addAttr( theContainer, ln='typeName', dt='string', parent='_rigPrimitive' )
	addAttr( theContainer, ln='script', dt='string', parent='_rigPrimitive' )
	addAttr( theContainer, ln='version', at='long', parent='_rigPrimitive' )
	addAttr( theContainer, ln='skeletonPart', at='message', parent='_rigPrimitive' )
	addAttr( theContainer, ln='buildKwargs', dt='string', parent='_rigPrimitive' )
	addAttr( theContainer, ln='controls',
	         multi=True,
	         indexMatters=True,
	         attributeType='message',
	         parent='_rigPrimitive' )


	#now set the attribute values...
	setAttr( '%s._rigPrimitive.typeName' % theContainer, typeClass.__name__, type='string' )
	setAttr( '%s._rigPrimitive.script' % theContainer, inspect.getfile( typeClass ), type='string' )
	setAttr( '%s._rigPrimitive.version' % theContainer, typeClass.__version__ )
	setAttr( '%s._rigPrimitive.buildKwargs' % theContainer, str( kwDict ), type='string' )


	#now add all the nodes
	nodes = [ str( node ) if node is not None else node for node in nodes ]
	controls = [ str( node ) if node is not None else node for node in controls ]
	for node in set( nodes ) | set( controls ):
		if node is None:
			continue

		if objectType( node, isAType='dagNode' ):
			sets( node, e=True, add=theContainer )

		#if the node is a rig part container add it to this container otherwise skip it
		elif objectType( node, isAType='objectSet' ):
			if isRigPartContainer( node ):
				sets( node, e=True, add=theContainer )


	#and now hook up all the controls
	controlNames = typeClass.CONTROL_NAMES or []  #CONTROL_NAMES can validly be None, so in this case just call it an empty list
	for idx, control in enumerate( controls ):
		if control is None:
			continue

		connectAttr( '%s.message' % control, '%s._rigPrimitive.controls[%d]' % (theContainer, idx), f=True )

		#set the kill state on the control if its a transform node
		if objectType( control, isAType='transform' ):
			triggered.setKillState( control, True )


	return theInstance


class RigPart(filesystem.trackableClassFactory()):
	'''
	base rig part class.  deals with rig part creation.

	rig parts are instantiated by passing the class a rig part container node

	to create a new rig part, simply call the RigPartClass.Create( skeletonPart, *args )
	where the skeletonPart is the SkeletonPart instance created via the skeleton builder
	'''

	__version__ = 0
	PRIORITY = 0
	CONTROL_NAMES = None
	AVAILABLE_IN_UI = False  #determines whether this part should appear in the UI or not...
	ADD_CONTROLS_TO_QSS = True

	AUTO_PICKER = True

	def __init__( self, partContainer, skeletonPart=None ):
		if partContainer is not None:
			assert isRigPartContainer( partContainer ), "Must pass a valid rig part container! (received %s - a %s)" % (partContainer, nodeType( partContainer ))

		self.container = partContainer
		self._skeletonPart = skeletonPart
	def __unicode__( self ):
		return u"%s_%d( %r )" % (self.__class__.__name__, self.getIdx(), self.container)
	__str__ = __unicode__
	def __repr__( self ):
		return repr( unicode( self ) )
	def __hash__( self ):
		'''
		the hash for the container mobject uniquely identifies this rig control
		'''
		return hash( apiExtensions.asMObject( self.container ) )
	def __eq__( self, other ):
		return self.base == other.base
	def __neq__( self, other ):
		return not self == other
	def __getattr__( self, attrName ):
		'''
		returns the control named <attrName>.  control "names" are defined by the CONTROL_NAMES class
		variable.  This list is asked for the index of <attrName> and the control at that index is returned
		'''
		if self.CONTROL_NAMES is None:
			raise AttributeError( "The %s rig primitive has no named controls" % self.__class__.__name__ )

		idx = list( self.CONTROL_NAMES ).index( attrName )
		if idx < 0:
			raise AttributeError( "No control with the name %s" % attrName )

		connected = listConnections( '%s._rigPrimitive.controls[%d]' % (self.container, idx), d=False )
		if connected:
			assert len( connected ) == 1, "More than one control was found!!!"
			return connected[ 0 ]

		return None
	def __getitem__( self, idx ):
		'''
		returns the control at <idx>
		'''
		connected = listConnections( '%s._rigPrimitive.controls[%d]' % (self.container, idx), d=False )
		if connected:
			assert len( connected ) == 1, "More than one control was found!!!"
			return connected[ 0 ]

		return None
	def __len__( self ):
		'''
		returns the number of controls registered on the rig
		'''
		return getAttr( '%s._rigPrimitive.controls' % self.container, size=True )
	def __iter__( self ):
		'''
		iterates over all controls in the rig
		'''
		for n in range( len( self ) ):
			yield self[ n ]
	def nodes( self ):
		'''
		returns ALL the nodes that make up this rig part
		'''
		return sets( self.container, q=True )
	@classmethod
	def GetPartName( cls ):
		'''
		can be used to get a "nice" name for the part class
		'''
		return camelCaseToNice( cls.__name__ )
	@classmethod
	def InitFromItem( cls, item ):
		'''
		inits the rigPart from a member item - the RigPart instance returned is
		cast to teh most appropriate type
		'''

		if isRigPartContainer( item ):
			typeClassStr = getAttr( '%s._rigPrimitive.typeName' % partContainer )
			typeClass = RigPart.GetNamedSubclass( typeClassStr )

			return typeClass( item )

		cons = listConnections( item, s=False, type='objectSet' )
		if not cons:
			raise RigPartError( "Cannot find a rig container for %s" % item )

		for con in cons:
			if isRigPartContainer( con ):
				typeClassStr = getAttr( '%s._rigPrimitive.typeName' % con )
				typeClass = RigPart.GetNamedSubclass( typeClassStr )

				return typeClass( con )

		raise RigPartError( "Cannot find a rig container for %s" % item )
	@classmethod
	def IterAllParts( cls ):
		'''
		iterates over all RigParts in the current scene
		'''
		for c in getRigPartContainers():
			if objExists( '%s._rigPrimitive' % c ):
				thisClsName = getAttr( '%s._rigPrimitive.typeName' % c )
				thisCls = RigPart.GetNamedSubclass( thisClsName )

				if thisCls is None:
					raise SkeletonError( "No RigPart called %s" % thisClsName )

				if issubclass( thisCls, cls ):
					yield cls( c )
	@classmethod
	def GetUniqueIdx( cls ):
		'''
		returns a unique index (unique against the universe of existing indices
		in the scene) for the current part class
		'''
		existingIdxs = []
		for part in cls.IterAllParts():
			idx = part.getBuildKwargs()[ 'idx' ]
			existingIdxs.append( idx )

		existingIdxs.sort()
		assert len( existingIdxs ) == len( set( existingIdxs ) ), "There is a duplicate ID! %s, %s" % (cls, existingIdxs)

		#return the first, lowest, available index
		for orderedIdx, existingIdx in enumerate( existingIdxs ):
			if existingIdx != orderedIdx:
				return orderedIdx

		if existingIdxs:
			return existingIdxs[ -1 ] + 1

		return 0
	def createSharedShape( self, name ):
		return asMObject( createNode( 'nurbsCurve', n=name +'#', p=self.sharedShapeParent ) )
	@classmethod
	def Create( cls, skeletonPart, *a, **kw ):
		'''
		you can pass in the following kwargs to control the build process
		addControlsToQss		defaults to cls.ADD_CONTROLS_TO_QSS
		'''

		addControlsToQss = kw.get( 'addControlsToQss', cls.ADD_CONTROLS_TO_QSS )

		if not cls.CanRigThisPart( skeletonPart ):
			return

		buildFunc = getattr( cls, '_build', None )
		if buildFunc is None:
			raise RigPartError( "The rigPart %s has no _build method!" % cls.__name__ )

		assert isinstance( skeletonPart, SkeletonPart ), "Need a SkeletonPart instance, got a %s instead" % skeletonPart.__class__

		if not skeletonPart.compareAgainstHash():
			raise NotFinalizedError( "ERROR :: %s hasn't been finalized!" % skeletonPart )


		#now turn the args passed in are a single kwargs dict
		argNames, vArgs, vKwargs, defaults = inspect.getargspec( buildFunc )
		if defaults is None:
			defaults = []

		argNames = argNames[ 2: ]  #strip the first two args - which should be the instance arg (usually self) and the skeletonPart
		if vArgs is not None:
			raise RigPartError( 'cannot have *a in rig build functions' )

		for argName, value in zip( argNames, a ):
			kw[ argName ] = value

		#now explicitly add the defaults
		for argName, default in zip( argNames, defaults ):
			kw.setdefault( argName, default )


		#generate an index for the rig part - each part must have a unique index
		idx = cls.GetUniqueIdx()
		kw[ 'idx' ] = idx


		#construct an empty instance - empty RigPart instances are only valid inside this method...
		self = cls( None )
		self._skeletonPart = skeletonPart


		#generate a default scale for the rig part
		kw.setdefault( 'scale', getDefaultScale() / 10.0 )


		#make sure the world part is created first - if its created by the part, then its nodes will be included in its container...
		worldPart = WorldPart.Create()

		qss = worldPart.qss


		#create the shared shape transform - this is the transform under which all shared shapes are temporarily parented to, and all
		#shapes under this transform are automatically added to all controls returned after the build function returns
		self.sharedShapeParent = asMObject( createNode( 'transform', n='_tmp_sharedShape' ) )
		defaultSharedShape = self.createSharedShape( '%s_sharedAttrs' % cls.GetPartName() )
		kw[ 'sharedShape' ] = defaultSharedShape


		#run the build function
		newNodes, controls = getNodesCreatedBy( self._build, skeletonPart, **kw )
		realControls = [ c for c in controls if c is not None ]  #its possible for a build function to return None in the control list because it wants to preserve the length of the control list returned - so construct a list of controls that actually exist
		if addControlsToQss:
			for c in realControls:
				sets( c, add=qss )


		#make sure there are no intermediate shapes
		for c in realControls:
			for shape in listRelatives( c, s=True, pa=True ) or []:
				if getAttr( '%s.intermediateObject' % shape ):
					delete( shape )


		#build the container and initialize the rigPrimtive
		buildContainer( self, kw, newNodes, controls )


		#add shared shapes to all controls, and remove shared shapes that are empty
		sharedShapeParent = self.sharedShapeParent
		sharedShapes = listRelatives( sharedShapeParent, pa=True, s=True ) or []
		for c in realControls:
			if objectType( c, isAType='transform' ):
				for shape in sharedShapes:
					parent( shape, c, add=True, s=True )

		for shape in sharedShapes:
			if not listAttr( shape, ud=True ):
				delete( shape )

		delete( sharedShapeParent )
		del( self.sharedShapeParent )


		#stuff the part container into the world container - we want a clean top level in the outliner
		theContainer = self.container
		sets( theContainer, e=True, add=worldPart.container )


		#make sure the container "knows" the skeleton part - its not always obvious trawling through
		#the nodes in teh container which items are the skeleton part
		connectAttr( '%s.message' % skeletonPart.base, '%s._rigPrimitive.skeletonPart' % theContainer )


		return self
	@classmethod
	def GetControlName( cls, control ):
		'''
		returns the name of the control as defined in the CONTROL_NAMES attribute
		for the part class
		'''
		cons = listConnections( control.message, s=False, p=True, type='objectSet' )
		for c in cons:
			typeClassStr = getAttr( '%s._rigPrimitive.typeName' % c.node() )
			typeClass = RigPart.GetNamedSubclass( typeClassStr )
			if typeClass.CONTROL_NAMES is None:
				return str( control )

			idx = c[ c.rfind( '[' )+1:-1 ]
			try: name = typeClass.CONTROL_NAMES[ idx ]
			except ValueError:
				print typeClass, control
				raise RigPartError( "Doesn't have a name!" )

			return name

		raise RigPartError( "The control isn't associated with a rig primitive" )
	@classmethod
	def CanRigThisPart( cls, skeletonPart ):
		return True
	@classmethod
	def GetDefaultBuildKwargList( cls ):
		'''
		returns a list of 2 tuples: argName, defaultValue
		'''
		buildFunc = getattr( cls, '_build', None )
		spec = inspect.getargspec( buildFunc )

		argNames = spec[ 0 ][ 2: ]  #strip the first two items because the _build method is a bound method - so the first item is always the class arg (usually called cls), and the second arg is always the skeletonPart
		defaults = spec[ 3 ]

		if defaults is None:
			defaults = []

		assert len( argNames ) == len( defaults ), "%s has no default value set for one of its args - this is not allowed" % cls

		kwargList = []
		for argName, default in zip( argNames, defaults ):
			kwargList.append( (argName, default) )

		return kwargList
	def getBuildKwargs( self ):
		theDict = eval( getAttr( '%s._rigPrimitive.buildKwargs' % self.container ) )
		return theDict
	def getIdx( self ):
		'''
		returns the index of the part - all parts have a unique index associated
		with them
		'''
		return self.getBuildKwargs()[ 'idx' ]
	def getBuildScale( self ):
		return self.getBuildKwargs().get( 'scale', self.PART_SCALE )
	def getSkeletonPart( self ):
		'''
		returns the skeleton part this rig part is driving
		'''
		if self._skeletonPart:
			return self._skeletonPart

		connected = listConnections( '%s.skeletonPart' % self.container )[ 0 ]
		self._skeletonPart = skeletonPart = SkeletonPart.InitFromItem( connected )

		return skeletonPart
	def getSkeletonPartParity( self ):
		return self.getSkeletonPart().getParity()
	def getControlName( self, control ):
		'''
		returns the name of the control as defined in the CONTROL_NAMES attribute
		for the part class
		'''
		if self.CONTROL_NAMES is None:
			return str( control )

		cons = cmd.listConnections( '%s.message' % control, s=False, p=True ) or []
		for c in cons:
			node = c.split( '.' )[0]
			if not isRigPartContainer( node ):
				continue

			if objExists( node ):
				if node != self.container:
					continue

				index = int( c[ c.rfind( '[' )+1:-1 ] )
				name = self.CONTROL_NAMES[ index ]

				return name

		raise RigPartError( "The control %s isn't associated with this rig primitive %s" % (control, self) )


def generateNiceControlName( control ):
	niceName = getNiceName( control )
	if niceName is not None:
		return niceName

	try:
		rigPart = RigPart.InitFromItem( control )
		if rigPart is None: raise RigPartError( "null" )
		controlName = rigPart.getControlName( control )
	except RigPartError:
		controlName = str( control )

	controlName = Name( controlName )
	parity = controlName.get_parity()

	if parity == Parity.LEFT:
		controlName = 'Left '+ str( stripParity( controlName )  )
	if parity == Parity.RIGHT:
		controlName = 'Right '+ str( stripParity( controlName )  )
	else:
		controlName = str( controlName )

	return camelCaseToNice( controlName )


def getSpaceSwitchControls( theJoint ):
	'''
	walks up the joint chain and returns a list of controls that drive parent joints
	'''
	parentControls = []

	for p in api.iterParents( theJoint ):
		theControl = getItemRigControl( p )
		if theControl is not None:
			parentControls.append( theControl )

	return parentControls


def buildDefaultSpaceSwitching( theJoint, control=None, additionalParents=(), additionalParentNames=(), reverseHierarchy=False, **buildKwargs ):
	if control is None:
		control = getItemRigControl( theJoint )

	theWorld = WorldPart.Create()
	spaces = getSpaceSwitchControls( theJoint )
	spaces.append( theWorld.control )

	#determine default names for the given controls
	names = []
	for s in spaces:
		names.append( generateNiceControlName( s ) )

	additionalParents = list( additionalParents )
	additionalParentNames = list( additionalParentNames )

	for n in range( len( additionalParentNames ), len( additionalParents ) ):
		additionalParentNames.append( generateNiceControlName( additionalParents[ n ] ) )

	spaces += additionalParents
	names += additionalParentNames

	#we don't care about space switching if there aren't any non world spaces...
	if not spaces:
		return

	if reverseHierarchy:
		spaces.reverse()
		names.reverse()

	return spaceSwitching.build( control, spaces, names, **buildKwargs )


def getParentAndRootControl( theJoint ):
	'''
	returns a 2 tuple containing the nearest control up the hierarchy, and the
	most likely control to use as the "root" control for the rig.  either of these
	may be the world control, but both values are guaranteed to be an existing
	control object
	'''
	parentControl, rootControl = None, None
	for p in api.iterParents( theJoint ):
		theControl = getItemRigControl( p )
		if theControl is None:
			continue

		if parentControl is None:
			parentControl = theControl

		skelPart = SkeletonPart.InitFromItem( p )
		if isinstance( skelPart, skeletonBuilder.Root ):
			rootControl = theControl

	if parentControl is None or rootControl is None:
		world = WorldPart.Create()
		if parentControl is None:
			parentControl = world.control

		if rootControl is None:
			rootControl = world.control

	return parentControl, rootControl


def createLineOfActionMenu( controls, joints ):
	'''
	deals with adding a "draw line of action" menu to each control in the controls
	list.  the line is drawn through the list of joints passed
	'''
	if not joints: return
	if not isinstance( controls, (list, tuple) ):
		controls = [ controls ]

	joints = list( joints )
	jParent = getNodeParent( joints[ 0 ] )
	if jParent:
		joints.insert( 0, jParent )

	for c in controls:
		cTrigger = Trigger( c )
		spineConnects = [ cTrigger.connect( j ) for j in joints ]
		Trigger.CreateMenu( c,
		                    "draw line of action",
		                    "zooLineOfAction;\nzooLineOfAction_multi { %s } \"\";" % ', '.join( '"%%%d"'%idx for idx in spineConnects ) )


class WorldPart(RigPart):
	'''
	the world part can only be created once per scene.  if an existing world part instance is found
	when calling WorldPart.Create() it will be returned instead of creating a new instance
	'''

	__version__ = 0
	CONTROL_NAMES = [ 'control', 'parts', 'masterQss', 'qss', 'exportRelative' ]

	WORLD_OBJ_MENUS = [ ('toggle rig vis', """{\nstring $childs[] = `listRelatives -pa -type transform #`;\nint $vis = !`getAttr ( $childs[0]+\".v\" )`;\nfor($a in $childs) if( `objExists ( $a+\".v\" )`) if( `getAttr -se ( $a+\".v\" )`) setAttr ( $a+\".v\" ) $vis;\n}"""),
	                    ('draw all lines of action', """string $menuObjs[] = `zooGetObjsWithMenus`;\nfor( $m in $menuObjs ) {\n\tint $cmds[] = `zooObjMenuListCmds $m`;\n\tfor( $c in $cmds ) {\n\t\tstring $name = `zooGetObjMenuCmdName $m $c`;\n\t\tif( `match \"draw line of action\" $name` != \"\" ) eval(`zooPopulateCmdStr $m (zooGetObjMenuCmdStr($m,$c)) {}`);\n\t\t}\n\t}"""),
	                    ('show "export relative" node', """""") ]

	@classmethod
	def Create( cls, **kw ):
		for existingWorld in cls.IterAllParts():
			return existingWorld

		#try to determine scale - walk through all existing skeleton parts in the scene
		for skeletonPart in SkeletonPart.IterAllPartsInOrder():
			kw.setdefault( 'scale', skeletonPart.getBuildScale() )
			break

		worldNodes, controls = getNodesCreatedBy( cls._build, **kw )
		worldPart = buildContainer( WorldPart, { 'idx': 0 }, worldNodes, controls )

		return worldPart
	@classmethod
	def _build( cls, **kw ):
		scale = kw.get( 'scale', skeletonBuilder.TYPICAL_HEIGHT )
		scale /= 1.5

		world = buildControl( 'main', shapeDesc=ShapeDesc( None, 'hex', AX_Y ), oriented=False, scale=scale, niceName='The World' )

		parts = group( empty=True, name='parts_grp' )
		qss = sets( empty=True, text="gCharacterSet", n="body_ctrls" )
		masterQss = sets( empty=True, text="gCharacterSet", n="all_ctrls" )

		exportRelative = buildControl( 'exportRelative', shapeDesc=ShapeDesc( None, 'cube', AX_Y_NEG ), pivotModeDesc=PivotModeDesc.BASE, oriented=False, size=(1, 0.5, 1), scale=scale )
		parentConstraint( world, exportRelative )
		attrState( exportRelative, ('t', 'r', 's'), *LOCK_HIDE )
		attrState( exportRelative, 'v', *HIDE )
		setAttr( '%s.v' % exportRelative, False )

		#turn scale segment compensation off for all joints in the scene
		for j in ls( type='joint' ):
			setAttr( '%s.ssc' % j, False )

		sets( qss, add=masterQss )

		attrState( world, 's', *NORMAL )
		connectAttr( '%s.scale' % world, '%s.scale' % parts )
		connectAttr( '%s.scaleX' % world, '%s.scaleY' % world )
		connectAttr( '%s.scaleX' % world, '%s.scaleZ' % world )

		#add right click items to the world controller menu
		worldTrigger = Trigger( str( world ) )
		qssIdx = worldTrigger.connect( str( masterQss ) )


		#add world control to master qss
		sets( world, add=masterQss )
		sets( exportRelative, add=masterQss )


		#turn unwanted transforms off, so that they are locked, and no longer keyable
		attrState( world, 's', *NO_KEY )
		attrState( world, ('sy', 'sz'), *LOCK_HIDE )
		attrState( parts, [ 't', 'r', 's', 'v' ], *LOCK_HIDE )


		return world, parts, masterQss, qss, exportRelative


class RigSubPart(RigPart):
	'''
	'''

	#this attribute describes what skeleton parts the rig primitive is associated with.  If the attribute's value is None, then the rig primitive
	#is considered a "hidden" primitive that has
	SKELETON_PRIM_ASSOC = None


class PrimaryRigPart(RigPart):
	'''
	all subclasses of this class are exposed as available rigging methods to the user
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def DISPLAY_NAME( cls ):
		return camelCaseToNice( cls.__name__ )


"""
def createPicker():
	name = 'auto'

	pickerNode = createNode( 'geometryVarGroup', name=name )
	addAttr( pickerNode, longName='bgColor', dt='string' )
	addAttr( pickerNode, longName='bgImage', dt='string' )
	addAttr( pickerNode, longName='namespace', dt='string' )
	addAttr( pickerNode, longName='data', dt='stringArray' )
	addAttr( pickerNode, longName='controls', at='short' )

	#setAttr( '%s.bgImage' % pickerNode, bgImage, type='string' )

	#if self.namespace!=None:
		#setAttr( '%s.namespace' % pickerNode, namespace, type='string' )

	# build data strings now x,y,w,h,color,target string
	buttonData = []
	for rigPart in RigPart.IterAllParts():
		if rigPart.AUTO_PICKER:
			for n, rigControl in enumerate( rigPart ):
				if rigPart.CONTROL_NAMES and len( rigPart.CONTROL_NAMES ) > n:
					label = rigPart.CONTROL_NAMES[ n ]
				else:
					label = ''

				x, y = 10, 10
				w, h = 15, 15
				colour = '1,0,0'

				dataStr = '%0.3g;%0.3g;' % (x, y)
				dataStr += '%0.3g;%0.3g;' % (w, h)
				dataStr += '%s;%s;' % (colour, label)
				dataStr += rigControl

				buttonData.append( dataStr )
				break
		break

	# break data into MEL strings for eval
	#eStr =" ".join(data)
	#ev = "setAttr "+self.pickerNode+".data -type stringArray "+str(len(data))+" "+eStr+""
	setAttr( '%s.data' % pickerNode, type='stringArray', *buttonData )
	cmds.setAttr( '%s.controls' % pickerNode, len( buttonData ) )
"""


def cleanMeshControls( doConfirm=True ):
	shapesRemoved = 0
	for node in getRigPartContainers( True ):

		clsName = getAttr( '%s._rigPrimitive.typeName' % node )
		cls = RigPart.GetNamedSubclass( clsName )

		if cls is None:
			continue

		rigPart = cls( node )
		for c in rigPart:
			for shape in listRelatives( c, s=True, pa=True ) or []:
				if getAttr( '%s.intermediateObject' % shape ):
					delete( shape )
					shapesRemoved += 1

	print "Clean up %d bogus shapes" % shapesRemoved
	if doConfirm:
		cmd.confirmDialog( t='Done!', m="I'm done polishing your rig!\n%d shapes removed." % shapesRemoved, b='OK', db='OK' )


#end
