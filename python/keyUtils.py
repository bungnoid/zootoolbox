import maya.mel
import maya.mel as m
import maya.cmds as cmd

mel = maya.mel.eval
g_validWorldAttrs = ['translateX','translateY','translateZ','rotateX','rotateY','rotateZ']

class Key():
	'''this is simply a convenient abstraction of a key object in maya - which doesn't
	really exist...  working with key data is a pain in the ass.  you can specify either
	a key time or a key index when creating an instance.  if both are specifed, index is
	used.  if time is specified, and there is no key at that time, a phantom key is
	created using the curve value at that point - the index is set to -1 in this case,
	and tangent data is guessed'''
	def __init__( self, attrpath, keyTime=None, keyIdx=None ):
		#if the attrpath doesn't exist, then just create an empty key instance
		if not cmd.objExists(attrpath):
			self.obj = None
			self.attr = None
			self.time = None
			self.value = None
			self.iw = None
			self.ow = None
			self.itt = None
			self.ott = None
			return

		self.obj,self.attr = attrpath.split('.')

		#make sure the attr name is the long version of the name, its too annoying to have to deal with shortnames AND long names...
		self.attr = cmd.attributeQuery(self.attr,longName=True,node=self.obj)

		#and just for uber convenience, store the attrpath as well...
		self.attrpath = attrpath

		if keyIdx != None:
			times = cmd.keyframe(attrpath,index=keyIdx,query=True)
			self.time = times[0]
		elif keyTime != None:
			self.time = keyTime

		#is there a key at the time?
		if cmd.keyframe(attrpath,time=(keyTime,),query=True,keyframeCount=True):
			self.value = cmd.keyframe(attrpath,time=(keyTime,),query=True,valueChange=True)[0]
			self.iw,self.ow,self.ia,self.oa = cmd.keyTangent(attrpath,time=(keyTime,),query=True,inWeight=True,outWeight=True,inAngle=True,outAngle=True)
			self.itt,self.ott = cmd.keyTangent(attrpath,time=(keyTime,),query=True,inTangentType=True,outTangentType=True)

			#this is purely 'clean up after maya' code.  for whatever reason maya will return a tangent type of "fixed" even though its a completely invalid tangent type...  not sure what its supposed to map to, so I'm just assuming spline
			if self.itt == 'fixed': self.itt = 'spline'
			if self.ott == 'fixed': self.ott = 'spline'

		else:
			self.value = cmd.keyframe(attrpath,time=(keyTime,),query=True,eval=True,valueChange=True)
			index = self.index
			previousOutTT = None
			previousOutTW = None
			nextInTT = None
			nextInTW = None
			if index > 1:
				previousOutTT = cmd.keyTangent(attrpath,index=(index-1,),query=True,outTangentType=True)
				previousOutTW = cmd.keyTangent(attrpath,index=(index-1,),query=True,outWeight=True)
			else:
				previousOutTT = cmd.keyTangent(attrpath,index=(index,),query=True,outTangentType=True)
				previousOutTW = cmd.keyTangent(attrpath,index=(index,),query=True,outWeight=True)

			if index < cmd.keyframe(self.attr,query=True,keyframeCount=True):
				nextInTT = cmd.keyTangent(attrpath,index=(index+1,),query=True,inTangentType=True)
				nextInTW = cmd.keyTangent(attrpath,index=(index+1,),query=True,inWeight=True)
			else:
				nextInTT = cmd.keyTangent(attrpath,index=(index,),query=True,inTangentType=True)
				nextInTW = cmd.keyTangent(attrpath,index=(index,),query=True,inWeight=True)

			#now average the tangents
				self.iw = self.ow = (previousOutTW + nextInTW )/2
	def __str__(self):
		return '%.1f'% (self.time,)
	def __repr__(self):
		return self.__str__()
	def __cmp__(self,other):
		'''key value comparisons are done on a time basis - we could use value, but time
		makes a lot more sense.  it is more useful to have temporally ordered keys than
		it is value ordered'''
		if self.time < other.time: return -1
		if self.time == other.time: return 0
		if self.time > other.time: return 1
	def get_index( self ):
		'''returns the key object's index'''
		return cmd.keyframe(self.attr,time=(":"+str(self.time),),query=True,keyframeCount=True)-1
	index = property(get_index,None,None,'''returns the key's index on the anim curve it exists on''')


class Channel():
	'''a channel is simply a list of key objects with some convenience methods attached'''
	def __init__( self, attrpath=None, start=None, end=None ):
		self.obj = None
		self.attr = None
		self.attrpath = attrpath
		
		if start == None:
			#get the timecount of the first key
			start = cmd.keyframe(attrpath,index=(0,),query=True)[0]  
		if end == None: 
			#get the timecount of the first key
			lastKeyIdx = cmd.keyframe(attrpath,keyframeCount=True,query=True)-1
			end = cmd.keyframe(attrpath,index=(lastKeyIdx,),query=True)[0] 

		self.keys = []

		if attrpath != None:
			self.obj,self.attr = attrpath.split('.')
			self.attr = cmd.attributeQuery(self.attr,longName=True,node=self.obj)
			self.weighted = cmd.keyTangent(self.attrpath,query=True,weightedTangents=True)

			if self.weighted == 1: self.weighted = True
			else: self.weighted = False
			if cmd.objExists(attrpath):
				keyTimes = cmd.keyframe(attrpath,time=(start,end),query=True)
				if keyTimes != None:
					for k in keyTimes:
						self.keys.append(Key(attrpath,keyTime=k))
	def get_start(self):
		keyTimes = [key.time for key in self.keys]
		return min(keyTimes)
	start = property(get_start,None,None,None)
	def get_end(self):
		keyTimes = [key.time for key in self.keys]
		return max(keyTimes)
	end = property(get_end,None,None,None)
	def __str__(self):
		return self.attrpath +': '+ str(self.keys)
	def __repr__(self):
		return self.__str__()
	def __add__(self,other):
		#overloading operators for channels would be neat for animation clipping...
		boundTimes = [self.start,self.end,other.start,other.end]
		boundTimes.sort()
		newStart, newEnd = boundTimes[0], boundTimes[-1]
		newChannel = Channel(None,newStart,newEnd)

		#add all keys from the left
		for key in self.keys:
			newChannel.keys.append(key)

		#now add the keys on the other - there are a few special cases here
		if other.keys[-1].time > newChannel.keys[-1].time: newChannel.extend(other.keys)
		elif other.keys[-1].time == newChannel.keys[-1].time:
			newChannel.keys[-1].value += other.keys[-1].value
			newChannel.extend(other.keys[1:])
		elif other.keys[0].time < newChannel.keys[0].time: newChannel.keys = other.keys + newChannel.keys
		elif other.keys[0].time == newChannel.keys[0].time:
			newChannel.keys = other.keys + newChannel.keys
		else:
			n = 1
			while True:
				if other.keys[0] >= newChannel.keys[n].time: break
				n += 1

			for key in other.keys:
				if key.time == newChannel.keys[n].time:
					newChannel.keys.insert(n,key)
					n += 1
				elif key.time > newChannel.keys[n].time:
					newChannel.keys.insert(n,key)
					n += 1

		return newChannel
	def __getitem__(self, key):
		return self.keys[key]
	def __setitem__(self,key,value):
		self.keys[key] = value
	def __len__(self):
		return len(self.keys)
	def applyToObj( self, obj, applyAsWorld=False ):
		'''applies the current channel to a given attrpath'''
		tgtAttrpath = obj +'.'+ self.attr
		if cmd.objExists(tgtAttrpath):
			if applyAsWorld and self.hasWorld:
				#apply as world - NOT DONE YET
				for key in self.keys:
					cmd.setKeyframe(tgtAttrpath,time=(key.time,),value=key.value,inTangentType=key.itt,outTangentType=key.ott)
					cmd.keyTangent(tgtAttrpath,time=(key.time,),edit=True,inWeight=key.iw,outWeight=key.ow,inAngle=self.ia,outAngle=self.oa)
			else:
				cmd.setKeyframe(tgtAttrpath,time=(self.keys[0].time,))
				cmd.keyTangent(tgtAttrpath,edit=True,weightedTangents=self.weighted)
				for key in self.keys:
					cmd.setKeyframe(tgtAttrpath,time=(key.time,),value=key.value,inTangentType=key.itt,outTangentType=key.ott)
					cmd.keyTangent(tgtAttrpath,time=(key.time,),edit=True,inWeight=key.iw,outWeight=key.ow)
	#def sensibleTangent(self):
		#would be neat to be able to integrate the 'sensible tangents' feature in the old setKey mel
	def getTurningPoints(self):
		'''returns a list of keys that are turning points'''
		if len(self.keys) < 3:
			return []

		turningPoints = []
		keyIter = iter(self.keys)
		prevKey = keyIter.next()
		curKey = keyIter.next()
		nextKey = keyIter.next()
		while True:
			try:
				prevValue = prevKey.value - curKey.value
				nextValue = nextKey.value - curKey.value
				if ( prevValue<0 and nextValue<0 ) or ( prevValue>0 and nextValue>0 ):
					#in this case nextKey is a turning point
					turningPoints.append(curKey)
	
				prevKey = curKey
				curKey = nextKey
				nextKey = keyIter.next()
			except StopIteration:
				break

		return turningPoints
	def keyReduce( self ):
		#get the nodeType of the animCurve driving this channel
		animCurve = cmd.listConnections(self.attrpath,type='animCurve',destination=False)[0]
		nodeType = cmd.nodeType(animCurve)

		#create an array to hold the "reduced" set of keys to create - start/end and turning points are mandatory
		newKeys = [self.keys[0]] + self.getTurningPoints() + [self.keys[-1]]

		#create the new animCurve - we do this because asking maya to query the interpolation between keys is way easier than doing it via script
		reduce = cmd.createNode(nodeType)
		for key in newKeys: cmd.setKeyframe(reduce,time=(key.time,),value=key.value,inTangentType='linear',outTangentType='linear')

		#
		
		return reduce


class Clip():
	'''creates a convenient abstraction of a collection of animation data on multiple
	channels.  supports adding, removing etc...'''
	def __init__( self, node, start=None, end=None, channels=None ):
		#if channels is the default value, assume all keyable channels on the node
		if channels == None:
			attributes = cmd.listAttr(node,keyable=True,multi=True,scalar=True)
			channels = [a for a in attributes if cmd.keyframe(node+'.'+a,query=True,keyframeCount=True)]

		channelObjs = []
		for channel in channels:
			channelObjs.append(Channel(node+'.'+channel,start,end))

		#create object attrs
		self.channels = channelObjs
		self.hasWorld = False
	def __str__( self ):
		asStr = ''
		for chan in self.channels: asStr += str(chan) +'\n'
		return asStr
	def get_start(self):
		starts = []
		for channel in self.channels:
			starts.append(channel.start)
		return min(starts)
	start = property(get_start,None,None,None)
	def get_end(self):
		ends = []
		for channel in self.channels:
			ends.append(channel.end)
		return max(ends)
	end = property(get_end,None,None,None)
	def __getattr__(self,name):
		#run through all channels looking for the given name
		for chan in self.channels:
			if chan.attr == name:
				return chan
		raise AttributeError("the channel .%s doesn't exist"%(name,))
	def __getitem__(self, key):
		return self.channels[key]
	def __setitem__(self,key,value):
		self.channels[key] = value
	def __len__(self):
		return len(self.keys)
	def get_channels( self, channelListToGet ):
		resultingChannels = []
		for name in channelListToGet:
			resultingChannels.append(getattr(self,name))

		return resultingChannels
	def listKeysInOrder( self, channels=None ):
		'''returns a list of the clip's keys in ascending temporal order'''
		if not channels: channels = self.channels
		keys = []
		for channel in channels: keys.extend(channel.keys)
		keys.sort()
		return keys
	keys = property(listKeysInOrder,None,None,None)
	def as_frames( self, channels=None ):
		'''bundles the keys in this channel into groups of unique times - we call these frames.  ie: each frame has one or more keys at that time and ONLY that time
		return value is a list of lists (a list of frames).  each frame contains all the keys at that time'''
		frames = [[]]
		keys = self.listKeysInOrder(channels)
		prevTime = keys[0].time
		for key in keys:
			if prevTime != key.time:
				prevTime = key.time
				frames.append([])
			frames[-1].append(key)

		return frames
	frames = property(as_frames,None,None,None)
	def as_keys( self ):
		keys = []
		for channel in self.channels:
			keys += channel.keys
		return keys
	keys = property(as_keys,None,None,None)
	def applyToObj( self, obj, applyAsWorld=False ):
		'''applies the current clip to an object - if the animation is being applied as world space, first check to make
		sure the world space animation for the clip exists.  then separate the transform channels out of the channels list
		and apply them as world space data.  then we need to apply the rest of the channels as per normal'''
		transformChannels = []
		nonTransformChannels = []
		for channel in self.channels:
			if channel.attr in g_validWorldAttrs: transformChannels.append(channel)
			else: nonTransformChannels.append(channel)

		if applyAsWorld and self.hasWorld:
			'''NOT DONE YET'''
			frames = self.as_frames(transformChannels)
			for channel in transformChannels:
				tgtAttrpath = obj +'.'+ channel.attr
				channel.applyToObj(obj,applyAsWorld)

			#run a euler filter over the resulting rotation animation - converting to world space
			#rotations often causes all sorts of nasty euler flips
			mel('filterCurve %s.rx %s.ry %s.rz;'%(obj,obj,obj))
		else:
			for channel in transformChannels:
				channel.applyToObj(obj)
			
		for channel in nonTransformChannels:
			channel.applyToObj(obj)
			#for key in channel.keys:
				#cmd.setKeyframe(tgtAttrpath,time=(key.time,),value=key.value,inTangentType=key.itt,outTangentType=key.ott)
				##mel('keyTangent -t %f -e -iw %f -ow %f %s;'%(key.time,key.iw,key.ow,tgtAttrpath))
				#mel('filterCurve %s.rx %s.ry %s.rz;'%(obj,obj,obj))
	def convertToWorld( self ):
		'''converts the clip's motion to a world space path'''
		global g_validWorldAttrs
		import maya.OpenMaya as api
		import maya.OpenMayaAnim as anim

		#use the api to control the time changes as it doesn't refresh viewports making it way faster
		timeControl = anim.MAnimControl()
		orgTime = timeControl.currentTime()
		for frame in self.frames:
			timeControl.setCurrentTime(api.MTime(frame[0].time))
			#cmd.currentTime(frame[0].time)
			transformKeys = [key for key in frame if key.attr in g_validWorldAttrs]
			xform = cmd.xform(key.obj,query=True,worldSpace=True,rotatePivot=True)
			xform += cmd.xform(key.obj,query=True,worldSpace=True,rotation=True)
			for k in transformKeys:
				try:
					idx = g_validWorldAttrs.index(k.attr)
					k.value = xform[idx]
				except:
					print 'bad',k.attrpath,k.time
					continue

		timeControl.setCurrentTime(orgTime) #restore time
		self.hasWorld = True
	def write( self, filepath ):
		import pickle
		fileobj = file(filepath,'w')
		pickle.dump(self,fileobj)
		fileobj.close()
	def load( self, filepath ):
		import pickle
		fileobj = file(filepath)
		newChannel = pickle.load(fileobj)
		fileobj.close()
		return newChannel


class MotionPath():
	'''a motion path is a set of transform channels that defines a path in space'''
	def __init__(self,clip):
		keys = clip.listKeysInOrder()
		transformKeys = [key for key in keys if key.attr in g_validWorldAttrs]
		worldKeys = []

		prevTime = transformKeys[0].time
		cmd.currentTime(prevTime)
		mel('zooAllViews 0;')

		for key in transformKeys:
			#make sure the time is set to that of the current key
			if prevTime != key.time:
				cmd.currentTime(key.time)
				prevTime = key.time

			xyz = cmd.xform(key.obj,query=True,worldSpace=True,rotatePivot=True)

		mel('zooAllViews 1;')

		self.t = (tx,ty,tz)
		self.r = (rx,ry,rz)
	def transform(newSpace):
		'''returns a new key in the new space.  by default all keys are created in
		local space.  this method is used to transform the key to world space.
		NOTE: transforming doesn't make sense for all attribute types'''
		if newspace == 'world':
			global g_validWorldAttrs
			attr = self.attr.split('.')[-1]
			if attr in g_validWorldAttrs:
				cmd.currentTime(self.time)
'''
def getWorldSpaceXform( obj, time ):
	import maya.OpenMaya as api
	import maya.OpenMayaAnim as anim
	from math import pi

	TWOPI = 2*pi
	timeControl = anim.MAnimControl()
	orgTime = timeControl.currentTime()
	sel = api.MSelectionList()
	sel.add(obj)
	sel.add('pSphere1')
	dagNode = api.MDagPath()
	tgt = api.MDagPath()
	sel.getDagPath(0,dagNode)
	sel.getDagPath(1,tgt)

	timeControl.setCurrentTime(api.MTime(time))
	objMatrix = api.MFnTransform(dagNode)
	pos = objMatrix.rotatePivot(api.MSpace.kWorld)
	rotAsQuat = api.MQuaternion()
	objMatrix.getRotation(rotAsQuat,api.MSpace.kWorld)
	rotAsEuler = rotAsQuat.asEulerRotation()
	rot = [rotAsEuler.x,rotAsEuler.y,rotAsEuler.z]
	rot[0] = rotAsEuler.x * TWOPI
	rot[1] = rotAsEuler.y * TWOPI
	rot[2] = rotAsEuler.z * TWOPI
	timeControl.setCurrentTime(orgTime) #restore time

	tgtMatrix = api.MFnTransform(tgt)
	tgtMatrix.setRotation(rotAsQuat,api.MSpace.kWorld)

	return pos.x,pos.y,pos.z,rot[0],rot[1],rot[2]
'''

def createCompassRun():
	namespace = ''
	worldSpaceObjs = ['leg','leg_R','root','arm_L','arm_R']