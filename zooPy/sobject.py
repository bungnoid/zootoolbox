
from __future__ import with_statement


class ListStream(object):
	def __init__( self ):
		self._lines = []
	def __str__( self ):
		return ''.join( self._lines )
	def __iter__( self ):
		return iter( ''.join( self._lines ).split( '\n' ) )
	def write( self, line ):
		self._lines.append( line )


class SObject(object):

	#stores any types that have been registered with this class for serialization
	__REGISTERED_TYPES = []

	@classmethod
	def RegisterType( cls, type ):
		cls.__REGISTERED_TYPES.append( type )
	@classmethod
	def UnregisterType( cls, type ):
		try:
			cls.__REGISTERED_TYPES.remove( type )
		except ValueError: pass
	@classmethod
	def IsTypeRegistered( cls, type ):
		return type in cls.__REGISTERED_TYPES

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
	def serialize( self, stream, depth=0, serializedObjects=None ):
		if serializedObjects is None:
			serializedObjects = set()

		#write in the uuid for this SObject - we use the uuid for object referencing
		depthPrefix = '\t' * depth
		stream.write( '<%s>\n' % id( self ) )

		#track SObjects serialized so we don't get infinite loops if objects self reference
		if self in serializedObjects:
			return

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
				value = value.replace( '\n', '\\n' ).replace( '\r', '\\t' )

			maxAttrNameLength = max( maxAttrNameLength, len( attr ) )
			maxTypeNameLength = max( maxTypeNameLength, len( valueTypeName ) )

			attrNameValTypeAndTypeStr.append( (attr, value, valueType, valueTypeName) )

		attrNamePadding = maxAttrNameLength + maxTypeNameLength + 2
		for attr, value, valueType, valueTypeName in attrNameValTypeAndTypeStr:
			if issubclass( valueType, SObject ):
				attrNameAndTypeStr = '%s(*)' % attr
				stream.write( '%s%s:' % (depthPrefix, attrNameAndTypeStr.ljust( attrNamePadding )) )
				value.serialize( stream, depth+1, serializedObjects )
			else:
				attrNameAndTypeStr = '%s(%s)' % (attr, valueTypeName)
				stream.write( '%s%s:%s\n' % (depthPrefix, attrNameAndTypeStr.ljust(attrNamePadding), value) )
	def write( self, filepath ):
		with open( filepath, 'w' ) as fStream:
			self.serialize( fStream )
	@classmethod
	def Unserialize( cls, stream ):
		def getTypeFromTypeStr( typeStr ):
			typeCls = __builtins__.get( typeStr, None )
			if typeCls is not None:
				return typeCls

			for typeCls in cls.__REGISTERED_TYPES:
				if typeCls.__name__ == typeStr:
					return typeCls

			raise TypeError( "Unable to find the appropriate type for the type string %s" % typeStr )

		lineIter = iter( stream )
		objectStack = []

		serializedIdToObjDict = {}  #track objects

		def objectParser( line, depth=0 ):
			serializedId = int( line[1:-2] )  #-2 because we want to strip the newline character and the closing > character

			#if an object has already been created for the given id, use it, otherwise construct a new object
			newObj = serializedIdToObjDict.get( serializedId, SObject() )

			#append the new object to the stack
			objectStack.append( newObj )

			#track the object
			serializedIdToObjDict[ serializedId ] = newObj
			for line in lineIter:
				if not line:
					continue

				idx_parenStart = line.find( '(' )
				idx_parenEnd = line.find( ')', idx_parenStart )
				idx_valueStart = line.find( ':', idx_parenEnd )

				attrName = line[ depth:idx_parenStart ]
				typeStr = line[ idx_parenStart+1:idx_parenEnd ]
				valueStr = line[ idx_valueStart+1: ]

				if typeStr == '*':
					value = objectParser( valueStr, depth+1 )
				else:
					typeCls = getTypeFromTypeStr( typeStr )
					value = typeCls( valueStr )
					if typeCls is str or typeCls is unicode:
						value = value.replace( '\\n', '\n' ).replace( '\\r', '\r' )

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
	def toDict( self ):
		raise NotImplemented


#end