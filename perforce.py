from filesystem import Path
import subprocess
import time
import re


class P4Exception(Exception): pass


class P4Path(Path):
	TIMEOUT_PERIOD = 5
	USE_P4 = True

	def __new__( cls, path='', caseMatters=None, envDict=None ):
		pass
	def __init__( self, path='', caseMatters=None, envDict=None ):
		pass


class P4Output(dict):
	EXIT_PREFIX = 'exit:'
	INFO_PREFIX = 'info:'
	INFO_LEN = len( INFO_PREFIX )

	#
	END_DIGITS = re.compile( '(.*)([0-9]+$)' )

	def __init__( self, outStr, keysColonDelimited=True ):
		EXIT_PREFIX = P4Output.EXIT_PREFIX
		INFO_PREFIX = P4Output.INFO_PREFIX
		INFO_LEN = P4Output.INFO_LEN

		if isinstance( outStr, basestring ):
			lines = outStr.split( '\n' )
		elif isinstance( outStr, (list, tuple) ):
			lines = outStr
		else:
			print outStr
			raise P4Exception( "unsupported type (%s) given to %s" % (type( outStr ), self.__class__.__name__) )

		delimiter = ':' if keysColonDelimited else ' '
		for line in lines:
			line = line.strip()

			if line.startswith( EXIT_PREFIX ):
				break

			if not line:
				continue

			idx = line.find( ':' )
			if idx == -1:
				continue

			line = line[ idx + 1: ].strip()
			idx = line.find( delimiter )
			if idx == -1:
				prefix = line
				data = True
			else:
				prefix = line[ :idx ].strip()
				data = line[ idx + 1: ].strip()

			if keysColonDelimited:
				prefix = ''.join( [ s.capitalize() if n else s for n, s in enumerate( prefix.lower().split() ) ] )

			self[ prefix ] = data

		#finally, if there are prefixes which have a numeral at the end, strip it and pack the data into a list
		multiKeys = {}
		for k in self.keys():
			m = self.END_DIGITS.search( k )
			if m is None:
				continue

			prefix, idx = m.groups()
			idx = int( idx )

			data = self.pop( k )
			try:
				multiKeys[ prefix ].append( (idx, data) )
			except KeyError:
				multiKeys[ prefix ] = [ (idx, data) ]

		for prefix, dataList in multiKeys.iteritems():
			try:
				self.pop( prefix )
			except KeyError: pass

			dataList.sort()
			self[ prefix ] = [ d[ 1 ] for d in dataList ]
	def __getattr__( self, attr ):
		return self[ attr ]


def _p4run( *args ):
	if not P4Path.USE_P4:
		return False

	try:
		p4Proc = subprocess.Popen( 'p4 '+ ' '.join( map( str, args ) ), stdout=subprocess.PIPE, stderr=subprocess.PIPE )
	except OSError:
		P4Path.USE_P4 = False
		return False

	startTime = time.clock()
	stdoutAccum = []
	stderrAccum = []
	while True:
		ret = p4Proc.poll()

		#if the proc has terminated, deal with returning appropriate data
		if ret is not None:
			if ret == 0:
				return stdoutAccum
			else:
				return stderrAccum

		newStdout = p4Proc.stdout.readlines()
		newStderr = p4Proc.stderr.readlines()

		#if there has been new output, the proc is still very much alive, so reset counters
		if newStderr or newStdout:
			startTime = time.clock()

		stdoutAccum += newStdout
		stderrAccum += newStderr

		#make sure we haven't timedout
		curTime = time.clock()
		if curTime - startTime > P4Path.TIMEOUT_PERIOD:
			return False


def p4run( *args ):
	ret = _p4run( *args )
	if ret is False:
		return False

	return P4Output( ret )


P4INFO = None
def p4Info():
	global P4INFO

	if P4INFO is not None:
		return P4INFO

	P4INFO = p4run( '-s info' )

	return P4INFO


class P4Change(dict):
	def __init__( self ):
		self.change = None
		self.description = None
		self.files = []
		self.actions = []
		self.revisions = []
	def __len__( self ):
		return len( self.files )
	def __iter__( self ):
		return zip( self.files, self.revisions, self.actions )
	@classmethod
	def Create( cls, description ):
		pass
	@classmethod
	def FetchByNumber( cls, number ):
		lines = _p4run( '-s', 'describe', number )
		if not lines:
			return None

		change = cls()
		change.change = number

		change.description = ''
		lineIter = iter( lines[ 2: ] )
		try:
			prefix = 'text:'
			PREFIX_LEN = len( prefix )

			line = lineIter.next()
			while line.startswith( prefix ):
				line = line[ PREFIX_LEN: ].lstrip()

				if line.startswith( 'Affected files ...' ):
					break

				change.description += line
				line = lineIter.next()

			prefix = 'info1:'
			PREFIX_LEN = len( prefix )
			while not line.startswith( prefix ):
				line = lineIter.next()

			while line.startswith( prefix ):
				line = line[ PREFIX_LEN: ].lstrip()
				idx = line.rfind( '#' )
				depotFile = Path( line[ :idx ] )

				revAndAct = line[ idx + 1: ].split()
				rev = int( revAndAct[ 0 ] )
				act = revAndAct[ 1 ]

				change.files.append( depotFile )
				change.actions.append( act )
				change.revisions.append( rev )

				line = lineIter.next()
		except StopIteration:
			pass

		return change
	@classmethod
	def FetchByDescription( cls, description ):
		'''
		fetches a changelist based on a given description from the list of pending changelists
		'''
		cleanDesc = ''.join( [ s.strip() for s in description.lower().strip().split( '\n' ) ] )
		for change in cls.IterPending():
			thisDesc = ''.join( [ s.strip() for s in change.description.lower().strip().split( '\n' ) ] )
			if thisDesc == cleanDesc:
				return change
	@classmethod
	def IterPending( cls ):
		'''
		iterates over pending changelists
		'''
		info = p4Info()
		for line in _p4run( 'changes -u %s -s pending -c %s' % (info.userName, info.clientName) ):
			toks = line.split()
			changeNum = int( toks[ 1 ] )

			yield cls.FetchByNumber( changeNum )


print _p4run( '-s fstat //valvegames/l4d/main/game/bin/base.fgd' )
#FROM FSTAT...  FUCK YOU PERFORCE
s='''
info1: depotFile //valvegames/l4d/main/game/bin/base.fgd
info1: clientFile z:/valve/l4d\game\bin\base.fgd
info1: isMapped
info1: headAction edit
info1: headType text
info1: headTime 1252691117
info1: headRev 100
info1: headChange 732580
info1: headModTime 1252689561
info1: haveRev 99
info2: otherOpen0 sergiy@sergiy_l4d_linux
info2: otherAction0 edit
info2: otherChange0 default
info2: otherOpen1 zoid@zoidi7
info2: otherAction1 edit
info2: otherChange1 default
info2: otherOpen 2
exit: 0
'''
print P4Output( s, False )


#end
