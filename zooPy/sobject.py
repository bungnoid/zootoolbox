
from __future__ import with_statement
from typeFactories import interfaceTypeFactory, doesImplement

class ListStream(object):
	def __init__( self ):
		self._lines = []
	def __str__( self ):
		return ''.join( self._lines )
	def __iter__( self ):
		blob = ''.join( self._lines )
		for line in blob.split( '\n' ):
			yield line + '\n'
	def write( self, line ):
		self._lines.append( line )


class ISerializer(object):
	__metaclass__ = interfaceTypeFactory()
	def serializer( self, stream, depth, value ):
		'''
		This method needs to handle serialization of the given value.  No return value is expected

		stream must be a file-like object
		depth is the current depth in the serialization stack
		value is the actual instance currently being serialized
		'''


class SObject(object):

	#these are the types supported
	__SUPPORTED_TYPES = str, unicode, int, float, str, bool, long

	#these are the user supported types - they need to be registered via the registerType method
	__REGISTERED_TYPES = {}

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

		if self in nodesCompared:
			return True

		nodesCompared.add( self )
		thisAttrNames, otherAttrNames = self.getAttrs(), other.getAttrs()
		if len( thisAttrNames ) != len( otherAttrNames ):
			return False

		for thisAttrName, otherAttrName in zip( thisAttrNames, otherAttrNames ):
			if thisAttrName != otherAttrName:
				return False

			thisAttrValue = getattr( self, thisAttrName )
			otherAttrValue = getattr( self, otherAttrName )

			if isinstance( thisAttrValue, SObject ):
				if not thisAttrValue.__eq__( otherAttrValue, nodesCompared ):
					return False
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
	def getAttrs( self ):
		'''
		returns a tuple of attributes present on this object
		'''
		return tuple( self._attrNames )
	def registerType( self, type, serializer ):
		if not doesImplement( serializer, ISerializer ):
			raise TypeError( "The given serializer doesn't implement the required methods for serialization!" )

		self.__REGISTERED_TYPES[ type ] = serializer
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

		#grab data about the attributes - we need to do this first because we need string length
		#information for serialization formatting below
		maxAttrNameLength = 0
		maxTypeNameLength = 0
		attrNameValTypeAndTypeStr = []
		for attr in self.getAttrs():
			value = getattr( self, attr )
			valueType = type( value )
			valueTypeName = valueType.__name__

			#escape newline characters
			if valueType is str or valueType is unicode:
				value = value.replace( '\n', '\\n' ).replace( '\r', '\\r' )

			maxAttrNameLength = max( maxAttrNameLength, len( attr ) )
			maxTypeNameLength = max( maxTypeNameLength, len( valueTypeName ) )

			attrNameValTypeAndTypeStr.append( (attr, value, valueType, valueTypeName) )

		attrNamePadding = maxAttrNameLength + maxTypeNameLength + 2
		for attr, value, valueType, valueTypeName in attrNameValTypeAndTypeStr:
			if valueType is SObject:
				attrNameAndTypeStr = '%s(*)' % attr
				stream.write( '%s%s:' % (depthPrefix, attrNameAndTypeStr.ljust( attrNamePadding )) )
				value.serialize( stream, depth+1, serializedObjects )
			elif valueType in self.__SUPPORTED_TYPES:
				attrNameAndTypeStr = '%s(%s)' % (attr, valueTypeName)
				stream.write( '%s%s:%s\n' % (depthPrefix, attrNameAndTypeStr.ljust(attrNamePadding), value) )
			elif valueType in self.__REGISTERED_TYPES:
				serializer = self._getTypeSerializer( valueType )
				serializer( stream, depth, value )

		stream.write( '%s}\n' % depthPrefix )
	def write( self, filepath ):
		with open( filepath, 'w' ) as fStream:
			self.serialize( fStream )
	@classmethod
	def Unserialize( cls, stream ):
		def getTypeFromTypeStr( typeStr ):
			typeCls = __builtins__.get( typeStr, None )
			if typeCls is not None:
				return typeCls

			raise TypeError( "Unable to find the appropriate type for the type string %s" % typeStr )

		lineIter = iter( stream )
		objectStack = []
		lineStack = []

		serializedIdToObjDict = {}  #track objects

		def getLineDepth( line ):
			depth = 0
			while line[depth] == '\t':
				depth += 1

			return depth

		def findDigits( line ):
			idx = 0
			isdigit = str.isdigit
			while isdigit( line[idx] ):
				idx += 1

			return line[ :idx ]

		def objectParser( line, depth=0 ):
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

				if line[depth:].strip() == '}':
					return objectStack.pop()

				idx_parenStart = line.find( '(' )
				idx_parenEnd = line.find( ')', idx_parenStart )
				idx_valueStart = line.find( ':', idx_parenEnd )

				attrName = line[ depth:idx_parenStart ].strip()
				typeStr = line[ idx_parenStart+1:idx_parenEnd ].strip()

				if typeStr == '*':
					value = objectParser( line[idx_valueStart+1:].lstrip(), depth+1 )
				else:
					valueStr = line[ idx_valueStart+1:-1 ].lstrip()
					typeCls = getTypeFromTypeStr( typeStr )
					if typeCls is str or typeCls is unicode:
						value = valueStr.replace( '\\n', '\n' ).replace( '\\r', '\r' )
					else:
						value = typeCls( valueStr )

				setattr( objectStack[-1], attrName, value )

			return objectStack.pop()

		for line in lineIter:
			return objectParser( line )
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
		for key, value in theDict.iteritems():
			if isinstance( value, dict ):
				valueId = id( value )
				value = dictObjectMap[ valueId ] = cls.FromDict( value, dictObjectMap )

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

	#the following provide dictionary-like functionality
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
