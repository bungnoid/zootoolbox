import os
import sys
import threading
import inspect


def trackableClassFactory( superClass=object ):
	'''
	returns a class that tracks subclasses.  for example, if you had classB(classA)
	ad you wanted to track subclasses, you could do this:

	class classB(trackableClassFactory( classA )):
		...

	a classmethod called GetSubclasses is created in the returned class for
	querying the list of subclasses
	'''
	subclassList = []
	class TrackableType(type):
		def __new__( cls, name, bases, attrs ):
			new = type.__new__( cls, name, bases, attrs )
			subclassList.append( new )

			return new

	class TrackableClass(superClass): __metaclass__ = TrackableType
	def IterSubclasses( cls ):
		'''
		returns an iterator for subclasses
		'''
		for c in subclassList:
			if c is cls:
				continue

			if issubclass( c, cls ):
				yield c
	def GetSubclasses( cls ):
		'''
		returns a list of subclasses
		'''
		return list( cls.IterSubclasses() )
	def GetNamedSubclass( cls, name ):
		'''
		returns the first subclass found with the given name
		'''
		for c in cls.IterSubclasses():
			if c.__name__ == name: return c

	TrackableClass.IterSubclasses = classmethod( IterSubclasses )
	TrackableClass.GetSubclasses = classmethod( GetSubclasses )
	TrackableClass.GetNamedSubclass = classmethod( GetNamedSubclass )

	return TrackableClass


def removeDupes( iterable ):
	'''
	'''
	unique = set()
	newIterable = iterable.__class__()
	for item in iterable:
		if item not in unique: newIterable.append(item)
		unique.add(item)

	return newIterable


def iterBy( iterable, count ):
	'''
	returns an generator which will yield "chunks" of the iterable supplied of size "count".  eg:
	for chunk in iterBy( range( 7 ), 3 ): print chunk

	results in the following output:
	[0, 1, 2]
	[3, 4, 5]
	[6]
	'''
	cur = 0
	i = iter( iterable )
	while True:
		try:
			toYield = []
			for n in range( count ): toYield.append( i.next() )
			yield toYield
		except StopIteration:
			if toYield: yield toYield
			break


def findMostRecentDefitionOf( variableName ):
	'''
	'''
	try:
		fr = inspect.currentframe()
		frameInfos = inspect.getouterframes( fr, 0 )

		#in this case, walk up the caller tree and find the first occurance of the variable named <variableName>
		for frameInfo in frameInfos:
			frame = frameInfo[0]
			var = None

			if var is None:
				try:
					var = frame.f_locals[ variableName ]
					return var
				except KeyError: pass

				try:
					var = frame.f_globals[ variableName ]
					return var
				except KeyError: pass

	#NOTE: this method should never ever throw an exception...
	except: pass


def getArgDefault( function, argName ):
	'''
	returns the default value of the given named arg.  if the arg doesn't exist,
	or a NameError is raised.  if the given arg has no default an IndexError is
	raised.
	'''
	args, va, vkw, defaults = inspect.getargspec( function )
	if argName not in args:
		raise NameError( "The given arg does not exist in the %s function" % function )

	args.reverse()
	idx = args.index( argName )

	try:
		return list( reversed( defaults ) )[ idx ]
	except IndexError:
		raise IndexError( "The function %s has no default for the %s arg" % (function, argName) )


#end
