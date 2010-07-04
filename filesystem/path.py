from cacheDecorators import *

import os
import re
import sys
import time
import stat
import shutil
import cPickle
import datetime
import subprocess


#the mail server used to send mail
MAIL_SERVER = 'exchange'

DEFAULT_AUTHOR = 'default_username@your_domain.com'


#try to import the windows api - this may fail if we're not running on windows
try:
	import win32con, win32api
except ImportError: pass


#set the pickle protocol to use
PICKLE_PROTOCOL = 2

#set some variables for separators
NICE_SEPARATOR = '/'
NASTY_SEPARATOR = '\\'
NATIVE_SEPARATOR = (NICE_SEPARATOR, NASTY_SEPARATOR)[ os.name == 'nt' ]
PATH_SEPARATOR = '/' #(NICE_SEPARATOR, NASTY_SEPARATOR)[ os.name == 'nt' ]
OTHER_SEPARATOR = '\\' #(NASTY_SEPARATOR, NICE_SEPARATOR)[ os.name == 'nt' ]
UNC_PREFIX = PATH_SEPARATOR * 2


def cleanPath( pathString ):
	'''
	will clean out all nasty crap that gets into pathnames from various sources.
	maya will often put double, sometimes triple slashes, different slash types etc
	'''
	path = str( pathString ).strip().replace( OTHER_SEPARATOR, PATH_SEPARATOR )
	isUNC = path.startswith( UNC_PREFIX )
	while path.find( UNC_PREFIX ) != -1:
		path = path.replace( UNC_PREFIX, PATH_SEPARATOR)

	if isUNC:
		path = PATH_SEPARATOR + path

	return path


ENV_REGEX = re.compile( "\%[^%]+\%" )
def resolve( path, envDict=None, raiseOnMissing=False ):
	'''
	recursively expands all environment variables and '..' tokens in a pathname
	'''
	if envDict is None:
		envDict = os.environ

	#first resolve any env variables
	global ENV_REGEX
	matches = re.findall( ENV_REGEX, path )
	missingVars = set()
	while matches:
		for match in matches:
			try:
				path = str( path ).replace( match, envDict[ match[ 1:-1 ] ] )
			except KeyError:
				if raiseOnMissing: raise
				missingVars.add( match )
		matches = set( re.findall( ENV_REGEX, path ) )

		#remove any variables that have been found to be missing...
		[ matches.remove( missing ) for missing in missingVars ]

	#now resolve any subpath navigation
	path = str( path ).replace( OTHER_SEPARATOR, PATH_SEPARATOR )
	isUNC = path.startswith( UNC_PREFIX )
	if isUNC:
		path = path[ 2: ]

	pathToks = path.split( PATH_SEPARATOR )
	pathsToUse = []
	for n, tok in enumerate( pathToks ):
		if tok == "..":
			try: pathsToUse.pop()
			except IndexError:
				if raiseOnMissing: raise
				pathsToUse = pathToks[ n: ]
				break
		else:
			pathsToUse.append( tok )

	#finally convert it back into a path
	path = PATH_SEPARATOR.join( pathsToUse )
	if isUNC:
		return UNC_PREFIX + path

	return path

resolvePath = resolve


sz_BYTES = 0
sz_KILOBYTES = 1
sz_MEGABYTES = 2
sz_GIGABYTES = 3

class Path(str):
	__CASE_MATTERS = os.name != 'nt'

	@classmethod
	def DoP4( cls ):
		return False
	@classmethod
	def DoesCaseMatter( cls ):
		return cls.__CASE_MATTERS

	def __new__( cls, path='', caseMatters=None, envDict=None ):
		if path is None:
			path = ''

		resolvedPath = resolve( cleanPath( path ), envDict )
		new = str.__new__( cls, resolvedPath )
		new.isUNC = resolvedPath.startswith( UNC_PREFIX )
		new.hasTrailing = resolvedPath.endswith( PATH_SEPARATOR )

		return new
	@d_initCache
	def __init__( self, path='', caseMatters=None, envDict=None ):
		'''
		if case doesn't matter for the path instance you're creating, setting caseMatters
		to False will do things like caseless equality testing, caseless hash generation
		'''

		self._passed = path

		#case sensitivity, if not specified, defaults to system behaviour
		if caseMatters is not None:
			self.__CASE_MATTERS = caseMatters
	@classmethod
	def Temp( cls ):
		'''
		returns a temporary filepath - the file should be unique (i think) but certainly the file is guaranteed
		to not exist
		'''
		import datetime, random
		def generateRandomPathName():
			now = datetime.datetime.now()
			rnd = '%06d' % (abs(random.gauss(0.5, 0.5)*10**6))
			return '%TEMP%'+ PATH_SEPARATOR +'TMP_FILE_%s%s%s%s%s%s%s%s' % (now.year, now.month, now.day, now.hour, now.minute, now.second, now.microsecond, rnd)

		randomPathName = cls(generateRandomPathName())
		while randomPathName.exists:
			randomPathName = cls(generateRandomPathName())

		return randomPathName
	def __nonzero__( self ):
		if self.strip() == '':
			return False

		if self.strip() == PATH_SEPARATOR:
			return False

		return True
	def __add__( self, other ):
		return self.__class__( '%s%s%s' % (self, PATH_SEPARATOR, other), self.__CASE_MATTERS )
	#the / or + operator both concatenate path tokens
	__div__ = __add__
	def __radd__( self, other ):
		return self.__class__( other, self.__CASE_MATTERS ) + self
	__rdiv__ = __radd__
	def __getitem__( self, item ):
		toks = self.split()
		return toks[ item ]
	def __getslice__( self, a, b ):
		toks = self.split()
		newPath = PATH_SEPARATOR.join( toks[ a:b ] ) + ('', PATH_SEPARATOR)[ self.hasTrailing ]

		return self.__class__( newPath, self.__CASE_MATTERS )
	def __len__( self ):
		if not self:
			return 0

		return len( self.split() )
	def __contains__( self, item ):
		if not self.__CASE_MATTERS:
			return item.lower() in [ s.lower() for s in self.split() ]

		return item in self.split()
	def __hash__( self ):
		'''
		the hash for two paths that are identical should match - the most reliable way to do this
		is to use a tuple from self.split to generate the hash from
		'''
		if not self.__CASE_MATTERS:
			return hash( tuple( [ s.lower() for s in self.split() ] ) )

		return hash( tuple( self.split() ) )
	def _toksToPath( self, toks ):
		'''
		given a bunch of path tokens, deals with prepending and appending path
		separators for unc paths and paths with trailing separators
		'''
		if self.isUNC:
			toks = ['', ''] + toks

		if self.hasTrailing:
			toks.append( '' )

		return self.__class__( PATH_SEPARATOR.join( toks ), self.__CASE_MATTERS )
	def resolve( self, envDict=None, raiseOnMissing=False ):
		if envDict is None:
			return self
		else:
			return Path( self.unresolved(), self.__CASE_MATTERS, envDict )
	def unresolved( self ):
		return self._passed
	def isEqual( self, other ):
		'''
		compares two paths after all variables have been resolved, and case sensitivity has been
		taken into account - the idea being that two paths are only equal if they refer to the
		same filesystem object.  NOTE: this doesn't take into account any sort of linking on *nix
		systems...
		'''
		other = Path( other, self.__CASE_MATTERS )

		if self.__CASE_MATTERS:
			return str( self ) == str( other )
		else:
			return str.lower( self ) == str.lower( other )
	__eq__ = isEqual
	def __ne__( self, other ):
		return not self.isEqual( other )
	def doesCaseMatter( self ):
		return self.__CASE_MATTERS
	@classmethod
	def getcwd( cls ):
		'''
		returns the current working directory as a path object
		'''
		return cls( os.getcwd() )
	@classmethod
	def setcwd( cls, path ):
		'''
		simply sets the current working directory - NOTE: this is a class method so it can be called
		without first constructing a path object
		'''
		newPath = cls( path )
		try:
			os.chdir( newPath )
		except WindowsError: return None

		return newPath
	putcwd = setcwd
	def getStat( self ):
		try:
			return os.stat( self )
		except:
			#return a null stat_result object
			return os.stat_result( [ 0 for n in range( os.stat_result.n_sequence_fields ) ] )
	stat = property( getStat )
	def isAbs( self ):
		try:
			return os.path.isabs( str( self ) )
		except: return False
	def abs( self ):
		'''
		returns the absolute path as is reported by os.path.abspath
		'''
		return self.__class__( os.path.abspath( str( self ) ) )
	@d_cacheValue
	def split( self ):
		'''
		splits a path into directory/file tokens
		'''
		isUNC = self.isUNC
		newPath = str.replace( self, UNC_PREFIX, '' )
		if newPath.startswith( PATH_SEPARATOR ):
			newPath = newPath[1:]

		hasTrailing = newPath.endswith( PATH_SEPARATOR )
		if hasTrailing:
			newPath = newPath[ :-1 ]

		toks = newPath.split( PATH_SEPARATOR )

		return toks
	def asDir( self ):
		'''
		makes sure there is a trailing / on the end of a path
		'''
		if self.hasTrailing:
			return self

		return self.__class__( '%s%s' % (self, PATH_SEPARATOR), self.__CASE_MATTERS )
	asdir = asDir
	def asFile( self ):
		'''
		makes sure there is no trailing path separators
		'''
		if not self.hasTrailing:
			return self

		return self.__class__( str( self )[ :-1 ], self.__CASE_MATTERS )
	asfile = asFile
	def isDir( self ):
		'''
		bool indicating whether the path object points to an existing directory or not.  NOTE: a
		path object can still represent a file that refers to a file not yet in existence and this
		method will return False
		'''
		return os.path.isdir( self )
	isdir = isDir
	def isFile( self ):
		'''
		see isdir notes
		'''
		return os.path.isfile( self )
	isfile = isFile
	def getReadable( self ):
		'''
		returns whether the current instance's file is readable or not.  if the file
		doesn't exist False is returned
		'''
		try:
			s = os.stat( self )
			return s.st_mode & stat.S_IREAD
		except:
			#i think this only happens if the file doesn't exist
			return False
	def setWritable( self, state=True ):
		'''
		sets the writeable flag (ie: !readonly)
		'''
		try:
			setTo = stat.S_IREAD
			if state:
				setTo = stat.S_IWRITE

			os.chmod(self, setTo)
		except: pass
	def getWritable( self ):
		'''
		returns whether the current instance's file is writeable or not.  if the file
		doesn't exist True is returned
		'''
		try:
			s = os.stat( self )
			return s.st_mode & stat.S_IWRITE
		except:
			#i think this only happens if the file doesn't exist - so return true
			return True
	@d_cacheValue
	def getExtension( self ):
		'''
		returns the extension of the path object - an extension is defined as the string after a
		period (.) character in the final path token
		'''
		endTok = self[ -1 ]
		idx = endTok.rfind( '.' )
		if idx == -1:
			return ''

		return endTok[ idx+1: ] #add one to skip the period
	def setExtension( self, xtn=None, renameOnDisk=False ):
		'''
		sets the extension the path object.  deals with making sure there is only
		one period etc...

		if the renameOnDisk arg is true, the file on disk (if there is one) is
		renamed with the new extension
		'''
		if xtn is None:
			xtn = ''

		#make sure there is are no start periods
		while xtn.startswith( '.' ):
			xtn = xtn[ 1: ]

		toks = self.split()
		endTok = toks[ -1 ]
		idx = endTok.rfind( '.' )
		name = endTok
		if idx >= 0:
			name = endTok[ :idx ]

		if xtn: newEndTok = '%s.%s' % (name, xtn)
		else: newEndTok = name

		if renameOnDisk:
			self.rename( newEndTok, True )
		else:
			toks[ -1 ] = newEndTok

		return self._toksToPath( toks )
	extension = property(getExtension, setExtension)
	def isExtension( self, extension ):
		'''
		returns whether the extension is of a certain value or not
		'''
		ext = self.getExtension()
		if not self.__CASE_MATTERS:
			ext = ext.lower()
			extension = extension.lower()

		return ext == extension
	hasExtension = isExtension
	@d_cacheValueWithArgs
	def name( self, stripExtension=True, stripAllExtensions=False ):
		'''
		returns the filename by itself - by default it also strips the extension, as the actual filename can
		be easily obtained using self[-1], while extension stripping is either a multi line operation or a
		lengthy expression
		'''
		name = self[ -1 ]
		if stripExtension:
			pIdx = -1
			if stripAllExtensions:
				pIdx = name.find('.')
			else:
				pIdx = name.rfind('.')

			if pIdx != -1:
				return name[ :pIdx ]

		return name
	def up( self, levels=1 ):
		'''
		returns a new path object with <levels> path tokens removed from the tail.
		ie: Path("a/b/c/d").up(2) returns Path("a/b")
		'''
		if not levels:
			return self

		toks = self.split()
		levels = max( min( levels, len(toks)-1 ), 1 )
		toksToJoin = toks[ :-levels ]
		if self.hasTrailing:
			toksToJoin.append( '' )

		return self._toksToPath( toksToJoin )
	def replace( self, search, replace='', caseMatters=None ):
		'''
		a simple search replace method - works on path tokens.  if caseMatters is None, then the system
		default case sensitivity is used
		'''
		idx = self.find( search, caseMatters )
		toks = self.split()
		toks[ idx ] = replace

		return self._toksToPath( toks )
	def find( self, search, caseMatters=None ):
		'''
		returns the index of the given path token
		'''
		if caseMatters is None:
			#in this case assume system case sensitivity - ie sensitive only on *nix platforms
			caseMatters = self.__CASE_MATTERS

		if not caseMatters:
			toks = [ s.lower() for s in self.split() ]
			search = search.lower()
		else:
			toks = self.split()

		idx = toks.index( search )

		return idx
	index = find
	def doesExist( self ):
		'''
		returns whether the file exists on disk or not
		'''
		try:
			return os.path.exists( self )
		except IndexError: return False
	exists = property( doesExist )
	def matchCase( self ):
		'''
		If running under an env where file case doesn't matter, this method will return a Path instance
		whose case matches the file on disk.  It assumes the file exists
		'''
		if self.doesCaseMatter(): return self

		for f in self.up().files():
			if f == self:
				return f
	def getSize( self, units=sz_MEGABYTES ):
		'''
		returns the size of the file in mega-bytes
		'''
		div = float( 1024 ** units )
		return os.path.getsize( self ) / div
	def create( self ):
		'''
		if the directory doesn't exist - create it
		'''
		if not self.exists:
			os.makedirs( str( self ) )
	def delete( self, doP4=True ):
		'''
		WindowsError is raised if the file cannot be deleted.  if the file is managed by perforce, then a p4 delete is performed
		'''
		if doP4 and self.DoP4():
			try:
				asP4 = self.asP4()
				if asP4.managed():
					if asP4.action is None:
						asP4.delete()
						return
					else:
						asP4.revert()
						asP4.delete()

						#only return if the file doesn't exist anymore - it may have been open for add in
						#which case we still need to do a normal delete...
						if not self.exists: return
			except Exception, e: pass

		if self.isfile():
			try:
				os.remove( self )
			except WindowsError, e:
				win32api.SetFileAttributes( self, win32con.FILE_ATTRIBUTE_NORMAL )
				os.remove( self )
		elif self.isdir():
			for f in self.files( recursive=True ):
				f.delete()

			win32api.SetFileAttributes( self, win32con.FILE_ATTRIBUTE_NORMAL )
			shutil.rmtree( self.asDir(), True )
	remove = delete
	def rename( self, newName, nameIsLeaf=False, doP4=True ):
		'''
		it is assumed newPath is a fullpath to the new dir OR file.  if nameIsLeaf is True then
		newName is taken to be a filename, not a filepath.  the instance is modified in place.
		if the file is in perforce, then a p4 rename (integrate/delete) is performed
		'''
		reAdd, change = False, None
		asP4 = None

		newPath = Path( newName )
		if nameIsLeaf:
			newPath = Path( self ).up() / newName

		if self.isfile():
			tgtExists = newPath.exists
			if doP4 and self.DoP4():
				try:
					asP4 = P4File( self )

					#if its open for add, revert - we're going to rename the file...
					if asP4.action == 'add':
						asP4.revert()
						change = asP4.getChange()
						reAdd = True

					#so if we're managed by p4 - try a p4 rename, and return on success.  if it
					#fails however, then just do a normal rename...
					if asP4.managed():
						asP4.rename( newPath )
						self.setPath( str(newPath) )
						return

					#if the target exists and is managed by p4, make sure its open for edit
					if tgtExists and asP4.managed( newPath ):
						asP4.edit( newPath )
				except Exception: pass

			#now perform the rename
			os.rename( self, newPath )

			if reAdd:
				asP4.add( newPath )
				asP4.setChange( change, newPath )
		elif self.isdir():
			raise NotImplementedError('dir renaming not implemented yet...')

		return newPath
	move = rename
	def copy( self, target, nameIsLeaf=False, doP4=True ):
		'''
		same as rename - except for copying.  returns the new target name
		'''
		if self.isfile():
			target = Path( target )
			if nameIsLeaf:
				asPath = self.up() / target
				target = asPath

			if doP4 and self.DoP4():
				try:
					asP4 = P4File( self )
					tgtAsP4 = P4File( target )
					if asP4.managed() and tgtAsP4.isUnderClient():
						'''
						so if we're managed by p4 - try a p4 rename, and return on success.  if it
						fails however, then just do a normal rename...
						'''
						asP4.copy( target )
						return target
				except: pass

			try:
				shutil.copy2( self, target )
			#this happens when src and dest are the same...  its pretty harmless, so we do nothing...
			except shutil.Error:
				pass

			return target
		elif self.isdir():
			raise NotImplementedError('dir copying not implemented yet...')
			#shutil.copytree( str(self), str(target) )
	def read( self, strip=True ):
		'''
		returns a list of lines contained in the file. NOTE: newlines are stripped from the end but whitespace
		at the head of each line is preserved unless strip=False
		'''
		if self.exists and self.isfile():
			fileId = file( self )
			if strip:
				lines = [line.rstrip() for line in fileId.readlines()]
			else:
				lines = fileId.read()
			fileId.close()

			return lines
	def write( self, contentsStr, doP4=True ):
		'''
		writes a given string to the file defined by self.  if doP4 is true, the file will be either
		checked out of p4 before writing or add to perforce after writing if its not managed already
		'''
		#make sure the directory to we're writing the file to exists
		self.up().create()

		existedBeforeWrite = self.exists
		isUnderClient = False
		if doP4 and self.DoP4():
			asP4 = self.asP4()
			isUnderClient = asP4.isUnderClient()
			if existedBeforeWrite and isUnderClient:
				asP4.edit()

		fileId = file( self, 'w' )
		fileId.write( str(contentsStr) )
		fileId.close()

		if doP4 and not existedBeforeWrite and isUnderClient:
			asP4.add()
	def pickle( self, toPickle, doP4=True ):
		'''
		similar to the write method but pickles the file
		'''
		Path( self ).up().create()

		existedBeforeWrite = self.exists
		if existedBeforeWrite and doP4 and self.DoP4():
			self.edit()

		#make sure the file is writeable - it may have been made unwriteable by copying from a non writeable source (ie from p4)
		if not self.getWritable():
			self.setWritable()

		fileId = file( self, 'wb' )
		cPickle.dump( toPickle, fileId, PICKLE_PROTOCOL )
		fileId.close()

		if not existedBeforeWrite and doP4 and self.DoP4():
			#need to explicitly add pickled files as binary type files, otherwise p4 mangles them
			self.asP4().add(type=P4File.BINARY)
	def unpickle( self ):
		'''
		unpickles the file
		'''
		fileId = file( self, 'rb' )
		data = cPickle.load(fileId)
		fileId.close()

		return data
	def relativeTo( self, other ):
		'''
		returns self as a path relative to another
		'''
		path = self
		other = Path( other )

		#if the first path token is different, early out - one is not a subset of the other in any fashion
		lenPath, lenOther = len( path ), len( other )
		if other[0].lower() != path[0].lower():
			return None
		elif lenPath < lenOther:
			return None

		newPathToks = []
		pathsToDiscard = lenOther
		for pathN, otherN in zip(path, other):
			if pathN.lower() == otherN.lower():
				continue
			else:
				newPathToks.append( '..' )
				pathsToDiscard -= 1

		newPathToks.extend( path[ pathsToDiscard: ] )
		path = Path( PATH_SEPARATOR.join( newPathToks ), self.__CASE_MATTERS )

		return path
	__sub__ = relativeTo
	def __rsub__( self, other ):
		return self.__class__( other, self.__CASE_MATTERS ).relativeTo( self )
	def inject( self, other, envDict=None ):
		'''
		injects an env variable into the path - if the env variable doesn't
		resolve to tokens that exist in the path, a path string with the same
		value as self is returned...

		NOTE: a string is returned, not a Path instance - as Path instances are
		always resolved

		NOTE: this method is alias'd by __lshift__ and so can be accessed using the << operator:
		d:/main/content/mod/models/someModel.ma << '%VCONTENT%' results in %VCONTENT%/mod/models/someModel.ma
		'''
		#if not isinstance(other, Path): other = Path(other)
		toks = toksLower = tuple(self.split())
		otherToks = Path( other ).split()
		newToks = []
		n = 0
		if not self.__CASE_MATTERS:
			toksLower = [ t.lower() for t in toks ]
			otherToks = [ t.lower() for t in otherToks ]

		while n < len( toks ):
			tok, tokLower = toks[ n ], toksLower[ n ]
			if tokLower == otherToks[ 0 ]:
				allMatch = True
				for tok, otherTok in zip( toksLower[ n + 1: ], otherToks[ 1: ] ):
					if tok != otherTok:
						allMatch = False
						break

				if allMatch:
					newToks.append( other )
					n += len( otherToks ) - 1
				else:
					newToks.append( toks[ n ] )
			else:
				newToks.append( tok )
			n += 1

		return PATH_SEPARATOR.join( newToks )
	__lshift__ = inject
	def findNearest( self ):
		'''
		returns the longest path that exists on disk
		'''
		path = self
		while not path.exists and len( path ) > 1:
			path = path.up()

		if not path.exists:
			return None
		return path
	getClosestExisting = findNearest
	nearest = findNearest
	def asNative( self ):
		'''
		returns a string with system native path separators
		'''
		return str( self ).replace( PATH_SEPARATOR, NATIVE_SEPARATOR )
	def startswith( self, other ):
		'''
		returns whether the current instance begins with a given path fragment.  ie:
		Path('d:/temp/someDir/').startswith('d:/temp') returns True
		'''
		otherToks = Path( other, self.__CASE_MATTERS ).split()
		selfToks = self.split()
		if not self.__CASE_MATTERS:
			otherToks = [ t.lower() for t in otherToks ]
			selfToks = [ t.lower() for t in selfToks ]

		if len( otherToks ) > len( selfToks ):
			return False

		for tokOther, tokSelf in zip(otherToks, selfToks):
			if tokOther != tokSelf: return False

		return True
	isUnder = startswith
	def endswith( self, other ):
		'''
		determines whether self ends with the given path - it can be a string
		'''
		#copies of these objects NEED to be made, as the results from them are often cached - hence modification to them
		#would screw up the cache, causing really hard to track down bugs...  not sure what the best answer to this is,
		#but this is clearly not it...  the caching decorator could always return copies of mutable objects, but that
		#sounds wasteful...  for now, this is a workaround
		otherToks = Path( other ).split()[:]
		selfToks = self.split()[:]
		otherToks.reverse()
		selfToks.reverse()
		if not self.__CASE_MATTERS:
			otherToks = [ t.lower() for t in otherToks ]
			selfToks = [ t.lower() for t in selfToks ]

		for tokOther, tokSelf in zip(otherToks, selfToks):
			if tokOther != tokSelf:
				return False

		return True
	def belongsToContent( self, gameInfo ):
		for mod in gameInfo.getSearchMods():
			if self.isUnder( content() / mod ):
				return True

		return False
	def belongsToGame( self, gameInfo ):
		for mod in gameInfo.getSearchMods():
			if self.isUnder( game() / mod ):
				return True

		return False
	def _list_filesystem_items( self, itemtest, namesOnly=False, recursive=False ):
		'''
		does all the listing work - itemtest can generally only be one of os.path.isfile or
		os.path.isdir.  if anything else is passed in, the arg given is the full path as a
		string to the filesystem item
		'''
		if not self.exists:
			return []

		start = len(self)
		items = []
		if recursive:
			walker = os.walk( self )
			for path, subs, files in walker:
				items.append( Path(path, self.__CASE_MATTERS) )
				fileItems = [path + Path(item, self.__CASE_MATTERS) for item in files]
				items.extend( fileItems )

			#first item is always ./
			try: items.pop(0)
			except IndexError: pass
		else: items = [ self / item for item in os.listdir( self ) ]

		if namesOnly: return [ item[ start: ] for item in items if itemtest( item ) ]
		return [ item for item in items if itemtest( item ) ]
	def dirs( self, namesOnly=False, recursive=False ):
		'''
		lists all sub-directories.  If namesOnly is True, then only directory names (relative to
		teh current dir) are returned
		'''
		return self._list_filesystem_items( os.path.isdir, namesOnly, recursive )
	def files( self, namesOnly=False, recursive=False ):
		'''
		lists all files in the directory.  If namesOnly is True, then only directory names (relative
		to teh current dir) are returned
		'''
		return self._list_filesystem_items( os.path.isfile, namesOnly, recursive )


def findInPyPath( filename ):
	'''
	given a filename or path fragment, will return the full path to the first matching file found in
	the sys.path variable
	'''
	for p in map( Path, sys.path ):
		loc = p / filename
		if loc.exists:
			return loc

	return None


#end
