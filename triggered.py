import vMaya.api as api
import maya.cmds as cmd
import re, time

mel = api.mel
melecho = api.melecho
objExists = cmd.objExists
INVALID = '<invalid connect>'

class Trigger(object):
	'''provides an interface to a trigger item'''
	def __init__( self, object ):
		self.obj = longname(object)
	@classmethod
	def CreateTrigger( cls, object, cmdStr='//blank' ):
		new = cls(object)
		new.setCmd(cmdStr)

		return new
	@classmethod
	def CreateMenu( cls, object, name='<empty>', cmdStr='//blank', slot=None ):
		new = cls(object)
		new.setMenuInfo(slot,name,cmdStr)

		return new
	def __getitem__( self, slot ):
		'''returns the connect at index <slot>'''
		if slot == 0: return self.obj

		slotPrefix = 'zooTrig'
		attrPath = "%s.zooTrig%d" % ( self.obj, slot )
		try:
			objPath = cmd.connectionInfo( attrPath, sfd=True )
			if objPath: return objPath.split('.')[0]
		except TypeError:
			#in this case there is no attribute - so pass and look to the connect cache
			pass

		attrPathCached = "%scache" % attrPath
		try:
			obj = cmd.getAttr( attrPathCached )
			if cmd.objExists(obj): return obj
		except TypeError: pass

		raise IndexError('no such connect exists')
	def __len__( self ):
		return len(self.connects())
	def iterConnects( self ):
		'''iterator that returns connectObj,connectIdx'''
		return iter( self.connects()[1:] )
	def iterMenus( self, resolve=False ):
		'''iterator that returns slot,name,cmd'''
		return iter( self.menus(resolve) )
	def getCmd( self, resolve=False, optionals=[] ):
		attrPath = '%s.zooTrigCmd0' % self.obj
		if objExists( attrPath  ):
			cmdStr = cmd.getAttr(attrPath)
			if resolve: return self.resolve(cmdStr,optionals)
			return cmdStr
		return None
	def setCmd( self, cmdStr ):
		#creates the triggered cmd
		cmdAttr = "zooTrigCmd0"
		if not objExists( "%s.%s" % ( self.obj, cmdAttr ) ): cmd.addAttr(self.obj, ln=cmdAttr, dt="string")
		if cmdStr is None or cmdStr == '':
			cmd.deleteAttr(self.obj, at=cmdAttr)
			return

		cmd.setAttr( '%s.%s' % ( self.obj, cmdAttr ), cmdStr, type='string' )
	def getMenuCmd( self, slot, resolve=False ):
		cmdInfo = cmd.getAttr( "%s.zooCmd%d" % ( self.obj, slot ) )
		idx = cmdInfo.find('^')
		if resolve: return self.resolve(cmdInfo[idx+1:])
		return cmdInfo[idx+1:]
	def setMenuCmd( self, slot, cmdStr ):
		newCmdInfo = '%s^%s' % ( self.getMenuName(slot), cmdStr )
		cmd.setAttr( "%s.zooCmd%d" % ( self.obj, slot ), newCmdInfo, type='string' )
	def setMenuInfo( self, slot=None, name='<empty>', cmd='//blank' ):
		cmd.setAttr( "%s.zooCmd%d" % ( self.obj, slot ), '%s^%s' % ( name, cmd ) )
	def getMenuName( self, slot ):
		cmdInfo = cmd.getAttr( "%s.zooCmd%d" % ( self.obj, slot ) )
		idx = cmdInfo.find('^')

		return cmdInfo[:idx]
	def setMenuName( self, slot, name ):
		newCmdInfo = '%s^%s' % ( name, self.getMenuCmd(slot) )
		cmd.setAttr( "%s.zooCmd%d" % ( self.obj, slot ), newCmdInfo )
	def getMenuInfo( self, slot, resolve=False ):
		cmdInfo = cmd.getAttr( "%s.zooCmd%d" % ( self.obj, slot ) )
		idx = cmdInfo.find('^')
		if resolve: return cmdInfo[:idx],self.resolve(cmdInfo[idx+1:])
		return cmdInfo[:idx],cmdInfo[idx+1:]
	def menus( self, resolve=False ):
		attrs = cmd.listAttr(self.obj,ud=True)
		slotPrefix = 'zooCmd'
		prefixSize = len(slotPrefix)
		slots = []

		for attr in attrs:
			try: slot = attr[prefixSize:]
			except IndexError: continue

			if attr.startswith(slotPrefix) and slot.isdigit():
				menuData = cmd.getAttr('%s.%s' % (self.obj,attr))
				idx = menuData.find('^')
				menuName = menuData[:idx]
				menuCmd = menuData[idx+1:]
				if resolve: menuCmd = self.resolve(menuCmd)
				slots.append( ( int(slot), menuName, menuCmd ) )

		slots.sort()

		return slots
	def connects( self ):
		'''returns a list of tuples with the format: (connectName,connectIdx)'''
		connects = [(self.obj,0)]
		attrs = cmd.listAttr(self.obj, ud=True)
		slotPrefix = 'zooTrig'
		prefixSize = len(slotPrefix)

		#the try is here simply because maya stupidly returns None if there are no attrs instead of an empty list...
		try:
			#so go through the attributes and make sure they're triggered attributes
			for attr in attrs:
				try: slot = attr[prefixSize:]
				except IndexError: continue

				if attr.startswith(slotPrefix) and slot.isdigit():
					slot = int(slot)

					#now that we've determined its a triggered attribute, trace the connect if it exists
					objPath = cmd.connectionInfo( "%s.%s" % ( self.obj, attr ), sfd=True )

					#append the object name to the connects list and early out
					if objExists(objPath):
						connects.append( (objPath.split('.')[0],slot) )
						continue

					#if there is no connect, then check to see if there is a name cache, and query it - no need to
					#check for its existence as we're already in a try block and catching the appropriate exception
					#should the attribute not exist...
					cacheAttrName = "%s.%s%d%s" % ( self.obj, slotPrefix, slot, "cache" )
					cacheName = cmd.getAttr( cacheAttrName )
					if objExists( cacheName ):
						self.connect( cacheName, slot )  #add the object to the connect slot
						connects.append( cacheName )
		except TypeError: pass

		return connects
	def listAllConnectSlots( self, connects=None, emptyValue=None ):
		'''returns a non-spare list of connects - unlike the connects method output, this is just a list of names.  slots
		that have no connect attached to them have <emptyValue> as their value'''
		if connects is None: connects = self.connects()

		#build the non-sparse connects list -first we need to find the largest connect idx, and then build a non-sparse list
		biggest = max( [c[1] for c in connects] ) + 1
		newConnects = [emptyValue]*biggest
		for name,idx in connects:
			newConnects[idx] = name

		return newConnects
	def resolve( self, cmdStr, optionals=[] ):
		'''returns a resolved cmd string.  the cmd string can be either passed in, or if you specify the slot number
		the the cmd string will be taken as the given slot's menu command'''
		connects = self.listAllConnectSlots(emptyValue=INVALID)

		#if the connects list is empty, early out
		if not connects: return cmdStr

		#resolve # tokens - these represent self
		cmdStr = cmdStr.replace('#',self.obj)

		#resolve ranged connect array tokens:  @<start>,<end> - these represent what is essentially a list slice - although they're end value inclusive unlike python slices...
		compile = re.compile
		arrayRE = compile('(@)([0-9]+),(-*[0-9]+)')
		def arraySubRep( matchobj ):
			char,start,end = matchobj.groups()
			start = int(start)
			end = int(end) + 1
			if end == 0: end = None
			try: return '{ "%s" }' % '","'.join( connects[start:end] )
			except IndexError: return "<invalid range: %s,%s>" % (start,end)

		cmdStr = arrayRE.sub(arraySubRep,cmdStr)

		#resolve all connect array tokens:  @ - these are represent a mel array for the entire connects array excluding self
		allConnectsArray = '{ "%s" }' % '","'.join( connects[1:] )
		cmdStr = cmdStr.replace('@',allConnectsArray)

		#resolve all single connect tokens:  %<x> - these represent single connects
		connectRE = compile('(%)(-*[0-9]+)')
		def connectRep( matchobj ):
			char,idx = matchobj.groups()
			return connects[ int(idx) ]

		cmdStr = connectRE.sub(connectRep,cmdStr)

		#finally resolve any optional arg list tokens:  %opt<x>%
		optionalRE = compile('(\%opt)(-*[0-9]+)(\%)')
		def optionalRep( matchobj ):
			charA,idx,charB = matchobj.groups()
			try: return optionals[ int(idx) ]
			except IndexError: return "<invalid optional>"

		cmdStr = optionalRE.sub(optionalRep,cmdStr)

		return cmdStr
	def unresolve( self, cmdStr, optionals=[] ):
		'''given a cmdStr this method will go through it looking to resolve any names into connect tokens.  it only looks for single cmd tokens
		and optionals - it doesn't attempt to unresolve arrays'''
		connects = self.connects()

		for connect,idx in connects:
			idx = '%'+ str(idx)
			connectRE = re.compile( '[^a-zA-Z_|]+%s[^a-zA-Z0-9_|]+' % connect )
			cmdStr = connectRE.sub(idx,cmdStr)

		return cmdStr
	def replaceConnectToken( self, cmdStr, searchConnect, replaceConnect ):
		'''returns a resolved cmd string.  the cmd string can be either passed in, or if you specify the slot number
		the the cmd string will be taken as the given slot's menu command'''
		connects = self.listAllConnectSlots()

		#perform some early out tests
		if not connects: return cmdStr
		if searchConnect == replaceConnect: return cmdStr

		#build the search and replace tokens - in the case that the replaceConnect is actually a string object, then just use it directly
		searchToken = '#' if searchConnect == 0 else '%'+ str(searchConnect)
		replaceToken = '#' if replaceConnect == 0 else '%'+ str(replaceConnect)
		if isinstance(replaceConnect,basestring): replaceToken = replaceConnect

		#build the regex to find the search data
		connectRE = re.compile( '(%s)([^0-9])' % searchToken )
		def tokenRep( matchobj ):
			connectToken,trailingChar = matchobj.groups()
			return '%s%s' % ( replaceToken, trailingChar )

		cmdStr = connectRE.sub(tokenRep,cmdStr)

		return cmdStr
	def replaceConnectInCmd( self, searchConnect, replaceConnect ):
		return self.replaceConnectToken( self.getCmd(slot), searchConnect, replaceConnect )
	def replaceConnectInMenuCmd( self, slot, searchConnect, replaceConnect ):
		return self.replaceConnectToken( self.getMenuCmd(slot), searchConnect, replaceConnect )
	def replaceConnectInMenuCmds( self, searchConnect, replaceConnect ):
		for connect,slot in self.connects:
			self.replaceConnectToken( self.getMenuCmd(slot), searchConnect, replaceConnect )
	def scrub( self, cmdStr ):
		#so build the set of missing connects
		allSlots = self.listAllConnectSlots(emptyValue=None)
		missingSlots = set( [idx for idx,val in enumerate(allSlots) if val is None] )

		#now build the list of connect tokens used in the cmd and compare it with the connects
		#that are valid - in the situation where there are connects in the cmdStr that don't
		#exist on the trigger, we want to scrub these
		singleRE = re.compile('%([0-9]+)')
		subArrayRE = re.compile('@([0-9]+),(-*[0-9]+)')

		nonexistantSlots = set( map(int, singleRE.findall(cmdStr)) )
		for start,end in subArrayRE.findall(cmdStr):
			start = int(start)
			end = int(end)
			if end < 0: end += len(allSlots)
			else: end += 1
			[nonexistantSlots.add(slot) for slot in xrange( start, end )]

		[nonexistantSlots.discard( slot ) for slot,connect in enumerate(allSlots)]
		missingSlots = missingSlots.union( nonexistantSlots )  #now add the nonexistantSlots to the missingSlots

		#early out if we can
		if not missingSlots: return cmdStr

		#otherwise iterate over the list of slots and remove any line that has that slot token in it
		for slot in missingSlots:
			missingRE = re.compile(r'''^(.*)(%-*'''+ str(slot) +')([^0-9].*)$\n',re.MULTILINE)
			cmdStr = missingRE.sub('',cmdStr)

		def replaceSubArray( matchObj ):
			junk1,start,end,junk2 = matchObj.groups()
			start = int(start)
			end = int(end)
			if end<0: end = start+end
			else: end += 1
			subArrayNums = set(range(start,end))
			common = subArrayNums.intersection( missingSlots )
			if common: return ''
			return matchObj.string[matchObj.start():matchObj.end()]

		subArrayRE = re.compile('^(.*@)([0-9]+),(-*[0-9]+)([^0-9].*)$\n',re.MULTILINE)
		cmdStr = subArrayRE.sub(replaceSubArray,cmdStr)

		return cmdStr
	def scrubCmd( self ):
		self.setCmd( self.scrub( self.getCmd() ))
	def scrubMenuCmd( self, slot ):
		self.setMenuCmd(slot, self.scrub( self.getMenuCmd(slot) ))
	def scrubMenuCmds( self ):
		for slot,name,cmdStr in self.menus(): self.scrubMenuCmd(slot)
	def collapseMenuCmd( self, slot ):
		'''resolves a menu item's command string and writes it back to the menu item - this is most useful when connects are being re-shuffled
		and you don't want to have to re-write command strings.  there is the counter function - uncollapseMenuCmd that undoes the results'''
		self.setMenuCmd(slot, self.getMenuCmd(slot,True) )
	def uncollapseMenuCmd( self, slot ):
		print self.unresolve( self.getMenuCmd(slot) )
		#self.setMenuCmd(slot, self.unresolve( self.getMenuCmd(slot) ) )
	def eval( self, cmdStr, optionals=[] ):
		return mel.eval( self.resolve(cmdStr,optionals) )
	def evalCmd( self ):
		return self.eval( self.getCmd() )
	def evalMenu( self, slot ):
		return self.eval( self.getMenuCmd(slot) )
	def evalCareful( self, cmdStr, optionals=[] ):
		'''so this does an eval on a line by line basis, catching errors as they happen - its most useful for
		when you have large cmdStrs with only a small number of errors'''
		start = time.clock()
		lines = cmdStr.split('\n')
		evalMethod = mel.eval
		validLines = []

		for line in lines:
			try:
				cmd.select(cl=True)  #selection is cleared so any missing connects don't work on selection instead of specified objects
				resolvedLine = self.resolve(line,optionals)
				evalMethod(resolvedLine)
			except RuntimeError: continue
			validLines.append( line )
		end = time.clock()
		print 'time taken', end-start, 'seconds'
		return '\n'.join(validLines)
	def isConnected( self, object ):
		#return a list of the slot indicies <object> is connected to
		if not objExists(object): return []

		conPrefix = 'zooTrig'
		prefixSize = len(conPrefix)
		connections = cmd.listConnections("%s.msg"%object, s=False, p=True)

		slots = []
		try:
			#this stupid try is to catch the cases where there are no connections and maya stupidly returns None...  thanks alias!
			for con in connections:
				try:
					attr = con.split('.')
					slot = attr[prefixSize:]
					if attr[-1].startswith('zooTrig') and slot.isdigit():
						slots.append( int(slot) )
				except IndexError: pass
		except TypeError: pass

		return slots
	def connect( self, object, slot=None ):
		'''performs the actual connection of an object to a connect slot'''
		#get the long name of the objects - this ensures when we get a long name for either, we know we're still dealing with the correct objects
		try: object = longname(object)
		except TypeError: return -1

		#if the user is trying to connect the trigger to itself, return zero which is the reserved slot for the trigger
		if self.obj == object: return 0
		if slot <= 0: return 0
		elif slot is None: slot = self.nextSlot()

		#make sure the connect isn't already connected - if it is, return the slot number
		existingSlots = self.isConnected(object)
		if existingSlots: return existingSlots

		conPrefix = 'zooTrig'
		prefixSize = len(conPrefix)

		slotPath = "%s.%s%d" % (self.obj, conPrefix, slot )
		if not objExists( slotPath ):
			cmd.addAttr(self.obj,ln= "%s%d" % (slotPrefix, slot ), at='message')

		cmd.connectAttr( "%s.msg" % object, slotPath, f=True )
		self.cacheConnect(slot)

		return slot
	def disconnect( self, object=None, slot=None ):
		'''removes either the specified object from all slots, or disconnects the object at the specified slot'''
		if object is not None and self.isConnected(object):
			#this is the object case
			slots = self.getConnectSlots(object)
			for slot in slots: cmd.deleteAttr( '%s.zooTrig%d' % ( self.obj, slot ))
		elif slot is not None:
			cmd.deleteAttr( '%s.zooTrig%d' % ( self.obj, slot ))
	def removeCmd( self, removeConnects=False ):
		'''removes the triggered cmd from self - can optionally remove all the connects as well'''
		try:
			#catches the case where there is no trigger cmd...  faster than a object existence test
			cmd.deleteAttr( '%s.zooTrigCmd0' % self.obj )
			if removeConnects:
				for connect,slot in self.connects():
					self.disconnect(slot=slot)
		except TypeError: pass
	def removeMenu( self, slot, removeConnects=False ):
		'''removes a given menu slot - if removeConnects is True, all connects will be removed ONLY if there are no other menu cmds'''
		attrpath = '%s.zooCmd%d' % ( self.obj, slot )
		try:
			cmd.deleteAttr( '%s.zooCmd%d' % ( self.obj, slot ))
			if removeConnects and not self.menus():
				for connect,slot in self.connects():
					self.disconnect(slot=slot)
		except TypeError: pass
	def removeAll( self, removeConnects=False ):
		'''removes all triggered data from self'''
		self.removeCmd(removeConnects)
		for idx,name,cmd in self.menus():
			self.removeMenu(idx)
	def nextSlot( self ):
		'''returns the first available slot index'''
		slots = self.listAllConnectSlots()
		unused = [con for con,obj in enumerate(slots) if obj == '']
		next = 1

		if unused: return unused[0]
		elif slots: return len(slots)

		return next
	def getConnectSlots( self, object ):
		'''returns the slots an object is connected to - if the object isn't connected to any, an empty list is returned'''
		attrPrefix = 'zooTrig'
		prefixSize = len(attrPrefix)
		connections = cmd.listConnections("%s.msg" % object, s=False, p=True )
		slots = []

		for n,con in enumerate(connections):
			try:
				attr = con.split('.')[-1]
				slot = attr[prefixSize:]
				if attr.startswith(attrPrefix) and slot.isdigit():
					slots.append( int(slot) )
			except IndexError: continue

		return slots
	def cacheConnect( self, slot ):
		'''caches the objectname of a slot connection'''
		try: connectName = self[slot]
		except IndexError: return None

		slotPrefix = 'zooTrig'
		cacheAttrName = '%s%d%cache' % ( slotPrefix, slot )
		cacheAttrPath = '%s.%s' % ( self.obj, cacheAttrName )

		if not cmd.objExists(cacheAttrPath): addAttr(self.obj, ln=cacheAttrName, dt='string')
		cmd.setAttr( cacheAttrPath, connectName, type='string')
	def validateConnects( self ):
		'''connects maintain a cache which "remembers" the last object that was plugged into them.  this method will
		run over all connects and for those unconnected ones, it will look for the object that it USED to be connected to
		and connect it, and for those that ARE connected, it will make sure the cache is valid.  the cache can become
		invalid if a connected object's name changes after it was connected'''
		slotPrefix = 'zooTrig'

		for connect,slot in self.iterConnects():
			attrpath = '%s.%s%d' % ( self.obj, slotPrefix, slot )
			objPath = cmd.connectionInfo(attrpath, sfd=True)
			if not cmd.objExists( objPath ):
				#get the cached connect and attach it
				cachedValue = cmd.getAttr('%scache' % attrpath)
				if cmd.objExists(cachedValue):
					self.connect(cachedValue,slot)
	def setKillState( self, state ):
		'''so the kill state tells the objMenu build script to stop after its build all menu items listed on the object - this method
		provides an interface to enabling/disabling that setting'''
		attr = 'zooObjMenuDie'
		attrpath = '%s.%s' % ( self.obj, attr )
		if state:
			if not objExists( attrpath ): cmd.addAttr(self.obj, at="bool", ln=attr)
			setAttr( attrpath, 1 )
		else:
			if objExists( attrpath ):
				cmd.deleteAttr(attrpath)
	def getKillState( self ):
		attrpath = "%s.zooObjMenuDie" % self.obj
		if objExists( attrpath ): return bool( cmd.getAttr(attrpath) )

		return False
	killState = property(getKillState,setKillState)


def writeSetAttrCmd( trigger, objs ):
	cmdLines = []
	trigger = Trigger(trigger)

	for obj in objs:
		attrs = cmd.listAttr(obj, k=True, s=True, v=True, m=True)
		objSlot = trigger.getConnectSlots(obj)
		slots = trigger.getConnectSlots(obj)

		if len(slots): objStr = "%"+ str(slots[0])

		for a in attrs:
			attrType = cmd.getAttr( "%s.%s"%(obj,a), type=True )
			if attrType.lower() == "double":
				attrVal = cmd.getAttr( "%s.%s" % (obj,a) )
				cmdLines.append( "setAttr %s.%s %0.5f;" % ( objStr, a, attrVal ) )
			else: cmdLines.append( "setAttr %s.%s %s;" % ( objStr, a, cmd.getAttr( "%s.%s"%(obj,a) ) ) )

	return '\n'.join( cmdLines )


def listTriggers():
	'''lists all trigger objects in the current scene'''
	allObjects = cmd.ls(type='transform')
	triggers = []
	attr = 'zooTrigCmd0'

	try:
		for obj in allObjects:
			if objExists( '%s.%s' % ( obj, attr ) ):
				triggers.connect( obj )
	except TypeError: pass

	return triggers


def listObjectsWithMenus():
	'''lists all objects with menu items in the scene'''
	allObjects = cmd.ls(type='transform')
	objMenus = []
	attrPrefix = 'zooCmd'
	prefixSize = len(attrPrefix)

	for obj in allObjects:
		attrs = cmd.listAttr(obj, ud=True)
		try:
			for attr in attrs:
				try: slot = attr[prefixSize:]
				except IndexError: continue
				if attr.startswith(attrPrefix) and slot.isdigit():
					objMenus.append( obj )
					break
		except TypeError: continue

	return objMenus



def getTriggeredState():
	'''returns the state of triggered'''
	return mel.zooTriggeredState()


def setTriggeredState( state=True ):
	if state: mel.zooTriggeredLoad()
	else: mel.zooTriggeredUnload()


def longname( object ):
	try:
		longname = cmd.ls(object,long=True)
		return longname[0]
	except IndexError: raise TypeError


#end