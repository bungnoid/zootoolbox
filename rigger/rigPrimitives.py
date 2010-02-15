'''
To create a new rig primitive, create a class and author the rigging code in the
_build
'''

import filesystem

from pymel.core import *
from pymel.core.nodetypes import DagNode, Container
from maya import cmds as cmd
from utils import *
from control import *
from names import Parity, Name, camelCaseToNice, stripParity
from skeletonBuilderCore import *

import pymel.core as pymelCore
import skeletonBuilderCore
import spaceSwitching
import triggered
import vectors
import api

#import wingdbstub

__author__ = 'hamish@valvesoftware.com'

Trigger = triggered.Trigger
AXES = Axis.BASE_AXES
Vector = vectors.Vector

AIM_AXIS = AX_X
ROT_AXIS = AX_Y

#make sure all setDrivenKeys have linear tangents
setDrivenKeyframe = lambda *a, **kw: pymelCore.setDrivenKeyframe( inTangentType='linear', outTangentType='linear', *a, **kw )


class RigPartError(Exception): pass


def getNodesCreatedBy( function, *args, **kwargs ):
	'''
	returns a 2-tuple containing all the nodes created by the passed function, and
	the return value of said function

	NOTE: if any container nodes were created, their contents are omitted from the
	resulting node list - the container itself encapsulates them
	'''
	preScene = ls()
	ret = function( *args, **kwargs )
	postScene = ls()

	newNodes = set( postScene ).difference( set( preScene ) )

	#now remove nodes from all containers from the newNodes list
	newContainers = ls( newNodes, type='container' )
	for c in newContainers:
		for n in c.getMembers():
			newNodes.remove( n )


	#containers contained by other containers don't need to be returned (as they're already contained by a parent)
	newTopLevelContainers = []
	for c in newContainers:
		try:
			if c.getParentContainer():
				continue
		except MayaNodeError: pass

		newTopLevelContainers.append( c )
		newNodes.add( c )


	return newNodes, ret


#for easier debugging when authoring rig creation functions set this variable to True - it will stop nodes getting added to a container making it easier to visualize in the outliner
_PART_DEBUG_MODE = False

def buildContainer( typeClass, kwDict, nodes, controls ):
	'''
	builds a container for the given nodes, and tags it with various attributes to record
	interesting information such as rig primitive version, and the args used to instantiate
	the rig.  it also registers control objects with attributes, so the control nodes can
	queried at a later date by their name
	'''
	global _PART_DEBUG_MODE


	#build the container, and add the special attribute to it to
	theContainer = container( name='%s_%s' % (typeClass.__name__, kwDict.get( 'idx', 'NOIDX' )) )

	theContainer.addAttr( '_rigPrimitive', attributeType='compound', numberOfChildren=5 )
	theContainer.addAttr( 'typeName', dt='string', parent='_rigPrimitive' )
	theContainer.addAttr( 'version', at='long', parent='_rigPrimitive' )
	theContainer.addAttr( 'skeletonPart', at='message', parent='_rigPrimitive' )
	theContainer.addAttr( 'buildKwargs', dt='string', parent='_rigPrimitive' )
	theContainer.addAttr( 'controls',
	                      multi=True,
	                      indexMatters=False,
	                      attributeType='message',
	                      parent='_rigPrimitive' )


	#now set the attribute values...
	theContainer._rigPrimitive.typeName.set( typeClass.__name__ )
	theContainer._rigPrimitive.version.set( typeClass.__version__ )
	theContainer._rigPrimitive.buildKwargs.set( str( kwDict ) )


	#now add all the nodes
	for node in nodes | set( controls ):
		if isinstance( node, (DagNode, Container) ):

			#if _PART_DEBUG_MODE is True, don't add the controls to the container - this makes it easier to debug problems when authoring rig creation functions
			if not _PART_DEBUG_MODE:
				try: theContainer.addNode( node, force=True )
				except: print 'PROBLEM ADDING', node, 'TO CONTAINER', theContainer


	#and now hook up all the controls
	controlNames = typeClass.CONTROL_NAMES or []  #CONTROL_NAMES can validly be None, so in this case just call it an empty list
	for idx, control in enumerate( controls ):
		connectAttr( control.message, theContainer._rigPrimitive.controls[ idx ], f=True )
		triggered.setKillState( control, True )


	return typeClass( theContainer )


class RigPart(filesystem.trackableClassFactory()):
	'''
	base rig part class.  deals with rig part creation.

	rig parts are instantiated by passing the class a rig part container node

	to create a new rig part, simply call the RigPartClass.Create( skeletonPart, *args )
	where the skeletonPart is the SkeletonPart instance created via the skeleton builder
	'''

	__version__ = 0
	CONTROL_NAMES = None
	AVAILABLE_IN_UI = False  #determines whether this part should appear in the UI or not...
	ADD_CONTROLS_TO_QSS = True

	def __init__( self, partContainer ):
		self.container = PyNode( partContainer )
	def __repr__( self ):
		return '%s_%d( %s )' % (self.__class__.__name__, self.getIdx(), self.container)
	def __hash__( self ):
		return hash( self.base )
	def __eq__( self, other ):
		return self.base == other.base
	def __neq__( self, other ):
		return not self == other
	def __getattr__( self, attrName ):
		if self.CONTROL_NAMES is None:
			raise AttributeError( "The %s rig primitive has no named controls" % self.__class__.__name__ )

		idx = list( self.CONTROL_NAMES ).index( attrName )
		if idx < 0:
			raise AttributeError( "No control with the name %s" % attrName )

		cons = listConnections( self.container._rigPrimitive.controls[ idx ], d=False )
		assert len( cons ) == 1, "More than one control was found!!!"

		return cons[ 0 ]
	def __getitem__( self, idx ):
		if self.CONTROL_NAMES is not None:
			try:
				attrName = self.CONTROL_NAMES[ idx ]
			except IndexError:
				raise IndexError( "Invalid control index - %s only has %d named controls" % (self, len( self.CONTROL_NAMES )) )

		return self.container._rigPrimitive.controls[ idx ]
	@classmethod
	def InitFromItem( cls, item ):
		'''
		inits the rigPart from a member item - the RigPart instance returned is
		cast to teh most appropriate type
		'''
		if not isinstance( item, PyNode ):
			item = PyNode( item )

		if isinstance( item, Container ):
			typeClass = RigPart.GetNamedSubclass( item._rigPrimitive.typeName.get() )
			return typeClass( item )

		theContainer = container( q=True, findContainer=[ item ] )
		if theContainer is None:
			return None

		theContainer = PyNode( theContainer )  #for some reason the container command returns a unicode object, not a PyNode hence the explicit cast...
		if theContainer:
			typeClass = RigPart.GetNamedSubclass( theContainer._rigPrimitive.typeName.get() )
			return typeClass( theContainer )

		return None
	@classmethod
	def IterAllParts( cls ):
		'''
		iterates over all SkeletonParts in the current scene
		'''
		for c in ls( type='container', r=True ):
			if c.hasAttr( '_rigPrimitive' ):
				thisClsName = c._rigPrimitive.typeName.get()
				thisCls = RigPart.GetNamedSubclass( thisClsName )
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
	@classmethod
	def Create( cls, skeletonPart, *a, **kw ):
		'''
		'''

		buildFunc = getattr( cls, '_build', None )
		if buildFunc is None:
			raise RigPartError( 'no such rig primitive' )

		assert isinstance( skeletonPart, SkeletonPart ), "Need a SkeletonPart instance, got a %s instead" % skeletonPart.__class__

		if not skeletonPart.compareAgainstHash():
			raise NotFinalizedError( "ERROR :: %s hasn't been finalized!" % skeletonPart )


		#now turn the args passed in are a single kwargs dict
		argNames, vArgs, vKwargs, defaults = inspect.getargspec( buildFunc )
		if defaults is None:
			defaults = []

		argNames = argNames[ 2: ]  #strip the first two args - which should be the class arg (usually cls) and the skeletonPart
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


		#generate a default scale for the rig part
		kw.setdefault( 'scale', getDefaultScale() / 10.0 )


		#make sure the world part is created first - if its created by the part, then its nodes will be included in its container...
		worldPart = WorldPart.Create()

		qss = worldPart.qss


		#run the build function
		newNodes, controls = getNodesCreatedBy( buildFunc, skeletonPart, **kw )
		if cls.ADD_CONTROLS_TO_QSS:
			for c in controls:
				qss.add( c )


		#build the container and initialize the rigPrimtive
		newPart = buildContainer( cls, kw, newNodes, controls )
		theContainer = newPart.container


		#publish the controls to the container - this is done here instead of the buildContainer function because we only want
		#controls published if the build function is called by Create - this allows build functions to call other build functions
		#and wrap them up as containers, but still publish their nodes
		if not _PART_DEBUG_MODE:
			controlNames = cls.CONTROL_NAMES or []  #CONTROL_NAMES can validly be None - so just use an empty list if this is the case
			for control in controls:
				if isinstance( control, DagNode ):
					try: controlName = controlNames[ idx ]
					except IndexError: controlName = 'c_%d' % idx
					container( theContainer, e=True, publishAsParent=(control, controlName) )


		#stuff the part container into the world container - we want a clean top level in the outliner
		worldPart.container.addNode( theContainer )


		#make sure the container "knows" the skeleton part - its not always obvious trawling through
		#the nodes in teh container which items are the skeleton part
		connectAttr( skeletonPart.base.message, theContainer._rigPrimitive.skeletonPart )


		#lock the parts so unpublished nodes can't be messed with
		theContainer.blackBox.set( True )


		return newPart
	@classmethod
	def GetControlName( cls, control ):
		'''
		returns the name of the control as defined in the CONTROL_NAMES attribute
		for the part class
		'''
		cons = listConnections( control.message, s=False, p=True, type='container' )
		for c in cons:
			typeClass = RigPart.GetNamedSubclass( c.node()._rigPrimitive.typeName.get() )
			if typeClass.CONTROL_NAMES is None:
				return str( control )

			try: name = typeClass.CONTROL_NAMES[ c.index() ]
			except ValueError:
				print typeClass, control
				raise RigPartError( "Doesn't have a name!" )

			return name

		raise RigPartError( "The control isn't associated with a rig primitive" )
	@classmethod
	def GetDefaultBuildKwargs( cls ):
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

		kwargs = []
		for argName, default in zip( argNames, defaults ):
			kwargs.append( (argName, default) )

		return kwargs
	def getBuildKwargs( self ):
		theDict = eval( self.container._rigPrimitive.buildKwargs.get() )
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
		connected = self.container._theSkeletonPart.listConnections()[ 0 ]
		return SkeletonPart.InitFromItem( connected )
	def getSkeletonPartParity( self ):
		return self.getSkeletonPart().getParity()
	def getControlName( self, control ):
		'''
		returns the name of the control as defined in the CONTROL_NAMES attribute
		for the part class
		'''
		if self.CONTROL_NAMES is None:
			return str( control )

		cons = cmd.listConnections( str(control.message), s=False, p=True, type='container' )  #listConnections( control.message, s=False, p=True, type='container' )
		for c in cons:
			try: c = PyNode( c )
			except MayaNodeError: continue

			if c.node() != self.container: continue
			name = self.CONTROL_NAMES[ c.index() ]

			return name

		raise RigPartError( "The control %s isn't associated with this rig primitive %s" % (control.shortName(), self) )


def niceControlName( control ):
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

	#determine default names for the given controls
	names = []
	for s in spaces:
		names.append( niceControlName( s ) )

	spaces += list( additionalParents )
	names += list( additionalParentNames )

	#we don't care about space switching if there aren't any non world spaces...
	if not spaces:
		return

	spaces.append( theWorld.control )
	names.append( 'The World' )

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
		if isinstance( skelPart, skeletonBuilderCore.Root ):
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
	jParent = joints[ 0 ].getParent()
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

	WORLD_OBJ_MENUS = [ ('toggle rig vis', """{\nstring $childs[] = `listRelatives -type transform #`;\nint $vis = !`getAttr ( $childs[0]+\".v\" )`;\nfor($a in $childs) if( `objExists ( $a+\".v\" )`) if( `getAttr -se ( $a+\".v\" )`) setAttr ( $a+\".v\" ) $vis;\n}"""),
	                    ('draw all lines of action', """string $menuObjs[] = `zooGetObjsWithMenus`;\nfor( $m in $menuObjs ) {\n\tint $cmds[] = `zooObjMenuListCmds $m`;\n\tfor( $c in $cmds ) {\n\t\tstring $name = `zooGetObjMenuCmdName $m $c`;\n\t\tif( `match \"draw line of action\" $name` != \"\" ) eval(`zooPopulateCmdStr $m (zooGetObjMenuCmdStr($m,$c)) {}`);\n\t\t}\n\t}"""),
	                    ('show "export relative" node', """"""),
	                    ]

	@classmethod
	def Create( cls, **kw ):
		for existingWorld in cls.IterAllParts():
			return existingWorld

		#try to determine scale - walk through all existing skeleton parts in the scene
		for skeletonPart in SkeletonPart.IterAllPartsInOrder():
			kw.setdefault( 'scale', skeletonPart.getBuildScale() )
			break

		worldNodes, controls = getNodesCreatedBy( cls._build, **kw )
		worldPart = buildContainer( WorldPart, { 'idx': 0 }, worldNodes, controls  )

		container( worldPart.container, e=True, publishAsRoot=(controls[ 0 ], 0) )
		if not _PART_DEBUG_MODE:
			for c, name in zip( controls, cls.CONTROL_NAMES ):
				if isinstance( c, DagNode ):
					container( worldPart.container, e=True, publishAsParent=(c, name) )

		container( worldPart.container, e=True, publishAsRoot=(controls[ 0 ], 0) )
		container( worldPart.container, e=True, publishAsRoot=(controls[ 1 ], 1) )

		return worldPart
	@classmethod
	def _build( cls, **kw ):
		scale = kw.get( 'scale', skeletonBuilderCore.TYPICAL_HEIGHT )
		scale /= 1.5

		world = buildControl( 'main', shapeDesc=ShapeDesc( None, 'hex', AX_Y ), oriented=False, scale=scale )

		parts = group( empty=True, name='parts_grp' )
		qss = sets( empty=True, text="gCharacterSet", n="body_ctrls" )
		masterQss = sets( empty=True, text="gCharacterSet", n="all_ctrls" )

		exportRelative = buildControl( 'exportRelative', shapeDesc=ShapeDesc( None, 'cube', AX_Y_NEG ), pivotModeDesc=PivotModeDesc.BASE, oriented=False, size=(1, 0.5, 1), scale=scale )
		parentConstraint( world, exportRelative )
		attrState( exportRelative, ('t', 'r', 's'), *LOCK_HIDE )
		attrState( exportRelative, 'v', *HIDE )
		exportRelative.v.set( False )

		#turn scale segment compensation off for all joints in the scene
		for j in ls( type='joint' ):
			j.ssc.set( False )

		masterQss.add( qss )

		attrState( world, 's', *NORMAL )
		world.scale >> parts.scale
		world.scaleX >> world.scaleY
		world.scaleX >> world.scaleZ

		#add right click items to the world controller menu
		worldTrigger = Trigger( str( world ) )
		qssIdx = worldTrigger.connect( str( masterQss ) )


		#add world control to master qss
		masterQss.add( world )
		masterQss.add( exportRelative )


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


class Root(RigSubPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( skeletonBuilderCore.Root, )
	CONTROL_NAMES = 'control', 'gimbal', 'hips'

	@classmethod
	def _build( cls, skeletonPart, buildHips=True, **kw ):
		return root( skeletonPart.base, buildHips, **kw )


def root( root, buildHips=True, **kw ):
	scale = kw[ 'scale' ]

	#deal with colours
	colour = ColourDesc( 'blue' )
	darkColour = colour.darken( 0.5 )
	lightColour = colour.lighten( 0.5 )


	#hook up the scale from the main control
	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	worldControl.scale.connect( root.scale )

	partParent, altRootControl = getParentAndRootControl( root )


	#try to determine a sensible size for the root control - basically grab teh autosize of the root joint, and take the x-z plane values
	size = control.getJointSize( [root], 0.5, WORLD )
	ringSize = Vector( size[0], size[0]+size[2]/3.0, size[2] )


	#create the controls, and parent them
	rootControl = buildControl( 'upperBodyControl', (root, PlaceDesc.WORLD), shapeDesc=ShapeDesc( 'band', axis=AX_Y ), colour=colour, constrain=False, size=size, parent=partParent )
	rootGimbal = buildControl( 'gimbalControl', (root, PlaceDesc.WORLD), shapeDesc=ShapeDesc( 'ring', axis=AX_Y ), colour=darkColour, oriented=False, offset=(0, size.y/2, 0), size=ringSize, parent=rootControl )
	hipsControl = buildControl( 'hipsControl', (root, PlaceDesc.WORLD), shapeDesc=ShapeDesc( 'ring', axis=AX_Y ), colour=lightColour, constrain=False, oriented=False, offset=(0, -size.y/2, 0), size=ringSize, parent=rootGimbal )
	rootSpace = rootControl.getParent()


	#delete the connections to rotation so we can put an orient constraint on the root joint to teh hips control
	for ax in AXES: delete( root.attr( 'r'+ ax ), icn=True )
	orientConstraint( hipsControl, root, mo=True )

	attrState( hipsControl, 't', *LOCK_HIDE )


	#turn unwanted transforms off, so that they are locked, and no longer keyable
	attrState( (rootGimbal, hipsControl), 't', *LOCK_HIDE )

	for s in listRelatives( rootGimbal, s=True ):
		s.visibility.set( False )

	xform( rootControl, p=1, roo='xzy' )
	xform( rootGimbal, p=1, roo='zxy' )


	#add right click menu to turn on the gimbal control
	Trigger.CreateMenu( rootControl,
	                    "toggle gimbal control",
	                    "{\nstring $kids[] = `listRelatives -type transform #`;\n$kids = `listRelatives -s $kids[0]`;\nint $vis = `getAttr ( $kids[0] +\".v\" )`;\nfor( $k in $kids ) setAttr ( $k +\".v\" ) (!$vis);\n}" )

	Trigger.CreateMenu( rootGimbal,
	                    "toggle gimbal control",
	                    "{\nstring $kids[] = `listRelatives -s #`;\nint $vis = `getAttr ( $kids[0] +\".v\" )`;\nfor( $k in $kids ) setAttr ( $k +\".v\" ) (!$vis);\nselect `listRelatives -p`;\n}" )

	return rootControl, rootGimbal, hipsControl


class IkFkBase(RigSubPart):
	'''
	this is a subpart, not generally exposed directly to the user
	'''
	__version__ = 0
	CONTROL_NAMES = 'control', 'fkUpper', 'fkMid', 'fkLower', 'poleControl', 'ikSpace', 'fkSpace', 'ikHandle', 'endOrient', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, **kw ):
		return ikFk( skeletonPart.bicep, skeletonPart.elbow, skeletonPart.wrist, **kw )


ARM_NAMING_SCHEME = 'arm', 'bicep', 'elbow', 'wrist'
LEG_NAMING_SCHEME = 'leg', 'thigh', 'knee', 'ankle'

def ikFk( bicep, elbow, wrist, nameScheme=ARM_NAMING_SCHEME, alignEnd=True, **kw ):
	'''
	'''

	idx = kw[ 'idx' ]
	scale = kw[ 'scale' ]

	parity = Parity( idx )
	suffix = parity.asName()

	if not isinstance( bicep, PyNode ): bicep = PyNode( bicep )
	if not isinstance( elbow, PyNode ): elbow = PyNode( elbow )
	if not isinstance( wrist, PyNode ): wrist = PyNode( wrist )


	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts

	colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )


	#grab a list of 'bicep joints' - these are the child joints of the bicep that aren't the elbow or any of its
	#children.  these joints are usually involved in deformation related to the bicep so we want to capture them
	#to use for geometry extraction for the control representation
	bicepJoints = [ bicep ]
	for child in bicep.getChildren( type='joint' ):
		if child == elbow: continue
		bicepJoints.append( child )
		bicepJoints += child.getChildren( type='joint', ad=True )

	#grab the 'elbow joints' as per the above description
	elbowJoints = [ elbow ]
	for child in elbow.getChildren( type='joint' ):
		if child == wrist: continue
		elbowJoints.append( child )
		elbowJoints += child.getChildren( type='joint', ad=True )


	#print 'THE BIPS', bicepJoints
	#print 'THE BOWS', elbowJoints


	### BUILD THE FK CONTROLS
	ikArmSpace = buildAlignedNull( wrist, "ik_%sSpace%s" % (nameScheme[ 0 ], suffix), parent=worldControl )
	fkArmSpace = buildAlignedNull( bicep, "fk_%sSpace%s" % (nameScheme[ 0 ], suffix) )

	BONE_AXIS = AIM_AXIS + 3 if parity else AIM_AXIS
	driverUpper = buildControl( "fk_%sControl%s" % (nameScheme[ 1 ], suffix), bicep, PivotModeDesc.MID, Shape_Skin( bicepJoints, axis=BONE_AXIS ), colour=colour, asJoint=True, oriented=False, scale=scale, parent=fkArmSpace )
	driverMid = buildControl( "fk_%sControl%s" % (nameScheme[ 2 ], suffix), elbow, PivotModeDesc.MID, Shape_Skin( elbowJoints, axis=BONE_AXIS ), colour=colour, asJoint=True, oriented=False, scale=scale, parent=driverUpper )
	driverLower = buildControl( "fk_%sControl%s" % (nameScheme[ 3 ], suffix), PlaceDesc( wrist, wrist if alignEnd else None ), shapeDesc=Shape_Skin( wrist, axis=BONE_AXIS ), colour=colour, asJoint=True, oriented=False, constrain=False, scale=scale )

	#don't parent the driverLower in the buildControl command otherwise the control won't be in worldspace
	parent( driverLower, driverMid )
	makeIdentity( driverLower )


	### BUILD THE POLE CONTROL
	polePos = api.mel.zooFindPolePosition( "-multiplier 5 -end %s" % str( driverLower ) )
	poleControl = buildControl( "%s_poleControl%s" % (nameScheme[ 0 ], suffix), PlaceDesc( elbow, PlaceDesc.WORLD ), shapeDesc=ShapeDesc( 'sphere', None ), colour=colour, constrain=False, parent=worldControl, scale=scale*0.5 )
	poleControlSpace = poleControl.getParent()
	attrState( poleControlSpace, 'v', lock=False, show=True )

	move( poleControlSpace, a=True, ws=True, rpr=True, *polePos )
	move( poleControl, a=True, ws=True, rpr=True, *polePos )
	makeIdentity( poleControlSpace, a=True, t=True )
	poleControl.v = False


	### BUILD THE POLE SELECTION TRIGGER
	lineNode = buildControl( "%s_poleSelectionTrigger%s" % (nameScheme[ 0 ], suffix), shapeDesc=ShapeDesc( 'sphere', None ), colour=ColourDesc( 'darkblue' ), scale=scale, constrain=False, oriented=False, parent=ikArmSpace )
	lineStart, lineEnd, lineShape = map( PyNode, utils.buildAnnotation( lineNode ) )

	parent( lineStart, poleControl )
	delete( pointConstraint( poleControl, lineStart ) )
	pointConstraint( elbow, lineNode )
	attrState( lineNode, ('t', 'r'), *LOCK_HIDE )

	lineStart.template.set( 1 )  #make the actual line unselectable


	#build the IK handle
	ikHandle = pymelCore.ikHandle( fs=1, sj=driverUpper, ee=driverLower, solver='ikRPsolver' )[ 0 ]
	limbControl = buildControl( '%sControl%s' % (nameScheme[ 0 ], suffix), PlaceDesc( wrist, wrist if alignEnd else None ), shapeDesc=Shape_Skin( wrist, axis=BONE_AXIS ), colour=colour, scale=scale, constrain=False, parent=ikArmSpace )

	xform( limbControl, p=True, rotateOrder='yzx' )
	ikHandle.snapEnable = False
	ikHandle.v = False

	limbControl.addAttr( 'ikBlend', shortName='ikb', dv=1, min=0, max=1, at='double' )
	limbControl.ikBlend.setKeyable( True )
	connectAttr( limbControl.ikBlend, ikHandle.ikBlend )

	attrState( ikHandle, 'v', *LOCK_HIDE )
	parent( ikHandle, partsControl )
	parentConstraint( limbControl, ikHandle )
	#parent( ikHandle, limbControl )  #

	poleVectorConstraint( poleControl, ikHandle )


	#setup constraints to the wrist - it is handled differently because it needs to blend between the ik and fk chains (the other controls are handled by maya)
	wristOrient = buildAlignedNull( wrist, "%s_follow%s" % (nameScheme[ 3 ], suffix), parent=partsControl )

	pointConstraint( driverLower, wrist )
	orientConstraint( wristOrient, wrist, mo=True )
	setItemRigControl( wrist, wristOrient )
	wristSpaceOrient = parentConstraint( limbControl, wristOrient, weight=0, mo=True )
	wristSpaceOrient = parentConstraint( driverLower, wristOrient, weight=0, mo=True )
	wristSpaceOrient.interpType.set( 2 )


	#connect the ikBlend of the arm controller to the orient constraint of the fk wrist - ie turn it off when ik is off...
	weightRevNode = shadingNode( 'reverse', asUtility=True )
	connectAttr( limbControl.ikBlend, weightRevNode.inputX, f=True )
	connectAttr( limbControl.ikBlend, wristSpaceOrient.listAttr( ud=True )[ 0 ], f=True )
	connectAttr( weightRevNode.outputX, wristSpaceOrient.listAttr( ud=True )[ 1 ], f=True )


	#build expressions for fk blending and control visibility
	fkVisCond = shadingNode( 'condition', asUtility=True )
	poleVisCond = shadingNode( 'condition', asUtility=True )
	connectAttr( limbControl.ikBlend, fkVisCond.firstTerm, f=True )
	connectAttr( limbControl.ikBlend, poleVisCond.firstTerm, f=True )
	connectAttr( fkVisCond.outColorR, driverUpper.v, f=True )
	connectAttr( poleVisCond.outColorG, poleControlSpace.v, f=True )
	connectAttr( poleVisCond.outColorG, limbControl.v, f=True )
	fkVisCond.secondTerm.set( 1 )


	#add set pole to fk pos command to pole control
	fkControls = driverUpper, driverMid, driverLower
	poleTrigger = Trigger( poleControl )
	poleConnectNums = [ poleTrigger.connect( c ) for c in fkControls ]

	idx_toFK = poleTrigger.setMenuInfo( None,
	                                    "move to FK position",
	                                    'zooVectors;\nfloat $pos[] = `zooFindPolePosition "-start %%%s -mid %%%s -end %%%s"`;\nmove -rpr $pos[0] $pos[1] $pos[2] #;' % tuple( poleConnectNums ) )
	poleTrigger.setMenuInfo( None,
	                         "move to FK pos for all keys",
	                         'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % idx_toFK )


	##build the post trace commands for the pole vectors - once they've been placed after a trace, its safe and almost always
	##desireable to place the pole vectors a little more sensibly
	#zooSetPostTraceCmd $poleControl ( "zooVectors; zooPlacePole \"-obj # -start %"+ $poleConnectNums[0] +" -mid %"+ $poleConnectNums[1] +" -end %"+ $poleConnectNums[2] +" -key 1 -removeKey 1 -invalidMode 1\";" );


	#add IK/FK switching commands
	limbTrigger = Trigger( limbControl )
	handleNum = limbTrigger.connect( ikHandle )
	poleNum = limbTrigger.connect( poleControl )
	fkIdx = limbTrigger.createMenu( "switch to FK",
	                                "zooAlign \"\";\nzooAlignFK \"-ikHandle %%%d -offCmd setAttr #.ikBlend 0;\";" % handleNum )
	limbTrigger.createMenu( "switch to FK for all keys",
	                        'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % fkIdx )
	ikIdx = limbTrigger.createMenu( "switch to IK",
	                                'zooAlign "";\nzooAlignIK "-ikHandle %%%d -pole %%%d -offCmd setAttr #.ikBlend 1;";' % (handleNum, poleNum) )
	limbTrigger.createMenu( "switch to IK for all keys",
	                        'source zooKeyCommandsWin;\nzooSetKeyCommandsWindowCmd "eval(zooPopulateCmdStr(\\\"#\\\",(zooGetObjMenuCmdStr(\\\"#\\\",%%%d)),{}))";' % ikIdx )


	#add all zooObjMenu commands to the fk controls
	for fk in fkControls:
		fkTrigger = Trigger( fk )
		c1 = fkTrigger.connect( ikHandle )
		c2 = fkTrigger.connect( poleControl )

		#"zooFlags;\nzooAlign \"\";\nzooAlignIK \"-ikHandle %%%d -pole %%%d\";\nselect %%%d;" % (c1, c2, c1) )
		fkTrigger.createMenu( 'switch to IK',
		                      'zooAlign "";\nstring $cs[] = `listConnections %%%d.ikBlend`;\nzooAlignIK ("-ikHandle %%%d -pole %%%d -control "+ $cs[0] +" -offCmd setAttr "+ $cs[0] +".ikBlend 1;" );' % (c1, c1, c2) )

	createLineOfActionMenu( [limbControl] + list( fkControls ), (elbow, wrist) )


	#add trigger commands
	Trigger.CreateTrigger( lineNode, Trigger.PRESET_SELECT_CONNECTED, [ poleControl ] )
	lineNode.displayHandle.set( True )


	#turn unwanted transforms off, so that they are locked, and no longer keyable
	attrState( fkControls, ('t', 'radi'), *LOCK_HIDE )
	attrState( poleControl, 'r', *LOCK_HIDE )


	return limbControl, driverUpper, driverMid, driverLower, poleControl, ikArmSpace, fkArmSpace, ikHandle, wristOrient, lineNode


class PrimaryRigPart(RigPart):
	'''
	all subclasses of this class are exposed as available rigging methods to the user
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def DISPLAY_NAME( cls ):
		return camelCaseToNice( cls.__name__ )


class FkSpine(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Spine, )

	@classmethod
	def _build( cls, skeletonPart, **kw ):
		return fkSpine( skeletonPart[ 0 ], skeletonPart[ -1 ], **kw )


def fkSpine( spineBase, spineEnd, parents=(), **kw ):
	'''
	'''
	scale = kw[ 'scale' ]

	spineBase, spineEnd = PyNode( spineBase ), PyNode( spineEnd )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts


	partParent, rootControl = getParentAndRootControl( spineBase )


	#build a list of all spine joints - start from the bottom of the heirarchy, and work up - a joint only has one parent
	spines = [ spineEnd ]
	if spineBase != spineEnd:
		while True:
			p = spines[ -1 ].getParent()
			spines.append( p )
			if p == spineBase: break

		spines.reverse()


	#try to figure out a sensible offset for the spine controls - this is basically just an average of the all offsets for all spine joints
	spineOffset = AX_Z.asVector() * getAutoOffsetAmount( spines[ 0 ], spines )


	#create the controls, and parent them
	#determine what axis to draw the spine controls - assume they're all the same as the spine base
	controlSpaces = []
	controllers = []
	startColour = ColourDesc( (1, 0.3, 0, 0.65) )
	endColour = ColourDesc( (0.8, 1, 0, 0.65) )
	spineColour = startColour
	colourInc = (endColour - startColour) / float( len( spines ) )

	for n, j in enumerate( spines ):
		c = buildControl( "spine_%d_fkControl" % n, j, PivotModeDesc.BASE, ShapeDesc( 'pin', axis=AX_Z ), colour=spineColour, offset=spineOffset, scale=scale*1.5 )
		cSpace = c.getParent()

		jParent = partParent
		if n: jParent = controllers[ -1 ]

		controllers.append( c )
		controlSpaces.append( cSpace )

		parent( cSpace, jParent )
		spineColour += colourInc


	#create the space switching
	for j, c in zip( spines, controllers ):
		buildDefaultSpaceSwitching( j, c, **spaceSwitching.NO_TRANSLATION )


	#create line of action commands
	createLineOfActionMenu( spines, controllers )


	#turn unwanted transforms off, so that they are locked, and no longer keyable
	attrState( controllers, 't', *NORMAL )


	return controllers


class ControlHierarchy(PrimaryRigPart):
	__version__ = 0
	#part doesn't have a CONTROL_NAMES list because parts are dynamic - use indices to refer to controls
	SKELETON_PRIM_ASSOC = ( ArbitraryChain, )

	@classmethod
	def _build( cls, part, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=False, parents=(), rigOrphans=False, **kw ):
		joints = list( part ) + (part.getOrphanJoints() if rigOrphans else [])
		return controlChain( joints, controlShape, spaceSwitchTranslation, parents, rigOrphans, **kw )


class WeaponControlHierarchy(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( WeaponRoot, )

	@classmethod
	def _build( cls, part, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=True, parents=(), **kw ):
		return controlChain( part.selfAndOrphans(), controlShape, spaceSwitchTranslation, parents, True, **kw )


def controlChain( joints, controlShape=DEFAULT_SHAPE_DESC, spaceSwitchTranslation=False, parents=(), rigOrphans=False, **kw ):
	scale = kw[ 'scale' ]

	worldPart = WorldPart.Create()
	worldControl = worldPart.control

	#discover parent nodes
	namespace = ''
	try: namespace = getNamespaceFromReferencing( joints[ 0 ] )
	except IndexError: pass

	parents = tuple( '%s%s' % (namespace, p) for p in parents )

	### DETERMINE THE PART'S PARENT CONTROL AND THE ROOT CONTROL ###
	parentControl, rootControl = getParentAndRootControl( joints[ 0 ] )

	ctrls = []
	prevParent = parentControl

	for item in joints:
		ctrl = buildControl( '%s_ctrl' % item, item, PivotModeDesc.BASE, controlShape, size=AUTO_SIZE )
		ctrlSpace = ctrl.getParent()

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


class QuadrupedIkFkLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( QuadrupedFrontLeg, QuadrupedBackLeg )
	CONTROL_NAMES = 'control', 'poleControl', 'clavicle'

	DISPLAY_NAME = 'Quadruped Leg'

	@classmethod
	def _build( cls, skeletonPart, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return quadrupedIkFkLeg( *items, **kw )


def quadrupedIkFkLeg( thigh, knee, ankle, clavicle, **kw ):
	idx = kw[ 'idx' ]
	scale = kw[ 'scale' ]

	parity = Parity( idx )
	parityMult = parity.asMultiplier()

	nameMod = kw.get( 'nameMod', 'front' )

	worldPart = WorldPart.Create()
	worldControl, partsControl = worldPart.control, worldPart.parts

	nameSuffix = '%s%s' % (nameMod.capitalize(), parity.asName())

	colour = ColourDesc( 'red 0.7' ) if parity else ColourDesc( 'green 0.7' )

	#determine the root
	partParent, rootControl = getParentAndRootControl( clavicle )

	#build out the control for the clavicle
	clavCtrl = buildControl( 'quadClavicle%s' % nameSuffix,
                             PlaceDesc( clavicle ),
                             PivotModeDesc.BASE,
                             ShapeDesc( 'cylinder', axis=-AIM_AXIS if parity else AIM_AXIS ),
                             colour, scale=scale )

	clavCtrlSpace = clavCtrl.getParent()
	clavCtrl.rotateOrder.set( 1 )

	pymelCore.parent( clavCtrlSpace, partParent )


	### BUILD THE LEG RIG PRIMITIVE ###
	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, thigh, knee, ankle, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )

	legCtrl = ikFkPart.control
	legFkSpace = ikFkPart.fkSpace

	parent( legFkSpace, clavCtrl )


	### SETUP CLAVICLE AIM ###
	dummyGrp = group( em=True )
	delete( pointConstraint( clavicle, dummyGrp ) )
	parent( dummyGrp, rootControl )

	aimVector = BONE_AIM_AXIS * parityMult
	sideClavAxis = utils.getObjectAxisInDirection( clavCtrlSpace, Vector( 1, 0, 0 ) ).asVector()
	sideCtrlAxis = utils.getObjectAxisInDirection( legCtrl, Vector( 1, 0, 0 ) ).asVector()

	aim = aimConstraint( legCtrl, clavCtrlSpace, aimVector=(1,0,0), upVector=sideClavAxis, worldUpVector=sideCtrlAxis, worldUpObject=legCtrl, worldUpType='objectrotation', mo=True )
	aimNode = aimConstraint( dummyGrp, clavCtrlSpace, weight=0, aimVector=(1,0,0) )

	revNode = createNode( 'reverse' )
	clavCtrl.addAttr( 'autoMotion', at='float', min=0, max=1, dv=1 )
	clavCtrl.autoMotion.setKeyable( True )

	connectAttr( clavCtrl.autoMotion, aimNode.target[0].targetWeight, f=True )
	connectAttr( clavCtrl.autoMotion, revNode.inputX, f=True )
	connectAttr( revNode.outputX, aimNode.target[1].targetWeight, f=True )


	### HOOK UP A FADE FOR THE AIM OFFSET
	mt, measure, la, lb = utils.buildMeasure( str( clavCtrlSpace ), str( legCtrl ) )
	maxLen = utils.chainLength( clavicle, ankle )
	curLen = getAttr( measure.distance )

	pymelCore.parent( la, rootControl )
	pymelCore.parent( mt, rootControl )

	for c in [ mt, la, lb ]:
		c.v.set( False )
		c.v.setLocked( True )

	return legCtrl, ikFkPart.poleControl, clavCtrl


class IkFkArm(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Arm, )
	CONTROL_NAMES = 'control', 'fkBicep', 'fkElbow', 'fkWrist', 'poleControl', 'clavicle', 'allPurpose', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, stretchy=False, **kw ):

		#this bit of zaniness is so we don't have to call the items by name, which makes it work with Arm or Leg skeleton primitives
		items = list( skeletonPart )[ :3 ]

		if len( skeletonPart ) == 4:
			items = list( skeletonPart )[ 1:4 ]
			items.append( skeletonPart[ 0 ] )

		return ikFkArm( stretchy=stretchy, *items, **kw )


def ikFkArm( bicep, elbow, wrist, clavicle=None, stretchy=True, **kw ):
	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	getWristToWorldRotation( wrist, True )

	colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts

	parentControl, rootControl = getParentAndRootControl( clavicle or bicep )


	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, bicep, elbow, wrist, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )

	#create variables for each control used
	armControl = ikFkPart.control
	ikHandle = ikFkPart.ikHandle
	ikArmSpace = ikFkPart.ikSpace
	fkArmSpace = ikFkPart.fkSpace
	driverBicep = ikFkPart.fkUpper
	driverElbow = ikFkPart.fkMid
	driverWrist = ikFkPart.fkLower
	elbowControl = ikFkPart.poleControl
	fkControls = driverBicep, driverElbow, driverWrist


	#build the clavicle
	if clavicle:
		clavOffset = AX_Y.asVector() * getAutoOffsetAmount( clavicle, clavicle.getChildren(), AX_Y )
		clavControl = buildControl( 'clavicleControl%s' % parity.asName(), PlaceDesc( bicep, clavicle, clavicle ), shapeDesc=ShapeDesc( 'sphere' ), scale=scale*1.25, offset=clavOffset, offsetSpace=WORLD, colour=colour )
		clavControlOrient = clavControl.getParent()

		parent( clavControlOrient, parentControl )
		parent( fkArmSpace, clavControl )
		attrState( clavControl, 't', *LOCK_HIDE )
	else:
		parent( fkArmSpace, parentControl )


	#build space switching
	allPurposeObj = spaceLocator()
	allPurposeObj.rename( "arm_all_purpose_loc%s" % parity.asName() )
	parent( allPurposeObj, worldControl )

	buildDefaultSpaceSwitching( bicep, armControl, [ allPurposeObj ], [ 'All Purpose' ], True )
	buildDefaultSpaceSwitching( bicep, driverBicep, **spaceSwitching.NO_TRANSLATION )


	##make the limb stretchy?
	#if stretchy:
		#makeStretchy( armControl, ikHandle, "-axis x -parts %s" % str( partsControl ) )


	return armControl, driverBicep, driverElbow, driverWrist, elbowControl, clavControl, allPurposeObj, ikFkPart.poleTrigger


def makeStretchy( control, ikHandle, axis=BONE_AIM_AXIS, startObj=None, endObj=None, parity=Parity.LEFT, elbowPos=1 ):
	'''
	creates stretch attribs on the $control object, and makes all joints controlled by the ikHandle stretchy
	-------

	$control - the character prefix used to identify the character
	$parity - which side is the arm on?  l (left) or r (right)
	$ikHandle - the bicep, upper arm, or humerous
	$optionStr - standard option string - see technical docs for info on option strings

	option flags
	-------
	-axis [string]			the stretch axis used by the joints in the limb.  default: x
	-scale [float]			scale factor to apply to the control (purely a visual thing - scale is frozen).  default: 1
	-startObj [string]	the beginning of the measure node is attached to the start object.  if its not specified, then the script assumes the start object is the start of the ik chain (usally the case)
	-endObj [string]		this is the object the end of the measure is attached to - by default its the
	-invert [int]				use this flag if the script inverts the limb when adding stretch
	-parts [string]		the parts node is simply an object that miscellanous dag nodes are parented under - if not specified, miscellanous objects are simply left in worldspace
	// -dampen [float]				this flag allows control over the dampen range - lower values cause the dampening to happen over a shorter range.  setting to zero turns damping off.  its technical range is 0-100, but in practice, its probably best to keep between 0-25.  defaults to 12
	// -dampstrength [float]		this is the strength of the dampening - ie how much the arm gets elongated as it nears maximum extension.  the technical range is 0-100, but in reality, you'd probably never go beyond 10.  default is 2

	It is reccommended that this proc has a "root" control, a "chest" control and a "head" control already
	built (and branded with these names) as it uses them as dynamic parents for the actual arm control.

	For example:
	zooCSTMakeStretchy primoBoy_arm_ctrl_L l primoBoy_arm_ctrl_L "-axis x -scale 0.5";
	'''
	#float $dampRange = 12.0
	#float $dampStrength = 2.0;
	#int $elbowpos = 1;
	#if( $dampRange <= 0 ) $dampstrength = 0;
	#$dampRange = abs($dampRange);
	#$dampStrength = abs($dampStrength);
	#$dampRange /= 200.0;  //divide by 200 because we want the input range to be 0-100, but internally it needs to range from 0-0.5
	#$dampStrength /= 100.0;


	#setup some current unit variables, and take parity into account
	stretchAuto = "autoStretch"
	stretchName = "stretch"
	parityFactor = parity.asMultiplier()

	control.addAttr( stretchAuto, at='double', min=0, max=1, dv=1 )
	control.addAttr( stretchName, at='double', min=0, max=10, dv=0 )
	attrState( control, (stretchAuto, stretchName), keyable=True )


	#build the network for distributing stretch from the fk controls to the actual joints
	plusNodes = []
	initialNodes = []
	fractionNodes = []
	clients = []
	allNodes = []

	clients = pymelCore.ikHandle( ikHandle, q=True, jl=True )
	if axis is None:
		raise NotImplemented( 'axis support not written yet - complain loudly!' )
		#axis = `zooCSTJointDirection $clients[1]`;  #if no axis is specified, assume the second joint in the chain has the correct axis set

	#get the end joint in the chain...
	cons = getattr( ikHandle, 't'+ axis.asCleanName() ).listConnections( s=False )
	clients.append( cons[ 0 ] )

	for c in clients:
		md = shadingNode( 'multiplyDivide', asUtility=True, name='%s_fraction_pos' % str( c ) )
		fractionNodes.append( md )

	if startObj is None:
		startObj = clients[ 0 ]

	if endObj is None:
		endObj = ikHandle


	clientLengths = []
	totalLength = 0
	for n, c in enumerate( clients[ :-1 ] ):
		thisPos = Vector( xform( c, q=True, ws=True, rp=True ) )
		nextPos = Vector( xform( clients[ n+1 ], q=True, ws=True, rp=True ) )
		l = (thisPos - nextPos).length()
		clientLengths.append( l )
		totalLength += l


	#build the network to measure limb length
	loc_a = group( empty=True )
	loc_b = group( empty=True )
	measure = loc_b

	parent( loc_b, loc_a )
	constraint_a = pointConstraint( startObj, loc_a )

	aim = aimConstraint( endObj, loc_a, aimVector=(1,0,0) )
	loc_b.tx.set( totalLength )
	makeIdentity( loc_b, a=True, t=True)  #by doing this, the zero point for the null is the max extension for the limb
	constraint_b = pointConstraint( endObj, loc_b )
	attrState( [ loc_a, loc_b ], ('t', 'r'), *LOCK_HIDE )


	#create the stretch network
	stretchEnable = shadingNode( 'multiplyDivide', asUtility=True, n='stretch_enable' )  #blends the auto length smooth back to zero when blending to fk
	fkikBlend = shadingNode( 'multiplyDivide', asUtility=True, n='fkik_stretch_blend' )  #blends the auto length smooth back to zero when blending to fk
	actualLength = shadingNode( 'plusMinusAverage', asUtility=True, n='actual_length' )  #adds the length mods to the normal limb length
	lengthMods = shadingNode( 'plusMinusAverage', asUtility=True, n='length_mods' )  #adds all lengths together
	finalLength = shadingNode( 'clamp', asUtility=True, n='final_length' )  #clamps the length the limb can be
	manualStretchMult = shadingNode( 'multiplyDivide', asUtility=True, n='manualStretch_range_multiplier' )  #multiplys manual stretch to a sensible range
	dampen = createNode( 'animCurveUU', n='dampen' )

	#for n, cl in enumerate( clientLengths ):  #if any of the lengths are negative, the stretch will still be wrong, but will be easier to fix manually if this number is correct
	setKeyframe( dampen, f=totalLength * -0.5, v=0 )
	setKeyframe( dampen, f=totalLength * -dampRange, v=totalLength * dampStrength )
	setKeyframe( dampen, f=totalLength * dampRange, v=0 )
	keyTangent( dampen, f=":", itt='flat', ott='flat' )

	#NOTE: the second term attribute of the length condition node holds the initial length for the limb, and is thus connected to the false attribute of all condition nodes
	manualStretchMult.input2X.set( totalLength / 10 )
	actualLength.input1D[ 0 ].set( totalLength )
	actualLength.input1D[ 0 ].set( totalLength )
	finalLength.minR.set( totalLength )
	finalLength.maxR.set( totalLength * 3 )
	connectAttr( measure.tx, dampen.input, f=True )
	connectAttr( lengthMods.output1D, fkikBlend.input1X, f=True )
	connectAttr( ikHandle.ikBlend, fkikBlend.input2X, f=True )
	connectAttr( fkikBlend.outputX, stretchEnable.input1X, f=True )
	connectAttr( getattr( control, stretchAuto ), stretchEnable.input2X, f=True )
	connectAttr( measure.tx, lengthMods.input1D[ 0 ], f=True )
	connectAttr( getattr( control, stretchName ), manualStretchMult.input1X, f=True )
	connectAttr( manualStretchMult.outputX, lengthMods.input1D[ 1 ], f=True )
	connectAttr( dampen.output, lengthMods.input1D[ 2 ], f=True )
	connectAttr( stretchEnable.outputX, actualLength.input1D[ 1 ], f=True )
	connectAttr( actualLength.output1D, finalLength.inputR, f=True )


	#connect the stretch distribution network up - NOTE this loop starts at 1 because we don't need to connect the
	#start of the limb chain (ie the bicep or the thigh) as it doesn't move
	for n, c in enumerate( clients ):
		if n == 0: continue
		fractionNodes[ n ].input2X.set( clientLengths[ n ] / totalLength * parityFactor )

		#now connect the inital coords to the plus node - then connect the
		connectAttr( finalLength.outputR, fractionNodes[ n ].input1X, f=True )

		#then connect the result of the plus node to the t(axis) pos of the limb joints
		clients[ n ].tx.setLocked( False )
		connectAttr( fractionNodes[ n ].outputX, clients[ n ].tx, f=True )


	#now if we have only 3 clients, that means we have a simple limb structure
	#in which case, lets build an elbow pos network
	if len( clients ) == 3 and elbowPos:
		default = clientLengths[ 1 ] / totalLength * parityFactor
		isNeg = default < 0

		default = abs( default )
		control.addAttr( 'elbowPos', at='double', min=0, max=1, dv=default )
		control.elbowPos.setKeyable( True )

		elbowPos = shadingNode( 'reverse', asUtility=True, n='%s_elbowPos' % clients[ 1 ] )
		if isNeg:
			mult = shadingNode( 'multiplyDivide', asUtility=True )
			mult.input2.set( (-1, -1, -1) )
			connectAttr( control.elbowPos, elbowPos.inputX, f=True )
			connectAttr( control.elbowPos, mult.input1X, f=True )
			connectAttr( elbowPos.outputX, mult.input1Y, f=True )
			connectAttr( mult.outputY, fractionNodes[2].input2X, f=True )
			connectAttr( mult.outputX, fractionNodes[1].input2X, f=True )
		else:
			connectAttr( control.elbowPos, elbowPos.inputX, f=True )
			connectAttr( elbowPos.outputX, fractionNodes[2].input2X, f=True )
			connectAttr( control.elbowPos, fractionNodes[1].input2X, f=True )


class IkFkLeg(PrimaryRigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( Leg, )
	CONTROL_NAMES = 'control', 'fkThigh', 'fkKnee', 'fkAnkle', 'poleControl', 'allPurpose', 'poleTrigger'

	@classmethod
	def _build( cls, skeletonPart, stretchy=False, **kw ):
		return ikFkLeg( skeletonPart.thigh, skeletonPart.knee, skeletonPart.ankle, stretchy=stretchy, **kw )


def ikFkLeg( thigh, knee, ankle, stretchy=True, **kw ):
	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	suffix = parity.asName()

	colour = ColourDesc( 'green' ) if parity == Parity.LEFT else ColourDesc( 'red' )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts


	#first rotate the foot so its aligned to a world axis
	footCtrlRot = Vector( getAnkleToWorldRotation( str( ankle ), 'z', True ) )
	footCtrlRot = (0, -footCtrlRot.y, 0)


	### BUILD THE IKFK BASE
	ikFkNodes, ikFkControls = getNodesCreatedBy( ikFk, thigh, knee, ankle, LEG_NAMING_SCHEME, False, **kw )
	ikFkPart = buildContainer( IkFkBase, kw, ikFkNodes, ikFkControls )


	partParent, rootControl = getParentAndRootControl( thigh )


	#if the part parent in a Root primitive, grab the hips control instead of the root gimbal - for the leg parts this is preferable
	parentRigPart = RigPart.InitFromItem( partParent )
	if isinstance( parentRigPart, Root ):
		print 'FOUND ZE HIPS!'
		partParent = parentRigPart.hips


	#create variables for each control used
	legControl = ikFkPart.control
	legControlSpace = legControl.getParent()

	ikLegSpace = ikFkPart.ikSpace
	fkLegSpace = ikFkPart.fkSpace
	driverThigh = ikFkPart.fkUpper
	driverKnee = ikFkPart.fkMid
	driverAnkle = ikFkPart.fkLower
	ikHandle = ikFkPart.ikHandle
	kneeControl = ikFkPart.poleControl
	kneeControlSpace = kneeControl.getParent()
	toe = listRelatives( ankle, type='joint' )[ 0 ]
	toeTip = None

	fkControls = driverThigh, driverKnee, driverAnkle


	#if the toe doesn't exist, build a temp one
	if not toe:
		toe = group( em=True )
		parent( toe, ankle, r=True )
		move( toe, 0, -scale, scale, r=True, ws=True )

	possibleTips = listRelatives( toe, type='joint' )
	if possibleTips:
		toeTip = possibleTips[ 0 ]


	#build the objects to control the foot
	footControlSpace = buildNullControl( "foot_controlSpace"+ suffix, ankle, parent=legControl )
	heelRoll = buildNullControl( "heel_roll_piv"+ suffix, ankle, offset=(0, 0, -scale) )
	footBankL = buildNullControl( "bank_in_piv"+ suffix, toe )
	footBankR = buildNullControl( "bank_out_piv"+ suffix, toe )
	footRollControl = buildNullControl( "roll_piv"+ suffix, toe )
	toeOrient = buildNullControl( "toe_orient_piv"+ suffix, toe )

	if toeTip:
		toeRoll = buildNullControl( "leg_toe_roll_piv"+ suffix, toeTip )
	else:
		toeRoll = buildNullControl( "leg_toe_roll_piv"+ suffix, toe, offset=(0, 0, scale) )

	select( heelRoll )  #stupid move command doesn't support object naming when specifying a single axis move, so we must selec the object first
	move( (0, 0, 0), rpr=True, y=True )


	#move bank pivots to a good spot on the ground
	toePos = toe.getRotatePivot( 'world' )
	sideOffset = -scale if parity == Parity.LEFT else scale
	move( footBankL, (toePos.x+sideOffset, 0, toePos.z), a=True, ws=True, rpr=True )
	move( footBankR, (toePos.x-sideOffset, 0, toePos.z), a=True, ws=True, rpr=True )


	#parent the leg pivots together
	parent( kneeControlSpace, partParent )

	parent( heelRoll, footControlSpace )
	parent( toeRoll, heelRoll )
	parent( footBankL, toeRoll )
	parent( footBankR, footBankL )
	parent( footRollControl, footBankR )
	parent( toeOrient, footBankR )
	if toe: orientConstraint( toeOrient, toe, mo=True )
	makeIdentity( heelRoll, apply=True, t=True, r=True )


	#move the knee control so its inline with the leg
	#move( kneeControlSpace, newPos, a=True, ws=True, rpr=True )
	rotate( kneeControlSpace, footCtrlRot, p=thigh.getRotatePivot( 'world' ), a=True, ws=True )
	makeIdentity( kneeControl, apply=True, t=True )


	#add attributes to the leg control, to control the pivots
	legControl.addAttr( 'rollBall', at='double', min=0, max=10, k=True )
	legControl.addAttr( 'rollToe', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'twistFoot', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'toe', at='double', min=-10, max=10, k=True )
	legControl.addAttr( 'bank', at='double', min=-10, max=10, k=True )


	#replace the legControl as a target to teh parent constraint on the endOrient transform so the ikHandle respects the foot slider controls
	footFinalPivot = buildNullControl( "final_piv"+ suffix, ankle, parent=footRollControl )
	endOrientConstraint = ikFkPart.endOrient.tx.listConnections( type='constraint', d=False )[ 0 ]
	for attr in endOrientConstraint.target[ 0 ].getChildren():
		for con in attr.listConnections( p=True, type='transform', d=False ):
			if con.node() == legControl:
				#footFinalPivot.attr( con.shortName() ) >> attr  ##there is a bug here - instantiating a rotatePivot doesn't return an Attribute instance - so we need to go back to dealing with strings...

				toks = str( con ).split( '.' )
				toks[ 0 ] = str( footFinalPivot )
				connectAttr( '.'.join( toks ), attr, f=True )

	delete( parentConstraint( footFinalPivot, ikHandle, mo=True ) )
	parent( ikHandle, footFinalPivot )


	#build the SDK's to control the pivots
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=0, v=0 )
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=10, v=90 )
	setDrivenKeyframe( footRollControl.rx, cd=legControl.rollBall, dv=-10, v=-90 )

	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=0, v=0 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=10, v=90 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=0, v=0 )
	setDrivenKeyframe( toeRoll.rx, cd=legControl.rollToe, dv=-10, v=-90 )
	setDrivenKeyframe( toeRoll.ry, cd=legControl.twistFoot, dv=-10, v=-90 )
	setDrivenKeyframe( toeRoll.ry, cd=legControl.twistFoot, dv=10, v=90 )

	setDrivenKeyframe( toeOrient.ry, cd=legControl.toe, dv=-10, v=90 )
	setDrivenKeyframe( toeOrient.ry, cd=legControl.toe, dv=10, v=-90 )

	min = -90 if parity == Parity.LEFT else 90
	max = 90 if parity == Parity.LEFT else -90
	setDrivenKeyframe( footBankL.rz, cd=legControl.bank, dv=0, v=0 )
	setDrivenKeyframe( footBankL.rz, cd=legControl.bank, dv=10, v=max )
	setDrivenKeyframe( footBankR.rz, cd=legControl.bank, dv=0, v=0 )
	setDrivenKeyframe( footBankR.rz, cd=legControl.bank, dv=-10, v=min )


	#build all purpose
	allPurposeObj = spaceLocator( name="leg_all_purpose_loc%s" % suffix )
	parent( allPurposeObj, worldControl )


	#build space switching
	parent( fkLegSpace, partParent )
	spaceSwitching.build( legControl, (worldControl, partParent, rootControl, allPurposeObj), ('World', None, 'Root', 'All Purpose'), space=legControlSpace )
	spaceSwitching.build( kneeControl, (legControl, partParent, rootControl, worldControl), ("Leg", None, "Root", "World"), **spaceSwitching.NO_ROTATION )
	spaceSwitching.build( driverThigh, (partParent, rootControl, worldControl), (None, 'Root', 'World'), **spaceSwitching.NO_TRANSLATION )


	#make the limb stretchy
	#makeStretchy( legControl, ikHandle, parity=parity )  #( $optionStr +" -startObj "+ $thigh +" -endObj "+ $legControl +" -register 1 -primitive "+ $primitive +" -axis "+ zooCSTJointDirection($ankle) +" -prefix "+ $prefix +" -parts "+ $partsControl )
	#renameAttr( legControl.elbowPos, 'kneePos' )


	#hide attribs, objects and cleanup
	attrState( legControl, 'kneePos', *LOCK_HIDE )


	return legControl, driverThigh, driverKnee, driverAnkle, kneeControl, allPurposeObj, ikFkPart.poleTrigger


class Head(RigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( skeletonBuilderCore.Head, )
	CONTROL_NAMES = 'control', 'gimbal', 'neck'

	@classmethod
	def _build( cls, skeletonPart, **kw ):
		return head( skeletonPart.head, **kw )


def head( head, neckCount=1, **kw ):
	scale = kw[ 'scale' ]

	partParent, rootControl = getParentAndRootControl( head )

	worldPart = WorldPart.Create()
	worldControl = worldPart.control
	partsControl = worldPart.parts

	colour = ColourDesc( 'blue' )
	lightBlue = ColourDesc( 'lightblue' )


	#build the head controls - we always need them
	headControl = buildControl( "headControl", head,
	                            shapeDesc=Shape_Skin( [head] + listRelatives( head, ad=True, type='joint' ) ),
	                            colour=colour, scale=scale )

	headControlSpace = headControl.getParent()
	headGimbal = buildControl( "head_gimbalControl", head, shapeDesc=ShapeDesc( None, 'starCircle' ), colour=colour, oriented=False, scale=scale, autoScale=True, parent=headControl )


	#now find the neck joints
	neckJoints = []
	curParent = head
	for n in range( neckCount ):
		curParent = curParent.getParent()
		neckJoints.append( curParent )

	neckJoints.reverse()


	#determine an offset amount for the neck controls based on the geometry skinned to the necks and head joint
	neckOffset = AX_Z.asVector() * getAutoOffsetAmount( head, neckJoints )


	#build the controls for them
	neckControls = []
	theParent = partParent
	for n, j in enumerate( neckJoints ):
		c = buildControl( 'neck_%d_Control' % n, j, PivotModeDesc.BASE, ShapeDesc( 'pin', axis=AX_Z ), colour=lightBlue, scale=scale*1.5, offset=neckOffset, parent=theParent )
		attrState( c, 't', *LOCK_HIDE )

		theParent = c
		neckControls.append( c )

	if neckCount == 1:
		neckControls[ 0 ].rename( 'neckControl' )

	parent( headControlSpace, neckControls[ -1 ] )


	#build space switching
	spaceSwitching.build( headControl,
	                      (neckControls[ 0 ], partParent, rootControl, worldControl),
	                      ('Neck', 'Parent Part', 'Root', 'World'),
	                      space=headControlSpace, **spaceSwitching.NO_TRANSLATION )

	for c in neckControls:
		spaceSwitching.build( c,
		                      (partParent, rootControl, worldControl),
			                  ('Parent Part', 'Root', 'World'),
			                  **spaceSwitching.NO_TRANSLATION )


	#add right click menu to turn on the gimbal control
	gimbalIdx = Trigger( headControl ).connect( headGimbal )
	Trigger.CreateMenu( headControl,
		                "toggle gimbal control",
		                "string $shapes[] = `listRelatives -f -s %%%d`;\nint $vis = `getAttr ( $shapes[0] +\".v\" )`;\nfor( $s in $shapes ) setAttr ( $s +\".v\" ) (!$vis);" % gimbalIdx )


	#turn unwanted transforms off, so that they are locked, and no longer keyable, and set rotation orders
	gimbalShapes = listRelatives( headGimbal, s=True )
	for s in gimbalShapes:
		s.v.set( 0 )

	headControl.ro.set( 3 )
	headGimbal.ro.set( 3 )

	attrState( (headControl, headGimbal), 't', *LOCK_HIDE )


	return [ headControl, headGimbal ] + neckControls


class Hand(RigPart):
	__version__ = 0
	SKELETON_PRIM_ASSOC = ( skeletonBuilderCore.Hand, )
	CONTROL_NAMES = 'control', 'poses', 'qss'

	ADD_CONTROLS_TO_QSS = False

	@classmethod
	def _build( cls, skeletonPart, taper=0.8, **kw ):
		worldPart = WorldPart.Create()
		qss = worldPart.qss

		controls = hand( skeletonPart.bases, taper=taper, **kw )
		for c, n in zip( controls, cls.CONTROL_NAMES ):
			qss.add( c )

		return controls


FINGER_IDX_NAMES = skeletonBuilderCore.FINGER_IDX_NAMES

def hand( bases, wrist=None, num=0, names=FINGER_IDX_NAMES, taper=0.8, **kw ):
	if wrist is None:
		wrist = bases[ 0 ].getParent()

	scale = kw[ 'scale' ]

	idx = kw[ 'idx' ]
	parity = Parity( idx )
	colour = ColourDesc( 'orange' )

	suffix = parity.asName()
	parityMult = parity.asMultiplier()

	worldPart = WorldPart.Create()
	partsControl = worldPart.parts
	partParent, rootControl = getParentAndRootControl( bases[ 0 ] )


	minSlider = -90
	maxSlider = 90
	minFingerRot = -45  #rotation at minimum slider value
	maxFingerRot = 90  #rotation at maxiumum slider value


	#get the bounds of the geo skinned to the hand and use it to determine default placement of the slider control
	bounds = utils.getJointBounds( [ wrist ] + bases )
	backwardAxis = utils.getObjectAxisInDirection( wrist, Vector( (0, 0, -1) ) )
	dist = bounds[ not backwardAxis.isNegative() ][ backwardAxis % 3 ]


	#build the main hand group, and the slider control for the fingers
	handSliders = buildControl( "hand_sliders"+ suffix, wrist, shapeDesc=ShapeDesc( None, 'pointer', backwardAxis ), constrain=False, colour=colour, offset=(0, 0, dist*1.25), scale=scale*1.25 )
	poseCurve = buildControl( "hand_poses"+ suffix, handSliders, shapeDesc=ShapeDesc( None, 'starCircle', AX_Y ), oriented=False, constrain=False, colour=colour, parent=handSliders, scale=scale )
	handQss = sets( empty=True, text="gCharacterSet", n="hand_ctrls"+ suffix )
	handGrp = handSliders.getParent()

	poseCurveTrigger = Trigger( poseCurve )
	poseCurve.v.set( False )

	#constrain the group to the wrist
	parentConstraint( wrist, handGrp )
	parent( handGrp, partsControl )

	attrState( (handSliders, poseCurve), ('t', 'r'), *LOCK_HIDE )

	poseCurve.addAttr( 'controlObject', at='message' )  #build the attribute so posesToSliders knows where to write the pose sliders to when poses are rebuilt
	connectAttr( handSliders.message, poseCurve.controlObject )


	#now start building the controls
	allCtrls = [ handSliders, poseCurve, handQss ]
	allSpaces = []
	allConstraints = []
	baseControls = []
	baseSpaces = []
	slider_curl = []
	slider_bend = []

	for n, base in enumerate( bases ):
		#discover the list of joints under the current base
		name = names[ n ]

		if not num: num = 100

		joints = [ base ]
		for i in range( num ):
			children = listRelatives( joints[ -1 ], type='joint' )
			if not children: break
			joints.append( children[ 0 ] )

		num = len( joints )

		#build the controls
		ctrls = []
		for i, j in enumerate( joints ):
			ctrlScale = scale * (taper ** i)

			c = buildControl( "%sControl_%d%s" % (name, i, suffix), j, shapeDesc=ShapeDesc( 'sphere', 'ring', axis=AIM_AXIS ), colour=colour, parent=handGrp, scale=ctrlScale, qss=handQss )
			c.v = False  #hidden by default
			cParent = c.getParent()
			if i:
				parent( cParent, ctrls[ -1 ] )

			ctrls.append( c )

			poseCurveTrigger.connect( c.getParent() )

		allCtrls += ctrls


		###------
		###CURL SLIDERS
		###------
		driverAttr = name +"Curl"

		handSliders.addAttr( driverAttr, k=True, at='double', min=minSlider, max=maxSlider, dv=0 )
		driverAttr = handSliders.attr( driverAttr )
		driverAttr.setKeyable( True )
		spaces = [ c.getParent() for c in ctrls ]
		for s in spaces:
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( maxSlider )
		for s in spaces:
			rotate( s, ( 0, maxFingerRot * parityMult, 0), r=True, os=True )
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( minSlider )
		for s in spaces:
			rotate( s, ( 0, minFingerRot * parityMult, 0), r=True, os=True )
			setDrivenKeyframe( s.r, cd=driverAttr )

		driverAttr.set( 0 )
		slider_curl.append( driverAttr.shortName() )


		###------
		###BEND SLIDERS
		###------
		driverAttr = name +"Bend"

		handSliders.addAttr( driverAttr, k=True, at='double', min=minSlider, max=maxSlider, dv=0 )
		driverAttr = handSliders.attr( driverAttr )
		driverAttr.setKeyable( True )

		baseCtrlSpace = spaces[ 0 ]
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( maxSlider )
		rotate( baseCtrlSpace, ( 0, maxFingerRot * parityMult, 0), r=True, os=True )
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( minSlider )
		rotate( baseCtrlSpace, ( 0, minFingerRot * parityMult, 0), r=True, os=True )
		setDrivenKeyframe( baseCtrlSpace.r, cd=driverAttr )

		driverAttr.set( 0 )
		slider_bend.append( driverAttr.shortName() )


	#reorder the finger sliders
	attrOrder = slider_curl + slider_bend
	mel.zooReorderAttrs( str( handSliders ), attrOrder )


	#add toggle finger control vis
	handSlidersTrigger = Trigger( handSliders )
	qssIdx = handSlidersTrigger.connect( handQss )
	handSlidersTrigger.createMenu( 'Toggle Finger Controls',
	                               'string $objs[] = `sets -q %%%d`;\nint $vis = !getAttr( $objs[0] +".v" );\nfor( $o in $objs ) setAttr( $o +".v", $vis );' % qssIdx )


	return allCtrls


#now populate the
_rigMethodDict = {}
for cls in RigPart.GetSubclasses():
	try:
		assoc = cls.SKELETON_PRIM_ASSOC
	except AttributeError: continue

	if assoc is None:
		continue

	for partCls in assoc:
		try:
			_rigMethodDict[ partCls ].append( cls )
		except KeyError:
			_rigMethodDict[ partCls ] = [ cls ]

for partCls, rigTypes in _rigMethodDict.iteritems():
	partCls.RigTypes = rigTypes


#end
