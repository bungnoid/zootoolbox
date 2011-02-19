

def trackableClassFactory( superClass=object ):
	'''
	returns a class that tracks subclasses.  for example, if you had classB(classA)
	ad you wanted to track subclasses, you could do this:

	class classB(trackableClassFactory( classA )):
		...

	a classmethod called GetSubclasses is created in the returned class for
	querying the list of subclasses
	'''
	subclassList = []  #to preserve ordering of subclass definitions
	subclassDict = {}  #for fast named subclass lookups
	class TrackableType(type):
		def __new__( cls, name, bases, attrs ):
			new = type.__new__( cls, name, bases, attrs )
			subclassList.append( new )
			subclassDict.setdefault( name, new )  #set default so subclass name clashes are resolved using the first definition parsed

			return new

	class TrackableClass(superClass): __metaclass__ = TrackableType
	def IterSubclasses( cls ):
		'''
		returns an iterator for subclasses
		'''
		for c in subclassList:
			if c is cls:  #skip the class we're calling this on
				continue

			if issubclass( c, cls ):
				yield c
	def GetSubclasses( cls ):
		'''
		returns a list of subclasses
		'''
		return list( cls.IterSubclasses() )  #doing this instead of just returning subclassList ensures the caller is given a copy of the subclass list
	def GetNamedSubclass( cls, name ):
		'''
		returns the first subclass found with the given name
		'''
		return subclassDict.get( name, None )

	TrackableClass.IterSubclasses = classmethod( IterSubclasses )
	TrackableClass.GetSubclasses = classmethod( GetSubclasses )
	TrackableClass.GetNamedSubclass = classmethod( GetNamedSubclass )

	#the TrackableClass item will be in this list already - so pop it out of the list and the dict.  we don't ever want to see it in the list
	subclassList.pop()
	subclassDict.pop( TrackableClass.__name__ )

	return TrackableClass


#end
