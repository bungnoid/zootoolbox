
import __future__

from filesystem import *
from vectors import *

import maya.OpenMaya as OpenMaya
import maya.cmds as cmd
import maya.mel

import maya.utils
import names

melEval = maya.mel.eval
mayaVer = melEval( 'getApplicationVersionAsFloat()' )

MATRIX_ROTATION_ORDER_CONVERSIONS_TO = Matrix.ToEulerXYZ, Matrix.ToEulerYZX, Matrix.ToEulerZXY, Matrix.ToEulerXZY, Matrix.ToEulerYXZ, Matrix.ToEulerZYX


def getRotateDelta__( srcJoint, jointControl ):
	'''
	srcJoint should be the joint to which we want to align the rigged skeleton
	tgtJoint is the joint on the rigged skeleton which is driven by the jointControl
	'''
	mat_j = Matrix( getAttr( '%s.worldInverseMatrix' % srcJoint ) )
	mat_c = Matrix( getAttr( '%s.worldMatrix' % jointControl ) )

	#generate the matrix describing offset between joint and the rig control
	mat_o = mat_j * mat_c

	#put into space of the control
	rel_mat = mat_o * Matrix( getAttr( '%s.parentInverseMatrix' % jointControl ) )

	#now figure out the euler rotations for the offset
	ro = getAttr( '%s.ro' % jointControl )
	asEuler = MATRIX_ROTATION_ORDER_CONVERSIONS_TO[ ro ]( rel_mat, True )

	cmd.rotate( asEuler[ 0 ], asEuler[ 1 ], asEuler[ 2 ], jointControl, relative=True, os=True )

	return asEuler


def getFps():
	'''
	returns the current fps as a number
	'''
	timebases = {'ntsc': 30, 'pal': 25, 'film': 24, 'game': 15, 'show': 48, 'palf': 50, 'ntscf': 60}
	base = cmd.currentUnit(q=True, time=True)
	return timebases[base]


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
			print cmdStr

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


#end