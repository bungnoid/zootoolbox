'''
this is a collection of lazy man's functions for using the API via python in maya
its not uncommon for useful things that you often want to do to take quite a few
lines of code in the API.  these aren't particularly efficient, but they'll make
easier to read scripts if speed isn't a consideration
'''


try:
	import maya.OpenMaya as OpenMaya
	import maya.cmds as cmd
	import maya.mel

	melEval = maya.mel.eval
except AttributeError: pass

from cacheDecorators import *
from qcTools import getMdlFromQc
from filesystem import *
import names, traceback, datetime, maya.utils, assetTools, utils, filesystem
from vectors import *

Callback = utils.Callback


'''
_today = datetime.datetime.today()
kMAYA_SCRIPT_EDITOR_LOG = 'c:/mayaScriptEditorLog_%d%d%d%d%d%d%d' % (_today.year, _today.month, _today.day, _today.hour, _today.minute, _today.second, _today.microsecond)


#turn on script editor logging - so we can query script editor dumps when sending maya bug reports
try:
	cmd.scriptEditorInfo(hfn=kMAYA_SCRIPT_EDITOR_LOG, wh=1)
	cmd.scriptEditorInfo(clearHistoryFile=True)
except RuntimeError: pass
'''


def getMObject( objectName ):
	'''given an object name string, this will return the MDagPath api handle to that object'''
	sel = OpenMaya.MSelectionList()
	sel.add( objectName )
	obj = OpenMaya.MObject()
	sel.getDependNode(0,obj)

	return obj


def getMDagPath( objectName ):
	'''given an object name string, this will return the MDagPath api handle to that object'''
	sel = OpenMaya.MSelectionList()
	sel.add( objectName )
	obj = OpenMaya.MDagPath()
	sel.getDagPath(0,obj)

	return obj


def getObjectMatrix( objectName ):
	'''returns an MMatrix representing the local transform matrix for the given object'''
	dagPath = getMDagPath(objectName)
	matrix = OpenMaya.MFnTransform(dagPath).transformation().asMatrix()

	return matrix


def getWorldSpaceMatrix( objectName ):
	#NOTE: so i just found out that this can be done easily using:
	#getMDagPath(obj).inclusiveMatrix()
	#so - this function is kinda redundant
	#first traverse parents - NOTE: this will fail as it is if there are non-unique leaf names - ideally the routine should march up the path list
	parents = getMDagPath(objectName).fullPathName()[1:].split('|') #the slice is to remove the | at the head of the string - its always there
	parents.reverse()

	sel = OpenMaya.MSelectionList()
	for p in parents: sel.add(p)

	matrix = OpenMaya.MMatrix()
	for n in xrange(sel.length()):
		obj = OpenMaya.MDagPath()
		sel.getDagPath(n,obj)
		curMatrix = OpenMaya.MFnTransform(obj).transformation().asMatrix()
		matrix *= curMatrix

	return matrix


def getBases( objectName ):
	'''returns a 3-tuple of world space orthonormal basis vectors that represent the orientation of the given object'''
	x = OpenMaya.MVector(1,0,0)
	y = OpenMaya.MVector(0,1,0)
	z = OpenMaya.MVector(0,0,1)
	objMatrix = getMDagPath( objectName ).inclusiveMatrix()

	return x*objMatrix,y*objMatrix,z*objMatrix


def getRotateDelta( src, tgt, other=None ):
	'''
	returns the euler rotation delta from src to tgt - if other is a valid
	object the rotation is the euler rotation for the other object - typical
	uses of this are for determining the postTrace cmd for rig controls.
	for a leg control for example, getRotateDelta('ankleBone', 'legControl')
	'''
	matA = getMDagPath(src).inclusiveMatrix()
	matB = getMDagPath(tgt).inclusiveMatrix()

	if other is not None:
		matC = getMDagPath(other).exclusiveMatrix().inverse()
		matB = matC * matB

	diffMat = matB * matA.inverse()
	tMat = OpenMaya.MTransformationMatrix(diffMat)
	asEuler = tMat.rotation().inverse().asEulerRotation()
	asEuler = map(OpenMaya.MAngle, (asEuler.x, asEuler.y, asEuler.z))
	asEuler = [a.asDegrees() for a in asEuler]

	return asEuler


def printRotateDelta( **kwargs ):
	'''
	prints data from getRotateDelta
	'''
	sel = cmd.ls(sl=1)

	delta = None
	objToRotate = sel[1]
	if len(sel) == 3:
		objToRotate = sel[2]
		delta = getRotateDelta(sel[0], sel[1], objToRotate)
	else: delta = getRotateDelta(sel[0], sel[1])

	doRotate = kwargs.get('rotate', False)
	if doRotate:
		cmd.rotate(delta[0], delta[1], delta[2], objToRotate, os=True, r=True)

	melPrint('the rotation delta is: %.5f %.5f %.5f' % (delta[0], delta[1], delta[2]))


def MVectorToVector( mvector ):
	return Vector( [mvector.x, mvector.y, mvector.z] )


def VectorToMVector( vector ):
	return OpenMaya.MVector( *vector )


def getFps():
	'''
	returns the current fps as a number
	'''
	timebases = {'ntsc': 30, 'pal': 25, 'film': 24, 'game': 15, 'show': 48, 'palf': 50, 'ntscf': 60}
	base = cmd.currentUnit(q=True, time=True)
	return timebases[base]


def sceneChange():
	'''
	returns the changelist number for the current scene
	'''
	change = P4Data( cmd.file(q=True, sn=True) ).getChange()
	return change



inMainThread = maya.utils.executeInMainThreadWithResult

def iterParents( obj ):
	parent = cmd.listRelatives( obj, p=True, l=True )
	while parent is not None:
		yield parent[ 0 ]
		parent = cmd.listRelatives( obj, p=True, l=True )


def pyArgToMelArg(arg):
	#given a python arg, this method will attempt to convert it to a mel arg string
	if isinstance(arg, basestring): return '"%s"' % cmd.encodeString(arg)

	#if the object is iterable then turn it into a mel array string
	elif hasattr(arg, '__iter__'): return '{%s}' % ','.join(map(pyArgToMelArg, arg))

	#either lower case bools or ints for mel please...
	elif isinstance(arg, bool): return str(arg).lower()

	#otherwise try converting the sucka to a string directly
	return unicode(arg)


class Mel( object ):
	'''creates an easy to use interface to mel code as opposed to having string formatting operations
	all over the place in scripts that call mel functionality'''
	def __init__( self, echo=False ):
		self.echo = echo
	def __getattr__( self, attr ):
		if attr.startswith('__') and attr.endswith('__'):
			return self.__dict__[attr]

		#construct the mel cmd execution method
		echo = self.echo
		def melExecutor( *args ):
			strArgs = map(pyArgToMelArg,args)
			cmdStr = '%s(%s);' % (attr, ','.join(strArgs))

			if echo: print cmdStr
			try:
				retVal = melEval(cmdStr)
			except RuntimeError:
				print 'cmdStr: %s' % cmdStr
				return
			return retVal

		return melExecutor
	def source( self, script ):
		return melEval('source "%s";' % script)
	def eval( self, cmdStr ):
		if self.echo:
			melPrint(cmdStr)

		try:
			return melEval(cmdStr)
		except RuntimeError:
			print 'ERROR :: trying to execute the cmd:'
			print cmdStr
			raise


mel = Mel()
melecho = Mel(echo=True)


class CmdQueue(list):
	'''
	the cmdQueue is generally used as a bucket to store a list of maya commands to execute.  for whatever
	reason executing individual maya commands through python causes each command to get put into the undo
	queue - making tool writing a pain.  so for scripts that have to execute maya commands one at a time,
	consider putting them into a CmdQueue object and executing the object once you're done generating
	commands...  to execute a CmdQueue instance, simply call it
	'''
	def __init__( self ):
		list.__init__(self)
	def __call__( self, echo=False ):
		m = mel
		if echo:
			m = melecho

		m.eval( ';'.join( self ) )


def melPrint( strToPrint ):
	'''
	this dumb looking method routes a print through the mel print command instead of the python print statement.  this
	is useful because it seems the script line in the main maya UI doesn't echo data printed to the python.stdout.  so
	if you want to communicate via this script line from python scripts, you need to print using this method
	'''
	try:
		melEval('''print "%s\\n";''' % cmd.encodeString(str(strToPrint)))
	except RuntimeError:
		#if encodeString fails, bail...
		pass


def melPrintTrace( msgStr, typeStr='INFO' ):
	trace = traceback.extract_stack()
	callerToks = []

	#we want to skip the first item (as its always the <maya console>, and we want to skip
	#the last item which is always this method...
	for frame in trace[:-2]:
		type = frame[2]
		if type == '<module>':
			callerToks.append( '<%s>' % Path(frame[0]).setExtension()[-1] )
		else: callerToks.append(type)

	caller = '::'.join(callerToks)
	melPrint('### %s %s()  %s' % (typeStr, caller, msgStr))


def melError( errorStr ):
	melPrintTrace(errorStr, 'ERROR')


def melWarning( errorStr ):
	melPrintTrace(errorStr, 'WARNING')


def validateAsMayaName( theStr, replaceChar='_' ):
	invalidMayaChars = """`~!@#$%^&*()-+=[]\\{}|;':"/?><., """
	for char in invalidMayaChars:
		theStr = theStr.replace(char, '_')

	return theStr


ui_BUTTONS = OK, CANCEL = 'OK', 'Cancel'
ui_QUESTION = YES, NO = 'Yes', 'No'
def doPrompt( **kwargs ):
	'''
	does a prompt dialog (all args are passed directly to the dial creation method) and returns a 2 tuple of the dial dismiss
	string and the actual input value
	'''
	kwargs.setdefault('t', 'enter name')
	kwargs.setdefault('m', 'enter name')
	kwargs.setdefault('b', ui_BUTTONS)

	#set the default button	- buttons is always an iterable, so use the first item
	kwargs.setdefault('db', kwargs['b'][0])

	#throw up the dial
	ans = cmd.promptDialog(**kwargs)

	return ans, cmd.promptDialog(q=True, tx=True)


def doConfirm( **kwargs ):
	kwargs.setdefault('t', 'are you sure?')
	kwargs.setdefault('m', 'are you sure?')
	kwargs.setdefault('b', ui_QUESTION)

	#set the default button	- buttons is always an iterable, so use the first item
	kwargs.setdefault('db', kwargs['b'][0])

	#throw up the dial
	ans = cmd.confirmDialog(**kwargs)

	return ans


#
def checkIfp4Edit( sceneName ):
	p4Enabled = isPerforceEnabled()
	sceneName = P4File( sceneName )

	#check out of perforce
	if not Path( sceneName ).exists:
		return

	if not p4Enabled:
		ans = cmd.confirmDialog( t="p4 integration disabled", m="perforce integration has been turned off\ndo you want to turn it back on?", b=("Yes", "No"), db="Yes" )
		if ans == "Yes":
			enablePerforce()
		else:
			return

	names = []
	data = []
	isEdit = sceneName.isEdit()

	if isEdit is False:
		ans = ''
		default = cmd.optionVar( q='vSaveAutoCheckout' ) if cmd.optionVar( ex='vSaveAutoCheckout' ) else ''
		if default == "":
			ans = cmd.confirmDialog( t="file isn't checked out", m="the file: %s\nisn't checked out\ndo you want me to open for edit?" % sceneName, b=("Yes", "No", "always", "never"), db="OK" )
			if ans == "always":
				cmd.optionVar( sv=('vSaveAutoCheckout', "always") )
			elif ans == "never":
				cmd.optionVar( sv=('vSaveAutoCheckout', "never") )
				melWarning( "file is checked into perforce - and pref is set to never checkout before save, so bailing..." )
				return

			default = cmd.optionVar( q='vSaveAutoCheckout' )

		#if the user has specified never - and the file isn't open for edit, then bail.  we don't even want to try to save because the file isn't writeable
		if default == "never":
			ans = cmd.confirmDialog( t="file isn't checked out", m="file isn't checked out - bailing on save", b=("OK", "turn auto checkout back on"), db="OK" )
			if ans != "OK":
				cmd.optionVar( rm='vSaveAutoCheckout' )
			else:
				melWarning( "file is checked into perforce - and pref is set to never checkout before save, so bailing..." )
				return

		if ans == "Yes" or ans == "always":
			sceneName.edit()


#there are here to follow the convention specified in the assetTools writeExportDict method
kEXPORT_DICT_SCENE = 'scene'
kEXPORT_DICT_APP_VERSION = 'app_version'
def writeExportDict( toolName=None, toolVersion=None, **kwargs ):
	'''
	wraps the assetTools method of the same name - and populates the dict with maya
	specific data
	'''
	d = assetTools.writeExportDict(toolName, toolVersion, **kwargs)
	d[kEXPORT_DICT_SCENE] = cmd.file(q=True, sn=True)
	d[kEXPORT_DICT_APP_VERSION] = cmd.about(version=True)

	return d


class Name(object):
	@initCache
	def __init__( self, name ):
		self.name = str(name)
		self._root = False
	@classmethod
	def Obj( cls, object ):
		return cls( longname(name) )
	def __str__( self ):
		return self.name
	__repr__ = __str__
	def __add__( self, other ):
		if isinstance(other,self.__class__):
			other = other.name
		return self.__class__(self.name+'|'+other)
	#the | or + operator both concatenate path tokens
	__or__ = __add__
	@cacheValueWithArgs
	def __getitem__( self, item ):
		toks = self.split()
		return toks[item]
	@resetCache
	def __setitem__( self, item, value ):
		toks = self.split()
		toks[item] = value
		self.name = '|'.join(toks)
	@cacheValueWithArgs
	def __getslice__( self, a, b ):
		toks = self.split()
		newPath = '|'.join(toks[a:b])
		return self.__class__(newPath)
	def __eq__( self, other ):
		cmpStr = other
		if isinstance(other,self.__class__): cmpStr = other.name
		return self.name == cmpStr
	def __neq__( self, other ):
		cmpStr = other
		if isinstance(other,self.__class__): cmpStr = other.name
		return self.name != cmpStr
	@cacheValue
	def __len__( self ):
		return len(self.split())
	def __contains__( self, item ):
		return item in self.split()
	def long( self ):
		'''
		returns the full path to the node
		'''
		try:
			longStr = longname( str(self) )
		except TypeError:
			longStr = str( self )

		long = self.__class__( longStr )
		self._root = longStr.startswith('|')

		return self.__class__( long )
	def short( self ):
		'''
		returns the shortest possible path to the object
		'''
		short = getMDagPath(str(self)).partialPathName()
		return self.__class__( short )
	def copy( self ):
		return self.__class__(self)
	@cacheValue
	def split( self ):
		return map(self.__class__, [s for s in str(self.long() ).split('|') if s])
	def up( self, levels=1 ):
		'''
		returns a new path object with <levels> path tokens removed from the tail.
		ie: Path("a/b/c/d").up(2) returns Path("a/b")
		'''
		toks = self.split()
		levels = max( min( levels, len(toks)-1 ), 1 )
		newPath = '|'.join(toks[:-levels])

		return self.__class__(newPath)
	@resetCache
	def pop( self, levels=1 ):
		'''NOTE: levels acts as the number of trailing path tokens to pop out of the list, NOT the index
		of path token to pop - this is different from the pop implementation in lists'''
		toks = self.split()
		levels = max( min( levels, len(toks)-1 ), 1 )
		toReturn = toks[-levels:]
		self.name = '|'.join(toks[:-levels])

		return toReturn
	@resetCache
	def append( self, item ):
		'''acts just like a list append - adds the given item to the list of path tokens'''
		if item is None: return self
		toks = self.split('|')
		toks.append(item)
		self.name = '|'.join(toks)

		return self
	@resetCache
	def extend( self, items ):
		'''just like list.extend() - this method will extend the token list by a given iterable'''
		toks = self.split()
		toks.extend(items)
		self.name = '|'.join(toks)

		return self
	def attrdata( self ):
		'''returns a tuple containing all the attribute data contained in the name - the objectName, attributePath, componentID'''
		name = str(self)
		nameData = self[-1].split('.')
		numToks = len(nameData)
		if numToks == 1: return None

		lenName = len(name)
		attr = '.'.join( nameData[1:] )
		id = None
		idType = None
		bracketIdx = name.rfind('[')
		idType = attr[:attr.find('[')]
		if bracketIdx > 0:
			id = name[ bracketIdx+1:-1 ]

		return nameData[0], attr, id, idType
	@resetCache
	def lower( self ):
		'''returns a str representation in lowercase of self'''
		return self.name.lower()
	@resetCache
	def replace( self, search, replace ):
		'''a simple search replace method'''
		toks = self.split()
		try:
			idx = toks.index(search)
			toks[idx] = replace
		except ValueError:
			pass
	@cacheValue
	def _exists( self ):
		return cmd.objExists( str(self) )
	exists = property(_exists)
	def delete( self ):
		try: cmd.delete( str(self) )
		except TypeError: pass
	remove = delete
	@resetCache
	def rename( self, newName ):
		'''
		the instance is modified in place
		'''
		if self.exists:
			newName = self.__class__( str(newName) )
			oldName = str(self)
			renamed = cmd.rename( str(self) ,newName[-1] )
			self.name = renamed

		return self
	def getOpposite( self ):
		'''
		returns the opposite path to the instance.  NOTE: the object may not exist in the scene
		'''
		toks = self.split()
		oppToks = []
		if self._root: oppToks.append('')  #this makes sure a | prefixes the name
		for tok in toks:
			oppToks.append( names.Name(tok).swap_parity() )
		return self.__class__( '|'.join(map(str, oppToks)) )
	def addNamespace( self, namespace ):
		toks = self.split()
		toks = [ '%s:%s' % (namespace, tok) for tok in toks ]

		return '|'.join( toks )


def longname( name ):
	try:
		longname = cmd.ls(name, long=True)
		return longname[0]
	except IndexError: raise TypeError
	except AttributeError: return name


def updateProgressCallback( curLine, numLines ):
	'''
	provides a generic callback for progress window updating when doing lengthy tasks
	'''
	progress = int( curLine/float(numLines)*100 )
	progressWindow(edit=True,progress=progress)


def lengthyPerforceOpWarning( *a, **kw ):
	cmd.confirmDialog( t='PERFORCE IS BEING TARDY', m='perforce is taking a long time...  the command issued was:\n%s, %s' % (a, kw), b=('OK',), db='OK' )


filesystem.P4_LENGTHY_CALLBACK = lengthyPerforceOpWarning
def addPerforceMenuItems( filepath, **kwargs ):
	'''
	keyword args:
	  others=[iterable]  if others is an iterable, they get included in any perforce operation on the primary file (specified using filepath)
	  previous=True      controls whether the previous revisions menu is displayed
	'''
	#defaults
	DEF_NUM_PREV = 10
	DEF_SHOW_PREV = kwargs.get('previous', True)

	p4Enabled = isPerforceEnabled()
	if not p4Enabled:
		cmd.menuItem(en=False, l='Perforce Integration Disabled', ann='perforce is not available')
		cmd.menuItem(l='Re-Enable Perforce Integration', c=lambda *a: enablePerforce(), ann='attempt to re-enable the perforce connection')
		return

	asPath = Path(filepath)
	p4 = P4Data(asPath)
	status = p4.getStatus()
	filepath = str(asPath.resolve())
	isManaged = p4.managed()
	exists = asPath.exists

	#build a list of files to operate on
	files = [filepath]
	others = kwargs.get('others', None)
	if others:
		for f in others:
			files.append(f)

	thisScene = Path( cmd.file( q=True, sn=True ) )
	def doReload():
		if thisScene in files:
			ans = cmd.confirmDialog( m="Do you want to reload the file?", b=("Yes", "No"), db="No" )
			if ans == "Yes": cmd.file( thisScene, f=True, o=True )

	if exists:
		if isManaged:
			action = status.get('action')
			otherOpen = status.get('otherOpen')

			if otherOpen is not None:
				for person in otherOpen:
					cmd.menuItem(l='ALSO OPENED BY %s' % person, boldFont=True, ann='this file is also opened by %s' % person)

			isEdit = False
			if action == 'add' or action == 'edit':
				isEdit = True

			headRev, haveRev = int(status.get('headRev', 0)), int(status.get('haveRev', 0))
			def onEdit(*x):
				p4 = P4Data()
				for f in files: p4.edit(f)
			cmd.menuItem( l='Open for Add' if headRev==0 else 'Open for Edit', cb=isEdit, c=onEdit, ann='open the file for add')

			def onSync(*x):
				p4 = P4Data()
				for f in files: p4.sync(f)
				doReload()
			cmd.menuItem(en=headRev!=haveRev, l='Sync %s/%s' % (haveRev, headRev), c=onSync, ann='sync to the head revision for this file')

			#build the previous revisions menu if desired
			if DEF_SHOW_PREV and headRev>1:
				cmd.menuItem(l='Sync to previous...', sm=True, ann='sync to a previous revision for this file')
				num = min( headRev - 1, kwargs.get( 'numPrev', DEF_NUM_PREV ) )
				for n in range( num ):
					nRev = headRev - n - 1
					def onSyncRev( files, rev ):
						p4 = P4File()
						for f in files: p4.sync( f, rev=rev )
						doReload()
					cmd.menuItem(cb=haveRev==nRev, l='Sync to rev %s' % nRev, c=Callback(onSyncRev, files, nRev), ann='sync to revision %s' % nRev)
				cmd.menuItem(d=True)

				def onSyncRev(*x):
					ans, num = doPrompt(t='Enter revision number', m='Enter revision number', db=OK)
					if ans == DB and num:
						p4 = P4Data()
						for f in files: p4.sync(f, rev=num)
						doReload()
				cmd.menuItem(l='Sync to rev...', c=onSyncRev, ann='opens a window for you to specify which revision to sync to')
				cmd.setParent('..', m=True)

			def onRevert(*x):
				p4 = P4Data()
				for f in files: p4.revert(f)
				doReload()
			cmd.menuItem(en=isEdit, l='Revert', c=onRevert, ann='revert all changes')
		elif p4.isUnderClient():
			def onAdd(*x):
				p4 = P4Data()
				for f in files: p4.add(f)
			cmd.menuItem(l='Add to perforce', c=onAdd, ann='open the file for add')
		else:
			cmd.menuItem(en=False, l='Not under perforce root', ann='the file doesnt appear to be under the perforce client')
	else:
		cmd.menuItem(en=False, l="File doesn't exist" )


def addExploreToMenuItems( filepath ):
	filepath = Path(filepath)
	if not filepath.exists:
		filepath = filepath.getClosestExisting()

	try: filepathResolved = str( filepath.resolve() )
	except AttributeError:
		cmd.menuItem(en=False, l='File not specified')
		return

	xtn = filepath.getExtension().lower()
	if xtn == 'qc':
		mdlPath = getMdlFromQc(filepathResolved)
		try:
			if mdlPath.exists:
				cmd.menuItem(l="Explore to .mdl", c=lambda x: mel.zooExploreTo( mdlPath ), ann='open an explorer window to the location of the .mdl file this .qc file compiles to')
				cmd.menuItem(l="View .mdl in HLMV", c=lambda x: utils.spawnProcess('hlmv.bat "%s"' % mdlPath.resolve(), mdlPath.resolve().up()), ann='open the .mdl this .qc file compiles to in hlmv')
				cmd.menuItem(d=True)
		except AttributeError: pass
	elif xtn == 'mdl':
		try:
			if filepath.exists:
				cmd.menuItem(l="View .mdl in HLMV", c=lambda x: utils.spawnProcess('hlmv.bat "%s"' % filepath.resolve()), ann='open the .mdl in hlmv')
				cmd.menuItem(d=True)
		except AttributeError: pass

	cmd.menuItem(l="Explore to location...", c=lambda x: mel.zooExploreTo( filepathResolved ), ann='open an explorer window to the location of this file/directory')
	cmd.menuItem(l="CMD prompt to location...", c=lambda x: mel.zooCmdTo( filepathResolved ), ann='open a command prompt to the location of this directory')
	cmd.menuItem(l="Perforce to location...", c=lambda x: mel.openp4At( filepathResolved ), ann='open p4win to the location of this file/directory')

	#useP4V = cmd.optionVar(q='vUseP4V')
	#cmd.menuItem(l='use P4V as GUI', cb=useP4V, c='cmd.optionVar(iv=("vUseP4V", %d))' % (not useP4V))
	#cmd.setParent('..', m=True)


def p4buildMenu( parent, file=None ):
	file = Path( file )

	cmd.menu( parent, e=True, dai=True )
	cmd.setParent( parent, m=True )

	#if the given file is an empty string, then query the currently opened file and use that
	if not file:
		file = Path( cmd.file( q=True, sn=True ) )

	addPerforceMenuItems( file )
	cmd.menuItem( d=True )

	if isPerforceEnabled() and file.exists:
		def doGather( *a ):
			import exportManagerCore
			exportManagerCore.gatherSceneDependenciesIntoChange()
		cmd.menuItem( l="Generate Changelist For This Scene", c=doGather, ann="adds all files that this scene depends on or generates (ie textures, dmx files, .qc files, .mdl files etc...) to the changelist for the current scene" )

		#ignoreTexs = cmd.optionVar( q='vIgnoreTexturesOnCheckin' ) if cmd.optionVar( ex='vIgnoreTexturesOnCheckin' ) else True
		#def doTex( *a ):
			#cmd.optionVar( iv=('vIgnoreTexturesOnCheckin', a[ 0 ] ) )
		#cmd.menuItem( l="Ignore Textures", cb=ignoreTexs, c=doTex, ann="ignores textures by default when doing most perforce operations" )

		def syncDeps( *a ):
			import exportManagerCore
			exportManagerCore.syncStaleSceneDependencies()
			ans = cmd.confirmDialog( m="do you want to reload the file?", b=("Yes", "No"), db="No" )
			if ans == "Yes": cmd.file( file, f=True, o=True )
		cmd.menuItem( l="Sync Maya Dependencies", c=syncDeps )
		cmd.menuItem( d=True )

	addExploreToMenuItems( file )


def listOutOfSyncDependencies():
	refFiles = map( Path, cmd.file( q=True, l=True ) )
	relevantExts = [ "ma", "mb", "dmx" ]
	relevantFiles = [ f for f in refFiles if f.getExtension().lower() in relevantExts ]

	badSyncFiles = []
	for f in relevantFiles:
		isLatest = P4File( f ).isLatest()
		if isLatest is None:
			continue

		if not isLatest:
			badSyncFiles.append( f )

	return badSyncFiles


def onFileOpenCB():
	#make sure the file being loaded is under the current project - otherwise weird things can happen
	#with the export manager etc...
	import exportManagerCore
	if not exportManagerCore.isSceneUnderCurrentProject():
		cmd.confirmDialog( m="WARNING: the current scene isn't under the current project...\n\nthis will most likely cause problems.  please exit maya and\nset your project correctly", t="project/scene mismatch", db="OK" )

	#update export manager data...
	import exportManagerUI
	exportManager = exportManagerCore.ExportManager()
	exportManager.update()
	exportManagerUI.update()


	#check for the existence of various windows, and reopen them
	if cmd.window( 'modelCompiler', ex=True ):
		cmd.deleteUI( 'modelCompiler' )


	file = Path( cmd.file( q=True, sn=True ) )
	if file.exists:
		statusDict = P4File( file ).getStatus()
		msgs = []

		staleDeps = listOutOfSyncDependencies()
		if staleDeps:
			msgs.append( "WARNING: the following files are used by this scene, but aren't up to date with the latest perforce revision:\n\n%s\n\nyou can sync all dependencies from the perforce menu in maya:\nPerforce -> Sync Maya Dependencies" % '\n'.join( staleDeps ) )

		#check to see if the file is open for edit by someone else, and warn the user
		otherOpens = []
		try:
			otherOpens = statusDict[ 'otherOpen' ]
		except KeyError: pass
		except TypeError: pass

		if otherOpens:
			msgs.append( "WARNING: this file is open for edit by:\n%s\n\nif you plan of making changes, make sure you check when them first before putting in too much work" % '\n'.join( otherOpens ) )

		if msgs:
			cmd.confirmDialog( m='\n------------------------------\n\n'.join( msgs ), b='OK', db='OK' )


######  DECORATORS  ######
def d_showWaitCursor(f):
	'''
	turns the wait cursor on while the decorated method is executing, and off again once finished
	'''
	def func(*args, **kwargs):
		cmd.waitCursor(state=True)
		try:
			retVal = f(*args, **kwargs)
		except:
			raise
		finally:
			cmd.waitCursor(state=False)

		return retVal
	return func


def d_confirmAction( *a, **dec_kwargs ):
	'''
	decorates a method with an 'are you sure' style dialog.  this decorator is a little clunky because of maya's long and
	short kwargs.  but to specify flags when using this decorator, always use long arg names.  also, by default the function
	being decorated gets executed on an response of 'OK'.  this response can be changed by setting the 'answer' kwarg when
	decorating
	'''
	dec_kwargs.setdefault('message', 'Are you sure?')
	dec_kwargs.setdefault('title', 'Are you sure?')
	dec_kwargs.setdefault('button', ('OK', 'Cancel'))

	dec_kwargs.setdefault('m', dec_kwargs['message'])
	dec_kwargs.setdefault('t', dec_kwargs['title'])
	def dec(f):
		def func(*args, **kwargs):
			ans = cmd.confirmDialog(**dec_kwargs)
			if ans == dec_kwargs.get('answer', 'OK'):
				return f(*args, **kwargs)
		return func
	return dec


def d_disableViews( f ):
	'''
	disables all viewports before, and re-enables them after
	'''
	def func(*args, **kwargs):
		modelPanels = cmd.getPanel(vis=True)
		emptySelConn = cmd.selectionConnection()

		for panel in modelPanels:
			if cmd.getPanel(to=panel) == 'modelPanel':
				cmd.isolateSelect(panel, state=True)
				cmd.modelEditor(panel, e=True, mlc=emptySelConn)

		try:
			ret = f(*args, **kwargs)
		except:
			raise
		finally:
			cmd.deleteUI(emptySelConn)

		return ret
	return func


def d_noAutoKey( f ):
	'''
	forces autoKey off
	'''
	def func(*args, **kwargs):
		initialState = cmd.autoKeyframe(q=True, state=True)
		cmd.autoKeyframe(state=False)
		try:
			ret = f(*args, **kwargs)
		except:
			raise
		finally:
			cmd.autoKeyframe(state=initialState)

		return ret
	return func


def d_noUndo( f ):
	'''
	forces undo off
	'''
	def func(*args, **kwargs):
		initialState = cmd.undoInfo(q=True, state=True)
		cmd.undoInfo(stateWithoutFlush=False)
		try:
			ret = f(*args, **kwargs)
		except:
			raise
		finally:
			cmd.undoInfo(stateWithoutFlush=initialState)

		return ret
	return func


def d_progress( **dec_kwargs ):
	'''
	deals with progress window...  any kwargs given to the decorator on init are passed to the progressWindow init method
	'''
	def dec(f):
		def func(*args, **kwargs):
			try:
				cmd.progressWindow(**dec_kwargs)
			except: print 'error init-ing the progressWindow'

			try: ret = f(*args, **kwargs)
			except:
				#end the progressWindow on any exception and re-raise...
				raise
			finally:
				cmd.progressWindow(ep=True)

			return ret
		return func
	return dec


#end