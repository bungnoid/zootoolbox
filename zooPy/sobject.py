
from __future__ import with_statement
from cStringIO import StringIO


class RewindableStreamIter(object):
	def __init__( self, iterable ):
		requiredMethodNames = 'tell', 'seek', 'readline'
		for methodName in requiredMethodNames:
			if not hasattr( iterable, methodName ):
				raise TypeError( "The given iterable is missing the required method %s" % methodName )

		self._iterable = iterable
		self._lineStartIdxStack = []
	def __iter__( self ):
		iterable = self._iterable
		lineStartIdxStack = self._lineStartIdxStack

		line = True

		while line:
			lineStartIdxStack.append( iterable.tell() )
			yield iterable.readline()
	def rewind( self ):
		self._iterable.seek( self._lineStartIdxStack.pop() )


class SObject(object):

	#these are the types supported
	__SUPPORTED_TYPES = str, unicode, int, float, str, bool, long, list, tuple
	__SUPPORTED_TYPE_DICT = dict( ((t.__name__, t) for t in __SUPPORTED_TYPES) )
	__SUPPORTED_TYPES_SET = set( __SUPPORTED_TYPES )

	def __init__( self, *attrNameValuePairs, **kw ):

		#for preserving attribute ordering
		self.__dict__[ '_attrNames' ] = []

		for attrName, attrValue in attrNameValuePairs:
			setattr( self, attrName, attrValue )
	def __hash__( self ):
		return id( self )
	def __eq__( self, other, nodesCompared=None ):
		'''
		two SObjects are equal only if all they both possess the same attributes in the same order with
		the same values
		'''
		if nodesCompared is None:
			nodesCompared = set()

		#if we've already visited this node then it must match - otherwise we'd have returned False already
		if self in nodesCompared:
			return True

		#add this node to the list of nodes compared already - we do this before the comparison below so that cyclical references
		#don't turn into infinite loops
		nodesCompared.add( self )

		#compare attribute lists - attribute counts must match
		thisAttrNames, otherAttrNames = self.getAttrs(), other.getAttrs()
		if len( thisAttrNames ) != len( otherAttrNames ):
			return False

		#now that we know the attribute counts are the same, zip them together and iterate over them to compare names and values
		for thisAttrName, otherAttrName in zip( thisAttrNames, otherAttrNames ):

			#attribute names must match - attribute ordering is important, so the attribute names must match exactly
			if thisAttrName != otherAttrName:
				return False

			#grab the actual attribute values
			thisAttrValue = getattr( self, thisAttrName )
			otherAttrValue = getattr( self, otherAttrName )

			#if the attribute is an SObject instance, recurse - we can't rely on __eq__ because we need to pass in the nodesCompared set
			#so we don't get infinite recursion
			if type( thisAttrValue ) is SObject:
				if not thisAttrValue.__eq__( otherAttrValue, nodesCompared ):
					return False

			#otherwise just compare normally
			else:
				if thisAttrValue != otherAttrValue:
					return False

		return True
	def __ne__( self, other ):
		return not self.__eq__( other )
	def __setattr__( self, attr, value ):
		valueType = type( value )

		#type check the value - only certain types are supported
		if valueType is not SObject and valueType not in self.__SUPPORTED_TYPES:
			raise TypeError( "Serialization of the type %s is not yet supported!" % type( value ) )

		if attr not in self.__dict__:
			self.__dict__[ '_attrNames' ].append( attr )

		self.__dict__[ attr ] = value
	def __getitem__( self, item ):
		if hasattr( self, item ):
			return getattr( self, item )

		raise KeyError( "Object contains no such key '%s'!" % item )
	def __contains__( self, attr ):
		return hasattr( self, attr )
	def __str__( self ):
		stringBuffer = StringIO()
		self.serialize( stringBuffer )

		return stringBuffer.getvalue()
	def _roundTrip( self ):
		'''
		serialized the object to a string buffer and then unserializes from the same buffer - mainly
		useful for testing purposes
		'''
		stringBuffer = StringIO()
		self.serialize( stringBuffer )

		#make sure to rewind the buffer!
		stringBuffer.seek( 0 )

		return self.Unserialize( stringBuffer )
	def getAttrs( self ):
		'''
		returns a tuple of attributes present on this object
		'''
		return tuple( self._attrNames )
	def serialize( self, stream, depth=0, serializedObjects=None ):
		if serializedObjects is None:
			serializedObjects = set()

		#write in the uuid for this SObject - we use the uuid for object referencing
		depthPrefix = '\t' * depth

		#track SObjects serialized so we don't get infinite loops if objects self reference
		if self in serializedObjects:
			stream.write( '%s\n' % id( self ) )
			return

		stream.write( '%s {\n' % id( self ) )
		serializedObjects.add( self )

		supportedTypes = self.__SUPPORTED_TYPES_SET
		for attr in self.getAttrs():
			value = getattr( self, attr )
			valueType = type( value )
			valueTypeName = valueType.__name__

			if valueType is SObject:
				stream.write( '%s%s(*):' % (depthPrefix, attr) )
				value.serialize( stream, depth+1, serializedObjects )
			else:
				attrNameAndTypeStr = '%s(%s)' % (attr, valueTypeName)
				if valueType in (list, tuple):

					attrLine = '%s%s:\n' % (depthPrefix, attrNameAndTypeStr)
					stream.write( attrLine )

					valueDepthPrefix = '\t' + depthPrefix
					for v in value:
						vType = type( v )
						if vType is SObject:
							stream.write( '%s-(*):' % valueDepthPrefix )
							v.serialize( stream, depth+1, serializedObjects )
						elif vType in supportedTypes:
							stream.write( '%s-(%s):%s\n' % (valueDepthPrefix, vType.__name__, v) )
						else:
							raise TypeError( "The type %s isn't supported!" % vType.__name__ )
				elif valueType in supportedTypes:

					#escape newline characters
					if valueType is str or valueType is unicode:
						value = value.replace( '\n', '\\n' ).replace( '\r', '\\r' )

					stream.write( '%s%s:%s\n' % (depthPrefix, attrNameAndTypeStr, value) )
				else:
					raise TypeError( "The type %s isn't supported!" % valueTypeName )

		stream.write( '%s}\n' % depthPrefix )
	def write( self, filepath ):
		with open( filepath, 'w' ) as fStream:
			self.serialize( fStream )
	@classmethod
	def Unserialize( cls, stream ):
		def getTypeFromTypeStr( typeStr ):
			typeCls = cls.__SUPPORTED_TYPE_DICT.get( typeStr, None )
			if typeCls is not None:
				return typeCls

			if typeStr is '*':
				return SObject

			raise TypeError( 'Unable to find the appropriate type for the type string "%s"' % typeStr )

		lineIter = RewindableStreamIter( stream )
		objectStack = []

		serializedIdToObjDict = {}  #track objects

		def findDigits( line ):
			idx = 0
			isdigit = str.isdigit
			for char in line:
				if not isdigit( char ):
					break

				idx += 1

			return line[ :idx ]

		def getAttrDataFromLine( line ):
			idx_parenStart = line.find( '(' )
			idx_parenEnd = line.find( ')', idx_parenStart )
			idx_valueStart = line.find( ':', idx_parenEnd )

			attrName = line[ :idx_parenStart ].strip()
			typeStr = line[ idx_parenStart+1:idx_parenEnd ].strip()
			valueStr = line[ idx_valueStart+1:-1 ].lstrip()

			return attrName, typeStr, valueStr

		def listParser( line, depth, isTuple=False ):
			value = []
			for line in lineIter:
				if not line:
					continue

				line = line.lstrip()
				if line.startswith( '-' ):
					_, typeStr, valueStr = getAttrDataFromLine( line )
					typeCls = getTypeFromTypeStr( typeStr )
					if typeCls is str or typeCls is unicode:
						value.append( valueStr.replace( '\\n', '\n' ).replace( '\\r', '\r' ) )
					elif typeCls is SObject:
						value.append( objectParser( valueStr, depth+1 ) )
					else:
						value.append( typeCls( valueStr ) )

				#we're done!
				else:
					lineIter.rewind()
					return tuple( value ) if isTuple else value

		def objectParser( line, depth ):
			serializedId = int( findDigits( line ) )

			#check to see if the id has already been unserialized
			if serializedId in serializedIdToObjDict:
				return serializedIdToObjDict[ serializedId ]

			#otherwise, construct a new object
			newObj = SObject()

			#append the new object to the stack
			objectStack.append( newObj )

			#track the object
			serializedIdToObjDict[ serializedId ] = newObj
			for line in lineIter:
				if not line:
					continue

				if line.strip() == '}':
					return objectStack.pop()

				attrName, typeStr, valueStr = getAttrDataFromLine( line )
				if typeStr == '*':
					value = objectParser( valueStr, depth+1 )
				else:
					typeCls = getTypeFromTypeStr( typeStr )
					if typeCls is str or typeCls is unicode:
						value = valueStr.replace( '\\n', '\n' ).replace( '\\r', '\r' )
					elif typeCls is list:
						value = listParser( line, depth )
					elif typeCls is tuple:
						value = listParser( line, depth, True )
					else:
						value = typeCls( valueStr )

				setattr( objectStack[-1], attrName, value )

			return objectStack.pop()

		for line in lineIter:
			return objectParser( line, 0 )
	@classmethod
	def Load( cls, filepath ):
		with open( filepath ) as fStream:
			return self.Unserialize( fStream )
	@classmethod
	def FromDict( cls, theDict, dictObjectMap=None ):
		if dictObjectMap is None:
			dictObjectMap = {}

		theDictId = id( theDict )
		if theDictId in dictObjectMap:
			return dictObjectMap[ theDictId ]

		obj = cls()
		dictObjectMap[ theDictId ] = obj
		supportedTypes = cls.__SUPPORTED_TYPES_SET
		for key, value in theDict.iteritems():
			valueType = type( value )

			if valueType is dict:
				value = dictObjectMap[ id( value ) ] = cls.FromDict( value, dictObjectMap )
			elif valueType is list or valueType is tuple:
				isTuple = valueType is tuple
				if isTuple:
					value = list( value )

				for n, v in enumerate( value ):
					if type( v ) is dict:
						value[n] = dictObjectMap[ id( v ) ] = cls.FromDict( v, dictObjectMap )

				if isTuple:
					value = tuple( value )
			elif not valueType in supportedTypes:
				raise TypeError( "The type %s isn't supported!" % valueType.__name__ )

			setattr( obj, key, value )

		return obj
	def toDict( self, dictObjectMap=None ):
		if dictObjectMap is None:
			dictObjectMap = {}

		if self in dictObjectMap:
			return dictObjectMap[ self ]

		thisDict = dictObjectMap[ self ] = {}
		for key, value in self.iteritems():
			if type( value ) is SObject:
				thisDict[ key ] = value.toDict( dictObjectMap )
			else:
				thisDict[ key ] = value

		return thisDict

	#the following provide the dictionary interface
	def iteritems( self ):
		for attr in self.getAttrs():
			yield attr, getattr( self, attr )
	def items( self ):
		return list( self.iteritems() )
	def iterkeys( self ):
		return iter( self.getAttrs() )
	keys = getAttrs
	def itervalues( self ):
		for attr in self.getAttrs():
			yield getattr( self, attr )
	def values( self ):
		return self.itervalues()


#end
