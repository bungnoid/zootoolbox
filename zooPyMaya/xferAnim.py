
from maya.cmds import *
from maya import OpenMaya

from zooPy.path import Path
from zooPy.presets import Preset, GLOBAL, LOCAL
from zooPy.misc import removeDupes
from zooPy.names import *
from zooPy.vectors import *

from melUtils import mel
from picker import resolveCmdStr
from mappingUtils import *
from melUtils import printWarningStr, printErrorStr
from mayaDecorators import d_noAutoKey, d_unifyUndo, d_disableViews, d_restoreTime

import melUtils
import maya


TOOL_NAME = 'xferAnim'
EXTENSION = 'postTraceScheme'

eul = OpenMaya.MEulerRotation

AXES = "x", "y", "z"
kROOS = "xyz", "yzx", "zxy", "xzy", "yxz", "zyx"
kM_ROOS = [eul.kXYZ, eul.kYZX, eul.kZXY, eul.kXZY, eul.kYXZ, eul.kZYX]

POST_TRACE_ATTR_NAME = 'xferPostTraceCmd'
MATRIX_ROTATION_ORDER_CONVERSIONS_TO = Matrix.ToEulerXYZ, Matrix.ToEulerYZX, Matrix.ToEulerZXY, Matrix.ToEulerXZY, Matrix.ToEulerYXZ, Matrix.ToEulerZYX


def bakeRotateDelta( src, ctrl, presetStr ):
	'''
	Bakes a post trace command into the ctrl object such that when ctrl is aligned to src (with post
	trace cmds enabled) src and tgt are perfectly aligned.

	This is useful because rig controls are rarely aligned to the actual joints they drive, but it
	can be useful when you have motion from a tool such as SFM, or generated from motion capture that
	needs to be applied back to a rig.
	'''
	mat_j = Matrix( getAttr( '%s.worldInverseMatrix' % srcJoint ) )
	mat_c = Matrix( getAttr( '%s.worldMatrix' % jointControl ) )

	#generate the matrix describing offset between joint and the rig control
	mat_o = mat_j * mat_c

	#put into space of the control
	rel_mat = mat_o * Matrix( getAttr( '%s.parentInverseMatrix' % jointControl ) )

	#now figure out the euler rotations for the offset
	ro = getAttr( '%s.ro' % jointControl )
	offset = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ ro ]( rel_mat, True )

	cmd.rotate( asEuler[ 0 ], asEuler[ 1 ], asEuler[ 2 ], jointControl, relative=True, os=True )

	mel.zooSetPostTraceCmd( ctrl, presetStr % offset )
	mel.zooAlign( "-src %s -tgt %s -postCmds 1" % (src, ctrl) )

	return offset


def bakeManualRotateDelta( src, ctrl, presetStr ):
	'''
	When you need to apply motion from a skeleton that is completely different from a skeleton driven
	by the rig you're working with (transferring motion from old assets to newer assets for example)
	you can manually align the control to the joint and then use this function to generate offset
	rotations and bake a post trace cmd.
	'''
	srcInvMat = Matrix( getAttr( '%s.worldInverseMatrix' % src ) )
	ctrlMat = Matrix( getAttr( '%s.worldMatrix' % ctrl ) )

	#generate the offset matrix as
	mat_o = ctrlMat * srcInvMat

	#now figure out the euler rotations for the offset
	ro = getAttr( '%s.ro' % ctrl )
	rotDelta = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ ro ]( mat_o, True )

	#now get the positional delta
	posDelta = Vector( xform( src, q=True, ws=True, rp=True ) ) - Vector( xform( ctrl, q=True, ws=True, rp=True ) )
	posDelta *= -1
	ctrlParentInvMat = Matrix( getAttr( '%s.parentInverseMatrix' % ctrl ) )
	posDelta = posDelta * ctrlParentInvMat

	#construct a list to use for the format str
	formatArgs = tuple( rotDelta ) + tuple( posDelta )

	#build the post trace cmd str
	mel.zooSetPostTraceCmd( ctrl, presetStr % formatArgs )

	return rotDelta


#this dict contains UI labels and a presets for offset commands...  when adding new ones make sure it contains exactly three format strings...
CMD_PRESETS = CMD_DEFAULT, CMD_SRC_TGT, CMD_IK_FOOT, CMD_COPY = ( ('rotate -r -os %0.2f %0.2f %0.2f #; move -r -os %0.4f %0.4f %0.4f #;', bakeManualRotateDelta),
                                                                  ('rotate -r -os %0.2f %0.2f %0.2f #; move -r -os %0.4f %0.4f %0.4f #;', bakeRotateDelta),
                                                                  ('rotate -r -os %0.2f %0.2f %0.2f #; move -r -os %0.4f %0.4f %0.4f #; traceToe # %%opt0%% x z;', bakeRotateDelta),
                                                                  ('float $f[] = `getAttr %%opt0%%.r`; setAttr #.rx $f[0]; setAttr #.ry $f[1]; setAttr #.rz $f[2];', None) )


def savePostTraceScheme( presetName ):
	'''
	stores all post trace commands found in the current scene out to disk
	'''

	#grab a list of transforms with post trace commands on them
	postTraceNodes = ls( "*.%s" % POST_TRACE_ATTR_NAME, r=True )

	postTraceDict = {}
	for n in postTraceNodes:
		noNS = n.split( ':' )[ -1 ]  #strip the namespace
		noNS = noNS.split( '.' )[ 0 ]  #strip the attribute
		postTraceDict[ noNS ] = getAttr( n )

	xportDict = melUtils.writeExportDict( TOOL_NAME, 0 )

	p = Preset( GLOBAL, TOOL_NAME, presetName, EXTENSION )
	p.pickle( (xportDict, postTraceDict) )

	return p


def clearPostTraceScheme():
	postTraceNodes = ls( "*.%s" % POST_TRACE_ATTR_NAME, r=True )
	for n in postTraceNodes:
		#ideally delete the attribute
		try:
			deleteAttr( n )

		#this can happen if the node is referenced - so just set it to an empty string...
		except RuntimeError:
			setAttr( n, '', typ='string' )


def loadPostTraceSchemeFilepath( presetFile ):
	'''
	re-applies a stored post trace command scheme back to the controls found in the current scene
	'''

	#first we need to purge all existing post trace commands
	clearPostTraceScheme()

	if not isinstance( presetFile, Path ):
		presetFile = Path( presetFile )

	if not presetFile.isfile():
		raise IOError, "no such preset"

	xportDict, postTraceDict = presetFile.unpickle()

	for n, postTraceCmd in postTraceDict.iteritems():
		n = n.split( '.' )[ 0 ]  #strip off the attribute
		possibles = ls( '*%s' % n, r=True )
		if possibles:
			nInScene = possibles[0]
			mel.zooSetPostTraceCmd( nInScene, postTraceCmd )


def loadPostTraceScheme( presetName ):
	'''
	added so the load save commands are symmetrical - its sometimes more convenient to load from just
	a preset name instead of a full filepath...  esp when debugging
	'''
	p = findPreset( presetName, TOOL_NAME, EXTENSION, LOCAL )
	return loadPostTraceSchemeFilepath( p )


def autoGeneratePostTraceScheme( mapping, presetName=None ):
	cmdStr, cmdFunc = CMD_DEFAULT
	for src, tgt in mapping.iteritems():
		src, tgt = findItem( src ), findItem( tgt )
		if not src:
			continue

		if not tgt:
			continue

		t, r = getAttr( '%s.t' % tgt )[0], getAttr( '%s.r' % tgt )[0]
		print tgt, cmdFunc( src, tgt, cmdStr )

		try: setAttr( '%s.t' % tgt, *t )
		except RuntimeError: pass

		try: setAttr( '%s.r' % tgt, *r )
		except RuntimeError: pass

	if presetName is not None:
		print 'SAVING TO', presetName
		savePostTraceScheme( presetName )


def getMappingFromPreset( presetName ):
	'''
	parses a mapping file and returns the mapping dict
	'''
	p = findPreset( presetName, 'zoo', 'mapping', LOCAL )
	return p.read()


def getPostTraceCmd( node ):
	return getAttr( '%s.%s' % (node, POST_TRACE_ATTR_NAME) )


def executePostTraceCmd( node ):
	cmdStr = getPostTraceCmd( node )
	resolvedCmdStr = resolveCmdStr( cmdStr, node, [] )
	mel.eval( resolvedCmdStr )


"""
def trace( srcs, tgts, keysOnly=True, matchRotationOrder=True, processPostCmds=True, sortByHeirarchy=True, start=None, end=None, skip=1 ):
	if start is None:
		keys = keyframe( srcs, q=True )
		keys.sort()
		start = keys[0]

	if end is None:
		keys = keyframe( srcs, q=True )
		keys.sort()
		end = keys[-1]

	melUtils.mel.zooXferAnimUtils()
	melUtils.mel._zooXferTrace( srcs, tgts, 2 if keysOnly else 0, 0, int( matchRotationOrder ), int( processPostCmds ), int( sortByHeirarchy ), int( start ), int( end ), int( skip ) )
"""


def constructDummyParentConstraint( src, tgt ):
	grp = group( em=True )
	constraintNode = parentConstraint( src, grp )[0]
	parent( constraintNode, w=True )
	delete( grp )

	connectAttr( '%s.ro' % tgt, '%s.constraintRotateOrder' % constraintNode )
	connectAttr( '%s.rotatePivotTranslate' % tgt, '%s.constraintRotateTranslate' % constraintNode )
	connectAttr( '%s.rotatePivot' % tgt, '%s.constraintRotatePivot' % constraintNode )
	connectAttr( '%s.parentInverseMatrix' % tgt, '%s.constraintParentInverseMatrix' % constraintNode )

	return constraintNode


def getParentCount( node ):
	count = 1
	nodeParent = node
	while nodeParent:
		nodeParent = listRelatives( nodeParent, p=True, pa=True )
		if nodeParent is None:
			break

		count += 1

	return count


class TracePair(object):
	SHORT_TRANSFORM_ATTRS = ('tx', 'ty', 'tz',
	                         'rx', 'ry', 'rz')

	def __init__( self, src, tgt ):
		self._src = src
		self._tgt = tgt
		self._isTransform = objectType( src, isAType='transform' ) and objectType( tgt, isAType='transform' )

		self._keyTimeData = {}
		self._postTraceCmd = None
		self._constraint = None
		self._parentCount = getParentCount( tgt )
		self._attrsWeightedTangentsDealtWith = []
	def __repr__( self ):
		return '%s( "%s", "%s" )' % (type( self ).__name__, self._src, self._tgt)
	__str__ = __repr__
	def isTransform( self ):
		return self._isTransform
	def getSrcTgt( self ):
		return self._src, self._tgt
	def getParentCount( self ):
		return self._parentCount
	def getKeyTimes( self ):
		return self._keyTimeData.keys()
	def dealWithWeightedTangents( self, tgtAttrpath ):
		'''
		this is annoying - so maya has two types of curves - weighted and non-weighted tangent curves, and they've not compatible.
		so we need to see what the type of the curve we're querying and make sure the keys we trace have the same curve type.  this
		is easier said than done - the tgt object may already have keys.  if it does, we can just convert the curve right now and be
		done with it, but if it doesn't, then we need to convert the curve to weighted tangents after the first key is set, or mess
		with the users preferences.  neither is pretty...  god maya sucks
		'''
		if keyframe( tgtAttrpath, q=True, kc=True ):
			attr = tgtAttrpath[ tgtAttrpath.find( '.' ) + 1: ]
			srcAttrpath = '%s.%s' % (self._src, attr)
			srcWeightedTangentState = keyTangent( srcAttrpath, q=True, weightedTangents=True )[0]
			tgtWeightedTangentState = keyTangent( tgtAttrpath, q=True, weightedTangents=True )[0]
			if srcWeightedTangentState != tgtWeightedTangentState:
				keyTangent( tgtAttrpath, e=True, weightedTangents=srcWeightedTangentState )

			self._attrsWeightedTangentsDealtWith.append( tgtAttrpath )
	def preTrace( self ):
		if self._isTransform:
			if self._constraint is None:
				self._constraint = constructDummyParentConstraint( self._src, self._tgt )

		#now grab any other keyable attributes
		keyableAttrs = listAttr( self._src, keyable=True, scalar=True, shortNames=True ) or []
		for attr in keyableAttrs:
			tgtAttrpath = '%s.%s' % (self._tgt, attr)
			if not objExists( tgtAttrpath ):
				continue

			#check to see if we need to deal with weighted tangents
			srcAttrpath = '%s.%s' % (self._src, attr)
			if tgtAttrpath not in self._attrsWeightedTangentsDealtWith:
				self.dealWithWeightedTangents( tgtAttrpath )

			#now get the list of keys for the attribute and store that as well
			srcKeysTimes = keyframe( srcAttrpath, q=True )
			if srcKeysTimes:
				srcKeysInTangents = keyTangent( srcAttrpath, q=True, itt=True )
				srcKeysOutTangents = keyTangent( srcAttrpath, q=True, ott=True )

				srcKeysInX = keyTangent( srcAttrpath, q=True, ix=True )
				srcKeysInY = keyTangent( srcAttrpath, q=True, iy=True )
				srcKeysOutX = keyTangent( srcAttrpath, q=True, ox=True )
				srcKeysOutY = keyTangent( srcAttrpath, q=True, oy=True )

				#if the attr is a transform attr - set the srcAttrpath to the appropriate attribute on the constraint
				if attr in self.SHORT_TRANSFORM_ATTRS:
					srcAttrpath = '%s.c%s' % (self._constraint, attr)

				for keyTime, keyItt, keyOtt, ix, iy, ox, oy in zip( srcKeysTimes, srcKeysInTangents, srcKeysOutTangents, srcKeysInX, srcKeysInY, srcKeysOutX, srcKeysOutY ):
					self._keyTimeData.setdefault( keyTime, [] )
					self._keyTimeData[ keyTime ].append( (srcAttrpath, tgtAttrpath, keyItt, keyOtt, ix, iy, ox, oy) )

		#finally see if the node has a post trace cmd - if it does, track it
		postTraceCmdAttrpath = '%s.xferPostTraceCmd' % self._tgt
		if objExists( postTraceCmdAttrpath ):
			cmdStr = getAttr( postTraceCmdAttrpath )
			self._postTraceCmd = resolveCmdStr( cmdStr, self._tgt, [] )
	def traceFrame( self, keyTime ):
		if keyTime not in self._keyTimeData:
			return

		attrDataList = self._keyTimeData[ keyTime ]
		for attrData in attrDataList:

			#unpack the node data
			srcAttrpath, tgtAttrpath, keyItt, keyOtt, ix, iy, ox, oy = attrData

			#NOTE: setting itt and ott in the keyframe command doesn't work properly - if itt is spline and ott is stepped, maya sets them both to stepped...  win.
			setKeyframe( tgtAttrpath, v=getAttr( srcAttrpath ) )

			#check to see if we need to deal with weighted tangents
			#NOTE: we need to do this BEFORE setting any tangent data!
			if tgtAttrpath not in self._attrsWeightedTangentsDealtWith:
				self.dealWithWeightedTangents( tgtAttrpath )

			#need to special case this otherwise maya will screw up the stepped tangents on the out curve...  holy shit maya sucks  :(
			if keyOtt == 'step':
				keyTangent( tgtAttrpath, e=True, t=(keyTime,), itt=keyItt, ott=keyOtt )#, ix=ix, iy=iy )
			else:
				keyTangent( tgtAttrpath, e=True, t=(keyTime,), itt=keyItt, ott=keyOtt )#, ix=ix, iy=iy, ox=ox, oy=oy )

		#execute any post trace command for the tgt nodes on this keyframe
		if self._postTraceCmd:
			postTraceCmdStr = resolveCmdStr( self._postTraceCmd, self._tgt, [] )
			if postTraceCmdStr:
				maya.mel.eval( postTraceCmdStr )

				#once the post trace cmd has been executed, make sure to re-key each attribute with a key on this frame
				for attrData in attrDataList:
					tgtAttrpath = attrData[1]
					setKeyframe( tgtAttrpath )
	def postTrace( self ):
		if self._constraint:
			delete( self._constraint )
			self._constraint = None

		#run an euler filter on the rotation curves
		if self._isTransform:
			filterCurve( '%s.rx' % self._tgt, '%s.ry' % self._tgt, '%s.rz' % self._tgt, filter='euler' )


class Tracer(object):
	def __init__( self, keysOnly=True, matchRotationOrder=True, processPostCmds=True, sortByHeirarchy=True, start=None, end=None, skip=1 ):
		self._tracePairs = []

		self._keysOnly = keysOnly
		self._matchRotationOrder = matchRotationOrder
		self._processPostCmds = processPostCmds

		self._start = start
		self._end = end
		self._skipFrames = skip
	def setKeysOnly( self, state ):
		self._keysOnly = state
	def setMatchRotationOrder( self, state ):
		self._matchRotationOrder = state
	def setProcessPostCmds( self, state ):
		self._processPostCmds = state
	def setStart( self, frame ):
		self._start = frame
	def setEnd( self, frame ):
		self._end = frame
	def setSkip( self, count ):
		self._skipFrames = cound
	def _sortTransformNodes( self ):
		'''
		ensures all nodes in the _keysTransformAttrpathDict are sorted hierarchically
		'''

		parentCountDecoratedTracePairs = []
		for tracePair in self._tracePairs:
			parentCountDecoratedTracePairs.append( (tracePair.getParentCount(), tracePair) )

		parentCountDecoratedTracePairs.sort()
		tracePairs = [ tracePair for pCnt, tracePair in parentCountDecoratedTracePairs ]

		self._tracePairs = tracePairs
	def appendPair( self, src, tgt ):
		if not objExists( src ) or not objExists( tgt ):
			printWarningStr( "Either the src or tgt nodes don't exist!" )
			return

		self._tracePairs.append( TracePair( src, tgt ) )
	def setSrcsAndTgts( self, srcList, tgtList ):
		for src, tgt in zip( srcList, tgtList ):
			self.appendPair( src, tgt )
	def getKeyTimes( self ):
		'''
		returns a list of key times
		'''
		if self._keysOnly:
			keyTimes = []
			for tracePair in self._tracePairs:
				keyTimes += tracePair.getKeyTimes()

			keyTimes = list( set( keyTimes ) )  #this removes duplicates
			keyTimes.sort()

			return keyTimes
		else:
			start = self._start
			if start is None:
				start = playbackOptions( q=True, min=True )

			end = self._end
			if end is None:
				end = playbackOptions( q=True, max=True )

			keyTimes = range( start, end, self._skipFrames )
	def getTransformNodePairs( self ):
		transformNodePairs = []
		for tracePair in self._tracePairs:
			if tracePair.isTransform():
				transformNodePairs.append( tracePair )

		return transformNodePairs
	@d_unifyUndo
	@d_noAutoKey
	@d_disableViews
	@d_restoreTime
	def trace( self ):
		if not self._tracePairs:
			printWarningStr( "No objects to trace!" )
			return

		#wrap the following in a try so we can ensure cleanup gets called always
		try:

			#make sure the objects in the transform list are sorted properly
			self._sortTransformNodes()

			#run the pre-trace method on all tracePair instances
			for tracePair in self._tracePairs:
				tracePair.preTrace()

			#early out if there are no keyframes
			keyTimes = self.getKeyTimes()
			if not keyTimes:
				printWarningStr( "No keys to trace!" )
				return

			#match rotation orders if required
			transformTracePairs = list( self.getTransformNodePairs() )
			if self._matchRotationOrder:
				for tracePair in transformTracePairs:
					src, tgt = tracePair.getSrcTgt()
					if getAttr( '%s.ro' % tgt, se=True ):
						setAttr( '%s.ro' % tgt, getAttr( '%s.ro' % src ) )

			#clear out existing animation for the duration of the trace on target nodes
			for tracePair in self._tracePairs:
				src, tgt = tracePair.getSrcTgt()
				cutKey( tgt, t=(keyTimes[0], keyTimes[-1]), clear=True )

			#execute the traceFrame method for each tracePair instance
			for keyTime in keyTimes:
				currentTime( keyTime )
				for tracePair in self._tracePairs:
					tracePair.traceFrame( keyTime )

		#make sure the postTrace method gets executed once the trace finishes
		finally:
			for tracePair in self._tracePairs:
				tracePair.postTrace()


def trace( srcs, tgts, keysOnly=True, matchRotationOrder=True, processPostCmds=True, sortByHeirarchy=True, start=None, end=None, skip=1 ):
	tracer = Tracer( keysOnly, matchRotationOrder, processPostCmds, sortByHeirarchy, start, end, skip )
	tracer.setSrcsAndTgts( srcs, tgts )
	tracer.trace()


class AnimCurveCopier(object):
	def __init__( self, srcAnimCurve, tgtAnimCurve ):
		self._src = srcAnimCurve
		self._tgt = tgtAnimCurve
	def iterSrcTgtKeyIndices( self ):
		src, tgt = self._src, self._tgt
		srcIndices = getAttr( '%s.keyTimeValue' % src, multiIndices=True ) or []
		tgtIndices = getAttr( '%s.keyTimeValue' % tgt, multiIndices=True ) or []

		srcTimeValues = getAttr( '%s.keyTimeValue[*]' % src ) or []
		tgtTimeValues = getAttr( '%s.keyTimeValue[*]' % tgt ) or []

		zippedTgtData = zip( tgtIndices, tgtTimeValues )
		for srcIdx, (srcTime, srcValue) in zip( srcIndices, srcTimeValues ):
			for n, (tgtIdx, (tgtTime, tgtValue)) in enumerate( zippedTgtData ):
				if srcTime == tgtTime:
					yield (srcIdx, srcTime, srcValue), (tgtIdx, tgtTime, tgtValue)

					zippedTgtData = zippedTgtData[ n: ]  #chop off the values before this one - we don't need to iterate over them again...
					break
	def copy( self, values=True, tangents=True, other=True ):
		src, tgt = self._src, self._tgt

		for srcData, tgtData in self.iterSrcTgtKeyIndices():
			srcIdx, srcTime, srcValue = srcData
			tgtIdx, tgtTime, tgtValue = tgtData

			#if values:
				#setAttr( '%s.keyTimeValue[%d]' % (tgt, tgtIdx), tgtTime, srcValue )

			if tangents:
				setAttr( '%s.keyTanLocked[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanLocked[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyWeightLocked[%d]' % (tgt, tgtIdx), getAttr( '%s.keyWeightLocked[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanInX[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanInX[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanInY[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanInY[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanOutX[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanOutX[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanOutY[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanOutY[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanInType[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanInType[%d]' % (tgt, tgtIdx) ) )
				setAttr( '%s.keyTanOutType[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTanOutType[%d]' % (tgt, tgtIdx) ) )

			if other:
				setAttr( '%s.keyBreakdown[%d]' % (tgt, tgtIdx), getAttr( '%s.keyBreakdown[%d]' % (tgt, tgtIdx) ) )
				#setAttr( '%s.keyTickDrawSpecial[%d]' % (tgt, tgtIdx), getAttr( '%s.keyTickDrawSpecial[%d]' % (tgt, tgtIdx) ) )


def test():
	tracer = Tracer()
	tracer.setSrcsAndTgts( ['pSphere2', 'pCylinder1'], ['pSphere1', 'pCube1'] )
	tracer.trace()


#end