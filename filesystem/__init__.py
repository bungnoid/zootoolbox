
from path import *
from misc import *
#from perforce import *
from presets import *


IS_WING_DEBUG = 'WINGDB_ACTIVE' in os.environ


class GoodException(Exception):
	'''
	good exceptions are just a general purpose way of breaking out of loops and whatnot.  basically anytime an exception is
	needed to control code flow and not indicate an actual problem using a GoodException makes it a little more obvious what
	the code is doing in the absence of comments
	'''
	pass

BreakException = GoodException


class Callback(object):
	'''
	stupid little callable object for when you need to "bake" temporary args into a
	callback - useful mainly when creating callbacks for dynamicly generated UI items
	'''
	def __init__( self, func, *args, **kwargs ):
		self.func = func
		self.args = args
		self.kwargs = kwargs
	def __call__( self, *args ):
		return self.func( *self.args, **self.kwargs )


#end
