import maya.mel as m

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
		if not m.eval('objExists "%s";'%(attrpath,)):
			self.obj = None
			self.attr = None
			self.time = None
			self.value = None
			self.iw = None
			self.ow = None
			self.itt = None
			self.ott = None
			self.time = None
			return

		self.obj,self.attr = attrpath.split('.')

		#make sure the attr name is the long version of the name, its too annoying to have to deal with shortnames AND long names...
		self.attr = m.eval('attributeQuery -ln -n %s %s'%(self.obj,self.attr))

		#and just for uber convenience, store the attrpath as well...
		self.attrpath = attrpath

		if keyIdx != None:
			times = m.eval('keyframe -in %d -q %s;'&(keyIdx,attrpath))
			self.time = times[0]
		elif keyTime != None:
			self.time = keyTime

		#is there a key at the time?
		if m.eval('keyframe -t %d -q -kc %s;'%(keyTime,attrpath)):
			self.value = m.eval('keyframe -t %d -q -vc %s;'%(keyTime,attrpath))[0]
			self.iw,self.ow = m.eval('keyTangent -t %d -q -iw -ow %s;'%(keyTime,attrpath))
			self.itt,self.ott = m.eval('keyTangent -t %d -q -itt -ott %s;'%(keyTime,attrpath))

			#this is purely 'clean up after maya' code.  for whatever reason maya will return a tangent type of "fixed" even though its a completely invalid tangent type...  not sure what its supposed to map to, so I'm just assuming spline
			if self.itt == 'fixed': self.itt = 'spline'
			if self.ott == 'fixed': self.ott = 'spline'

		else:
			self.value = m.eval('keyframe -t %d -q -eval -vc %s;'%(keyTime,attrpath))
			index = self.index()
			previousOutTT = None
			previousOutTW = None
			nextInTT = None
			nextInTW = None
			if index > 1:
				previousOutTT = m.eval('keyTangent -in %d -q -ott %s;'%(index-1,attrpath))
				previousOutTW = m.eval('keyTangent -in %d -q -ow %s;'%(index-1,attrpath))
			else:
				previousOutTT = m.eval('keyTangent -in %d -q -ott %s;'%(index,attrpath))
				previousOutTW = m.eval('keyTangent -in %d -q -ow %s;'%(index,attrpath))

			if index < m.eval('keyframe -q -kc %s'%(self.attr,)):
				nextInTT = m.eval('keyTangent -in %d -q -itt %s;'%(index+1,attrpath))
				nextInTW = m.eval('keyTangent -in %d -q -iw %s;'%(index+1,attrpath))
			else:
				nextInTT = m.eval('keyTangent -in %d -q -itt %s;'%(index,attrpath))
				nextInTW = m.eval('keyTangent -in %d -q -iw %s;'%(index,attrpath))

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
	def index( self ):
		'''returns the key object's index'''
		return (m.eval('keyframe -t ":%d" -q -kc %s;'%(self.time,self.attr))-1)
	#def sensibleTangent(self):
		#would be neat to be able to integrate the 'sensible tangents' feature in the old setKey mel


class Channel():
	'''a channel is simply a list of key objects with some convenience methods attached'''
	def __init__( self, attrpath=None, start=0, end=0 ):
		self.obj = None
		self.attr = None
		self.attrpath = attrpath
		self.start = start
		self.end = end
		self.keys = []

		if attrpath != None:
			self.obj,self.attr = attrpath.split('.')
			self.attr = m.eval('attributeQuery -ln -n %s %s'%(self.obj,self.attr))

			if m.eval('objExists '+ attrpath +';'):
				self.populateKeyData(attrpath,self.start,self.end)
	def populateKeyData( self, attrpath, keyTime, keyIdx ):
		keyTimes = m.eval('keyframe -t "%d:%d" -q %s;'%(self.start,self.end,attrpath))
		if keyTimes != None:
			for k in keyTimes:
				self.keys.append(Key(attrpath,keyTime=k))
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
	def applyToObj( self, obj, isWorld=False ):
		'''applies the current channel to a given attrpath'''
		tgtAttrpath = obj +'.'+ self.attr
		if m.eval('objExists %s'%(tgtAttrpath,)):
			for key in self.keys:
				m.eval('setKeyframe -t %f -v %f -itt %s -ott %s %s;'%(key.time,key.value,key.itt,key.ott,tgtAttrpath))
				m.eval('keyTangent -t %f -e -iw %f -ow %f %s;'%(key.time,key.iw,key.ow,tgtAttrpath))
				m.eval('filterCurve %s.rx %s.ry %s.rz;'%(obj,obj,obj))


class Clip():
	'''creates a convenient abstraction of a collection of animation data on multiple
	channels.  supports adding, removing etc...'''
	def __init__( self, node, start, end, channels=None ):
		#if channels is the default value, assume all keyable channels on the node
		if channels == None:
			channels = m.eval('listAttr -k -m -s %s'%(node,))

		channelObjs = []
		for channel in channels:
			channelObjs.append(Channel(node+'.'+channel,start,end))

		#create object attrs
		self.start = start
		self.end = end
		self.channels = channelObjs
		self.frames = self.getFrames()
	def __str__( self ):
		asStr = ''
		for chan in self.channels: asStr += str(chan) +'\n'
		return asStr
	def listKeysInOrder( self ):
		'''returns a list of the clip's keys in ascending temporal order'''
		keys = []
		for channel in self.channels: keys.extend(channel.keys)
		keys.sort()
		return keys
	def getFrames( self ):
		'''returns a list of unique times - we call these frames.  ie: a frame may have one or more keys at that time'''
		frames = [[]]
		keys = self.listKeysInOrder()
		prevTime = keys[0].time
		for key in keys:
			if prevTime != key.time:
				prevTime = key.time
				frames.append([])
			frames[-1].append(key)

		return frames
	def applyToObj( self, obj ):
		'''applies the current clip to an object'''
		for channel in self.channels:
			tgtAttrpath = obj +'.'+ channel.attr
			if m.eval('objExists %s'%(tgtAttrpath,)):
				for key in channel.keys:
					print 'setKeyframe -t %f -v %f -itt %s -ott %s %s;'%(key.time,key.value,key.itt,key.ott,tgtAttrpath)
					m.eval('setKeyframe -t %f -v %f -itt %s -ott %s %s;'%(key.time,key.value,key.itt,key.ott,tgtAttrpath))
					#m.eval('keyTangent -t %f -e -iw %f -ow %f %s;'%(key.time,key.iw,key.ow,tgtAttrpath))
					m.eval('filterCurve %s.rx %s.ry %s.rz;'%(obj,obj,obj))
	def convertToWorld( self ):
		'''converts the clip's motion to a world space path'''
		global g_validWorldAttrs
		m.eval('zooAllViews 0;')
		for frame in self.frames:
			m.eval('currentTime %d'%(frame[0].time,))
			transformKeys = [key for key in frame if key.attr in g_validWorldAttrs]
			xform = m.eval('xform -q -ws -rp %s;'%(key.obj,))
			xform.extend(m.eval('xform -q -ws -ro %s;'%(key.obj,)))
			for k in transformKeys:
				try:
					idx = g_validWorldAttrs.index(k.attr)
					k.value = xform[idx]
				except:
					print 'bad',k.attrpath,k.time
					continue

		m.eval('zooAllViews 1;')


class MotionPath():
	'''a motion path is a set of transform channels that defines a path in space'''
	def __init__(self,clip):
		keys = clip.listKeysInOrder()
		transformKeys = [key for key in keys if key.attr in g_validWorldAttrs]
		worldKeys = []

		prevTime = transformKeys[0].time
		m.eval('currentTime %d'%(prevTime,))
		m.eval('zooAllViews 0;')

		for key in transformKeys:
			#make sure the time is set to that of the current key
			if prevTime != key.time:
				m.eval('currentTime %d;'%(key.time,))
				prevTime = key.time

			xyz = m.eval('xform -q -ws -rp %s;'%(key.obj,))
			#if keyAttr.attr ==

		m.eval('zooAllViews 1;')

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
				m.eval('currentTime -e %d;' % self.time,)

