import maya.cmds as cmd, api
from names import *
from vectors import *
import mayaVectors
import triggered
import maya.OpenMaya as OpenMaya


eul = api.OpenMaya.MEulerRotation

AXES = [ "x", "y", "z" ]
kROOS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]
kM_ROOS = [eul.kXYZ, eul.kYZX, eul.kZXY, eul.kXZY, eul.kYXZ, eul.kZYX]
def align( src, tgt, key=False ):
	'''
	this is separated into a separate proc, because its less "user friendly" ie require less syntax to work
	its better to call zooAlign in non speed intensive operations because the syntax for this command may change
	if the scope of the script is expanded in future - ie I add more functionality
	'''
	try:
		#grab the positions and rotations of the src object in world space
		srcRp = OpenMaya.MVector( *cmd.getAttr( src +'.rp' )[0] )
		srcMatrix = api.getMDagPath( src ).inclusiveMatrix()
		srcRp *= srcMatrix

		tgtRp = OpenMaya.MVector( *cmd.getAttr( tgt +'.rp' )[0] )
		tgtMatrix = api.getMDagPath( tgt ).exclusiveMatrix()
		tgtMatrixInv = api.getMDagPath( tgt ).exclusiveMatrixInverse()
		tgtRp *= tgtMatrix

		print mayaVectors.MayaVector( tgtRp )
		xformMatrix = srcMatrix * tgtMatrixInv
		new = mayaVectors.MayaMatrix( xformMatrix )

		pos = new.get_position() - mayaVectors.MayaVector( tgtRp ) + mayaVectors.MayaVector( srcRp )
		cmd.setAttr( tgt +'.t', *pos )
		cmd.setAttr( tgt +'.r', *new.get_rotXYZ( asdeg=True ) )
		raise Exception

		srcRo = kM_ROOS[ cmd.getAttr( src +".ro" ) ]
		tgtRo = kM_ROOS[ cmd.getAttr( tgt +".ro" ) ]
		rot = OpenMaya.MVector( *cmd.xform(src, q=True, ws=True, ro=True) )
		rot = OpenMaya.MEulerRotation( rot, srcRo ).asMatrix()
		tgtXformMatrixInv = api.getMDagPath( tgt ).exclusiveMatrixInverse()
	except RuntimeError, x:
		print 'ERRR', x
		return

	#so if the rotation orders are different, we need to deal with that

	#tgtRo = cmd.getAttr( tgt +".ro" )
	#if srcRo != tgtRo:
		#cmd.setAttr(tgt +".ro", srcRo)

	#transform the world space position and rotation to the tgt object's local space
	pos = pos * tgtXformMatrixInv
	rot = rot * tgtXformMatrixInv

	rot = mayaVectors.MayaMatrix( rot )
	rot = getattr(rot, 'get_rot' + kROOS[ tgtRo ].upper())( asdeg=True )

	#rot = OpenMaya.MTransformationMatrix( rot ).eulerRotation()
	#rot = Angle(rot.x, True).degrees, Angle(rot.y, True).degrees, Angle(rot.z, True).degrees
	print rot

	strT = tgt +'.t'
	strR = tgt +'.r'
	for ax, p, r in zip( AXES, pos, rot ):
		try:
			print strT + ax, p
			cmd.setAttr(strT + ax, p)
		except RuntimeError: print 'err' #pass

		try:
			print strR + ax, r
			cmd.setAttr(strR + ax, r)
		except RuntimeError: pass


	#now restore the original rotation order
	#if srcRo != tgtRo:
		#cmd.xform(tgt, p=True, roo=kROOS[ tgtRo ])

	if key:
		cmd.setKeyframe(tgt, at='t', at='r')


def transfer( src, tgt, instance=False, matchRo=True ):
	'''
	this is the core proc for node duplication/instancing animation transfers. you can call this proc
	directly, but it was meant to be called from the zooXferBatch command. this command donly deals with
	a single source, single target. it therefore must be called once for each source object
	'''
	try:
		attribs = cmd.listAttr(src, keyable=True, visible=True, scalar=True, multi=True)
	except RuntimeError: return

	for attrib in attribs:
		tgtAttrPath = '%s.%s' % (tgt, attrib )
		try:
			#### can remove this - wrap the setAttr below in a try block instead, and remove isTgtSettable if test below...
			isTgtSettable = cmd.getAttr(tgtAttrPath, settable=True)
		except RuntimeError:
			continue

		if not isTgtSettable:
			continue

		if matchRo:
			try:
				cmd.setAttr(tgt +".ro", cmd.getAttr(src +".ro"))
			except RuntimeError: pass

		srcAttrPath = '%s.%s' % (src, attrib)
		srcAnimCurveInfo = cmd.listConnections(srcAttrPath, d=False, connections=False, plugs=True, type='animCurve')
		if srcAnimCurveInfo is None:
			continue

		toks = srcAnimCurveInfo[0].split( '.' )
		srcAnimCurveName, srcAnimCurveOut = toks

		#if the user doesn't want to instance the anim curves, then duplicate the anim curve nodes
		if not instance:
			srcAnimCurveName = cmd.duplicate( srcAnimCurveName )[0]

		cmd.connectAttr(tgtAttrPath, f='%s.%s' % (srcAnimCurveName, srcAnimCurveOut))


def transferAdd( src, tgt, range=None, tgtTime=None, matchRo=False ):
	'''
	this is the core proc for copy/paste animation transfers. like the transfer command, this proc only
	works with a single source, single target
	'''
	#if there are no keys, quit
	try:
		if cmd.keyframe(src, q=True, kc=True):
			return
	except RuntimeError: return

	time = tgtTime
	if tgtTime is None:
		time = cmd.currentTime(q=True)

	#match the rotation orders of the objects.
	if matchRo:
		try:
			cmd.setAttr(tgt +".ro", cmd.getAttr(src +".ro"))
		except RuntimeError:
			pass

	#finally, perform the copy - this may fail as we still haven't validated the existence of tgt...
	try:
		cmd.copyKey(src, time=range, hierarchy='none', animation='objects', o='curve')
		cmd.pasteKey(tgt, time=time, option='merge', animation='objects')
	except RuntimeError:
		return


@api.d_noAutoKey
@api.d_disableViews
def trace( srcList, tgtList, keysOnly=True, keysOnlyRotate=False, matchRo=False, processPostCmds=True, sortByHeirarchy=True, start=None, end=None ):
	'''
	given a list of source objects, and a list of targets, trace all source objects to the corresponding
	objects in the target array

	unlike the core functions for the transfer and add function, the trace
	function takes an array of source objects and an array of target objects. this is because the proc
	steps through all frames specified by the user. knowing all the objects in advance allows the proc
	to trace each object on a single frame before advancing to the next. this saves having to step through
	all frames once for each object
	'''
	#first, make sure the src and tgt lists contain only valid items
	cleanSrc = []
	cleanTgt = []
	for src, tgt in zip(srcList, tgtList):
		if cmd.objExists(src) and cmd.objExists(tgt):
			cleanSrc.append( src )
			cleanTgt.append( tgt )

	srcList = cleanSrc
	tgtList = cleanTgt

	try:
		timeList = cmd.keyframe(srcList, q=True, tc=True)
	except RuntimeError:
		print 'no src objects to trace'
		return

	progress = 0
	numSrcs = len( srcList )
	numTgts = len( tgtList )
	increment = 100 / float( numSrcs )

	#make sure the start time is smaller than the end time, and turn off autokey
	start = min(start, end)
	end = max(start, end)

	#sort the targets properly - we want the targets sorted heirarchically - but we also need to sort the source objects the exact same way
	if sortByHeirarchy:
		orderList = api.mel.zooGetHeirarchyLevels( tgtList )
		srcList = api.mel.zooOrderArrayUsing_str( srcList, orderList )
		tgtList = api.mel.zooOrderArrayUsing_str( tgtList, orderList )

	cmd.progressWindow(title="Trace in progress", progress=int( progress ), isInterruptable=True)

	#if keys only is non-zero, the create an array with all key times
	if keysOnly > 0:
		timeList = set( timeList )
		timeList.sort()

	#if its not keys only, build a list of each frame to trace
	if keysOnly == 0:
		timeList = range(start, end+1)
	#if keys only is 2, this means trace only keys within a given time range - so crop the key time array to suit
	elif keysOnly == 2:
		#timeList = api.mel.zooCropArray_float(timeList, start, end)
		timeList = [t for t in set( timeList ) if start <= t <= end]
		timeList.sort()

	#if there are no keys in the key list, issue a warning
	try:
		timeList[0]
	except IndexError:
		cmd.progressWindow(ep=True)
		print "no keys on source"
		return

	#match the rotation orders of the objects.
	if matchRo:
		for src, tgt in zip( srcList, tgtList ):
			try:
				cmd.setAttr( tgt +".ro", cmd.getAttr( src +".ro" ))
			except RuntimeError: continue

	#create an array with post cmd state
	postCmds = []
	for src, tgt in zip( srcList, tgtList ):
		cmd = api.mel.zooGetPostTraceCmd( tgt )
		if cmd:
			postCmds.append( api.mel.zooPopulateCmdStr(tgt, cmd, [src]) )

	for t in timeList:
		if cmd.progressWindow(q=True, isCancelled=True):
			break

		cmd.currentTime(t)
		for src, tgt, postCmd in zip( srcList, tgtList, postCmds ):
			#update progress window
			progress += increment
			cmd.progressWindow(e=True, progress=int( progress ), status=tgt)

			#if we're doing keys only, make sure there is a key on the current frame of the src object before doing the trace
			didTrace = 0
			if keysOnly:
				if cmd.keyframe(src, t=t, q=True, kc=True):
					traceTime( src, tgt, t, keysOnly, keysOnlyRotate )
					didTrace = 1

			#otherwise, just do the trace
			else:
				traceTime( src, tgt, t, keysOnly, keysOnlyRotate )
				didTrace = 1

			#execute any post trace commands on the tgt object
			if processPostCmds and didTrace:
				if postCmd != "":
					try:
						api.mel.eval( postCmd )
					except:
						print "the post trace command failed"

	cmd.progressWindow(endProgress=True)


transformAttrs_t = set([ "translateX", "translateY", "translateZ" ])
transformAttrs_r = set([ "rotateX", "rotateY", "rotateZ" ])
transformAttrs = transformAttrs_t.union( transformAttrs_r )
def traceTime( src, tgt, time, keysOnly, keysOnlyRotate ):
	'''
	this proc snaps the target to the source object, and matches any attributes on the target to
	corresponding attributes on the source if they exist. this proc is called for each object on each
	frame in the target list by the zooXferTrace proc

	keysOnlyRotate only creates keys on rotation channels if there is a key on the source rotation channel - if its on then
	its possible that rotations won't be the same orientation
	'''
	align(src, tgt, False, False)

	#so now go and set a keyframe for the transform attributes that are keyed on the source object for this frame
	if keysOnly:
		for tAttr in transformAttrs_t:
			if cmd.keyframe('%s.%s' % (src, tAttr), t=time, q=True, kc=True):
				cmd.setKeyframe('%s.%s' % (tgt, tAttr))

		if keysOnlyRotate:
			for rAttr in transformAttrs_r:
				if cmd.keyframe('%s.%s' % (src, rAttr), t=time, q=True, kc=True):
					cmd.setKeyframe('%s.%s' % (tgt, rAttr))

		elif cmd.keyframe(src +'.r', t=time, q=True, kc=True):
			for rAttr in transformAttrs_r:
				cmd.setKeyframe('%s.%s' % (tgt, rAttr))

	#if keysonly is off, then just set keys on all transform attrs
	else:
		cmd.setKeyframe( tgt +".t", tgt +".r" )

	#remove all transform attrs from the list of keyable attrs...
	attrs = set( cmd.listAttr(src, keyable=True, visible=True, scalar=True, multi=True) )
	attrs = attrs.difference( transformAttrs )
	for attr in attrs:
		try:
			tgtAttrpath = '%s.%s' % (tgt, attr)
			if cmd.getAttr(tgtAttrpath, settable=True, keyable=True):
				#if keysOnly is on, check to see if there is a key on the source attr
				if keysOnly:
					if cmd.keyframe('%s.%s' % (src, attr), q=True, kc=True):
						cmd.setKeyframe(tgt, at=attr, v=cmd.getAttr( '%s.%s' % (src, attr)))
				#otherwise just set a key anyway
				else:
					cmd.setKeyframe(tgt, at=attr, v=cmd.getAttr( '%s.%s' % (src, attr)))
		except: continue


#end