import os
import sys

from pymel.core import *
from filesystem import Path, removeDupes, BreakException, getArgDefault
from vectors import Vector

import pymel.core as pymelCore
import filesystem
import utils
import triggered
import colours

import meshUtils


WORLD = utils.WORLD
LOCAL = utils.LOCAL
OBJECT = utils.OBJECT

Axis = utils.Axis
CONTROL_DIRECTORY = Path( '%VTOOLS%/maya/scripts/zoo' ) #Path( __file__ ).up()

AX_X, AX_Y, AX_Z, AX_X_NEG, AX_Y_NEG, AX_Z_NEG = map( Axis, range( 6 ) )
DEFAULT_AXIS = AX_X

AXIS_ROTATIONS = { AX_X: (0, 0, -90),
                   AX_Y: (0, 0, -180),
                   AX_Z: (90, 0, 0),
                   AX_X_NEG: (0, 0, 90),
                   AX_Y_NEG: (0, 0, 180),
                   AX_Z_NEG: (-90, 0, 0) }


class ShapeDesc(object):
	'''
	store shape preferences about a control
	'''

	NULL_SHAPE = None
	SKIN = 1

	DEFAULT_TYPE = 'cube'

	def __init__( self, surfaceType=DEFAULT_TYPE, curveType=None, axis=DEFAULT_AXIS, expand=0.04, joints=None ):
		'''
		surfaceType must be a valid control preset name - defaults to cube if none is specified
		curveType must also be a valid control preset name and defaults to the surface name if not specified
		'''
		self.surfaceType = surfaceType
		self.curveType = curveType
		if curveType is None:
			self.curveType = surfaceType

		self.axis = axis

		self.expand = expand
		if joints is None:
			self.joints = []
		else:
			self.joints = joints if isinstance( joints, (tuple, list) ) else [ joints ]
	def __repr__( self ):
		return repr( self.surfaceType )
	__str__ = __repr__

DEFAULT_SHAPE_DESC = ShapeDesc()
SHAPE_NULL = ShapeDesc( ShapeDesc.NULL_SHAPE, ShapeDesc.NULL_SHAPE )
Shape_Skin = lambda joints=None, **kw: ShapeDesc( ShapeDesc.SKIN, ShapeDesc.NULL_SHAPE, joints=joints, **kw )

DEFAULT_SKIN_EXTRACTION_TOLERANCE = getArgDefault( meshUtils.extractMeshForJoints, 'tolerance' )


class PlaceDesc(object):
	WORLD = None

	PLACE_OBJ = 0
	ALIGN_OBJ = 1
	PIVOT_OBJ = 2

	Place = 0
	Align = 1
	Pivot = 2

	def __init__( self, placeAtObj=WORLD, alignToObj=PLACE_OBJ, snapPivotToObj=PLACE_OBJ ):
		#now convert the inputs to actual objects, if they're not already
		self._placeData = placeAtObj, alignToObj, snapPivotToObj

		self.place = self.getObj( self.Place )
		self.align = self.getObj( self.Align )
		self.pivot = self.getObj( self.Pivot )
	def getObj( self, item ):
		p = self._placeData[ item ]
		if p == self.PLACE_OBJ:
			p = self._placeData[ 0 ]
		elif p == self.ALIGN_OBJ:
			p = self._placeData[ 1 ]
		elif p == self.PIVOT_OBJ:
			p = self._placeData[ 2 ]

		if isinstance( p, PyNode ): return p
		if isinstance( p, int ): return self.WORLD
		if p is None: return self.WORLD

		return PyNode( p )
	def getLocation( self, obj ):
		if obj is None:
			return Vector()

		return xform( obj, q=True, ws=True, rp=True )
	placePos = property( lambda self: self.getLocation( self.place ) )
	alignPos = property( lambda self: self.getLocation( self.align ) )
	pivotPos = property( lambda self: self.getLocation( self.pivot ) )

DEFAULT_PLACE_DESC = PlaceDesc()


class PivotModeDesc(object):
	BASE, MID, TOP = 0, 1, 2


ColourDesc = colours.Colour
DEFAULT_COLOUR = ColourDesc( 'orange' )


def _performOnAttr( obj, attrName, functionName, *funcArgs, **funcKw ):
	obj = PyNode( obj )
	attr = getattr( obj, attrName, None )
	if attr is None:
		return

	if attr.isCompound():
		for a in attr.getChildren():
			function = getattr( a, functionName, None )
			if function is None:
				return

			function( *funcArgs, **funcKw )
	else:
		function = getattr( attr, functionName, None )
		if function is None:
			return

		function( *funcArgs, **funcKw )


NORMAL = False, True
HIDE = None, False, False
LOCK_HIDE = True, False, False
NO_KEY = False, False, True

def attrState( objs, attrNames, lock=None, keyable=None, show=None ):
	if not isinstance( objs, (list, tuple) ):
		objs = [ objs ]

	if not isinstance( attrNames, (list, tuple) ):
		attrNames = [ attrNames ]

	for obj in objs:
		for attrName in attrNames:
			#showInChannelBox( False ) doesn't work if setKeyable is true - which is kinda dumb...
			if show is not None:
				if not show:
					_performOnAttr( obj, attrName, 'setKeyable', False )
					keyable = None
				_performOnAttr( obj, attrName, 'showInChannelBox', show )

			if lock is not None: _performOnAttr( obj, attrName, 'setLocked', lock )

			if keyable is not None: _performOnAttr( obj, attrName, 'setKeyable', keyable )


def getJointSize( joints, threshold=0.65, space=OBJECT ):
	'''
	minor modification to the getJointSize function in rigging.utils - uses the
	child of the joint[ 0 ] (if any exist) to determine the size of the joint in
	the axis aiming toward
	'''
	joints = [ j for j in joints if j is not None ]
	if not joints:
		return Vector( 1, 1, 1 )

	size = utils.getJointSize( joints, threshold, space )
	if size.within( Vector.Zero( 3 ), 1e-2 ):
		while threshold > 1e-2:
			threshold *= 0.9
			size = utils.getJointSize( joints, threshold )

		if size.within( Vector.Zero( 3 ), 1e-2 ):
			size = Vector( 1, 1, 1 )

	children = joints[ 0 ].getChildren()
	if children:
		childPos = children[ 0 ].getRotatePivot( WORLD ) - joints[ 0 ].getRotatePivot( WORLD )
		childPos = Vector( childPos )  #case as non pymel vector - lazy

		axis = utils.getObjectAxisInDirection( joints[ 0 ], childPos, DEFAULT_AXIS )
		axisValue = children[ 0 ].attr( 't'+ axis.asCleanName() ).get()

		if space == WORLD:
			axis = Axis.FromVector( childPos )

		size[ axis % 3 ] = axisValue


	return size


def getAutoOffsetAmount( placeObject, joints=None, axis=AX_Z, threshold=0.65 ):
	'''
	returns a value reflecting the distance from the placeObject to the edge of
	the bounding box containing the verts skinned to the joints in the joints list

	the axis controls what edge of the bounding box is used

	if joints is None, [placeObject] is used
	'''
	if joints is None:
		joints = [ placeObject ]
	else:
		joints = removeDupes( [ placeObject ] + joints )  #make sure the placeObject is the first item in the joints list, otherwise the bounds won't be transformed to the correct space

	#get the bounds of the geo skinned to the hand and use it to determine default placement of the slider control
	bounds = utils.getJointBounds( joints )
	offsetAmount = abs( bounds[ axis.isNegative() ][ axis % 3 ] )
	#print bounds[ 0 ].x, bounds[ 0 ].y, bounds[ 0 ].z, bounds[ 1 ].x, bounds[ 1 ].y, bounds[ 1 ].z

	return offsetAmount


AUTO_SIZE = None

def buildControl( name,
                  placementDesc=DEFAULT_PLACE_DESC,
                  pivotModeDesc=PivotModeDesc.MID,
                  shapeDesc=DEFAULT_SHAPE_DESC,
                  colour=DEFAULT_COLOUR,
                  constrain=True,
                  oriented=True,
                  offset=Vector(), offsetSpace=utils.OBJECT,
                  size=Vector( 1, 1, 1 ), scale=1.0, autoScale=False,
                  parent=None, qss=None,
                  asJoint=False, freeze=True,
                  lockAttrs=( 'scale', ), hideAttrs=( 'scale', 'visibility' ) ):
	'''
	this rather verbosely called function deals with creating control objects in
	a variety of ways.

	the following args take "struct" like instances of the classes defined above,
	so look to them for more detail on defining those options
	'''

	select( cl=True )

	#sanity checks...
	if not isinstance( placementDesc, PlaceDesc ):
		if isinstance( placementDesc, (list, tuple) ):
			placementDesc = PlaceDesc( *placementDesc )
		else:
			placementDesc = PlaceDesc( placementDesc )

	if not isinstance( shapeDesc, ShapeDesc ):
		if isinstance( shapeDesc, (list, tuple) ):
			shapeDesc = ShapeDesc( *shapeDesc )
		else:
			shapeDesc = ShapeDesc( shapeDesc )

	offset = Vector( offset )


	#unpack placement objects
	place, align, pivot = placementDesc.place, placementDesc.align, placementDesc.pivot

	if shapeDesc.surfaceType == ShapeDesc.SKIN:
		shapeDesc.curveType = ShapeDesc.NULL_SHAPE  #never build curve shapes if the surface type is skin
		if shapeDesc.joints is None:
			shapeDesc.joints = [ str( place ) ]

		shapeDesc.expand *= scale


	#determine auto scale/size - if nessecary
	if autoScale:
		_scale = list( getJointSize( [ place ] + (shapeDesc.joints or []) ) )
		_scale = sorted( _scale )[ -1 ]
		if abs( _scale ) < 1e-2:
			print 'AUTO SCALE FAILED', _scale, name, place
			_scale = scale

		scale = _scale

	if size is AUTO_SIZE:
		tmpKw = {} if oriented else { 'space': WORLD }
		size = getJointSize( [ place ] + (shapeDesc.joints or []), **tmpKw )
		for n, v in enumerate( size ):
			if abs( v ) < 1e-2:
				size[ n ] = scale

		scale = 1.0


	#if we're doing a SKIN shape, ensure there is actually geometry skinned to the joints, otherwise bail on the skin and change to the default type
	if shapeDesc.surfaceType == ShapeDesc.SKIN:
		try:
			#loop over all joints and see if there is geo skinned to it
			for j in shapeDesc.joints:
				verts = meshUtils.jointVerts( j, tolerance=DEFAULT_SKIN_EXTRACTION_TOLERANCE )

				#if so throw a breakException to bail out of the loop
				if verts: raise BreakException

			#if we get this far that means none of the joints have geo skinned to them - so set the surface and curve types to their default values
			shapeDesc.surfaceType = shapeDesc.curveType = ShapeDesc.DEFAULT_TYPE
			print 'WARNING - surface type was set to SKIN, but no geometry is skinned to the joints: %s' % shapeDesc.joints
		except BreakException: pass


	#build the curve shapes first
	if shapeDesc.curveType != ShapeDesc.NULL_SHAPE \
	   and shapeDesc.curveType != ShapeDesc.SKIN:
		curveShapeFile = getFileForShapeName( shapeDesc.curveType )
		assert curveShapeFile is not None, "cannot find shape %s" % shapeDesc.curveType

		createCmd = ''.join( curveShapeFile.read() )
		mel.eval( createCmd )
	else:
		select( group( em=True ) )

	sel = ls( sl=True )
	obj = sel[ 0 ]

	#now to deal with the surface - if its different from the curve, then build it
	if shapeDesc.surfaceType != shapeDesc.curveType \
	   and shapeDesc.surfaceType != ShapeDesc.NULL_SHAPE \
	   and shapeDesc.surfaceType != ShapeDesc.SKIN:

		#if the typesurface is different from the typecurve, then first delete all existing surface shapes under the control
		shapesTemp = listRelatives( obj, s=1, f=1 )
		for s in shapesTemp:
			if nodeType( s ) == "nurbsSurface":
				delete( s )

		#now build the temporary control
		surfaceShapeFile = getFileForShapeName( shapeDesc.surfaceType )
		assert surfaceShapeFile is not None, "cannot find shape %s" % shapeDesc.surfaceType

		createCmd = ''.join( surfaceShapeFile.read() )
		mel.eval( createCmd )

		#and parent its surface shape nodes to the actual control, and then delete it
		tempSel = ls( sl=True )
		shapesTemp=listRelatives( tempSel[0], s=1, f=1 )
		for s in shapesTemp:
			if nodeType(s) == "nurbsSurface":
				pymelCore.parent( s, obj, add=True, s=True )

		delete( tempSel[ 0 ] )
		select( sel )


	#if the joint flag is true, parent the object shapes under a joint instead of a transform node
	if asJoint:
		select( cl=True )
		j = joint()
		for s in listRelatives( obj, s=True ):
			pymelCore.parent( s, j, add=1, s=1 )

		j.radius.setKeyable( False )
		delete( obj )
		obj = j

	obj.scale.set( scale, scale, scale )


	#rename the object
	if not name: name = 'control'
	obj.rename( name )


	#move the pivot - if needed
	makeIdentity( obj, a=1, s=1 )
	shapeStrs = getShapeStrs( obj )
	if pivotModeDesc == PivotModeDesc.TOP:
		for s in shapeStrs:
			move( s, 0, scale/2.0, 0, r=True )
	elif pivotModeDesc == PivotModeDesc.BASE:
		for s in shapeStrs:
			move( s, 0, -scale/2.0, 0, r=True )


	#rotate it accordingly
	rot = AXIS_ROTATIONS[ shapeDesc.axis ]
	rotate( obj, os=True, *rot )
	makeIdentity( obj, a=1, r=1 )


	#if the user wants the control oriented, create the orientation group and parent the control
	grp = obj
	if oriented:
		grp = group( em=True, n="%s_space#" % obj )
		pymelCore.parent( obj, grp )
		attrState( grp, ['s', 'v'], *LOCK_HIDE )
		if align is not None:
			delete( parentConstraint( align, grp ) )


	#place and align
	if place:
		delete( pointConstraint( place, grp ) )

	if align:
		delete( orientConstraint( align, grp ) )
	else:
		rotate( grp, (0, 0, 0), a=True, ws=True )


	#do the size scaling...
	if shapeDesc.surfaceType != ShapeDesc.SKIN:
		for s in shapeStrs:
			pymelCore.scale( s, size )


	#if the parent exists - parent the new control to the given parent
	if parent is not None:
		pymelCore.parent( grp, parent )


	#do offset
	for s in shapeStrs:
		mkw = { 'r': True }
		if offsetSpace == utils.OBJECT: mkw[ 'os' ] = True
		elif offsetSpace == utils.LOCAL: mkw[ 'ls' ] = True
		elif offsetSpace == utils.WORLD: mkw[ 'ws' ] = True
		move( s, *offset, **mkw )

	if freeze:
		makeIdentity( obj, a=1, r=1 )

	makeIdentity( obj, a=1, t=1 )  #always freeze translations


	#delete shape data that we don't want
	if shapeDesc.curveType is None:
		for s in listRelatives( obj, s=True ):
			if nodeType(s) == "nurbsCurve":
				delete(s)

	if shapeDesc.surfaceType is None:
		for s in listRelatives( obj, s=True ):
			if nodeType(s) == "nurbsSurface":
				delete(s)


	#now snap the pivot to alignpivot object if it exists
	if pivot is not None and objExists( pivot ):
		move( (obj.rp, obj.sp), placementDesc.pivotPos, a=True, ws=True, rpr=True )


	#constrain the target object to this control?
	if constrain:
		#check to see if the transform is constrained already - if so, bail.  buildControl doesn't do multi constraints
		if not listConnections( pivot, s=0, type='constraint' ):
			if place:
				parentConstraint( obj, pivot, mo=True )
				setItemRigControl( pivot, obj )


	#if the user has specified skin geometry as the representation type, then build the geo
	#NOTE: this really needs to happen after ALL the placement has happened otherwise the extracted
	#will be offset from the surface its supposed to be representing
	if shapeDesc.surfaceType == ShapeDesc.SKIN:

		#extract the surface geometry
		geo = meshUtils.extractMeshForJoints( shapeDesc.joints, expand=shapeDesc.expand )

		#if the geo is None, use the default control representation instead
		writeTrigger = True
		if geo is None:
			writeTrigger = False
			curveShapeFile = getFileForShapeName( ShapeDesc.DEFAULT_TYPE )
			createCmd = ''.join( curveShapeFile.read() )
			mel.eval( createCmd )
			geo = ls( sl=True )[ 0 ]

		pymelCore.parent( geo, obj )
		makeIdentity( geo, a=True, s=True, r=True, t=True )

		pymelCore.parent( listRelatives( geo, s=True, pa=True ), obj, add=True, s=True )
		delete( geo )

		#when selected, turn the mesh display off, and only highlight edges
		if writeTrigger:
			triggered.Trigger.CreateTrigger( str( obj ), cmdStr="for( $s in `listRelatives -s #` ) setAttr ( $s +\".displayEdges\" ) 2;" )


	#build a shader for the control
	if colour is not None:
		colours.setObjShader( obj, colours.getShader( colour, True ) )


	#add to a selection set if desired
	if qss is not None:
		qss.add( obj )


	#hide and lock attributes
	attrState( obj, lockAttrs, lock=True )
	attrState( obj, hideAttrs, show=False )


	return obj


def buildControlAt( name, *a, **kw ):
	kw[ 'constrain' ] = False
	return buildControl( name, *a, **kw )


def buildNullControl( name, *a, **kw ):
	kw[ 'shapeDesc' ] = SHAPE_NULL
	kw[ 'oriented' ] = False
	kw[ 'constrain' ] = False

	return buildControl( name, *a, **kw )


def buildAlignedNull( alignTo, name=None, *a, **kw ):
	if name is None:
		name = 'alignedNull'

	if not isinstance( alignTo, PyNode ):
		alignTo = PyNode( alignTo )

	return buildControl( name, alignTo, shapeDesc=SHAPE_NULL, constrain=False, oriented=False, freeze=False, *a, **kw )


def setItemRigControl( item, control ):
	'''
	used to associate an item within a skeleton part with a rig control
	'''
	item, control = map( PyNode, [item, control] )
	if not item.hasAttr( '_skeletonPartRigControl' ):
		item.addAttr( '_skeletonPartRigControl', at='message' )

	connectAttr( control.message, item._skeletonPartRigControl, f=True )

	return True


def getItemRigControl( item ):
	'''
	returns the control associated with the item within a skeleton part, or None
	if there is no control driving the item
	'''
	item = PyNode( item )
	if item.hasAttr( '_skeletonPartRigControl' ):
		cons = item._skeletonPartRigControl.listConnections( d=False )
		if cons:
			return cons[ 0 ]

	return None


SHAPE_TO_COMPONENT_NAME = { 'nurbsSurface': 'cv',
                            'nurbsCurve': 'cv',
                            'mesh': 'vtx' }

def getShapeStrs( obj ):
	'''
	returns a list of names to refer to all components for all shapes
	under the given object
	'''
	global SHAPE_TO_COMPONENT_NAME

	geo = []
	shapes = listRelatives( obj, s=1, pa=1 )
	for s in shapes:
		nType = str( nodeType( s ) )
		cName = SHAPE_TO_COMPONENT_NAME[ nType ]
		geo.append( "%s.%s[*]" % (s, cName) )

	return geo


def getControlShapeFiles():
	dir = CONTROL_DIRECTORY
	if isinstance( dir, basestring ):
		dir = Path( dir )

	if not isinstance( dir, Path ) or not dir.exists:
		dir = Path( __file__ ).up()

	shapes = []
	if dir.exists:
		shapes = [ f for f in dir.files() if f.hasExtension( 'shape' ) ]

	if not shapes:
		searchPaths = map( Path, sys.path )
		searchPaths += map( Path, os.environ.get( 'MAYA_SCRIPT_PATH', '' ).split( ';' ) )
		searchPaths = removeDupes( searchPaths )

		for d in searchPaths:
			try: shapes += [ f for f in d.files() if f.hasExtension( 'shape' ) ]
			except WindowsError: continue

	return shapes

CONTROL_SHAPE_FILES = getControlShapeFiles()
CONTROL_SHAPE_DICT = {}

for f in CONTROL_SHAPE_FILES:
	CONTROL_SHAPE_DICT[ f.name().split( '.' )[ -1 ].lower() ] = f


def getFileForShapeName( shapeName ):
	theFile = CONTROL_SHAPE_DICT.get( shapeName.lower(), None )
	return theFile


#end
