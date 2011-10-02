
import maya
import maya.cmds as cmd
from maya.cmds import getAttr, setAttr, objExists, createNode, xform, move, rotate, setKeyframe

from zooPy import names
from zooPyMaya.mayaDecorators import d_unifyUndo, d_noAutoKey, d_disableViews

_MAYA_VER = maya.mel.eval( 'getApplicationVersionAsFloat' )


class AnimLibError(Exception): pass


if _MAYA_VER <= 2009:
	def iterAtTimes( timeValues ):
		initialTime = cmd.currentTime( q=True )
		for time in timeValues:
			cmd.setAttr( 'time1.outTime', time )
			yield time

		cmd.currentTime( initialTime )
else:
	@d_disableViews
	def iterAtTimes( timeValues ):
		print 'DOOOOOING it'
		initialTime = cmd.currentTime( q=True )
		for time in timeValues:
			cmd.currentTime( time )
			yield time

		cmd.currentTime( initialTime )


class AttributeData(object):
	def __init__( self, attrPath ):
		self._value = getAttr( attrPath )
	def apply( self, attrPath, sourceRange, applyStart ):
		setAttr( attrPath, self._value )


class KeyframeData(tuple):
	DATA_IDX = TIME, VALUE, ITT, OTT, ITX, ITY, OTX, OTY, BREAKDOWN, TAN_LOCK, WEIGHT_LOCK, WEIGHTED, PRE_INF, POST_INF, CURVE_TYPE = range(15)

	def __new__( cls, attrPath ):
		animCurveNode = cmd.listConnections( attrPath, type='animCurve', d=False )
		if animCurveNode is None:
			return AttributeData( attrPath )

		animCurveNode = animCurveNode[0]
		times = getAttr( '%s.ktv[*].keyTime' % animCurveNode )
		values = getAttr( '%s.ktv[*].keyValue' % animCurveNode )

		itt = getAttr( '%s.kit[*]' % animCurveNode )
		ott = getAttr( '%s.kot[*]' % animCurveNode )

		itx = getAttr( '%s.kix[*]' % animCurveNode )
		ity = getAttr( '%s.kiy[*]' % animCurveNode )
		otx = getAttr( '%s.kox[*]' % animCurveNode )
		oty = getAttr( '%s.koy[*]' % animCurveNode )

		brk = getAttr( '%s.keyBreakdown[*]' % animCurveNode )
		tlk = getAttr( '%s.keyTanLocked[*]' % animCurveNode )
		wlk = getAttr( '%s.keyWeightLocked[*]' % animCurveNode )

		#if there is only one value in the array attributes above, maya in its infinite wisdom returns the value as a float, not a single element list.  well done.
		if len( times ) == 1:
			itt = [itt]
			ott = [ott]

			itx = [itx]
			ity = [ity]
			otx = [otx]
			oty = [oty]

		weighted = getAttr( '%s.wgt' % animCurveNode )
		preInf = getAttr( '%s.pre' % animCurveNode )
		postInf = getAttr( '%s.pst' % animCurveNode )
		curveType = cmd.nodeType( animCurveNode )

		return tuple.__new__( cls, (times, values, itt, ott, itx, ity, otx, oty, brk, tlk, wlk, weighted, preInf, postInf, curveType) )
	def constructNode( self, timeOffset=0 ):
		'''
		constructs an animCurve node using the data stored on the instance

		returns the node created
		'''
		animCurveNode = createNode( self[ self.CURVE_TYPE ] )

		#massage the time values
		times = [ t+timeOffset for t in self[ self.TIME ] ]
		values = self[ self.VALUE ]
		maxIdxVal = len( values ) - 1

		setKeyframe = cmd.setKeyframe
		for time, value in zip( times, values ):
			setKeyframe( animCurveNode, t=time, v=value )

		#set key data
		setAttr( '%s.wgt' % animCurveNode, self[ self.WEIGHTED ] )
		setAttr( '%s.pre' % animCurveNode, self[ self.PRE_INF ] )
		setAttr( '%s.pst' % animCurveNode, self[ self.POST_INF ] )

		setAttr( '%s.keyBreakdown[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.BREAKDOWN ] )
		setAttr( '%s.keyTanLocked[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.TAN_LOCK ] )
		setAttr( '%s.keyWeightLocked[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.WEIGHT_LOCK ] )

		setAttr( '%s.kix[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.ITX ] )
		setAttr( '%s.kiy[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.ITY ] )
		setAttr( '%s.kox[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.OTX ] )
		setAttr( '%s.koy[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.OTY ] )

		setAttr( '%s.kit[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.ITT ] )
		setAttr( '%s.kot[0:%d]' % (animCurveNode, maxIdxVal), *self[ self.OTT ] )

		return animCurveNode
	def apply( self, attrPath, sourceRange, applyStart ):
		'''
		used to put the animation data on this instance to an actual attribute

		sourceRange should be a 2-tuple representing the 0-based time range of the animation data to apply
		applyStart should be the start time at which to place the animation
		'''
		keyCmdKwargs = {}
		if sourceRange:
			keyCmdKwargs[ 't' ] = sourceRange

		animCurveNode = self.constructNode( applyStart )
		try:
			cmd.copyKey( animCurveNode, clipboard='api', **keyCmdKwargs )
			cmd.pasteKey( attrPath, option='replace', clipboard='api' )
		finally:
			cmd.delete( animCurveNode )


class NodeKeyServer(object):
	def __init__( self, nodes, visitKeys=True, attrs=None, range=(None, None) ):
		self._nodes = nodes

		#if True then each key time is actually visted during iteration
		self._visit = visitKeys

		#stores the attributes to key keys from
		self._attrs = attrs

		#if not None, only keys between the given range (inclusive) will be visited
		self._range = range

		#stores the objects stored at each time
		self._timeNodesDict = None

		#stores the current point in the iterator
		self._currentTime = None
	def _generateTimeNodesDict( self ):
		self._timeNodesDict = timeNodesDict = {}

		nodes = self._nodes
		keyframeKwargs = {}
		if self._attrs:
			keyframeKwargs[ 'at' ] = self._attrs

		keyTimes = tuple( sorted( set( cmd.keyframe( nodes, q=True, **keyframeKwargs ) ) ) )
		for keyTime in keyTimes:
			timeNodesDict[ keyTime ] = nodesAtTime = []
			for node in nodes:
				if cmd.keyframe( node, t=(keyTime,), q=True, kc=True ):
					nodesAtTime.append( node )

		return keyTimes, timeNodesDict
	def __iter__( self ):
		keyTimes, timeNodesDict = self._generateTimeNodesDict()
		iterFunction = iterAtTimes if self._visit else iter
		startTime, endTime = self._range
		for keyTime in iterFunction( keyTimes ):
			if startTime is not None:
				if keyTime < startTime:
					continue

			self._currentTime = keyTime
			yield keyTime

			if endTime is not None:
				if keyTime > endTime:
					break

		self._currentTime = None
	def getNodes( self ):
		'''
		returns the list of nodes that are at the time currently being iterated at
		'''
		if self._currentTime is None:
			raise TypeError( "Not currently iterating!  You can only query the nodes while iterating" )

		return tuple( self._timeNodesDict[ self._currentTime ] )


class AttrpathKeyServer(NodeKeyServer):
	def __init__( self, attrpaths, visitKeys=False ):
		super( AttrpathKeyServer, self ).__init__( attrpaths, visitKeys )
	def _get( self, idx ):
		attrpaths = super( AttrpathKeyServer, self ).getNodes()
		nodes = set( attrpath.split('.')[idx] for attrpath in attrpaths )

		return tuple( nodes )
	def getNodes( self ):
		return self._get( 0 )
	def getAttrNames( self ):
		return self._get( 1 )


def _getAttrNames( obj, attrNamesToSkip=() ):
	'''
	returns a list of attribute names on teh given node to slurp animation data from.  Attributes will be keyable and visible
	in the channelBox
	'''

	#grab attributes
	objAttrs = cmd.listAttr( obj, keyable=True, visible=True, scalar=True ) or []

	#also grab alias' - its possible to pass in an alias name, so we need to test against them as well
	aliass = cmd.aliasAttr( obj, q=True ) or []

	#because the aliasAttr cmd returns a list with the alias, attr pairs in a flat list, we need to iterate over the list, skipping every second entry
	itAliass = iter( aliass )
	for attr in itAliass:
		objAttrs.append( attr )
		itAliass.next()

	filteredAttrs = []
	for attr in objAttrs:
		skipAttr = False
		for skipName in attrNamesToSkip:
			if attr == skipName:
				skipAttr = True
			elif attr.startswith( skipName +'[' ) or attr.startswith( skipName +'.' ):
				skipAttr = True

		if skipAttr:
			continue

		filteredAttrs.append( attr )

	return filteredAttrs


#defines a mapping between node type, and the function used to get a list of attributes from that node to save to the clip.  by default getObjAttrNames( obj ) is called
GET_ATTR_BY_NODE_TYPE = { 'blendShape': lambda obj: getObjAttrNames( obj, ('envelope', 'weight', 'inputTarget') ) }


def getNodeAttrNames( node ):
	nodeType = cmd.nodeType( node )

	return GET_ATTR_BY_NODE_TYPE.get( nodeType, _getAttrNames )( node )


def getPlaybackRange():
	'''
	returns a 2-tuple of startTime, endTime.  The values are taken from the visible playback unless there is a time selection.
	If there is a time selection, then its range is returned instead
	'''
	if cmd.timeControl( 'timeControl1', q=True, rv=True ):  #NOTE: timeControl1 is the name of maya's default, global timeControl widget...
		return cmd.timeControl( 'timeControl1', q=True, range=True )

	return int( cmd.playbackOptions( q=True, min=True ) ), int( cmd.playbackOptions( q=True, max=True ) )


def getNamespacesFromStrings( theStrs ):
	'''
	returns list of all the namespaces found in the given list of strings
	'''
	namespaces = set()
	for aStr in theStrs:
		namespaces.add( ':'.join( aStr.split( '|' )[-1].split( ':' )[ :-1 ] ) )

	return list( namespaces )


def matchNames( srcObjs, tgtObjs ):
	namespaces = getNamespacesFromStrings( tgtObjs )
	tgtObjsSet = set( tgtObjs )
	mappedTgts = []

	namespacesToTest = []
	for namespace in namespaces:
		namespaceToks = [ tok for tok in namespace.split( '|' )[-1].split( ':' ) if tok ]
		for n, tok in enumerate( namespaceToks ):
			namespacesToTest.append( ':'.join( namespaceToks[ :n+1 ] ) )

	for srcObj in srcObjs:

		#see if the exact source is in the target list
		if srcObj in tgtObjsSet:
			mappedTgts.append( srcObj )

		#if not see if we're able to prepend the given namespace
		else:
			sourceNodeToks = srcObj.split( '|' )[-1].split( ':' )
			nodeName = sourceNodeToks[-1]
			foundCandidate = False
			for candidateNamespace in namespacesToTest:
				candidate = '%s:%s' % (candidateNamespace, nodeName)
				if candidate in tgtObjsSet:
					mappedTgts.append( candidate )
					foundCandidate = True
					break

			if not foundCandidate:
				if nodeName in tgtObjsSet:
					mappedTgts.append( nodeName )
				else:
					mappedTgts.append( '' )

	return names.Mapping( srcObjs, mappedTgts )


def _getTargetNodeInitialRotateOrderDict( mapping ):
	rotateOrderStrs = ('xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx')
	targetNodeInitialRotateOrderDict = {}

	#pre-lookup this data - otherwise we have to do a maya query within the loop below
	for node, targetNode in mapping.iteritems():
		targetRotateOrder = getAttr( '%s.ro' % targetNode )
		storedRotateOrder = getAttr( '%s.ro' % node )
		rotateOrderMatches = storedRotateOrder == targetRotateOrder
		targetNodeInitialRotateOrderDict[ targetNode ] = rotateOrderMatches, storedRotateOrder, rotateOrderStrs[ targetRotateOrder ]

	return targetNodeInitialRotateOrderDict


class BaseClip(object):
	class ApplySettings(object):
		def __init__( self, sourceRange=None, applyStart=None ):
			'''
			sourceRange is the 0-based range from the clip
			applyStart is the frame at which animation should be pasted - if it is None animation is pasted at the current time
			'''
			self.sourceRange = sourceRange
			self.applyStart = cmd.currentTime( q=True ) if applyStart is None else applyStart
		def getTimeOffset( self, originalRange=(0,None) ):
			originalStart, originalEnd = originalRange
			sourceRange = self.sourceRange
			applyStart = cmd.currentTime( q=True ) if self.applyStart is None else self.applyStart

			timeOffset = -originalStart
			if applyStart:
				timeOffset += applyStart

			if sourceRange:
				if sourceRange[1] < sourceRange[0]:
					raise ValueError( "Bad sourceRange specified: %s, %s" % sourceRange )

				timeOffset -= sourceRange[0]  #because we want the first frame

			return timeOffset
		def transformKeyTimes( self, keyTimes ):
			'''
			given a list of keyTimes this method will transform the keytimes based on the settings stored on this instance
			'''
			timeOffset = self.getTimeOffset( originalRange )
			sourceRange = self.sourceRange

			transformedKeyTimes = []
			for keyTime in sorted( keyTimes ):
				transformedKeyTime = keyTime + timeOffset

				#if there is a specified source range, make sure we haven't passed the end
				if sourceRange is not None:
					if keyTime - keyTimes[0] > sourceRange[1]:
						break

				transformedKeyTimes.append( transformedKeyTime )

			return transformedKeyTimes

	def applyToNodes( self, nodes, applySettings=None ):
		mapping = matchNames( self.getNodes(), nodes )
		self.apply( mapping, applySettings )
	def applyToSelection( self, applySettings=None ):
		selection = cmd.ls( sl=True ) or []
		self.applyToNodes( selection, applySettings )
	def applyDirectlyToNodes( self, nodes, applySettings=None ):
		mapping = names.Mapping( self.getNodes(), nodes )
		self.apply( mapping, applySettings )


class TransformClip(BaseClip):
	'''
	stores actual transform data for the given list of nodes
	'''
	_ATTRS = ('t', 'r')

	@classmethod
	def Generate( cls, nodes ):
		originalRange = getPlaybackRange()
		keyTimeDataDict = {}

		attrs = cls._ATTRS
		keyServer = NodeKeyServer( nodes, attrs=attrs )
		for keyTime in keyServer:
			nodesAtTime = keyServer.getNodes()
			keyTimeDataDict[ keyTime ] = nodeDataDict = {}
			for node in nodes:

				#skip non-transform nodes...  duh
				if not cmd.objectType( node, isAType='transform' ):
					continue

				if cmd.keyframe( node, t=(keyTime,), q=True, kc=True, at=attrs ):
					pos = xform( node, q=True, ws=True, rp=True )
					rot = xform( node, q=True, ws=True, ro=True )
					nodeDataDict[ node ] = pos, rot

		return cls( keyTimeDataDict, originalRange )

	def __init__( self, keyTimeDataDict, originalRange ):
		self._originalRange = originalRange
		self._keyTimeDataDict = keyTimeDataDict
	def getNodes( self ):
		nodes = set()
		for _x, nodeDataDict in self._keyTimeDataDict.iteritems():
			nodes.update( set( nodeDataDict.keys() ) )

		return list( nodes )
	@d_unifyUndo
	@d_noAutoKey
	def apply( self, mapping, applySettings=None ):
		if applySettings is None:
			applySettings = ApplySettings()

		targetNodeInitialRotateOrderDict = _getTargetNodeInitialRotateOrderDict( mapping )

		attrs = self._ATTRS
		keyTimes = sorted( self._keyTimeDataDict.keys() )

		#ok so this is a little ugly - not sure how to make it cleaner however.  Anyhoo, here we need to transform the key times
		#but we need the original key times because we use them as a lookup to the nodes with keys at that time...  so we build
		#a dictionary to store the mapping
		transformedKeyTimes = applySettings.transformKeyTimes( keyTimes, self._originalRange )
		transformedToInputKeyTimeDict = {}
		for transformedKeyTime, keyTime in zip( transformedKeyTimes, keyTimes ):
			transformedToInputKeyTimeDict[ transformedKeyTime ] = keyTime

		for transformedKeyTime in iterAtTimes( transformedKeyTimes ):
			keyTime = transformedToInputKeyTimeDict[ transformedKeyTime ]
			nodesAtTimeDict = self._keyTimeDataDict[ keyTime ]
			for node, targetNode in mapping.iteritems():
				if node not in nodesAtTimeDict:
					continue

				pos, rot = nodesAtTimeDict[ node ]
				move( pos[0], pos[1], pos[2], targetNode, ws=True, a=True, rpr=True )

				rotateOrderMatches, storedRotateOrder, targetRotateOrderStr = targetNodeInitialRotateOrderDict[ targetNode ]

				#if the rotation order is different, we need to compensate - we check because its faster if we don't have to compensate
				if rotateOrderMatches:
					rotate( rot[0], rot[1], rot[2], targetNode, ws=True, a=True )
				else:
					setAttr( '%s.ro' % targetNode, storedRotateOrder )
					rotate( rot[0], rot[1], rot[2], targetNode, ws=True, a=True )
					xform( targetNode, rotateOrder=targetRotateOrderStr, preserve=True )

				setKeyframe( targetNode, at=attrs )

		#make sure to filter rotation curves
		for targetNode in mapping.values():
			cmd.filterCurve( '%s.rx' % targetNode, '%s.ry' % targetNode, '%s.rz' % targetNode, filter='euler' )


class ChannelClip(BaseClip):
	'''
	stores raw keyframe data for all animated channels on the given list of nodes
	'''

	@classmethod
	def Generate( cls, nodes ):
		'''
		generates a new AnimClip instance from the given list of nodes
		'''
		originalRange = getPlaybackRange()
		nodeDict = {}
		for node in nodes:
			nodeDict[ node ] = dataDict = {}
			for attrName in getNodeAttrNames( node ):
				dataDict[ attrName ] = KeyframeData( '%s.%s' % (node, attrName) )

		return cls( nodeDict, originalRange )

	def __init__( self, nodeDict, originalRange ):
		self._originalRange = originalRange
		self._nodeDict = nodeDict
	def getNodes( self ):
		return self._nodeDict.keys()
	@d_unifyUndo
	def apply( self, mapping, applySettings=None ):
		'''
		will apply the animation data stored in this clip to the given mapping targets

		applySettings expects an AnimClip.ApplySettings instance or None
		'''
		if applySettings is None:
			applySettings = self.ApplySettings()

		timeOffset = applySettings.getTimeOffset()
		for node, targetNode in mapping.iteritems():
			if not targetNode:
				continue

			dataDict = self._nodeDict[ node ]
			for attrName, keyData in dataDict.iteritems():
				attrPath = '%s.%s' % (targetNode, attrName)
				try:
					keyData.apply( attrPath, sourceRange, timeOffset )

				#usually happens if the attrPath doesn't exist or is locked...
				except RuntimeError: continue


class AnimClip(BaseClip):
	'''
	stores both a ChannelClip instance and a TransformClip instance for the given list of nodes
	'''
	@classmethod
	def Generate( cls, nodes, worldSpace=False ):
		channelClip = ChannelClip.Generate( nodes )
		transformClip = None
		if worldSpace:
			transformClip = TransformClip.Generate( node for node in nodes if cmd.objectType( node, isAType='transform' ) )

		return cls( channelClip, transformClip )

	def __init__( self, channelClip, transformClip ):
		self._channelClip = channelClip
		self._transformClip = transformClip
	@d_unifyUndo
	def apply( self, mapping, applySettings=None, worldSpace=False ):
		self._channelClip.apply( mapping, applySettings )
		if worldSpace and self._transformClip:
			self._transformClip.apply( mapping, applySettings )


def generateAnimClipFromNodes( nodes, worldSpace=False ):
	return AnimClip.Generate( nodes, worldSpace )


def generateAnimClipFromSelection( worldSpace=False ):
	return AnimClip.Generate( cmd.ls( sl=True ), worldSpace )


class Tracer(object):
	'''
	does intra-scene tracing
	'''
	def __init__( self, keysOnly=True, processPostCmds=True, start=None, end=None, skip=1 ):

		#if we're not tracing keys, then we're baking.  In this case, if start and end haven't been specified, then
		#we assume the user wants the current timeline baked
		if not keysOnly:
			if start is None:
				start = cmd.playbackOption( q=True, min=True )

			if end is None:
				start = cmd.playbackOption( q=True, min=True )

		self._keysOnly = keysOnly
		self._processPostCmds = processPostCmds
		self._start = start
		self._end = end
		self._skip = skip
	@d_unifyUndo
	@d_noAutoKey
	def apply( self, mapping ):
		if not isinstance( mapping, names.Mapping ):
			mapping = names.Mapping( *mapping )

		targetNodeInitialRotateOrderDict = _getTargetNodeInitialRotateOrderDict( mapping )

		if self._keysOnly:
			keyServer = NodeKeyServer( mapping.keys() )
		else:
			keyServer = range( self._start, self._end, self._skip )

		for keyTime in keyServer:
			nodesAtTime = set( keyServer.getNodes() )
			for node, targetNode in mapping.iteritems():
				if node not in nodesAtTime:
					continue

				pos = xform( node, q=True, ws=True, rp=True )
				rot = xform( node, q=True, ws=True, ro=True )
				move( pos[0], pos[1], pos[2], targetNode, ws=True, a=True, rpr=True )

				rotateOrderMatches, storedRotateOrder, targetRotateOrderStr = targetNodeInitialRotateOrderDict[ targetNode ]

				#if the rotation order is different, we need to compensate - we check because its faster if we don't have to compensate
				if rotateOrderMatches:
					rotate( rot[0], rot[1], rot[2], targetNode, ws=True, a=True )
				else:
					setAttr( '%s.ro' % targetNode, storedRotateOrder )
					rotate( rot[0], rot[1], rot[2], targetNode, ws=True, a=True )
					xform( targetNode, rotateOrder=targetRotateOrderStr, preserve=True )

				setKeyframe( targetNode, at=TransformClip._ATTRS )


#end
