from pymel.core import *
from names import Parity, Name, camelCaseToNice
from vectors import Vector

import exceptionHandlers
import filesystem
import inspect
import control
import utils
import pymel.core as pymelCore

iterBy = filesystem.iterBy

TOOL_NAME = 'skeletonBuilder'


#now do maya imports and maya specific assignments
import api
import maya.cmds as cmd
from rigger import utils

from utils import ENGINE_FWD, ENGINE_UP, ENGINE_SIDE
from utils import MAYA_SIDE, MAYA_FWD, MAYA_UP
from utils import Axis, resetSkinCluster
from pymel.core.nodetypes import Joint

#import wingdbstub

mel = api.mel

AXES = Axis.BASE_AXES


#these are the symbols to use as standard rotation axes on bones...
BONE_AIM_AXIS = ENGINE_FWD			#this is the axis the joint should bank around, in general the axis the "aims" at the child joint
BONE_ROTATE_AXIS = ENGINE_SIDE		#this is the axis of "primary rotation" for the joint.  for example, the elbow would rotate primarily in this axis, as would knees and fingers

getLocalAxisInDirection = utils.getLocalAxisInDirection
getPlaneNormalForObjects = utils.getPlaneNormalForObjects

CHANNELS = ('x', 'y', 'z')
TYPICAL_HEIGHT = 70  #maya units


#odd indices are left sided, even are right sided
FINGER_IDX_NAMES = ('thumb', 'index', 'mid', 'ring', 'pinky', 'sixth' 'seventh', 'eighth')


def getDefaultScale():
	def isVisible( node ):
		if not node.v:
			return False

		for p in iterParents( node ):
			if not p.v: return False

		return True

	visibleMeshes = [ m for m in ls( type='mesh' ) if isVisible( m ) ]
	if not visibleMeshes:
		return TYPICAL_HEIGHT

	visibleSkinnedMeshes = [ m for m in visibleMeshes if mel.findRelatedSkinCluster( m ) ]
	if not visibleSkinnedMeshes:
		return TYPICAL_HEIGHT

	return utils.getObjsScale( visibleSkinnedMeshes )


def iterParents( obj ):
	parent = obj.getParent()
	while parent is not None:
		yield parent
		parent = parent.getParent()


def sortByHierarchy( objs ):
	sortedObjs = []
	for o in objs:
		pCount = len( o.getAllParents() )
		sortedObjs.append( (pCount, o) )

	sortedObjs.sort()

	return [ o[ 1 ] for o in sortedObjs ]


def d_restoreLocksAndNames(f):
	'''
	this decorator is for the alignment functions - it basically takes care of ensuring the children
	are unparented before alignment happens, re-parented after the fact, channel unlocking and re-locking,
	freezing transforms etc...
	'''
	def newF( item, *args, **kwargs ):
		if not isinstance( item, PyNode ):
			print 'AAARRRGGGHHHH - d_restorLocksAndNames'
			item = PyNode( item )

		attrs = ('t', 'r')

		#unparent and children in place, and store the original name, and lock
		#states of attributes - we need to unlock attributes as this item will
		#most likely change its orientation
		children = listRelatives( item, typ='transform' )
		childrenPreStates = {}
		for child in [ item ] + children:
			lockStates = []
			for a in attrs:
				for c in CHANNELS:
					attr = getattr( child, a+c )
					lockStates.append( (attr, attr.isLocked()) )
					attr.setLocked( False )

			originalChildName = str( child )
			if child != item:
				pymelCore.parent( child, world=True )

			childrenPreStates[ child ] = originalChildName, lockStates

		f( item, children=children, *args, **kwargs )
		try: makeIdentity( item, a=True, t=True, r=True )
		except:
			#import exceptionHandlers, sys
			#exceptionHandlers.exceptionHandler( *sys.exc_info() )
			#raise
			print 'still excepting'
			pass

		#now re-parent children
		for child, (originalName, lockStates) in childrenPreStates.iteritems():
			if child != item:
				pymelCore.parent( child, item )
				child.rename( originalName )

			for attr, lockState in lockStates:
				attr.setLocked( lockState )

	newF.__name__ = f.__name__
	newF.__doc__ = f.__doc__

	return newF


@d_restoreLocksAndNames
def autoAlignItem( item, invertAimAndUp=False, upVector=BONE_ROTATE_AXIS, worldUpVector=MAYA_SIDE, worldUpObject='', upType='vector', children=None, debug=False ):
	'''
	for cases where there is no strong preference about how the item is aligned, this function will determine the best course of action
	'''
	#if there is only one child, aim the x-axis at said child, and aim the z-axis toward scene-up
	### WARNING :: STILL NEED TO DELA WITH CASE WHERE JOINT IS CLOSE TO AIMING AT SCENE UP
	invertMult = -1 if invertAimAndUp else 1
	if len( children ) == 1:
		kw = { 'aimVector': BONE_AIM_AXIS * invertMult,
		       'upVector': upVector * invertMult,
		       'worldUpVector': worldUpVector,
		       'worldUpType': upType }

		if worldUpObject:
			kw[ 'worldUpObject' ] = worldUpObject

		c = aimConstraint( children[ 0 ], item, **kw )
		if not debug: delete( c )
	else:
		for a in [ 'jo', 'r' ]:
			for c in CHANNELS:
				getattr( item, a + c ).set( 0 )


@d_restoreLocksAndNames
def alignAimAtItem( item, aimAtItem, invertAimAndUp=False, upVector=BONE_ROTATE_AXIS, worldUpVector=MAYA_SIDE, worldUpObject='', upType='vector', children=None, debug=False ):
	'''
	aims the item at a specific transform in the scene.  the aim axis is always BONE_AIM_AXIS, but the up axis can be set to whatever is required
	'''
	invertMult = -1 if invertAimAndUp else 1
	kw = { 'aimVector': BONE_AIM_AXIS * invertMult,
           'upVector': upVector * invertMult,
           'worldUpVector': worldUpVector,
           'worldUpType': upType }

	if worldUpObject:
		kw[ 'worldUpObject' ] = worldUpObject

	c = aimConstraint( aimAtItem, item, **kw )
	if debug: raise Exception
	if not debug: delete( c )


@d_restoreLocksAndNames
def alignItemToWorld( item, children=None, skipX=False, skipY=False, skipZ=False ):
	'''
	aligns the item to world space axes, optionally skipping individual axes
	'''
	rotate( item, -90, -90, 0, a=True, ws=True )

	if skipX: rotate( item, 0, 0, 0, a=True, os=True, rotateX=True )
	if skipY: rotate( item, 0, 0, 0, a=True, os=True, rotateY=True )
	if skipZ: rotate( item, 0, 0, 0, a=True, os=True, rotateZ=True )


@d_restoreLocksAndNames
def alignItemToLocal( item, children=None, skipX=False, skipY=False, skipZ=False ):
	'''
	aligns the item to local space axes, optionally skipping individual axes
	'''
	for skip, axis in zip( (skipX, skipY, skipZ), CHANNELS ):
		if skipX:
			getattr( item, 'r'+ axis ).set( 0 )
			getattr( item, 'jo'+ axis ).set( 0 )


@d_restoreLocksAndNames
def alignPreserve( item, children=None ):
	pass


class SkeletonError(Exception): pass
class NotFinalizedError(SkeletonError): pass
class SceneNotSavedError(SkeletonError): pass


class SkeletonPart(filesystem.trackableClassFactory( list )):

	#parity is "sided-ness" of the part.  Ie if the part can exist on the left OR right side of the skeleton, the part has parity.  the spine
	#is an example of a part that has no parity, as is the head
	HAS_PARITY = True

	PART_SCALE = TYPICAL_HEIGHT

	ALL_PARTS = None
	RigTypes = ()

	def __init__( self, *a ):
		list.__init__( self, *a )
		self.verifyPart()
	def __repr__( self ):
		return '%s_%d( %s )' % (self.__class__.__name__, self.getIdx(), list.__repr__( self ))
	def __hash__( self ):
		return hash( self.base )
	def __eq__( self, other ):
		return self.base == other.base
	def __neq__( self, other ):
		return not self == other
	def verifyPart( self ): pass
	@property
	def base( self ):
		return self[ 0 ]
	@property
	def bases( self ):
		return [ self.base ]
	@property
	def end( self ):
		return self[ -1 ]
	def hasParity( self ):
		return self.HAS_PARITY
	@classmethod
	def ParityMultiplier( cls, idx ):
		return Parity( idx ).asMultiplier()
	@classmethod
	def GetPartName( cls ):
		'''
		can be used to get a "nice" name for the part class
		'''
		return camelCaseToNice( cls.__name__ )
	def getPartName( self ):
		'''
		returns a "nice" name for the part instance
		'''
		parityStr = 'Left ' if self.getParity() == Parity.LEFT else 'Right '
		if not self.hasParity():
			parityStr = ''

		return '%s%s %d' % (parityStr, self.GetPartName(), self.getIdx())
	def getIdx( self ):
		'''
		returns the index of the part - all parts have a unique index associated
		with them
		'''
		return self.getBuildKwargs()[ 'idx' ]
	def getBuildScale( self ):
		return self.getBuildKwargs().get( 'partScale', self.PART_SCALE )
	def getParity( self ):
		return Parity( self.getIdx() )
	def verifyPart( self ):
		'''
		this is merely a "hook" that can be used to fix anything up should the way
		skeleton parts are defined change
		'''
		baseItem = self[ 0 ]
		for n, item in enumerate( self ):
			item.segmentScaleCompensate.set( False )
			if not item.hasAttr( '_skeletonPartName' ):
				item.addAttr( '_skeletonPartName', dt='string' )

			if not item.hasAttr( '_skeletonPartArgs' ):
				item.addAttr( '_skeletonPartArgs', dt='string' )

			if n:
				if not baseItem._skeletonPartName.isConnectedTo( item._skeletonPartName ):
					baseItem._skeletonPartName.connect( item._skeletonPartName, f=True )

				if not baseItem._skeletonPartArgs.isConnectedTo( item._skeletonPartArgs ):
					baseItem._skeletonPartArgs.connect( item._skeletonPartArgs, f=True )
	def sort( self ):
		'''
		sorts the part by hierarchy
		'''
		thisSorted = sortByHierarchy( self )
		try:
			while True: self.pop()
		except IndexError: pass

		for item in thisSorted: self.append( item )
	def getBuildKwargs( self ):
		'''
		returns the kwarg dict that was used to create this particular part
		'''
		for base in self.bases:
			if base.hasAttr( '_skeletonPartArgs' ):
				argStr = base._skeletonPartArgs.get()
				kw = eval( argStr )

				return kw
	def getRigKwargs( self ):
		'''
		returns the kwarg dict that should be used to create the rig for this part
		'''
		try:
			argStr = self[ 0 ]._skeletonRigArgs.get()
		except AttributeError:
			return {}

		if argStr is None:
			return {}

		kw = eval( argStr )

		return kw
	def setRigKwargs( self, kwargs ):
		if not self.base.hasAttr( '_skeletonRigArgs' ):
			argStr = self.base.addAttr( '_skeletonRigArgs', dt='string' )

		self.base._skeletonRigArgs.set( str( kwargs ) )
	def updateRigKwargs( self, **kw ):
		currentKwargs = self.getRigKwargs()
		currentKwargs.update( kw )
		self.setRigKwargs( currentKwargs )
	def getActualScale( self ):
		return utils.getObjsScale( self )
	def getParent( self ):
		'''
		returns the parent of the part - the actual node name.  use getParentPart
		to query the part this part is parented to (if any)
		'''
		return self.base.getParent()
	def setParent( self, parent ):
		'''
		parents the part to a new object in the scene - if parent is None, the
		part is parented to the world
		'''
		if parent is None:
			pymelCore.parent( self.base, w=True )
		else:
			pymelCore.parent( self.base, parent )
	def getParentPart( self ):
		'''
		returns the part this part is parented to - if any.  if this part isn't
		parented to a part, None is returned.

		NOTE: this part may be parented to something that isn't a member of a
		part, so a result of None from this query doesn't mean the part has no
		parent, just that its parent isn't a member of a part
		'''
		parent = self.getParent()
		if parent is None:
			return None

		return self.InitFromItem( parent )
	@classmethod
	def GetDefaultBuildKwargs( cls ):
		'''
		returns a list of 2 tuples: argName, defaultValue
		'''
		buildFunc = getattr( cls, '_build', None )
		spec = inspect.getargspec( buildFunc )

		argNames = spec[ 0 ][ 1: ]  #strip the first item because the _build method is a bound method - so the first item is always the class arg (usually called cls)
		defaults = spec[ 3 ]

		if defaults is None:
			defaults = []

		assert len( argNames ) == len( defaults ), "%s has no default value set for one of its args - this is not allowed" % cls

		kwargs = []
		for argName, default in zip( argNames, defaults ):
			kwargs.append( (argName, default) )

		return kwargs
	@classmethod
	def InitFromItem( cls, item ):
		'''
		will instantiate a SkeletonPart from an item of a previously built part.
		if an item is given that isn't involved in a part None is returned
		'''

		try:
			items = cls.GetItems( item )
		except AssertionError:
			return None

		partClassName = items[ 0 ]._skeletonPartName.get()
		partClass = None
		for c in SkeletonPart.GetSubclasses():
			if c.__name__ == partClassName:
				partClass = c
				break

		return partClass( items )
	@classmethod
	def GetItems( cls, item ):
		'''
		given the item of a part, this will return a list of all the other
		joints of that part
		'''

		if not isinstance( item, PyNode ):
			print 'AAARRRGGGHHHH - GetItems'
			item = PyNode( item )

		baseItem = None
		if item.hasAttr( '_skeletonPart' ):
			baseItem = listConnections( item._skeletonPart, t='joint', source=True )[ 0 ]
		elif item.hasAttr( '_skeletonPartName' ):
			baseItem = item
		else:
			#if neither of the above are the case, then walk up the chain until one of the above criteria are met
			for p in iterParents( item ):
				if p.hasAttr( '_skeletonPart' ):
					baseItem = p._skeletonPart.listConnections( t='joint', source=True )[ 0 ]
					break
				elif p.hasAttr( '_skeletonPartName' ):
					baseItem = p
					break

			assert baseItem is not None, "Cannot find a SkeletonPart anywhere in the hierarchy for %s" % item

		cons = listConnections( baseItem.message, t='joint', destination=True )
		cons = [ baseItem ] + sortByHierarchy( cons )

		return cons
	@classmethod
	def Create( cls, partClass, *a, **kw ):
		'''
		this is the primary way to create a skeleton part.  build functions are
		defined outside the class and looked up by name.  this method ensures
		that all build methods (a build method is only required to return the
		list of nodes that define it) register nodes properly, and encode data
		about how the part was built into the part so that the part can be
		re-instantiated at a later date
		'''
		if isinstance( partClass, basestring ):
			partClass = globals().get( partClass.capitalize(), None )

		partScale = kw.setdefault( 'partScale', cls.PART_SCALE )

		buildFunc = getattr( partClass, '_build', None )
		if buildFunc is None:
			raise SkeletonError( 'no such part type' )


		#grab any kwargs out of the dict that shouldn't be there
		visualize = kw.pop( 'visualize', True )


		#now turn the args passed in are a single kwargs dict
		argNames, vArgs, vKwargs, defaults = inspect.getargspec( buildFunc )
		if defaults is None:
			defaults = []

		argNames = argNames[ 1: ]  #strip the first arg - which is the class arg (usually cls)
		if vArgs is not None:
			raise SkeletonError( 'cannot have *a in skeleton build functions' )

		for argName, value in zip( argNames, a ):
			kw[ argName ] = value

		#now explicitly add the defaults
		for argName, default in zip( argNames, defaults ):
			kw.setdefault( argName, default )


		#generate an index for the part - each part must have a unique index
		idx = partClass.GetUniqueIdx()
		kw[ 'idx' ] = idx


		#run the build function
		items = buildFunc( **kw )

		newPart = partClass( items )
		baseItem = newPart.base


		#convert any pymel instances in teh kw dict to strings so they serialize properly...
		kw.pop( 'parent', None )
		newKw = {}
		for k, v in kw.iteritems():
			if isinstance( v, PyNode ): newKw[ k ] = str( v )
			else: newKw[ k ] = v

		baseItem._skeletonPartName.set( partClass.__name__ )
		baseItem._skeletonPartArgs.set( str( newKw ) )

		for i in items[ 1: ]:
			i.addAttr( '_skeletonPart', at='message' )
			baseItem.message.connect( i._skeletonPart, f=True )

		newPart._align( _initialAlign=True )


		#turn of segment scale compensate - not sure why it defaults to on.
		for item in items:
			item.segmentScaleCompensate = False


		#are we doing visualizations?
		if visualize:
			newPart.visualize()

		newPart.sort()

		return newPart
	@classmethod
	def IterAllParts( cls, partClass=ALL_PARTS ):
		'''
		iterates over all SkeletonParts in the current scene
		'''

		#make sure the part is a valid part type
		if partClass is not cls.ALL_PARTS:
			if isinstance( partClass, basestring ):
				partClass = globals().get( partClass.capitalize(), None )

			buildFunc = getattr( partClass, '_build', None )
			if buildFunc is None:
				raise SkeletonError( 'no such part type' )

		partName = partClass.__name__ if partClass else ''
		for attrPath in ls( '*._skeletonPartName', r=True ):
			if partClass is cls.ALL_PARTS or attrPath.get() == partName:
				j = attrPath.node()
				if j.hasAttr( '_skeletonPart' ): continue  #skip items that have this attribute - they're leaf items, we only want the base item
				yield cls.InitFromItem( j )
	@classmethod
	def IterAllPartsInOrder( cls, partClass=ALL_PARTS ):
		allParts = [ part for part in cls.IterAllParts( partClass ) ]
		allParts = sortPartsByHierarchy( allParts )

		return iter( allParts )
	@classmethod
	def FindParts( cls, partClass, withKwargs=None ):
		'''
		given a part name and a kwargs dict (may be a partial dict) this method
		will return all matching parts in the current scene.  so if you wanted to
		get a list of all the finger parts with 3 joints you would do:

		SkeletonPart.FindParts( finger, { 'fingerJointCount': 3 } )
		'''
		withKwargs = withKwargs or {}

		matches = []
		for part in cls.IterAllParts( partClass ):
			partKwargs = part.getBuildKwargs()
			match = True
			for argName, argValue in withKwargs.iteritems():
				try:
					if partKwargs[ argName ] != argValue:
						match = False
						break
				except KeyError: continue

			if match: matches.append( part )

		return matches
	def getChildParts( self ):
		'''
		returns a list of all the parts parented directly to a member of this part
		'''

		#first get a list of all the joints directly parented to a memeber of this part
		allChildren = listRelatives( self, typ='transform' )
		if not allChildren:
			return

		#subtract all the items of this part from the children - to give us all the children of this part that don't belong to this part
		allChildren = set( allChildren ).difference( set( self ) )

		return getPartsFromObjects( allChildren )
	def getOrphanJoints( self ):
		'''
		orphan joints are joints parented to a member of this part, but don't
		belong to a part.  orphan joints get aligned using the same alignment
		method used by their parent part
		'''

		#first get a list of all the joints directly parented to a memeber of this part
		allChildren = listRelatives( self, typ='joint' )
		if not allChildren:
			return []

		childPartItems = []
		for part in self.getChildParts():
			childPartItems += list( part )

		jointsInSomePart = set( childPartItems + self )
		orphanChildren = set( allChildren ).difference( jointsInSomePart )
		orphanChildren = list( orphanChildren )

		childrenOfChildren = []
		for i in orphanChildren:
			iChildren = listRelatives( i, typ='joint' )
			if not iChildren: continue
			for c in iChildren:
				if c.hasAttr( '_skeletonPart' ): continue
				childrenOfChildren.append( c )

		return orphanChildren + childrenOfChildren
	def selfAndOrphans( self ):
		return self + self.getOrphanJoints()


def d_wrapAlign( f ):
	def new( self, *a, **kw ):
		#for all skin clusters iterate through all their joints and detach them
		#so we can freeze transforms - make sure to store initial state so we can
		#restore connections afterward
		skinClustersConnections = []
		skinClusters = ls( typ='skinCluster' )
		for c in skinClusters:
			cons = c.matrix.listConnections( destination=False, plugs=True, connections=True )
			if cons is None:
				print 'WARNING - no connections found on the skinCluster %s' % str( c )

			for dest, src in cons:
				#remove the actual connection...
				delete( dest, icn=True )

			skinClustersConnections += cons


		isRecursed = kw.pop( 'recursed', False )

		if not isRecursed:
			#store any driving or driven part, so when we're done we can restore the relationships
			driver = self.getDriver()
			drivenParts = self.getDriven()

			#break driving relationships
			self.breakDriver()
			for part in drivenParts:
				part.breakDriver()

		f( self, *a, **kw )
		if not isRecursed:
			#align all up/downstream parts
			if driver: driver._align()
			for part in drivenParts:
				part._align()

			#finally restore any up/downstream relationships if any...
			if driver: driver.driveOtherPart( self )
			for part in drivenParts:
				try: self.driveOtherPart( part )
				except AssertionError: continue  #the parts may have changed size since the initial connection, so if they differ in size just ignore the assertion...

		#re-connect all joints to skinClusters, and reset them
		for dest, src in skinClustersConnections:
			src >> dest

		for skinCluster in skinClusters:
			resetSkinCluster( skinCluster )

	new.__name__ = f.__name__
	new.__doc__ = f.__doc__

	return new



class BaseSkeletonPart(SkeletonPart):

	AVAILABLE_IN_UI = True  #determines whether this part should appear in the UI or not...

	@d_wrapAlign
	def align( self, _initialAlign=False ):
		self._align( _initialAlign )
	def unalign( self ):
		self.breakDriver()
		for p in self.getDriven():
			p.breakDriver()

		def doUnalign( item, *a, **kw ):
			control.attrState( item, 'r', *control.NORMAL )
			rot = xform( item, q=True, ws=True, ro=True )
			item.jo.set( (0, 0, 0) )
			rotate( item, rot, a=True, ws=True )

		for item in self.selfAndOrphans():
			doUnalign( item )
	@classmethod
	def IterAllParts( cls ):
		return SkeletonPart.IterAllParts( cls )
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
	def Create( cls, *a, **kw ):
		return SkeletonPart.Create( cls, *a, **kw )
	@classmethod
	def GetRigMethod( cls, methodName ):
		for method in cls.RigTypes:
			if method.__name__ == methodName:
				return method

		return None
	def getParityMultiplier( self ):
		return self.getParity().asMultiplier()
	def _align( self, _initialAlign=False ):
		for item in self.selfAndOrphans():
			autoAlignItem( item )
	def visualize( self ):
		'''
		can be used to create visualization for item orientation or whatever else.

		NOTE: visualizations should never add joints, but can use any other node
		machinery available.
		'''
		pass
	def unvisualize( self ):
		'''
		removes any visualization on the part
		'''
		for i in self.selfAndOrphans():
			children = listRelatives( i )
			for c in children:
				try:
					if isinstance( c, Joint ): continue
					delete( c )
				#this can happen if the deletion of a previous child causes some other child to also be deleted - its a fringe case but possible (i think)
				except TypeError: continue
	def driveOtherPart( self, otherPart ):
		'''
		drives the specified part with this part - meaning that all translations
		and rotations of items in this part will drive the corresponding items in
		the other part.  attributes are hooked up for the most part using direct
		connections, but some attributes are driven via an expression
		'''
		assert isinstance( otherPart, BaseSkeletonPart )  #this is just for WING...
		assert type( self ) is type( otherPart ), "Sorry, you cannot connect different types together"
		assert len( self ) == len( otherPart ), "Sorry, seems the two parts are different sizes (%d, %d) - not sure what to do" % (len( self ), len( otherPart ))

		attrs = 't', 'r'

		#first unlock trans and rot channels
		control.attrState( otherPart, [ 't', 'r' ], False )

		#self.unalign()
		#otherPart.unalign()

		#if the parts have parity AND differing parities, we may have to deal with mirroring differently
		if self.hasParity() and self.getParity() != otherPart.getParity():
			for thisItem, otherItem in zip( self, otherPart ):
				#translation will be inverted on all channels unless the parent of the items are the same
				expressionLines = []
				if thisItem.getParent() == otherItem.getParent():
					upAxis = getLocalAxisInDirection( thisItem, MAYA_UP ).asCleanName()
					fwdAxis = getLocalAxisInDirection( thisItem, MAYA_FWD ).asCleanName()
					sideAxis = getLocalAxisInDirection( thisItem, MAYA_SIDE ).asCleanName()

					expressionLines.append( '%s.t%s = -1 * %s.t%s;' % (otherItem, sideAxis, thisItem, sideAxis) )
					connectAttr( thisItem.attr( 't'+ upAxis ), otherItem.attr( 't'+ upAxis ), f=True )
					connectAttr( thisItem.attr( 't'+ fwdAxis ), otherItem.attr( 't'+ fwdAxis ), f=True )
				else:
					for c in CHANNELS:
						expressionLines.append( '%s.t%s = -1 * %s.t%s;' % (otherItem, c, thisItem, c) )

				expression( string='\n'.join( expressionLines ) )

				#rotation values should match
				for c in CHANNELS:
					connectAttr( thisItem.attr( 'r'+ c ), otherItem.attr( 'r'+ c ), f=True )

		#otherwise setting up the driven relationship is straight up attribute connections...
		else:
			for thisItem, otherItem in zip( self, otherPart ):
				for attr in attrs:
					for c in CHANNELS:
						connectAttr( thisItem.attr( attr + c ), otherItem.attr( attr + c ), f=True )
	def breakDriver( self ):
		attrs = 't', 'r'

		for item in self:
			for a in attrs:
				for c in CHANNELS:
					attr = item.attr( a + c )
					isLocked = attr.isLocked()
					attr.setLocked( False )  #need to make sure attributes are unlocked before trying to break a connection - regardless of whether the attribute is the source or destination...  8-o
					delete( attr, inputConnectionsAndNodes=True )
					if isLocked: attr.setLocked( True )
	def getDriver( self ):
		'''
		returns the part driving this part if any, otherwise None is returned
		'''
		attrs = 't', 'r'

		for item in self:
			for attr in attrs:
				for c in CHANNELS:
					cons = listConnections( item.attr( attr + c ), destination=False, skipConversionNodes=True, t='joint' )
					if cons:
						for c in cons:
							part = SkeletonPart.InitFromItem( c )
							if part: return part
	def getDriven( self ):
		'''
		returns a list of driven parts if any, otherwise an empty list is returned
		'''
		attrs = 't', 'r'

		allOutConnections = []
		for item in self:
			for attr in attrs:
				for c in CHANNELS:
					allOutConnections += listConnections( item.attr( attr + c ), source=False, skipConversionNodes=True, t='joint' ) or []

		if allOutConnections:
			allOutConnections = filesystem.removeDupes( allOutConnections )
			return getPartsFromObjects( allOutConnections )

		return []
	def unfinalize( self ):
		control.attrState( self.selfAndOrphans(), [ 't', 'r' ], *control.NO_KEY )
	def generateItemHash( self, item ):
		#create a hash for the position and orientation of the joint so we can ensure the state is still the same at a later date
		tHashAccum = 0
		joHashAccum = 0
		tChanValues = []
		joChanValues = []
		for c in CHANNELS:
			#we hash the rounded string of the float to eliminate floating point error
			t = item.attr( 't'+ c ).get()
			jo = item.attr( 'jo'+ c ).get()
			val = '%0.4f %0.4f' % (t, jo)

			tHashAccum += hash( val )

			tChanValues.append( t )
			joChanValues.append( jo )

		iParent = str( item.getParent() )

		return iParent, tHashAccum, tChanValues, joChanValues
	def _finalize( self ):
		'''
		performs some finalization on the skeleton - ensures everything is aligned,
		and then stores a has of the orientations into the skeleton so that we can
		later compare the skeleton orientation with the stored state
		'''

		#early out if finalization is valid
		if self.compareAgainstHash():
			return

		#finalized skeleton's aren't allowed to have a driven relationship with any other part, so break any relationship before anything else
		self.breakDriver()

		#make sure the part has been aligned
		self.align()

		#remove any visualizations
		self.unvisualize()

		#unlock all channels and make keyable - we cannot change lock/keyability
		#state once the skeleton is referenced into the rig, and we need them to
		#be in such a state to build the rig
		control.attrState( self.selfAndOrphans(), [ 't', 'r' ], False, True, True )

		#create a hash for the position and orientation of the joint so we can ensure the state is still the same at a later date
		for i in self.selfAndOrphans():
			if not i.hasAttr( '_skeletonFinalizeHash' ):
				i.addAttr( '_skeletonFinalizeHash', dt='string' )

			i._skeletonFinalizeHash.set( str( self.generateItemHash( i ) ) )
	def compareAgainstHash( self ):
		'''
		compares the current orientation of the partto the stored state hash when
		the part was last finalized.  if the part has differing

		a bool indicating whether the current state matches the stored finalization
		state is returned
		'''

		#create a hash for the position and orientation of the joint so we can ensure the state is still the same at a later date
		for i in self.selfAndOrphans():
			if not i.hasAttr( '_skeletonFinalizeHash' ):
				print 'no finalization hash found on %s' % i
				return False

			iParent, xformHash, xxa, yya = self.generateItemHash( i )
			try: storedParent, stored_xHash, xxb, yyb = eval( i._skeletonFinalizeHash.get() )
			except:
				print 'stored hash differs from the current hashing routine - please re-finalize'
				return False

			#if the stored parent is different from the current parent, there may only be a namespace conflict - so strip namespace prefixes and redo the comparison
			if iParent != storedParent:
				if Name( iParent ).strip() != Name( storedParent ).strip():
					print 'parenting mismatch on %s since finalization (%s vs %s)' % (i, iParent, storedParent)
					return False

			def doubleCheckValues( valuesA, valuesB ):
				for va, vb in zip( valuesA, valuesB ):
					va, vb = float( va ), float( vb )
					if va - vb > 1e-6: return False
				return True

			if xformHash != stored_xHash:
				#so did we really fail?  sometimes 0 gets stored as -0 or whatever, so make sure the values are actually different
				if not doubleCheckValues( xxa, xxb ):
					print 'the translation on %s changed since finalization (%s vs %s)' % (i, xxa, xxb)
					return False

				if not doubleCheckValues( yya, yyb ):
					print 'joint orienatation on %s changed since finalization (%s vs %s)' % (i, yya, yyb)
					return False

		return True
	def rebuild( self, **newBuildKwargs ):
		'''
		rebuilds the part by storing all the positions of the existing members,
		re-creating the part with optionally changed build args, positioning
		re-created joints as best as possible, and re-parenting child parts
		'''

		#grab the build kwargs used to create this part, and update it with the new kwargs passed in
		buildKwargs = self.getBuildKwargs()
		buildKwargs.update( newBuildKwargs )
		buildKwargs[ 'parent' ] = self.getParent()

		self.sort()
		self.unvisualize()

		posRots = []
		attrs = 't', 'r'
		for item in self:
			pos = xform( item, q=True, ws=True, rp=True )
			rot = xform( item, q=True, ws=True, ro=True )
			posRots.append( (item, pos, rot) )

		childParts = self.getChildParts()
		childParents = []
		childPartDrivers = []
		for part in childParts:
			childParents.append( part.getParent() )
			childPartDrivers.append( part.getDriver() )
			part.breakDriver()
			part.setParent( None )

		orphans = self.getOrphanJoints()
		orphanParents = []
		for orphan in orphans:
			orphanParents.append( orphan.getParent() )
			pymelCore.parent( orphan, w=True )

		delete( self )
		newPart = self.Create( **buildKwargs )
		newPart.sort()

		#clear the list for this item and re-populate it with the items of the new part
		try:
			while True: self.pop()
		except IndexError: pass

		for item in newPart:
			self.append( item )

		oldToNewNameMapping = {}
		for (oldItemName, pos, rot), item in zip( posRots, self ):
			move( item, pos[ 0 ], pos[ 1 ], pos[ 2 ], ws=True, a=True, rpr=True )
			rotate( item, rot[ 0 ], rot[ 1 ], rot[ 2 ], ws=True, a=True )
			oldToNewNameMapping[ oldItemName ] = item

		#reparent child parts
		for childPart, childParent in zip( childParts, childParents ):
			childParent = oldToNewNameMapping.get( childParent, childParent )
			childPart.setParent( childParent )

		#re-setup driver/driven relationships (should be done after re-parenting is done)
		for childPart, childDriver in zip( childParts, childPartDrivers ):
			if childDriver is not None:
				childDriver.driveOtherPart( childPart )

		#reparent orphans
		for orphan, orphanParent in zip( orphans, orphanParents ):
			orphanParent = oldToNewNameMapping.get( orphanParent, orphanParent )
			pymelCore.parent( orphan, orphanParent )

		self.visualize()
	def rig( self, **kw ):
		rigKw = self.getBuildKwargs()
		rigKw.update( self.getRigKwargs() )
		rigKw.update( kw )
		kw = rigKw

		if kw.get( 'disable', False ):
			print 'Rigging disabled for %s - skipping' % self
			return

		#pop the rig method name out of the kwarg dict, and look it up
		try: rigTypeName = kw.pop( 'rigTypeName', self.RigTypes[ 0 ].__name__ )
		except IndexError:
			print "No rig method defined for %s" % self
			return

		#discover the rigging method - it should be defined in the
		rigType = self.GetRigMethod( rigTypeName )
		if rigType is None:
			print 'ERROR :: there is no such rig method with the name %s' % rigTypeName
			return

		rigType.Create( self, **kw )


def kwargsToOptionStr( kwargDict ):
	toks = []
	for k, v in kwargDict.iteritems():
		if isinstance( v, (list, tuple) ):
			v = ' '.join( v )
		elif isinstance( v, bool ):
			v = int( v )

		toks.append( '-%s %s' % (k, v) )

	return ' '.join( toks )


def createJoint( name ):
	select( cl=True )
	if objExists( name ):
		name = joint( n='%s#' % name )  #maya is awesome.  it doesn't return a fullpath to the newly created node if there is a name clash.  well done!
	else:
		name = joint( n=name )

	return name


def jointSize( jointName, size ):
	setAttr( '%s.radius' % jointName, size )


def getRoot():
	joints = ls( typ='joint' )
	for j in joints:
		if j.hasAttr( TOOL_NAME ):
			return j

	return None


class Root(BaseSkeletonPart):
	'''
	all skeleton's must have a root part
	'''

	HAS_PARITY = False

	@classmethod
	def _build( cls, **kw ):
		idx = kw[ 'idx' ]
		partScale = kw[ 'partScale' ]

		root = createJoint( 'root' )
		move( root, 0, partScale / 1.8, 0, ws=True )
		jointSize( root, 3 )

		#tag the root joint with the tool name only if its the first root created - having multiple roots in a scene/skeleton is entirely valid
		if idx == 0: cmd.addAttr( ln=TOOL_NAME, at='message' )

		#the root can only have a parent if its not the first root created
		if idx:
			root = root.rename( 'root_%d' % idx )
			move( root, 0, 0, -partScale / 2, r=True )

		return [ root ]
	def _align( self, _initialAlign=False ):
		for i in self.selfAndOrphans():
			alignItemToWorld( self[ 0 ] )
	def _finalize( self ):
		#make sure the scale is unlocked on the base joint of the root part...
		control.attrState( self.base, 's', False, False, True )
		super( self.__class__, Root )._finalize( self )


def getParent( parent=None ):
	if parent is None:
		try: return ls( sl=True )[ 0 ]
		except IndexError:
			existingRoot = getRoot()
			return existingRoot or SkeletonPart.Create( root )

	if isinstance( parent, SkeletonPart ):
		return parent.end

	if not isinstance( parent, PyNode ):
		print 'AAARRRGGGGHHHH - getParent'
		parent = PyNode( parent )

	if parent.exists():
		return parent

	return getRoot() or SkeletonPart.Create( root )


class Spine(BaseSkeletonPart):
	'''
	simple, single hierarchy, multi joint spine
	'''

	HAS_PARITY = False

	@classmethod
	def _build( cls, parent=None, count=3, direction='y', **kw ):
		idx = kw[ 'idx' ]
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		directionAxis = utils.Axis.FromName( direction )

		allJoints = []
		prevJoint = str( parent )
		posInc = float( partScale ) / 2 / (count + 2)
		moveList = list( directionAxis.asVector() * posInc )
		for n in range( count ):
			j = createJoint( 'spine%s%d' % ('' if idx == 0 else '%d_' % idx, n+1) )
			pymelCore.parent( j, prevJoint, relative=True )
			move( j, r=True, ws=True, *moveList )
			allJoints.append( j )
			prevJoint = j

		jointSize( j, 2 )

		return allJoints
	def _align( self, _initialAlign=False ):
		for n, item in enumerate( self[ :-1 ] ):
			alignAimAtItem( item, self[ n+1 ] )

		#if there is a head part parented to this part, then use it as a look at for the end joint
		childParts = self.getChildParts()
		hasHeadPartAsChild = False
		headPart = None
		for p in childParts:
			if isinstance( p, Head ):
				headPart = p
				break

		if headPart is not None:
			alignAimAtItem( self.end, headPart.base )


class Head(BaseSkeletonPart):
	'''
	this part represents the head and neck.  the number of neck joints created
	is controllable
	'''

	HAS_PARITY = False

	@property
	def head( self ): return self[ -1 ]
	@classmethod
	def _build( cls, parent=None, neckCount=1, **kw ):
		idx = kw[ 'idx' ]
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )

		posInc = partScale / 25.0

		head = createJoint( 'head' )
		if not neckCount:
			pymelCore.parent( head, parent, relative=True )
			return [ head ]

		allJoints = []
		prevJoint = parent

		for n in range( neckCount ):
			j = createJoint( 'neck%d' % (n+1) )
			pymelCore.parent( j, prevJoint, relative=True )
			move( j, 0, posInc, posInc, r=True, ws=True )
			allJoints.append( j )
			prevJoint = j

		#move the first neck joint up a bunch
		move( allJoints[ 0 ], 0, partScale / 10.0, 0, r=True, ws=True )

		#parent the head appropriately
		pymelCore.parent( head, allJoints[ -1 ], relative=True )
		move( head, 0, posInc, posInc, r=True, ws=True )
		allJoints.append( head )

		jointSize( head, 2 )

		return allJoints
	def _align( self, _initialAlign=False ):
		#perform the align on all items except the head - which is the end item
		BaseSkeletonPart._align( self.__class__( self[ :-1 ] ), _initialAlign )

		if _initialAlign: alignItemToWorld( self.head )
		else: alignPreserve( self.head )
	def visualize( self ):
		scale = self.getBuildScale() / 10.0

		plane = polyCreateFacet( ch=False, tx=True, s=1, p=((0, -scale, 0), (0, scale, 0), (self.getParityMultiplier() * 2 * scale, 0, 0)) )
		pymelCore.parent( plane, self.head, relative=True )

		pymelCore.parent( listRelatives( plane, shapes=True ), self.head, add=True, shape=True )
		delete( plane )


class Arm(BaseSkeletonPart):
	'''
	this is a standard bipedal arm, including the clavicle
	'''

	@classmethod
	def _build( cls, parent=None, buildClavicle=True, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )

		allJoints = []
		dirMult = idx.asMultiplier()
		parityName = idx.asName()
		if buildClavicle:
			clavicle = createJoint( 'clavicle%s' % parityName )
			pymelCore.parent( clavicle, parent, relative=True )
			move( clavicle, dirMult * partScale / 50.0, partScale / 10.0, partScale / 25.0, r=True, ws=True )
			allJoints.append( clavicle )
			parent = clavicle

		bicep = createJoint( 'bicep%s' % parityName )
		pymelCore.parent( bicep, parent, relative=True )
		move( bicep, dirMult * partScale / 10.0, 0, 0, r=True, ws=True )

		elbow = createJoint( 'elbow%s' % parityName )
		pymelCore.parent( elbow, bicep, relative=True )
		move( elbow, dirMult * partScale / 5.0, 0, -partScale / 20.0, r=True, ws=True )

		wrist = createJoint( 'wrist%s' % parityName )
		pymelCore.parent( wrist, elbow, relative=True )
		move( wrist, dirMult * partScale / 5.0, 0, partScale / 20.0, r=True, ws=True )

		setAttr( str( bicep ) +'.rz', dirMult * 45 )

		jointSize( bicep, 2 )
		jointSize( wrist, 2 )

		return allJoints + [ bicep, elbow, wrist ]
	def visualize( self ):
		scale = self.getBuildScale() / 10.0

		plane = polyCreateFacet( ch=False, tx=True, s=1, p=((0, 0, -scale), (0, 0, scale), (self.getParityMultiplier() * 2 * scale, 0, 0)) )
		pymelCore.parent( plane, self.wrist, relative=True )

		pymelCore.parent( listRelatives( plane, shapes=True ), self.wrist, add=True, shape=True )
		delete( plane )
	@property
	def clavicle( self ): return self[ 0 ] if len( self ) > 3 else None
	@property
	def bicep( self ): return self[ -3 ]
	@property
	def elbow( self ): return self[ -2 ]
	@property
	def wrist( self ): return self[ -1 ]
	def _align( self, _initialAlign=False ):
		parity = self.getParity()

		normal = getPlaneNormalForObjects( self.bicep, self.elbow, self.wrist )
		normal *= parity.asMultiplier()

		if self.clavicle:
			parent = self.clavicle.getParent()
			alignAimAtItem( self.clavicle, self.bicep, parity, upType='objectrotation', worldUpObject=parent, worldUpVector=MAYA_FWD  )

		alignAimAtItem( self.bicep, self.elbow, parity, worldUpVector=normal )
		alignAimAtItem( self.elbow, self.wrist, parity, worldUpVector=normal )

		if _initialAlign:
			autoAlignItem( self.wrist, parity, worldUpVector=normal )
		else:
			alignPreserve( self.wrist )

		for i in self.getOrphanJoints():
			alignItemToLocal( i )


class Leg(BaseSkeletonPart):
	'''
	this is a standard bipedal leg
	'''

	@property
	def thigh( self ): return self[ 0 ]
	@property
	def knee( self ): return self[ 1 ]
	@property
	def ankle( self ): return self[ 2 ]
	@property
	def toe( self ): return self[ 3 ] if len( self ) > 3 else None
	@classmethod
	def _build( cls, parent=None, buildToe=True, toeCount=0, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )

		root = getRoot()
		height = xform( root, q=True, ws=True, rp=True )[ 1 ]

		dirMult = idx.asMultiplier()
		parityName = idx.asName()

		sidePos = dirMult * partScale / 10.0
		upPos = partScale / 20.0
		fwdPos = -(idx / 2) * partScale / 5.0

		footHeight = height / 15.0 if buildToe else 0
		kneeOutMove = dirMult * partScale / 35.0
		kneeFwdMove = partScale / 20.0

		thigh = createJoint( 'thigh%s' % parityName )
		pymelCore.parent( thigh, parent, relative=True )
		move( thigh, sidePos, -upPos, fwdPos, r=True, ws=True )

		knee = createJoint( 'knee%s' % parityName )
		pymelCore.parent( knee, thigh, relative=True )
		move( knee, 0, -(height - footHeight) / 2.0, kneeFwdMove, r=True, ws=True )

		ankle = createJoint( 'ankle%s' % parityName )
		pymelCore.parent( ankle, knee, relative=True )
		move( ankle, 0, -(height - footHeight) / 2.0, -kneeFwdMove, r=True, ws=True )

		jointSize( thigh, 2 )
		jointSize( ankle, 2 )

		allJoints = []
		if buildToe:
			toe = createJoint( 'toeBase%s' % parityName )
			pymelCore.parent( toe, ankle, relative=True )
			move( toe, 0, -footHeight, footHeight * 3, r=True, ws=True )
			allJoints.append( toe )

			jointSize( toe, 1.5 )

			for n in range( toeCount ):
				toeN = createJoint( 'toe_%d_%s' % (n, parityName) )
				allJoints.append( toeN )
				#move( toeN, dirMult * partScale / 50.0, 0, partScale / 25.0, ws=True )
				pymelCore.parent( toeN, toe, relative=True )

		rotate( thigh, 0, dirMult * 15, 0, r=True, ws=True )

		#finally create a "ground plane" visualization tool parented to ankle

		return [ thigh, knee, ankle ] + allJoints
	def _align( self, _initialAlign=False ):
		normal = getPlaneNormalForObjects( self.thigh, self.knee, self.ankle )
		normal *= self.getParityMultiplier()

		parity = self.getParity()

		alignAimAtItem( self.thigh, self.knee, parity, worldUpVector=normal )
		alignAimAtItem( self.knee, self.ankle, parity, worldUpVector=normal )

		if self.toe:
			alignAimAtItem( self.ankle, self.toe, parity, upVector=ENGINE_UP, worldUpVector=(1,0,0), upType='scene' )
		else:
			autoAlignItem( self.ankle, parity, upVector=ENGINE_UP, worldUpVector=(1,0,0), upType='scene' )

		for i in self.getOrphanJoints():
			alignItemToLocal( i )

class Hand(BaseSkeletonPart):

	def getParity( self ):
		'''
		the parity of a hand comes from the limb its parented to, not the idx of
		the finger part itself...
		'''
		try:
			return Parity( self.getBuildKwargs()[ 'limbIdx' ] )
		except KeyError:
			return Parity.NONE
	@property
	def bases( self ):
		'''
		returns all the bases for the hand - bases are the top most parents
		'''
		handParent = self[ 0 ].getParent()
		bases = []
		for item in self:
			itemParent = item.getParent()
			if itemParent == handParent:
				bases.append( item )

		return bases
	def iterFingerChains( self ):
		'''
		iterates over each finger chain in the hand - a chain is simply a list of
		joint names ordered hierarchically
		'''
		for base in self.bases:
			children = listRelatives( base, ad=True, path=True, type='joint' )
			children = [ base ] + sortByHierarchy( children )
			yield children
	@classmethod
	def _build( cls, parent=None, limbIdx=0, fingerCount=5, fingerJointCount=3, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )

		minPos, maxPos = -cls.PART_SCALE / 25.0, cls.PART_SCALE / 25.0
		posRange = float( maxPos - minPos )
		allJoints = []

		length = partScale / 3 / fingerJointCount
		lengthInc = cls.ParityMultiplier( limbIdx ) * (length / fingerJointCount)

		limbName = Parity.NAMES[ limbIdx ]
		for nameIdx in range( fingerCount ):
			fingerName = FINGER_IDX_NAMES[ nameIdx ]
			prevParent = parent
			for n in range( fingerJointCount ):
				j = createJoint( '%s%s_%d%s' % (fingerName, idx if idx > 1 else '', n, limbName) )
				pymelCore.parent( j, prevParent, r=True )
				move( j, lengthInc, 0, 0, r=True, os=True )

				if n == 0:
					move( j, lengthInc, 0, -maxPos + (posRange * nameIdx / (fingerCount - 1)), r=True, os=True )
				else:
					j.ty.setLocked( True )

				allJoints.append( j )
				prevParent = j

		return allJoints
	def visualize( self ):
		scale = self.getActualScale() / 1.5

		for base in self.bases:
			plane = polyPlane( w=scale, h=scale / 2.0, sx=1, sy=1, ax=(0, 1, 0), cuv=2, ch=False )[ 0 ]
			pymelCore.parent( plane, base, relative=True )

			plane.tx.set( self.getParityMultiplier() * scale / 2 )
			makeIdentity( plane, a=True, t=True )

			pymelCore.parent( listRelatives( plane, shapes=True ), base, add=True, shape=True )
			delete( plane )
	def _align( self, _initialAlign=False ):
		parity = self.getParity()
		wrist = self.getParent()

		parityMult = self.getParityMultiplier()

		defactoUpVector = utils.getObjectBasisVectors( wrist )[ 2 ]
		for chain in self.iterFingerChains():
			upVector = defactoUpVector
			if len( chain ) >= 3:
				midJoint = chain[ len( chain ) / 2 ]
				upVector = getPlaneNormalForObjects( chain[ 0 ], midJoint, chain[ -1 ], defactoUpVector )

			upVector = upVector * parityMult
			for n, item in enumerate( chain[ :-1 ] ):
				alignAimAtItem( item, chain[ n+1 ], parity, worldUpVector=upVector )

			autoAlignItem( chain[ -1 ], parity, worldUpVector=upVector )


class ArbitraryChain(BaseSkeletonPart):
	'''
	arbitrary chains are just simple joint hierarchies.  they can be used to build
	skeletal structures for things like tails, hair styles, clothing etc...
	'''

	HAS_PARITY = False

	def getPartName( self ):
		parityStr = 'Left ' if self.getParity() == Parity.LEFT else 'Right '
		if not self.hasParity():
			parityStr = ''

		chainName = camelCaseToNice( self.getBuildKwargs()[ 'chainName' ] )

		return '%s%s Chain %d' % (parityStr, chainName, self.getIdx())

	@classmethod
	def _build( cls, parent=None, chainName='', jointCount=5, direction='x', **kw ):
		if not chainName:
			raise SkeletonError( "Chain Name wasn't specified" )

		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		chainName = '%s%s' % (chainName, idx)

		parent = getParent( parent )

		dirMult = cls.ParityMultiplier( idx ) if cls.HAS_PARITY else 1
		length = partScale
		lengthInc = dirMult * length / jointCount

		directionAxis = utils.Axis.FromName( direction )
		directionVector = directionAxis.asVector() * lengthInc
		directionVector = list( directionVector )
		otherIdx = directionAxis.otherAxes()[ 1 ]

		parityStr = idx.asName() if cls.HAS_PARITY else ''
		allJoints = []
		prevParent = parent
		half = jointCount / 2
		for n in range( jointCount ):
			j = createJoint( '%s_%d%s' % (chainName, n, parityStr) )
			pymelCore.parent( j, prevParent, r=True )

			moveVector = directionVector + [ j ]
			moveVector[ otherIdx ] = dirMult * n * lengthInc / jointCount / 5.0
			move( j, r=True, ws=True, *moveVector )
			allJoints.append( j )
			prevParent = j

		return allJoints
	def _align( self, _initialAlign=False ):
		parity = Parity( 0 )
		if self.HAS_PARITY:
			parity = self.getParity()

		num = len( self )
		if num == 1:
			alignItemToWorld( self[ 0 ] )
		elif num == 2:
			for i in self.selfAndOrphans(): autoAlignItem( i, parity )
		else:
			#in this case we want to find a plane that roughly fits the chain.
			#for the sake of simplicity take the first, last and some joint in
			#the middle and fit a plane to them, and use it's normal for the upAxis
			midJoint = self[ num / 2 ]
			defaultUpVector = utils.getObjectBasisVectors( self[ 0 ] )[ 1 ]  #defaults to the "Y" axis of the part's parent
			normal = getPlaneNormalForObjects( self.base, midJoint, self.end, defaultUpVector )
			normal *= parity.asMultiplier()

			for n, i in enumerate( self[ :-1 ] ):
				alignAimAtItem( i, self[ n+1 ], parity, worldUpVector=normal )

			autoAlignItem( self[ -1 ], parity, worldUpVector=normal )
			for i in self.getOrphanJoints():
				autoAlignItem( i, parity, worldUpVector=normal )


def alignItems( items ):
	items = sortByHierarchy( items )

	num = len( items )
	if num == 1:
		alignItemToWorld( items[ 0 ] )
	elif num == 2:
		for i in items: autoAlignItem( i )
	else:
		midJoint = items[ num / 2 ]
		defaultUpVector = utils.getObjectBasisVectors( items[ 0 ] )[ 1 ]  #defaults to the "Y" axis of the part's parent
		normal = getPlaneNormalForObjects( items[ 0 ], midJoint, items[ -1 ], defaultUpVector )

		for n, i in enumerate( items[ :-1 ] ):
			alignAimAtItem( i, items[ n+1 ], worldUpVector=normal )

		autoAlignItem( items[ -1 ], worldUpVector=normal )


class ArbitraryParityChain(ArbitraryChain):
	HAS_PARITY = True


class QuadrupedFrontLeg(Arm):
	'''
	A quadruped's front leg is more like a biped's arm as it has clavicle/shoulder
	blade functionality, but is generally positioned more like a leg.  It is a separate
	part because it is rigged quite differently from either a bipedal arm or a bipedal
	leg.
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def _build( cls, parent=None, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		height = xform( parent, q=True, ws=True, rp=True )[ 1 ]

		dirMult = idx.asMultiplier()
		parityName = idx.asName()

		clavicle = createJoint( 'quadClavicle%s' % parityName )
		pymelCore.parent( clavicle, parent, relative=True )
		move( clavicle, dirMult * partScale / 10.0, -partScale / 10.0, partScale / 6.0, r=True, ws=True )

		bicep = createJoint( 'quadHumerous%s' % parityName )
		pymelCore.parent( bicep, clavicle, relative=True )
		move( bicep, 0, -height / 3.0, -height / 6.0, r=True, ws=True )

		elbow = createJoint( 'quadElbow%s' % parityName )
		pymelCore.parent( elbow, bicep, relative=True )
		move( elbow, 0, -height / 3.0, height / 10.0, r=True, ws=True )

		wrist = createJoint( 'quadWrist%s' % parityName )
		pymelCore.parent( wrist, elbow, relative=True )
		move( wrist, 0, -height / 3.0, 0, r=True, ws=True )

		jointSize( clavicle, 2 )
		jointSize( wrist, 2 )

		return [ clavicle, bicep, elbow, wrist ]


class QuadrupedBackLeg(Arm):
	'''
	The creature's back leg is more like a biped's leg in terms of the joints it contains.
	However, like the front leg, the creature stands on his "tip toes" at the back as well.
	'''

	AVAILABLE_IN_UI = True

	@classmethod
	def _build( cls, parent=None, **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		height = xform( parent, q=True, ws=True, rp=True )[ 1 ]

		dirMult = idx.asMultiplier()
		parityName = idx.asName()

		kneeFwdMove = height / 10.0

		thigh = createJoint( 'quadThigh%s' % parityName )
		thigh = pymelCore.parent( thigh, parent, relative=True )[ 0 ]
		move( thigh, dirMult * partScale / 10.0, -partScale / 10.0, -partScale / 5.0, r=True, ws=True )

		knee = createJoint( 'quadKnee%s' % parityName )
		knee = pymelCore.parent( knee, thigh, relative=True )[ 0 ]
		move( knee, 0, -height / 3.0, kneeFwdMove, r=True, ws=True )

		ankle = createJoint( 'quadAnkle%s' % parityName )
		ankle = pymelCore.parent( ankle, knee, relative=True )[ 0 ]
		move( ankle, 0, -height / 3.0, -kneeFwdMove, r=True, ws=True )

		toe = createJoint( 'quadToe%s' % parityName )
		toe = pymelCore.parent( toe, ankle, relative=True )[ 0 ]
		move( toe, 0, -height / 3.0, 0, r=True, ws=True )

		jointSize( thigh, 2 )
		jointSize( ankle, 2 )
		jointSize( toe, 1.5 )

		return [ thigh, knee, ankle, toe ]


class WeaponRoot(BaseSkeletonPart):
	'''
	weapon root parts are supposed to be used as the basis for weapon rigs.
	basically weapon parts can have a bunch of joints parented under them, and
	the rig built for the part will reflect the skeleton in every way bar some
	conveniences like space switching for root controls, and possibly others.
	'''

	HAS_PARITY = False

	@classmethod
	def _build( cls, parent=None, weaponName='', **kw ):
		idx = Parity( kw[ 'idx' ] )
		partScale = kw[ 'partScale' ]

		parent = getParent( parent )
		j = createJoint( '%s_%d' % (weaponName, idx+1) )
		pymelCore.parent( j, parent, r=True )

		#move it out a bit
		for ax in AXES: j.attr( 't'+ ax ).set( partScale )

		return [ j ]
	def _align( self, _initialAlign=False ):
		'''
		leave weapon parts alone - the user should define how they're aligned always
		'''
		pass


def saveSkeletonTemplate():
	pass


class SkeletonPreset(filesystem.trackableClassFactory()):
	AVAILABLE_IN_UI = True  #determines whether this part should appear in the UI or not...

	def __init__( self, *a, **kw ):
		self.create( *a, **kw )
	@classmethod
	def GetDefaultBuildKwargs( cls ):
		'''
		returns a list of 2 tuples: argName, defaultValue
		'''
		buildFunc = getattr( cls, 'create', None )
		spec = inspect.getargspec( buildFunc )

		kwargs = []
		for argName, default in zip( spec[ 0 ][ 1: ], spec[ 3 ] ):
			if argName == 'scale': continue
			kwargs.append( (argName, default) )

		return kwargs
	@classmethod
	def GetPartName( cls ):
		'''
		can be used to get a "nice" name for the preset
		'''
		return camelCaseToNice( cls.__name__ )


class Biped(SkeletonPreset):
	def create( self, scale=TYPICAL_HEIGHT, spineCount=3, neckCount=1, buildHands=True ):
		root = Root.Create( partScale=scale )

		theSpine = Spine.Create( root, spineCount, partScale=scale )
		theHead = Head.Create( theSpine.end, neckCount, partScale=scale )
		armL = Arm.Create( theSpine.end, partScale=scale )
		armR = Arm.Create( theSpine.end, partScale=scale )
		legL = Leg.Create( root, partScale=scale )
		legR = Leg.Create( root, partScale=scale )

		armL.driveOtherPart( armR )
		legL.driveOtherPart( legR )

		if buildHands:
			handL = Hand.Create( armL.wrist, armL.getIdx() )
			handR = Hand.Create( armR.wrist, armR.getIdx() )
			handL.driveOtherPart( handR )


def sortPartsByHierarchy( parts ):
	'''
	returns a list of the given parts in a list sorted by hierarchy
	'''
	sortedParts = sortByHierarchy( [ p.base for p in parts ] )
	return [ SkeletonPart.InitFromItem( p ) for p in sortedParts ]


def getPartsFromObjects( objs ):
	'''
	returns a list of parts that have at least one of their items selected
	'''
	parts = []
	for o in objs:
		try:
			parts.append( SkeletonPart.InitFromItem( o ) )
		except AssertionError: continue

	selectedParts = filesystem.removeDupes( parts )

	return selectedParts


@api.d_maintainSceneSelection
def realignSelectedParts():
	'''
	re-aligns all selected parts
	'''
	sel = ls( sl=True )
	selectedParts = getPartsFromObjects( sel )
	for part in selectedParts:
		part.align()


@api.d_showWaitCursor
@api.d_maintainSceneSelection
def realignAllParts():
	'''
	re-aligns all parts in the current scene
	'''
	for part in SkeletonPart.IterAllParts():
		part.align()


@api.d_showWaitCursor
def finalizeAllParts():

	#do a pre-pass on the skin clusters to remove un-used influences - this can speed up the speed of the alignment code
	#is directly impacted by the number of joints involved in the skin cluster
	skinClusters = ls( typ='skinCluster' )
	for s in skinClusters:
		skinCluster( s, e=True, removeUnusedInfluence=True )

	for part in sortPartsByHierarchy( part for part in SkeletonPart.IterAllParts() ):
		print 'Finalizing', part
		part.breakDriver()
		part._finalize()


def getNamespaceFromReferencing( node ):
	'''
	returns the namespace contribution from referencing.  this is potentially
	different from just querying the namespace directly from the node because the
	node in question may have had a namespace before it was referenced
	'''
	if referenceQuery( node, isNodeReferenced=True ):
		refNode = referenceQuery( node, referenceNode=True )
		namespace = cmd.file( cmd.referenceQuery( refNode, filename=True ), q=True, namespace=True )

		return '%s:' % namespace

	return ''


@api.d_showWaitCursor
def buildRigForModel( scene=None, autoFinalize=True, referenceModel=True ):
	'''
	given a model scene whose skeleton is assumed to have been built by the
	skeletonBuilder tool, this function will create a rig scene by referencing
	in said model, creating the rig as best it knows how, saving the scene in
	the appropriate spot etc...
	'''

	#if no scene was passed, assume we're acting on the current scene
	if scene is None:
		scene = filesystem.Path( cmd.file( q=True, sn=True ) )
	#if the scene WAS passed in, open the desired scene if it isn't already open
	else:
		scene = filesystem.Path( scene )
		curScene = filesystem.Path( cmd.file( q=True, sn=True ) )
		if curScene:
			if scene != curScene:
				mel.saveChanges( 'file -f -open "%s"' % scene )
		else: cmd.file( scene, f=True, open=True )

	#if the scene is still none bail...
	if not scene and referenceModel:
		raise SceneNotSavedError( "Uh oh, your scene hasn't been saved - Please save it somewhere on disk so I know where to put the rig.  Thanks!" )

	if scene:
		#backup the current state of the scene, just in case something goes south...
		backupFilename = scene.up() / ('%s_backup.%s' % (scene.name(), scene.getExtension()))
		if backupFilename.exists: backupFilename.delete()
		cmd.file( rename=backupFilename )
		try:
			cmd.file( save=True, force=True )
		finally:
			cmd.file( rename=scene )

	#finalize if desired
	if autoFinalize:
		finalizeAllParts()

	#if desired, create a new scene and reference in the model
	if referenceModel:
		scene.editoradd()
		cmd.file( f=True, save=True )
		cmd.file( f=True, new=True )

		api.referenceFile( scene, 'model' )

		#rename the scene to the rig
		rigSceneName = '%s_rig.ma' % scene.name()
		rigScene = scene.up() / rigSceneName
		cmd.file( rename=rigScene )
		rigScene.editoradd()
		cmd.file( f=True, save=True, typ='mayaAscii' )

	buildRigForAllParts()


def buildRigForAllParts():
	#sort all parts in the scene by hierarchy and build a rig for each part
	allParts = [ part for part in SkeletonPart.IterAllParts() ]
	allParts = sortPartsByHierarchy( allParts )

	scale = getDefaultScale() / 10.0
	for part in allParts:
		part.rig( scale=scale )


#end
