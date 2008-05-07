from vectors import *
from utils import *
import maya.cmds as cmd
import pickle,time,datetime


TOOL_VERSION = 1
DEFAULT_PATH = resolvePath('%TEMP%/temp_skin.weights')
class VertSkinWeight(Vector):
	'''this stupidly simple struct-like class is simply to store id, jointlist and weightlist data
	alongside a vert position vector - in hindsight i probably should have just used a dict...  duh'''
	def populate( self, vertIdx, jointList, weightList ):
		self.joints = jointList
		self.weights = weightList
		self.id = vertIdx


def saveWeights( geos, filepath=DEFAULT_PATH ):
	start = time.clock()
	miscData = {'version':TOOL_VERSION,\
				'file':cmd.file(q=True,sn=True),\
				'computer':resolvePath('%COMPUTERNAME%'),\
				'user':resolvePath('%USERNAME%'),\
				'date':datetime.date.today()}

	geoAndData = {}
	for geo in geos:
		verts = cmd.ls(cmd.polyListComponentConversion(geo,toVertex=True),fl=True)
		weightData = []
		skinCluster = cmd.ls(cmd.listHistory(geo),type='skinCluster')[0]
		id = 0
		joints = set()
		for vert in verts:
			jointList = cmd.skinPercent(skinCluster,vert,ib=1e-4,q=True,transform=None)
			weightList = cmd.skinPercent(skinCluster,vert,ib=1e-4,q=True,value=True)
			[joints.add(j) for j in jointList]
			pos = cmd.xform(vert,q=True,ws=True,t=True)
			vertData = VertSkinWeight(pos)
			vertData.populate(id,jointList,weightList)
			weightData.append(vertData)
			id += 1

		#so save the geoname and the corresponding weight data out to a file
		geoAndData[geo] = (joints,weightData)

	toWrite = miscData,geoAndData

	tmp = file(filepath,'w')
	pickle.dump(toWrite,tmp)
	tmp.close()
	print 'time for weight save: %.02f seconds'%(time.clock()-start)

	return filepath


def findMatchingVectors( theVector, vectors, tolerance=1e-6 ):
	'''do some binary culling before beginning the search - the 200 number is arbitrary,
	but values less than that don't lead to significant performance improvements'''
	numVectors = len(vectors)
	while numVectors > 200:
		half = numVectors/2
		halfPoint = vectors[half][0]

		if halfPoint+(tolerance*2) < theVector[0]: vectors = vectors[half:]
		elif halfPoint-(tolerance*2) > theVector[0]: vectors = vectors[:half]
		else: break

		numVectors = len(vectors)

	matchingX = []
	for i in vectors:
		diff = i.x - theVector.x
		if abs(diff) <= tolerance:
			matchingX.append(i)

	matchingY = []
	for i in matchingX:
		diff = i.y - theVector.y
		if abs(diff) <= tolerance:
			matchingY.append(i)

	matching = []
	for i in matchingY:
		diff = i.z - theVector.z
		if abs(diff) <= tolerance:
			matching.append(i)

	return matching


def findBestVector( theVector, vectors, tolerance=1e-6 ):
	matching = findMatchingVectors(theVector,vectors,tolerance)
	numMatches = len(matching)
	if numMatches == 0: return None
	elif numMatches == 1: return matching[0]

	#now iterate over the matching vectors and return the best match
	best = matching.pop()
	diff = (best - theVector).mag
	for match in matching:
		curDiff = (match - theVector).mag
		if curDiff < diff:
			best = match
			diff = curDiff

	return best


def sortByIdx( vectorList, idx=0 ):
	#sort the weightData by ascending x values so we can perform binary culling on the list when searching
	sortedByX = sorted([(i[idx],i) for i in vectorList])
	return [i[1] for i in sortedByX]


def loadWeights( geos=None, filepath=DEFAULT_PATH, usePosition=True, tolerance=1e-6 ):
	'''loads weights back on to a model given a file.  NOTE: the tolerance is an axis tolerance
	NOT a distance tolerance.  ie each axis must fall within the value of the given vector to be
	considered a match - this makes matching a heap faster because vectors can be culled from
	the a sorted list.  possibly implementing some sort of oct-tree class might speed up the
	matching more, but...  the majority of weight loading time at this stage is spent by maya
	actually applying skin weights, not the positional searching'''
	start = time.clock()
	miscData,geoAndData = loadData(filepath)


	#the miscData contains a dictionary with a bunch of data stored from when the weights was saved - do some
	#sanity checking to make sure we're not loading weights from some completely different source
	curFile = cmd.file(q=True,sn=True)
	origFile = miscData['file']
	if curFile != origFile:
		response = cmd.confirmDialog(t='files differ...',m='the file these weights were saved from was %s\nthis is different from your currently opened file.\n\nis that OK?'%miscData['file'],b=('Proceed','Cancel'))
		if response == 'Cancel': return


	#if the geo is None, then check for data in the verts arg - the user may just want weights
	#loaded on a specific list of verts - we can get the geo name from those verts
	skinCluster = ''
	verts = cmd.ls(cmd.polyListComponentConversion(geos,toVertex=True),fl=True)
	geoVertDict = {}
	for vert in verts:
		geo = vert[:vert.rfind('.')]
		try:
			geoVertDict[geo].append(vert)
		except KeyError:
			geoVertDict[geo] = [vert]


	#cache heavily access method objects as locals...
	skinPercent = cmd.skinPercent
	progressWindow = cmd.progressWindow
	xform = cmd.xform
	clock = time.clock


	numItems = len(geoVertDict)
	curItem = 1
	mayaTime = 0 #records the amount of time spent performing maya cmds...
	progressWindow(title='loading weights from file %d items'%numItems)
	for geo,verts in geoVertDict.iteritems():
		try:
			joints,weightData = geoAndData[geo]
		except KeyError:
			continue

		#sort the weightData by ascending x values so we can search faster
		weightData = sortByIdx(weightData)

		#are all the joints in the scene?
		joints = list(joints)
		for j in joints:
			if not cmd.objExists(j):
				raise Exception('missing joint %s'%j)

		#do we have a skinCluster on the geo already?  if not, build one
		skinCluster = cmd.ls(cmd.listHistory(geo),type='skinCluster')
		if not skinCluster:
			cmd.delete(geo,ch=True)
			skinCluster = cmd.skinCluster(geo,joints)[0]
			verts = cmd.ls(cmd.polyListComponentConversion(geo,toVertex=True),fl=True)
		else: skinCluster = skinCluster[0]

		num = len(verts)
		cur = 0.0
		inc = 100.0/num

		if usePosition:
			progressWindow(edit=True,status='by position: %s (%d/%d)'%(geo,curItem,numItems))
			for vert in verts:
				progressWindow(edit=True,progress=cur)
				cur += inc
				time1 = clock() ###--- time spent by maya...
				pos = Vector( xform(vert,q=True,ws=True,t=True) )
				mayaTime += clock() - time1 ###--- time spent by maya...
				vertData = findBestVector(pos,weightData,tolerance)

				try:
					id, jointList, weightList = vertData.id, vertData.joints, vertData.weights
					jointsAndWeights = zip(jointList,weightList)
					time1 = clock() ###--- time spent by maya...
					skinPercent(skinCluster,vert,tv=jointsAndWeights)
					mayaTime += clock() - time1 ###--- time spent by maya...
				except AttributeError:
					print '### no point found for %s'%vert
		else:
			progressWindow(status='by id: %s (%d/%d)'%(geo,curItem,numItems))
			for item in weightData:
				progressWindow(edit=True,progress=cur/float(num)*100)
				cur += 1
				id, jointList, weightList = item.id, item.joints, item.weights
				jointsAndWeights = zip(jointList,weightList)
				vertName = '%s.vtx[%d]'%(geo,id)
				time1 = clock() ###
				skinPercent(skinCluster,vertName,tv=jointsAndWeights)
				mayaTime += clock() - time1 ###

		curItem += 1

	progressWindow(ep=True)
	end = clock()
	print 'time for weight load %.02f secs'%(end-start)
	print 'time spent doing maya cmds %.02f secs'%mayaTime


def printDataFromFile( filepath=DEFAULT_PATH ):
	miscData,geoAndData = loadData(filepath)
	for geo,data in geoAndData.iteritems():
		print geo,'------------'
		joints,weightData = data
		for joint in joints:
			print '\t',joint
		print


def loadData( filepath ):
	tmp = file(filepath)
	data = pickle.load(tmp)
	tmp.close()

	return data


'''
tofind = Vector(.1,.2,.3)
vectors = sortByIdx([Vector.Random(3) for x in xrange(2000)])
print findBestVector(tofind,vectors,0.075)
#'''


#end