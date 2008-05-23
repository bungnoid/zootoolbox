import vMaya.api as api
import maya.cmds as cmd
import re

mel = api.mel
melecho = api.melecho
objExists = cmd.objExists

class Trigger(object):
	'''provides an interface to a trigger item'''
	def __init__( self, object ):
		#self.obj = longname(object)
		self.obj = object
	@classmethod
	def CreateMenu( cls, object, name='<empty>', cmdStr='//blank', slot=None ):
		new = cls(object)
		new.setMenuInfo(slot,name,cmdStr)

		return new
	def __getitem__( self, item ):
		#returns the connect at index item
		slotPrefix = 'zooTrig'
		attrPath = "%s.zooTrig%d" % ( self.obj, slot )
		if objExists(attrPath):
			objPath = cmd.connectionInfo( attrPath, sfd=True )
			return objPath.split('.')[0]
		attrPathCached = "%s.zooTrig%d%s" % ( self.obj, slotPrefix, slot, "cache" )
		if objExists(attrPathCached):
			objPath = cmd.connectionInfo( attrPathCached, sfd=True )
			return objPath.split('.')[0]
		return None
	def __len__( self ):
		#iterator that returns connectObj,connectIdx
		return len(self.connects())
	def iterConnects( self ):
		return iter( self.connects() )
	def iterMenus( self ):
		#iterator that returns slot,name,cmd
		return iter( self.listMenus() )
	def getCmd( self, resolve=False, optionals=[] ):
		attrPath = '%s.zooTrigCmd0'
		if objExists( attrPath  ):
			cmdStr = cmd.getAttr(attrPath)
			if resolve: return self.resolve(cmdStr,optionals)
			return cmdStr
		return None
	def setCmd( self, object, cmdStr='//blank' ):
		#creates the triggered cmd
		cmdAttr = "zooTrigCmd0"
		if not objExists( "%s.%s" % ( self.obj, cmdAttr ) ): cmd.addAttr(self.obj, ln=cmdAttr, dt="string")
		if cmdStr == "":
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
	def listMenus( self ):
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
					cacheAttrName = "%s.%s%d%s" % ( self.obj, slotPrefix, slot, "cache" )

					#append the object name to the connects list
					if objExists(objPath): connects.append( (objPath.split('.')[0],slot) )

					#if there is no connect, then check to see if there is a name cache, and query it
					elif objExists( cacheAttrName ):
						cacheName = cmd.getAttr( cacheAttrName )
						if objExists( cacheName ):
							self.connect( cacheName, slot )  #add the object to the connect slot
							connects.append( cacheName )
		except TypeError: pass

		return connects
	def listAllConnectSlots( self, connects=None ):
		'''returns a non-spare list of connects - unlike the connects method output, this is just a list of names.  slots
		that have no connect attached to them have empty strings as their value'''
		if connects is None: connects = self.connects()

		#build the non-sparse connects list -first we need to find the largest connect idx, and then build a non-sparse list
		connectsDict = {}
		biggest = connects[0][1]
		for name,idx in connects:
			connectsDict[idx] = name
			biggest = max(biggest,idx)

		newConnects = [''] * (biggest+1)
		print connects, biggest
		for name,idx in connects:
			newConnects[idx] = name

		return newConnects
	def resolve( self, cmd, optionals=[] ):
		'''returns a resolved cmd string.  the cmd string can be either passed in, or if you specify the slot number
		the the cmd string will be taken as the given slot's menu command'''
		connects = self.listAllConnectSlots()

		#if the connects list is empty, early out
		if not connects: return cmd

		#resolve # tokens - these represent self
		cmd = cmd.replace('#',self.obj)

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

		cmd = arrayRE.sub(arraySubRep,cmd)

		#resolve all connect array tokens:  @ - these are represent a mel array for the entire connects array excluding self
		allConnectsArray = '{ "%s" }' % '","'.join( connects[1:] )
		cmd = cmd.replace('@',allConnectsArray)

		#resolve all single connect tokens:  %<x> - these represent single connects
		connectRE = compile('(%)(-*[0-9]+)')
		def connectRep( matchobj ):
			char,idx = matchobj.groups()
			return connects[ int(idx) ]
			#except IndexError: return "<invalid connect>"

		cmd = connectRE.sub(connectRep,cmd)

		#finally resolve %opt<x>%
		optionalRE = compile('(\%opt)(-*[0-9]+)(\%)')
		def optionalRep( matchobj ):
			charA,idx,charB = matchobj.groups()
			try: return optionals[ int(idx) ]
			except IndexError: return "<invalid optional>"

		cmd = optionalRE.sub(optionalRep,cmd)

		return cmd
	def unresolve( self, cmdStr, optionals=[] ):
		'''given a cmdStr this method will go through it looking to resolve any names into connect tokens.  it only looks for single cmd tokens
		and optionals - it doesn't attempt to unresolve arrays'''
		connects = self.connects()

		for connect,idx in connects:
			idx = '%'+ str(idx)
			connectRE = re.compile( '[^a-zA-Z_|]+%s[^a-zA-Z0-9_|]+' % connect )
			cmdStr = connectRE.sub(idx,cmdStr)

		return cmdStr
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
		self.eval( self.getCmd() )
	def evalMenu( self, slot ):
		self.eval( self.getMenuCmd(slot) )
	def isConnected( self, object ):
		#return a list of the slot indicies <object> is connected to
		if not objExists(object): return []

		conPrefix = 'zooTrig'
		prefixSize = len(conPrefix)
		connections = cmd.listConnections("%s.msg"%object, s=False, p=True)

		slots = []
		for con in connections:
			try:
				attr = con.split('.')
				slot = attr[prefixSize:]
				if attr[-1].startswith('zooTrig') and slot.isdigit():
					slots.append( int(slot) )
			except IndexError: pass
		return slots
	def connect( self, object, slot=None ):
		if not objExists(object): return -1

		#get the long name of the objects - this ensures when we get a long name for either, we know we're still dealing with the correct objects
		object = longname(object)

		#if the user is trying to connect the trigger to itself, return zero which is the reserved slot for the trigger
		if self.obj == object: return 0

		#make sure the connect isn't already connected - if it is, return the slot number
		existingSlots = self.isConnected(object)
		if len(existingSlots): return existingSlots

		conPrefix = 'zooTrig'
		prefixSize = len(conPrefix)

		if slot <= 0: return 0
		elif slot is None: slot = self.nextSlot()

		slotPath = "%s.%s%d" % (self.obj, conPrefix, slot )
		if not objExists( slotPath ):
			cmd.addAttr(self.obj,ln= "%s%d" % (slotPrefix, slot ), at='message')
		cmd.connectAttr( "%s.msg" % object, slotPath, f=True )
		self.cacheConnect(slot)

		return slot
	def removeCmd( self, removeConnects=False ):
		pass
	def removeMenu( self, slot, removeConnects=False ):
		pass
	def removeAll( self, removeConnects=False ):
		pass
	def listSlots( self, haveConnections=True ):
		#lists all slot indicies - if haveConnections is true it will list only slots with connected objects
		pass
	def nextSlot( self ):
		pass
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
		#caches the objectname of a slot connection
		pass
	def cacheConnects( self ):
		pass
	def validateConnects( self ):
		pass
	def setKillState( self, state ):
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
	longname = cmd.ls(object,long=True)
	return longname[0]
