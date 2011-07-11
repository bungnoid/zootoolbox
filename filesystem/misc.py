
import os
import sys
import threading
import inspect


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
