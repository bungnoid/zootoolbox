'''
this is a collection of lazy man's functions for using the API via python in maya
its not uncommon for useful things that you often want to do to take quite a few
lines of code in the API.  these aren't particularly efficient, but they'll make
easier to read scripts if speed isn't a consideration
'''

import __future__
import traceback

from cacheDecorators import *
from filesystem import *
from vectors import *
from mayaDecorators import d_disableViews, d_noAutoKey, d_noUndo, d_progress, d_showWaitCursor

import maya.OpenMaya as OpenMaya
import maya.cmds as cmd
import maya.mel

import maya.utils
import names

melEval = maya.mel.eval
mayaVer = melEval( 'getApplicationVersionAsFloat()' )

MATRIX_ROTATION_ORDER_CONVERSIONS_TO = Matrix.ToEulerXYZ, Matrix.ToEulerYZX, Matrix.ToEulerZXY, Matrix.ToEulerXZY, Matrix.ToEulerYXZ, Matrix.ToEulerZYX


def getMObject( objectName ):
	'''given an object name string, this will return the MDagPath api handle to that object'''
	sel = OpenMaya.MSelectionList()
	sel.add( str( objectName ) )
	obj = OpenMaya.MObject()
	sel.getDependNode(0,obj)

	return obj


def getMDagPath( objectName ):
	'''given an object name string, this will return the MDagPath api handle to that object'''
	sel = OpenMaya.MSelectionList()
	sel.add( str( objectName ) )
	obj = OpenMaya.MDagPath()
	sel.getDagPath(0,obj)

	return obj


def getObjectMatrix( objectName ):
	'''returns an MMatrix representing the local transform matrix for the given object'''
	dagPath = getMDagPath(objectName)
	matrix = OpenMaya.MFnTransform(dagPath).transformation().asMatrix()

	return matrix


def getWorldSpaceMatrix( objectName ):
	return getMDagPath( objectName ).inclusiveMatrix()


def getObjectBases( objectName ):
	'''returns a 3-tuple of world space orthonormal basis vectors that represent the orientation of the given object'''
	x = OpenMaya.MVector( 1, 0, 0 )
	y = OpenMaya.MVector( 0, 1, 0 )
	z = OpenMaya.MVector( 0, 0, 1 )
	matrix = getMDagPath( objectName ).inclusiveMatrix()

	return x * matrix, y * matrix, z * matrix


def getLocalBases( objectName ):
	'''returns a 3-tuple of world space orthonormal basis vectors that represent the local coordinate system of the given object'''
	x = OpenMaya.MVector( 1, 0, 0 )
	y = OpenMaya.MVector( 0, 1, 0 )
	z = OpenMaya.MVector( 0, 0, 1 )
	matrix = getMDagPath( objectName ).exclusiveMatrix()

	return x * matrix, y * matrix, z * matrix


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
	asEuler = tuple( a.asDegrees() for a in asEuler )

	return asEuler


def getRotateDelta__( srcJoint, jointControl ):
	'''
	srcJoint should be the joint to which we want to align the rigged skeleton
	tgtJoint is the joint on the rigged skeleton which is driven by the jointControl
	'''
	mat_j = Matrix( getAttr( '%s.worldInverseMatrix' % srcJoint ) )  #getMDagPath( srcJoint ).inclusiveMatrix()
	mat_c = Matrix( getAttr( '%s.worldMatrix' % jointControl ) )  #getMDagPath( jointControl ).inclusiveMatrix()

	#generate the matrix describing offset between joint and the rig control
	mat_o = mat_j * mat_c

	#put into space of the control
	rel_mat = mat_o * Matrix( getAttr( '%s.parentInverseMatrix' % jointControl ) )  #getMDagPath( jointControl ).exclusiveMatrixInverse()

	#now figure out the euler rotations for the offset
	ro = getAttr( '%s.ro' % jointControl )
	asEuler = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ ro ]( rel_mat, True )

	cmd.rotate( asEuler[ 0 ], asEuler[ 1 ], asEuler[ 2 ], jointControl, relative=True, os=True )

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


def iterNamespaces( namespace=':' ):
	'''
	iterates over all namespaces under and including the one given...  holy sH1t namespaces suck
	b4lls in maya
	'''
	if namespace.endswith( ':' ):
		namespace = namespace[ :-1 ]

	namespaces = [ namespace ]
	idx = 0

	while True:
		try:
			curNS = namespaces[ idx ]
		except IndexError: break

		idx += 1

		try:
			cmd.namespace( set=curNS )
		except RuntimeError: continue

		subs = cmd.namespaceInfo( listOnlyNamespaces=True )
		if subs is None:
			continue

		namespaces += subs

	return iter( namespaces )


def lsSelectedAnimLayers():
	selected = []
	for animLayer in cmd.ls( typ='animLayer' ):
		if cmd.animLayer( animLayer, q=True, selected=True ):
			selected.append( animLayer )

	return selected


inMainThread = maya.utils.executeInMainThreadWithResult

def iterParents( obj ):
	parent = cmd.listRelatives( str( obj ), p=True, pa=True )
	while parent is not None:
		yield parent[ 0 ]
		parent = cmd.listRelatives( parent[ 0 ], p=True, pa=True )


def sortByHierarchy( objs ):
	sortedObjs = []
	for o in objs:
		pCount = len( list( iterParents( o ) ) )
		sortedObjs.append( (pCount, o) )

	sortedObjs.sort()

	return [ o[ 1 ] for o in sortedObjs ]


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
			strArgs = map( pyArgToMelArg, args )
			cmdStr = '%s(%s);' % (attr, ','.join( strArgs ))

			if echo: print cmdStr
			try:
				retVal = melEval( cmdStr )
			except RuntimeError:
				print 'cmdStr: %s' % cmdStr
				return
			return retVal

		melExecutor.__name__ = attr

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

		fp = Path( "%TEMP%/cmdQueue.mel" )
		f = open( fp, 'w' )
		f.writelines( '%s;\n' % l for l in self )
		f.close()
		print fp

		m.source( fp )


def melPrint( *args ):
	'''
	this dumb looking method routes a print through the mel print command instead of the python print statement.  this
	is useful because it seems the script line in the main maya UI doesn't echo data printed to the python.stdout.  so
	if you want to communicate via this script line from python scripts, you need to print using this method
	'''
	try:
		argsStr = ' '.join( cmd.encodeString( str(a) ) for a in args )
		melEval('''print "%s\\n";''' % argsStr )
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


#there are here to follow the convention specified in the filesystem writeExportDict method
kEXPORT_DICT_SCENE = 'scene'
kEXPORT_DICT_APP_VERSION = 'app_version'
def writeExportDict( toolName=None, toolVersion=None, **kwargs ):
	'''
	wraps the filesystem method of the same name - and populates the dict with maya
	specific data
	'''
	d = writeExportDict( toolName, toolVersion, **kwargs )
	d[ kEXPORT_DICT_SCENE ] = cmd.file( q=True, sn=True )
	d[ kEXPORT_DICT_APP_VERSION ] = cmd.about( version=True )

	return d


def referenceFile( filepath, namespace, silent=False ):
	filepath = Path( filepath )
	cmd.file( filepath, r=True, prompt=silent, namespace=namespace )


def openFile( filepath, silent=False ):
	filepath = Path( filepath )
	ext = filepath.getExtension().lower()
	if ext == 'ma' or ext == 'mb':
		mel.saveChanges( 'file -f -prompt %d -o "%s"' % (silent, filepath) )
		mel.addRecentFile( filepath, 'mayaAscii' if Path( filepath ).hasExtension( 'ma' ) else 'mayaBinary' )


def importFile( filepath, silent=False ):
	filepath = Path( filepath )
	ext = filepath.getExtension().lower()
	if ext == 'ma' or ext == 'mb':
		cmd.file( filepath, i=True, prompt=silent, rpr='__', type='mayaAscii', pr=True, loadReferenceDepth='all' )


class Name(object):
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
	def __getitem__( self, item ):
		toks = self.split()
		return toks[item]
	def __setitem__( self, item, value ):
		toks = self.split()
		toks[item] = value
		self.name = '|'.join(toks)
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
	def pop( self, levels=1 ):
		'''NOTE: levels acts as the number of trailing path tokens to pop out of the list, NOT the index
		of path token to pop - this is different from the pop implementation in lists'''
		toks = self.split()
		levels = max( min( levels, len(toks)-1 ), 1 )
		toReturn = toks[-levels:]
		self.name = '|'.join(toks[:-levels])

		return toReturn
	def append( self, item ):
		'''acts just like a list append - adds the given item to the list of path tokens'''
		if item is None: return self
		toks = self.split('|')
		toks.append(item)
		self.name = '|'.join(toks)

		return self
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
	def lower( self ):
		'''returns a str representation in lowercase of self'''
		return self.name.lower()
	def replace( self, search, replace ):
		'''a simple search replace method'''
		toks = self.split()
		try:
			idx = toks.index(search)
			toks[idx] = replace
		except ValueError:
			pass
	def _exists( self ):
		return cmd.objExists( str(self) )
	exists = property(_exists)
	def delete( self ):
		try: cmd.delete( str(self) )
		except TypeError: pass
	remove = delete
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
	def getNamespace( self ):
		idx = self.name.rfind( ':' ) + 1
		return self.name[ :idx ]


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


def addPerforceMenuItems( filepath, **kwargs ):
	pass


def addExploreToMenuItems( filepath ):
	if filepath is None:
		return

	filepath = Path( filepath )
	if not filepath.exists:
		filepath = filepath.getClosestExisting()

	if filepath is None:
		return


	cmd.menuItem(l="Explore to location...", c=lambda x: mel.zooExploreTo( filepath ), ann='open an explorer window to the location of this file/directory')

	cmd.menuItem(l="CMD prompt to location...", c=lambda x: mel.zooCmdTo( filepath ), ann='open a command prompt to the location of this directory')


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


def resolveMapping( mapping, **kw ):
	'''
	resolves the mapping to actual maya nodes - returns a mapping object with non existing nodes
	stripped.  any additional kw args are passed to the matchNames function
	'''
	assert isinstance( mapping, names.Mapping )

	toSearch = cmd.ls( typ='transform' )
	existingSrcs = []
	existingTgts = []

	for src, tgt in mapping.iteritems():
		if not cmd.objExists( src ):
			src = names.matchNames( [ src ], toSearch, **kw )[ 0 ]

		if not cmd.objExists( tgt ):
			tgt = names.matchNames( [ tgt ], toSearch, **kw )[ 0 ]

		if cmd.objExists( src ) and cmd.objExists( tgt ):
			existingSrcs.append( src )
			existingTgts.append( tgt )

	return names.Mapping( existingSrcs, existingTgts )


######  DECORATORS  ######

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


_ANIM_LAYER_ATTRS = [ 'mute',
					 'solo',
					 'lock',
					 'override',
					 #'passthrough',
					 'weight',
					 #'parentMute',
					 #'childsoloed',
					 #'siblingSolo',
					 #'outMute',
					 'preferred',
					 'selected',
					 'collapse',
					 'backgroundWeight' ]

if mayaVer >= 2011:
		_ANIM_LAYER_ATTRS += [ 'rotationAccumulationMode',
		                       'scaleAccumulationMode' ]
else:
	_ANIM_LAYER_ATTRS += [ 'rotationInterpolateMode',
	                       'scaleInterpolateMode' ]


def d_restoreAnimLayers( f ):
	'''
	restores animation layer state -
	'''

	#if this excepts, just return the function as is - anim layers aren't supported by this version
	try:
		cmd.ls( typ='animLayer' )
	except RuntimeError: return f

	def func( *a, **kw ):
		#store pre-function values
		preDict = {}
		selectedLayers = []
		for l in cmd.ls( typ='animLayer' ):
			preDict[ l ] = valueDict = {}
			if cmd.animLayer( l, q=True, selected=True ):
				selectedLayers.append( l )

			for attr in _ANIM_LAYER_ATTRS:
				valueDict[ attr ] = cmd.getAttr( '%s.%s' % (l, attr) )

		#run the function
		try:
			f( *a, **kw )
		finally:
			#restore selection and all layer attributes
			for l, valueDict in preDict.iteritems():
				for attr, value in valueDict.iteritems():
					try: cmd.setAttr( '%s.%s' % (l, attr), value )
					except RuntimeError: pass

			for l in cmd.ls( typ='animLayer' ):
				cmd.animLayer( l, e=True, selected=False )

			for l in selectedLayers:
				cmd.animLayer( l, e=True, selected=True )

			cmd.animLayer( forceUIRefresh=True )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_maintainSceneSelection(f):
	def func( *a, **kw ):
		initSel = cmd.ls( sl=True )
		ret = f( *a, **kw )

		if cmd.ls( sl=True ) != initSel:
			initSel = [ o for o in initSel if cmd.objExists( o ) ]
			if initSel: cmd.select( initSel )

		return ret

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


#end