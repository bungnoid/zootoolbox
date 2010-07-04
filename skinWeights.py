'''
this module provides code to save and load skinWeight files.  the skinWeight files contain vert skinning data stored
both by position and by index, and as such can be used to restore weights using either method.  the actual maya UI
for this tool is found in zooSkinWeights
'''

from skinWeightsBase import *
from api import melPrint
from filesystem import removeDupes

import maya.cmds as cmd
import api

#import wingdbstub


mel = api.mel
iterParents = api.iterParents
VertSkinWeight = MayaVertSkinWeight

def getAllParents( obj ):
	allParents = []
	parent = [ obj ]
	while parent is not None:
		allParents.append( parent[ 0 ] )
		parent = cmd.listRelatives( parent, p=True, pa=True )

	return allParents[ 1: ]


def getDefaultPath():
	scenePath = cmd.file(q=True, sn=True)
	if not scenePath:
		return DEFAULT_PATH

	scenePath = Path( scenePath )
	scenePath = scenePath.setExtension( EXTENSION )

	return scenePath


kAPPEND = 0
kREPLACE = 1
@api.d_showWaitCursor
def saveWeights( geos, filepath=None ):
	reportUsageToAuthor()
	start = time.clock()
	miscData = api.writeExportDict(TOOL_NAME, TOOL_VERSION)

	#if filepath is None, then generate a default filepath based on the location of the file
	if filepath is None:
		filepath = getDefaultPath()
	else: filepath = Path(filepath)

	geoAndData = {}
	skinPercent = cmd.skinPercent
	xform = cmd.xform

	#define teh data we're gathering
	masterJointList = []
	weightData = []

	#data gathering time!
	rigidBindObjects = []
	for geo in geos:
		geoNode = geo
		skinClusters = cmd.ls(cmd.listHistory(geo), type='skinCluster')
		if len( skinClusters ) > 1:
			api.melWarning("more than one skinCluster found on %s" % geo)
			continue

		#so the geo isn't skinned in the traditional way - check to see if it is parented to a joint.  if so,
		#stuff it into the rigid bind list to be dealt with outside this loop, and continue
		if not skinClusters:
			dealtWith = False
			for p in iterParents( geo ):
				if cmd.nodeType( p ) == 'joint':
					rigidBindObjects.append( (geo, p) )
					masterJointList.append( p )
					masterJointList = removeDupes( masterJointList )
					dealtWith = True
					break

			if not dealtWith:
				msg = "cannot find a skinCluster for %s" % geo
				api.melWarning(msg)

			continue

		skinCluster = skinClusters[ 0 ]
		masterJointList += cmd.skinCluster( skinCluster, q=True, inf=True )
		masterJointList = removeDupes( masterJointList )

		verts = cmd.ls(cmd.polyListComponentConversion(geo, toVertex=True), fl=True)
		for idx, vert in enumerate(verts):
			jointList = skinPercent(skinCluster, vert, ib=1e-4, q=True, transform=None)
			weightList = skinPercent(skinCluster, vert, ib=1e-4, q=True, value=True)
			if jointList is None:
				raise SkinWeightException("I can't find any joints - sorry.  do you have any post skin cluster history???")

			pos = xform(vert, q=True, ws=True, t=True)
			vertData = VertSkinWeight( pos )
			vertData.populate( geo, idx, [ masterJointList.index( j ) for j in jointList ], weightList )
			weightData.append( vertData )


	#deal with rigid bind objects
	for geo, j in rigidBindObjects:

		verts = cmd.ls( cmd.polyListComponentConversion(geo, toVertex=True), fl=True )
		for idx, vert in enumerate( verts ):
			jIdx = masterJointList.index( j )

			pos = xform( vert, q=True, ws=True, t=True )
			vertData = VertSkinWeight( pos )
			vertData.populate( geo, idx, [jIdx], [1] )
			weightData.append( vertData )


	#sort the weightData by ascending x values so we can search faster
	weightData = sortByIdx( weightData )

	#turn the masterJointList into a dict keyed by index
	joints = {}
	for n, j in enumerate( masterJointList ):
		joints[ n ] = j

	#generate joint hierarchy data - so if joints are missing on load we can find the best match
	jointHierarchies = {}
	for n, j in joints.iteritems():
		jointHierarchies[ n ] = getAllParents( j )

	toWrite = miscData, joints, jointHierarchies, weightData

	filepath = Path( filepath )
	filepath.pickle( toWrite, False )
	melPrint( 'Weights Successfully Saved to %s: time taken %.02f seconds' % (filepath, time.clock()-start) )

	return filepath


def findMatchingVectors( theVector, vectors, tolerance=1e-6 ):
	'''
	'''
	numVectors = len(vectors)

	#do some binary culling before beginning the search - the 200 number is arbitrary,
	#but values less than that don't lead to significant performance improvements
	idx = 0
	theVectorIdx = theVector[idx]
	while numVectors > 200:
		half = numVectors / 2
		halfPoint = vectors[half][idx]

		if (halfPoint + tolerance) < theVectorIdx: vectors = vectors[half:]
		elif (halfPoint - tolerance) > theVectorIdx: vectors = vectors[:half]
		else: break

		numVectors = len(vectors)

	matchingX = []
	for i in vectors:
		diff = i[0] - theVector[0]
		if abs(diff) <= tolerance:
			matchingX.append(i)

	matchingY = []
	for i in matchingX:
		diff = i[1] - theVector[1]
		if abs(diff) <= tolerance:
			matchingY.append(i)

	matching = []
	for i in matchingY:
		diff = i[2] - theVector[2]
		if abs(diff) <= tolerance:
			matching.append(i)

	#now the matching vectors is a list of vectors that fall within the bounding box with length of 2*tolerance.
	#we want to reduce this to a list of vectors that fall within the bounding sphere with radius tolerance
	inSphere = []
	for m in matching:
		if (theVector - m).mag <= tolerance:
			inSphere.append( m )

	return inSphere


_MAX_RECURSE = 35

def getClosestVector( theVector, vectors, tolerance=1e-6, doPreview=False ):
	'''
	given a list of vectors, this method will return the one with the best match based
	on the distance between any two vectors
	'''

	global _MAX_RECURSE

	matching = findMatchingVectors(theVector, vectors, tolerance)

	#if not matching: return None
	itCount = 0
	while not matching:
		tolerance *= 1.25
		itCount += 1
		matching = findMatchingVectors( theVector, vectors, tolerance )
		if itCount > _MAX_RECURSE: return None

	best = matching.pop()

	diff = (best - theVector).mag
	for match in matching:
		curDiff = (match - theVector).mag
		if curDiff < diff:
			best = match
			diff = curDiff

	if doPreview:
		cmd.select( best.getVertName() )
		print "skinning data"
		for x in zip( best.joints, best.weights ): print x
		raise Exception, 'preview mode'

	return best, diff


def getDistanceWeightedVector( theVector, vectors, tolerance=1e-6, doPreview=False ):
	global _MAX_RECURSE

	matching = findMatchingVectors( theVector, vectors, tolerance )

	#if not matching: return None
	itCount = 0
	while not matching:
		tolerance *= 1.25
		itCount += 1
		matching = findMatchingVectors( theVector, vectors, tolerance )
		if itCount > _MAX_RECURSE: return None

	newVec = VertSkinWeight( matching[ 0 ] )

	joints = []
	weights = []
	for v in matching:
		dist = ( v - theVector ).get_magnitude()
		distanceBiasedWeight = (tolerance - dist) / tolerance
		distanceBiasedWeight **= 3  #3 seems to produce magically good results...  tahts all there is to it
		joints += v.joints
		weights += [ w * distanceBiasedWeight for w in v.weights ]

	joints, weights = regatherWeights( joints, weights )
	newVec = VertSkinWeight( matching[ 0 ] )
	newVec.populate( None, -1, joints, weights )

	if doPreview:
		cmd.select( [ m.getVertName() for m in matching ] )
		print "skinning data"
		for x in zip( newVec.joints, newVec.weights ): print x
		raise Exception, "in preview mode"

	return newVec, tolerance


def getDistanceRatioWeightedVector( theVector, vectors, tolerance=1e-6, ratio=2, doPreview=False ):
	global _MAX_RECURSE

	matching = findMatchingVectors( theVector, vectors, tolerance )

	#if not matching: return None
	itCount = 0
	while not matching:
		tolerance *= 1.25
		itCount += 1
		matching = findMatchingVectors( theVector, vectors, tolerance )
		if itCount > _MAX_RECURSE: return None

	dists = []
	for v in matching:
		dist = ( v - theVector ).get_magnitude()
		dists.append( (dist, v) )

	dists.sort()
	closestDist, closestV = dists[ 0 ]

	matching = [ closestV ]
	if closestDist == 0:
		newVec = closestV
	else:
		jointsWeightsDict = {}
		for dist, v in dists:
			vDistRatio = dist / closestDist
			if vDistRatio > ratio: break  #the dists are sorted so if this is the case there are no more matches...
	
			matching.append( v )
			tolerance = dist
	
			for j, w in zip( v.joints, v.weights ):
				w = w / vDistRatio
				jointsWeightsDict.setdefault( j, w + jointsWeightsDict.get( j, 0 ) )

		#normalize weight values
		weightList = jointsWeightsDict.values()
		weightSum = sum( weightList )
		if weightSum != 1.0:
			weightList = [ w/weightSum for w in weightList ]
	
		newVec = VertSkinWeight( matching[ 0 ] )
		newVec.populate( None, -1, jointsWeightsDict.keys(), weightList )

	if doPreview:
		cmd.select( [ m.getVertName() for m in matching ] )
		print "skinning data - tolerance %0.5f" % tolerance
		for x in zip( newVec.joints, newVec.weights ): print x
		raise Exception, "in preview mode"

	return newVec, tolerance


@api.d_progress(t='initializing...', status='initializing...', isInterruptable=True)
def loadWeights( objects, filepath=None, usePosition=True, tolerance=TOL, axisMult=None, swapParity=True, averageVerts=True, doPreview=False, meshNameRemapDict=None, jointNameRemapDict=None ):
	'''
	loads weights back on to a model given a file.  NOTE: the tolerance is an axis tolerance
	NOT a distance tolerance.  ie each axis must fall within the value of the given vector to be
	considered a match - this makes matching a heap faster because vectors can be culled from
	the a sorted list.  possibly implementing some sort of oct-tree class might speed up the
	matching more, but...  the majority of weight loading time at this stage is spent by maya
	actually applying skin weights, not the positional searching
	'''

	#nothing to do...
	if not objects:
		print 'No objects given...'
		return

	if filepath is None:
		filepath = getDefaultPath()

	if not filepath.exists:
		print 'File does not exist %s' % filepath
		return

	reportUsageToAuthor()
	start = time.clock()


	#setup the mappings
	VertSkinWeight.MESH_NAME_REMAP_DICT = meshNameRemapDict
	VertSkinWeight.JOINT_NAME_REMAP_DICT = jointNameRemapDict


	#cache heavily access method objects as locals...
	skinPercent = cmd.skinPercent
	progressWindow = cmd.progressWindow
	xform = cmd.xform

	findMethod = getClosestVector
	findMethodKw = { 'tolerance': tolerance, 'doPreview': doPreview }
	if averageVerts:
		findMethod = getDistanceRatioWeightedVector


	#now get a list of all weight files that are listed on the given objects - and
	#then load them one by one and apply them to the appropriate objects
	objItemsDict = {}
	for obj in objects:
		items = []  #this holds the vert list passed in IF any
		if obj.find('.') != -1:
			items = [obj]
			obj = obj.split('.')[0]

		try: objItemsDict[obj].extend( items )
		except KeyError: objItemsDict[obj] = items


	unfoundVerts = []
	numItems = len(objItemsDict)
	curItem = 1
	progressWindow(e=True, title='loading weights from file %d items' % numItems)


	#load the data from the file
	miscData, joints, jointHierarchies, weightData = Path( filepath ).unpickle()

	if miscData[ api.kEXPORT_DICT_TOOL_VER ] != TOOL_VERSION:
		api.melWarning( "WARNING: the file being loaded was stored from an older version (%d) of the tool - please re-generate the file.  Current version is %d." % (miscData[ api.kEXPORT_DICT_TOOL_VER ], TOOL_VERSION) )


	#the miscData contains a dictionary with a bunch of data stored from when the weights was saved - do some
	#sanity checking to make sure we're not loading weights from some completely different source
	curFile = cmd.file(q=True, sn=True)
	origFile = miscData['scene']
	if curFile != origFile:
		api.melWarning('the file these weights were saved in a different file from the current: "%s"' % origFile)


	#remap joint names in the saved file to joint names that are in the scene - they may be namespace differences...
	missingJoints = set()
	for n, j in joints.iteritems():
		if not cmd.objExists(j):
			#see if the joint with the same leaf name exists in the scene
			idxA = j.rfind(':')
			idxB = j.rfind('|')
			idx = max(idxA, idxB)
			if idx != -1:
				leafName = j[idx:]
				search = cmd.ls('%s*' % leafName, r=True, type='joint')
				if len(search):
					joints[n] = search[0]
					print '%s remapped to %s' % (j, search[0])


	#now that we've remapped joint names, we go through the joints again and remap missing joints to their nearest parent
	#joint in the scene - NOTE: this needs to be done after the name remap so that parent joint names have also been remapped
	for n, j in joints.iteritems():
		if not cmd.objExists(j):
			dealtWith = False
			for jp in jointHierarchies[j]:
				if cmd.objExists( jp ):
					joints[n] = jp
					dealtWith = True
					break

			if dealtWith:
				print '%s remapped to %s' % (j, jp)
				continue

			missingJoints.add(n)

	#now remove them from the list
	[ joints.pop(n) for n in missingJoints ]


	#axisMults can be used to alter the positions of verts saved in the weightData array - this is mainly useful for applying
	#weights to a mirrored version of a mesh - so weights can be stored on meshA, meshA duplicated to meshB, and then the
	#saved weights can be applied to meshB by specifying an axisMult=(-1,1,1) OR axisMult=(-1,)
	if axisMult is not None:
		for data in weightData:
			for n, mult in enumerate(axisMult): data[n] *= mult

		#we need to re-sort the weightData as the multiplication could have potentially reversed things...  i could probably
		#be a bit smarter about when to re-order, but its not a huge hit...  so, meh
		weightData = sortByIdx(weightData)

		#using axisMult for mirroring also often means you want to swap parity tokens on joint names - if so, do that now.
		#parity needs to be swapped in both joints and jointHierarchies
		if swapParity:
			for joint, target in joints.iteritems():
				joints[joint] = str( names.Name(target).swap_parity() )
			for joint, parents in jointHierarchies.iteritems():
				jointHierarchies[joint] = [str( names.Name(p).swap_parity() ) for p in parents]


	for geo, items in objItemsDict.iteritems():
		#if the geo is None, then check for data in the verts arg - the user may just want weights
		#loaded on a specific list of verts - we can get the geo name from those verts
		skinCluster = ''
		verts = cmd.ls(cmd.polyListComponentConversion(items if items else geo, toVertex=True), fl=True)


		#do we have a skinCluster on the geo already?  if not, build one
		skinCluster = cmd.ls(cmd.listHistory(geo), type='skinCluster')
		if not skinCluster:
			skinCluster = cmd.skinCluster(geo,joints.values())[0]
			verts = cmd.ls(cmd.polyListComponentConversion(geo, toVertex=True), fl=True)
		else: skinCluster = skinCluster[0]


		num = len(verts)
		cur = 0.0
		inc = 100.0/num


		#if we're using position, the restore weights path is quite different
		queue = api.CmdQueue()
		if usePosition:
			progressWindow( e=True, status='searching by position: %s (%d/%d)' % (geo, curItem, numItems) )

			print "starting first iteration with", len( weightData ), "verts"

			iterationCount = 1
			tolAdjustInterval = 15
			while True:
				unfoundVerts = []
				foundVerts = []

				tolAccum = 0
				for vCount, vert in enumerate( verts ):
					pos = Vector( xform(vert, q=True, ws=True, t=True) )
					vertData = findMethod( pos, weightData, **findMethodKw )

					if vertData is None:
						unfoundVerts.append( vert )
						continue

					vertData, newTolerance = vertData
					tolAccum += newTolerance


					#unpack data to locals
					jointList, weightList = vertData.joints, vertData.weights
					actualJointNames = [ joints[ n ] for n in jointList ]


					#check sizes - if joints have been remapped, there may be two entries for a joint
					#in the re-mapped jointList - in this case, we need to re-gather weights
					actualJointsAsSet = set( actualJointNames )
					if len( actualJointsAsSet ) != len( actualJointNames ):
						#so if the set sizes are different, then at least one of the joints is listed twice,
						#so we need to gather up its weights into a single value
						new = {}
						[ new.setdefault(j, 0) for j in actualJointNames ]  #init the dict with 0 values
						for j, w in zip(actualJointNames, weightList):
							new[ j ] += w

						#if the weightList is empty after renormalizing, nothing to do - keep loopin
						actualJointNames, weightList = new.keys(), new.values()
						if not weightList: raise NoVertFound


					#normalize the weightlist
					weightList = normalizeWeightList( weightList )

					#zip the joint names and their corresponding weight values together (as thats how maya
					#accepts the data) and fire off the skinPercent cmd
					jointsAndWeights = zip(actualJointNames, weightList)

					queue.append( 'skinPercent -tv %s %s %s' % (' -tv '.join( [ '%s %s' % t for t in jointsAndWeights ] ), skinCluster, vert) )
					foundVertData = VertSkinWeight( pos )
					foundVertData.populate( vertData.mesh, vertData.idx, jointList, weightList )
					foundVerts.append( foundVertData )


					#every so often re-adjust the tolerance if it differs enough
					if vCount % tolAdjustInterval == 0:
						averagedTolerance = tolAccum / tolAdjustInterval
						mn, mx = sorted( [tolerance, averagedTolerance] )
						try:
							if mx/mn > 1.5:  #only if it different enough from the current tolerance do we bother adjusting
								findMethodKw[ 'tolerance' ] = averagedTolerance
								#print 'NEW TOLERANCE', averagedTolerance
						except ZeroDivisionError: pass

						tolAccum = 0


					#deal with the progress window - this isn't done EVERY vert because its kinda slow...
					cur += inc
					if vCount % 50 == 0:
						progressWindow( e=True, progress=cur )

						#bail if we've been asked to cancel
						if progressWindow( q=True, isCancelled=True ):
							progressWindow( ep=True )
							return


				#so with the unfound verts - sort them, call them "verts" and iterate over them with the newly grown weight data
				#the idea here is that when a vert is found its added to the weight data (in memory not on disk).  by performing
				#another iteration for the previously un-found verts, we should be able to get a better approximation
				verts = unfoundVerts
				if unfoundVerts:
					if foundVerts:
						weightData = sortByIdx( foundVerts )
					else:
						print "### still unfound verts, but no new matches were made in previous iteration - giving up.  %d iterations performed" % iterationCount
						break
				else:
					print "### all verts matched!  %d iterations performed" % iterationCount
					break

				iterationCount += 1
				print "starting iteration %d - using" % iterationCount, len( weightData ), "verts"
				#for www in weightData: print www

			progressWindow(e=True, status='maya is setting skin weights...')
			queue()

		#otherwise simply restore by id
		else:
			progressWindow(edit=True, status='searching by vert name: %s (%d/%d)' % (geo, curItem, numItems))

			#rearrange the weightData structure so its ordered by vertex name
			weightDataById = {}
			[ weightDataById.setdefault(i.getVertName(), (i.joints, i.weights)) for i in weightData ]

			for vert in verts:
				progressWindow(edit=True, progress=cur / num * 100.0)
				if progressWindow(q=True, isCancelled=True):
					progressWindow(ep=True)
					return

				cur += 1
				try:
					jointList, weightList = weightDataById[vert]
				except KeyError:
					#in this case, the vert doesn't exist in teh file...
					print '### no point found for %s' % vert
					continue
				else:
					jointsAndWeights = zip(jointList, weightList)
					skinPercent(skinCluster, vert, tv=jointsAndWeights)

		#remove unused influences from the skin cluster
		cmd.skinCluster( skinCluster, edit=True, removeUnusedInfluence=True )
		curItem += 1

	if unfoundVerts: cmd.select( unfoundVerts )
	end = time.clock()
	api.melPrint('time for weight load %.02f secs' % (end-start))


MAX_INFLUENCE_COUNT = 3
def normalizeWeightList( weightList ):
	sortedWeightList = sorted( weightList )[ -MAX_INFLUENCE_COUNT: ]
	smallestViable = sortedWeightList[ 0 ]

	weightSum = sum( sortedWeightList )
	try:
		return [ w / weightSum if w >= smallestViable else 0 for w in weightList ]
	except ZeroDivisionError:
		return []


def printDataFromFile( filepath=DEFAULT_PATH ):
	miscData,geoAndData = presets.PresetPath( filepath ).unpickle()
	for geo, data in geoAndData.iteritems():
		print geo,'------------'
		joints, weightData = data
		for joint in joints:
			print '\t', joint
		print


def printDataFromSelection( filepath=DEFAULT_PATH, tolerance=1e-4 ):
	miscData,geoAndData = presets.PresetPath(filepath).unpickle()
	selVerts = cmd.ls( cmd.polyListComponentConversion( cmd.ls( sl=True ), toVertex=True ), fl=True )
	selGeo = {}
	for v in selVerts:
		idx = v.rfind('.')
		geo = v[ :idx ]
		vec = Vector( cmd.xform( v, q=True, t=True, ws=True ) )
		try:
			selGeo[ geo ].append( ( vec, v ) )
		except KeyError:
			selGeo[ geo ] = [ ( vec, v ) ]

	#make sure the geo selected is actually in the file...
	names = selGeo.keys()
	for geo in names:
		try:
			geoAndData[ geo ]
		except KeyError:
			selGeo.pop( item )

	for geo,vecAndVert in selGeo.iteritems():
		joints, jointHierarchies, weightData = geoAndData[ geo ]
		weightData = sortByIdx( weightData )
		for vec, vertName in vecAndVert:
			try:
				vertData = getClosestVector( vec, weightData, tolerance )
				jointList, weightList = vertData.joints, vertData.weights
				tmpStr = []
				for items in zip( jointList, weightList ):
					tmpStr.append( '(%s %0.3f)' % items )
				print '%s: %s' % ( vertName, '  '.join( tmpStr ) )
			except AttributeError:
				print '%s no match'


def mirrorWeightsOnSelected( tolerance=TOL ):
	selObjs = cmd.ls(sl=True, o=True)

	#so first we need to grab the geo to save weights for - we save geo for all objects which have
	#verts selected
	saveWeights( selObjs, Path('%TEMP%/tmp.weights'), mode=kREPLACE )
	loadWeights( cmd.ls(sl=True), Path( '%TEMP%/tmp.weights' ), True, 2, (-1,), True )


#end