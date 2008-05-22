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
		#returns the number of connects
		pass
	def iterConnects( self ):
		pass
	def iterMenus( self ):
		#iterator that returns name,cmd
		pass
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
	def setMenuCmd( self, slot, cmd ):
		newCmdInfo = '%s^%s' % ( self.getMenuName(slot), cmd  )
		cmd.setAttr( "%s.zooCmd%d" % ( self.obj, slot ), newCmdInfo )
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

			if attr.startswith(slotPrefix) and slot.isdigit(): slots.append( int(slot) )
		slots.sort()

		return slots
	def connects( self ):
		connects = [self.obj]
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
					if objExists(objPath): connects.append( objPath.split('.')[0] )

					#if there is no connect, then check to see if there is a name cache, and query it
					elif objExists( cacheAttrName ):
						cacheName = cmd.getAttr( cacheAttrName )
						if objExists( cacheName ):
							self.append( cacheName, slot )  #add the object to the connect slot
							connects.append( cacheName )
		except TypeError: pass

		return connects
	@classmethod
	def CreateMenu( cls, object, name='<empty>', cmdStr='//blank', slot=None ):
		new = cls(object)
		new.setMenuInfo(slot,name,cmdStr)

		return new
	def resolve( self, cmd, optionals=[] ):
		'''returns a resolved cmd string.  the cmd string can be either passed in, or if you specify the slot number
		the the cmd string will be taken as the given slot's menu command'''
		connects = self.connects()

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
			try: return connects[ int(idx) ]
			except IndexError: return "<invalid connect>"

		cmd = connectRE.sub(connectRep,cmd)

		#finally resolve %opt<x>%
		optionalRE = compile('(\%opt)(-*[0-9]+)(\%)')
		def optionalRep( matchobj ):
			charA,idx,charB = matchobj.groups()
			try: return optionals[ int(idx) ]
			except IndexError: return "<invalid optional>"

		cmd = optionalRE.sub(optionalRep,cmd)

		return cmd
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
	def append( self, object, slot=None ):
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


def writeSetAttrCmd( trigger, slots ):
	return


def listTriggers():
	'''lists all trigger objects in the current scene'''
	allObjects = cmd.ls(type='transform')
	triggers = []
	attr = 'zooTrigCmd0'

	try:
		for obj in allObjects:
			if objExists( '%s.%s' % ( obj, attr ) ):
				triggers.append( obj )
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
