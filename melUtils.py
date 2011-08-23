
import maya.mel

from maya.cmds import cmd

melEval = maya.mel.eval


def pyArgToMelArg( arg ):
	#given a python arg, this method will attempt to convert it to a mel arg string
	if isinstance( arg, basestring ):
		return u'"%s"' % cmd.encodeString( arg )

	#if the object is iterable then turn it into a mel array string
	elif hasattr( arg, '__iter__' ):
		return '{%s}' % ','.join( map( pyArgToMelArg, arg ) )

	#either lower case bools or ints for mel please...
	elif isinstance( arg, bool ):
		return str( arg ).lower()

	#otherwise try converting the sucka to a string directly
	return unicode( arg )


class Mel( object ):
	'''
	creates an easy to use interface to mel code as opposed to having string formatting
	operations all over the place in scripts that call mel functionality
	'''
	def __init__( self, echo=False ):
		self.echo = echo
	def __getattr__( self, attr ):
		if attr.startswith( '__' ) and attr.endswith( '__' ):
			return self.__dict__[attr]

		#construct the mel cmd execution method
		echo = self.echo
		def melExecutor( *args ):
			strArgs = map( pyArgToMelArg, args )
			cmdStr = '%s(%s);' % (attr, ','.join( strArgs ))

			if echo:
				print cmdStr

			try:
				retVal = melEval( cmdStr )
			except RuntimeError:
				print 'cmdStr: %s' % cmdStr
				return

			return retVal

		melExecutor.__name__ = attr

		return melExecutor
	def source( self, script ):
		return melEval( 'source "%s";' % script )
	def eval( self, cmdStr ):
		if self.echo:
			print cmdStr

		try:
			return melEval( cmdStr )
		except RuntimeError:
			print 'ERROR :: trying to execute the cmd:'
			print cmdStr
			raise


mel = Mel()
melecho = Mel(echo=True)


#end
