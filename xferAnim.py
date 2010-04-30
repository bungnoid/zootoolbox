from pymel.core import *
from names import *
from vectors import *
from filesystem import removeDupes

import api

import mayaVectors
import triggered
import maya.OpenMaya as OpenMaya


Transform = nt.Transform
eul = api.OpenMaya.MEulerRotation

AXES = [ "x", "y", "z" ]
kROOS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]
kM_ROOS = [eul.kXYZ, eul.kYZX, eul.kZXY, eul.kXZY, eul.kYXZ, eul.kZYX]


def align( src=None, tgt=None, key=False, pivotOnly=False ):
	'''
	this is separated into a separate proc, because its less "user friendly" ie require less syntax to work
	its better to call zooAlign in non speed intensive operations because the syntax for this command may change
	if the scope of the script is expanded in future - ie I add more functionality
	'''

	if src is None or tgt is None:
		sel = selected()
		if src is None: src = sel[ 0 ]
		if tgt is None: tgt = sel[ 1 ]

	#these two lines check to make sure the objects to be aligned are both transform (or joint) nodes, otherwise, it quits
	if not isinstance( src, Transform ) or not isinstance( tgt, Transform ):
		return

	global AXES

	pos = xform( src, q=True, ws=True, rp=True )
	rot = xform( src, q=True, ws=True, ro=True )

	#create a list of all the axes to look at - we will check all these axes to make sure they're not locked
	#creating a constraint on a locked axis will give us an error
	moveCmdKw = { 'a': True, 'ws': True, 'rpr': True }
	rotateCmdKw = { 'a': True, 'ws': True }
	rotateCmdAxisAccum = ''
	performMove = False
	performRotate = False

	for ax in AXES:
		if tgt.attr( 't'+ ax ).isSettable():
			moveCmdKw[ ax ] = True
			performMove = True
		if tgt.attr( 'r'+ ax ).isSettable():
			rotateCmdAxisAccum += ax
			performRotate = True

	if pivotOnly:
		if performMove:
			move( tgt.rp, tgt.sp, **moveCmdKw )
	else:
		#so if the rotation orders are different, we need to deal with that because the xform cmd doesn't
		srcRo = src.ro.get()
		tgtRo = tgt.ro.get()
		if srcRo != tgtRo:
			tgt.ro.set( srcRo )

		if performMove:
			move( tgt, pos, **moveCmdKw )
		if performRotate:
			rotateCmdKw[ 'rotate'+ rotateCmdAxisAccum.upper() ] = True
			rotate( tgt, rot, **rotateCmdKw )

		#now restore the original rotation order
		if srcRo != tgtRo:
			xform( tgt, p=True, roo=kROOS[ tgtRo ] )

	if key:
		setKeyframe( tgt, at='t', at='r' )


TRACE_MODES = TRACE_ALL_FRAMES, TRACE_KEYFRAMES, TRACE_ALL_KEYFRAMES = range( 3 )

def trace( srcs, tgts, traceMode=TRACE_KEYFRAMES, keysOnlyRotate=True, matchRotationOrder=True, processPostCmds=True, sortByHeirarchy=True, start=None, end=None ):
	'''
	given a list of source objects, and a list of targets, trace all source objects to the corresponding
	objects in the target array

	unlike the core functions for the transfer and add function, the trace
	function takes an array of source objects and an array of target objects. this is because the proc
	steps through all frames specified by the user. knowing all the objects in advance allows the proc
	to trace each object on a single frame before advancing to the next. this saves having to step
	through all frames once for each object
	'''

	global Transform

	if start is None:
		start = playbackOptions( q=True, min=True )

	if end is None:
		end = playbackOptions( q=True, max=True )

	#first, make sure the src and tgt lists contain only valid items
	cleanSrcs = []
	cleanTgts = []
	for src, tgt in zip( srcs, tgts ):
		if objExists( src ) and objExists( tgt ):
			cleanSrcs.append( src )
			cleanTgts.append( tgt )

	srcs = cleanSrcs
	tgts = cleanTgts

	if not srcs and not tgts:
		print "xferAnim.trace()  no objects to trace"

	timeList = keyframe( srcs, q=True, tc=True )
	numSrcs = len( srcs )
	numTgts = len( tgts )

	#make sure the start time is smaller than the end time, and turn off autokey
	start, end = sorted( [start, end] )

	#sort the targets properly - we want the targets sorted heirarchically - but we also need to sort the source objects the exact same way
	if sortByHeirarchy:
		sortByTgtHierarchy = [ (len( list( api.iterParents( t ) ) ), s, t) for s, t in zip( srcs, tgts ) ]
		sortByTgtHierarchy.sort()

		srcs, tgts = [], []
		for n, s, t in sortByTgtHierarchy:
			srcs.append( s )
			tgts.append( t )

	#if keys only is non-zero, the create an array with all key times
	if traceMode:
		timeList.sort()
		timeList = removeDupes( timeList )

	#if keys only is 2, this means trace only keys within a given time range - so crop the key time array to suit
	if traceMode == TRACE_KEYFRAMES:
		timeList = [ t for t in timeList if t >= start and t <= end ]

	#if its not keys only, build a list of each frame to trace
	elif keysOnly == TRACE_ALL_FRAMES:
		timeList = range( end - start + 1 )

	#if there are no keys in the key list, issue a warning
	if not timeList:
		print "no keys on source"
		return

	#match the rotation orders of the objects.
	if matchRotationOrder:
		for src, tgt in zip( srcs, tgts ):
			if isinstance( src, Transform ) and isinstance( tgt, Transform ):
				tgt.ro.set( src.ro.get() )

	#create an array with post cmd state
	postCmds = []
	for src, tgt in zip( srcs, tgts ):
		cmd = mel.zooGetPostTraceCmd( tgt )
		postCmds.append( mel.zooPopulateCmdStr( tgt, cmd, [src] ) )

	for i, t in enumerate( timeList ):
		currentTime( t )
		for src, tgt, postCmd in zip( srcs, tgts, postCmds ):
			#if we're doing keys only, make sure there is a key on the current frame of the src object before doing the trace
			didTrace = False
			if traceMode:
				if keyframe( src, t=(t,), q=True, kc=True ):
					traceTime( src, tgt, t, traceMode, keysOnlyRotate )
					didTrace = True

			#otherwise, just do the trace
			else:
				traceTime( src, tgt, t, keysOnly, keysOnlyRotate )
				didTrace = True

			#execute any post trace commands on the tgt object
			if processPostCmds and didTrace:
				if postCmd:
					#if( catch(eval($cmd))) warning "the post trace command failed";
					pass

TRANSFORM_ATTRS = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz')
def traceTime( src, tgt, time, traceMode, keysOnlyRotate ):
	'''
	this proc snaps the target to the source object, and matches any attributes on the target to
	corresponding attributes on the source if they exist. this proc is called for each object on each
	frame in the target list by the zooXferTrace proc

	keysOnlyRotate only creates keys on rotation channels if there is a key on the source rotation channel - if its on then
	its possible that rotations won't be the same orientation
	'''
	global AXES, TRANSFORM_ATTRS, Transform

	attrsToTrace = listAttr( src, shortNames=True, keyable=True, visible=True, scalar=True, multi=True )

	for attr in attrsToTrace:
		#skip transform attributes
		if attr in TRANSFORM_ATTRS:
			continue

		if tgt.hasAttr( attr ):
			tgtAttr = tgt.attr( attr )
			if tgtAttr.isSettable() and tgtAttr.isKeyable():
				#if keysOnly is on, check to see if there is a key on the source attr
				srcAttr = src.attr( attr )
				if traceMode:
					if keyframe( srcAttr, q=True, kc=True ):
						setKeyframe( tgtAttr, v=srcAttr.get() )

				#otherwise just set a key anyway
				else:
					setKeyframe( tgtAttr, v=srcAttr.get() )

	if isinstance( src, Transform ) and isinstance( tgt, Transform ):
		align( src, tgt )

		#so now go and set a keyframe for the transform attributes that are keyed on the source object for this frame
		if traceMode:
			for ax in AXES:
				if keyframe( src.attr( 't'+ ax ), t=(time,), q=True, kc=True ):
					setKeyframe( tgt.attr( 't'+ ax ) )

			if keysOnlyRotate:
				for ax in AXES:
					if keyframe( src.attr( 'r'+ ax ), t=(time,), q=True, kc=True ):
						setKeyframe( tgt.attr( 'r'+ ax ) )

			elif keyframe( src.r, t=(time,), q=True, kc=True ):
				for ax in AXES:
					setKeyframe( tgt.attr( 'r'+ ax ) )

		#if traceMode is off, then just set keys on all transform attrs
		else:
			setKeyframe( tgt.t, tgt.r )


#end